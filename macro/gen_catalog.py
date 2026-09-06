"""Generate catalog.sql for the `macro` database from the retired 0018 seed.

Parses the surviving migration rather than retyping 33 rows by hand, so titles,
importance, SA/NSA companions, publication lags and source URLs come across
exactly as they were curated.
"""
import re
import sys

SRC = '/home/strawer/bigricebowl/postgres/migrations/0018_fred_seed.sql'

# 0018's column order.
COLS = ['series_id', 'source', 'title', 'frequency', 'country', 'category',
        'importance', 'seasonal_adjustment', 'companion_series_id',
        'validation_mode', 'pub_lag_days', 'staleness_mode', 'parent_series_id',
        'level', 'native_code', 'originator', 'dataset', 'source_url', 'unit',
        'native_unit']

# What we carry into the new schema.
# pub_lag_days and staleness_mode are deliberately NOT carried across: both
# were dropped on 6 September 2026, having never been read by anything.
# COLS above still lists them because it describes 0018's column order, which
# is fixed history and has to keep matching the file being parsed.
KEEP = ['series_id', 'source', 'title', 'frequency', 'country', 'category',
        'importance', 'seasonal_adjustment', 'companion_series_id',
        'validation_mode', 'originator',
        'dataset', 'source_url', 'unit']

# The old catalog held `dataset` as free text. Map it to a real release key so a
# dashboard resolves its "as of" stamp by foreign key, not string matching.
RELEASE_BY_DATASET = {
    'Employment Situation':                        'bls.employment_situation',
    'Job Openings and Labor Turnover Survey':      'bls.jolts',
    'Unemployment Insurance Weekly Claims Report': 'eta.claims',
    'Employment Cost Index':                       'bls.eci',
    'Productivity and Costs':                      'bls.productivity',
    'Wage Growth Tracker':                         'frb.wage_tracker',
}

# Labour-adjacent series filed under `prices` — wage and productivity context
# you cannot read an employment trend without.
ADJACENT = {'ECIALLCIV', 'ECIWAG', 'FRBATLWGT3MMAUMHWGO', 'OPHNFB', 'ULCNFB'}

# FINDINGS_revision_handling.md: eight series had no usable ALFRED history and
# were moved to fetch-date vintaging with diff-on-write. One is in our set.
FETCH_DATE = {'FRBATLWGT3MMAUMHWGO'}


def split_values(s):
    """Split one VALUES tuple on commas at depth 0, respecting '' escapes."""
    out, buf, i, in_str = [], [], 0, False
    while i < len(s):
        c = s[i]
        if in_str:
            if c == "'":
                if i + 1 < len(s) and s[i + 1] == "'":
                    buf.append("''")
                    i += 2
                    continue
                in_str = False
            buf.append(c)
        else:
            if c == "'":
                in_str = True
                buf.append(c)
            elif c == ',':
                out.append(''.join(buf).strip())
                buf = []
            else:
                buf.append(c)
        i += 1
    out.append(''.join(buf).strip())
    return out


def main():
    text = open(SRC, encoding='utf-8').read()
    body = text[text.index('VALUES'):]
    rows = []
    for m in re.finditer(r'^\s*\((.*?)\)[,;]\s*$', body, re.M | re.S):
        vals = split_values(m.group(1))
        if len(vals) != len(COLS):
            print(f'SKIP malformed row ({len(vals)} cols): {vals[0][:40]}', file=sys.stderr)
            continue
        rows.append(dict(zip(COLS, vals)))

    wanted = [r for r in rows
              if (r['country'] == "'US'" and r['category'] == "'employment'")
              or r['series_id'].strip("'") in ADJACENT]

    emp = [r for r in wanted if r['category'] == "'employment'"]
    adj = [r for r in wanted if r['category'] != "'employment'"]
    print(f'parsed {len(rows)} rows; selected {len(wanted)} '
          f'({len(emp)} employment + {len(adj)} adjacent)', file=sys.stderr)

    missing = ADJACENT - {r['series_id'].strip("'") for r in wanted}
    if missing:
        print(f'WARNING: adjacent series not found in seed: {sorted(missing)}', file=sys.stderr)

    lines = [
        '-- macro catalog: US employment and labour-adjacent series.',
        '-- Generated from the retired 0018_fred_seed.sql — curation preserved,',
        '-- not retyped. Do not hand-edit; regenerate with gen_catalog.py.',
        '',
        'BEGIN;',
        '',
        "INSERT INTO macro_releases (release_id, name, agency, cadence, url) VALUES",
        "  ('bls.employment_situation', 'Employment Situation', "
        "'U.S. Bureau of Labor Statistics', 'monthly', 'https://www.bls.gov/news.release/empsit.toc.htm'),",
        "  ('bls.jolts', 'Job Openings and Labor Turnover Survey', "
        "'U.S. Bureau of Labor Statistics', 'monthly', 'https://www.bls.gov/news.release/jolts.toc.htm'),",
        "  ('eta.claims', 'Unemployment Insurance Weekly Claims Report', "
        "'U.S. Employment and Training Administration', 'weekly', 'https://www.dol.gov/ui/data.pdf'),",
        "  ('bls.eci', 'Employment Cost Index', "
        "'U.S. Bureau of Labor Statistics', 'quarterly', 'https://www.bls.gov/news.release/eci.toc.htm'),",
        "  ('bls.productivity', 'Productivity and Costs', "
        "'U.S. Bureau of Labor Statistics', 'quarterly', 'https://www.bls.gov/news.release/prod2.toc.htm'),",
        "  ('frb.wage_tracker', 'Atlanta Fed Wage Growth Tracker', "
        "'Federal Reserve Bank of Atlanta', 'monthly', 'https://www.atlantafed.org/chcs/wage-growth-tracker')",
        'ON CONFLICT (release_id) DO NOTHING;',
        '',
        f'INSERT INTO macro_series_meta ({", ".join(KEEP)}, release_id, vintage_mode) VALUES',
    ]

    unmapped = {r['dataset'].strip("'") for r in wanted} - set(RELEASE_BY_DATASET)
    if unmapped:
        raise SystemExit(f'FATAL: dataset with no release mapping: {sorted(unmapped)}')

    tuples = []
    for r in sorted(wanted, key=lambda x: (x['dataset'], -int(x['importance']), x['series_id'])):
        sid = r['series_id'].strip("'")
        vals = [r[c] for c in KEEP]
        rel = "'" + RELEASE_BY_DATASET[r['dataset'].strip("'")] + "'"
        mode = "'fetch_date'" if sid in FETCH_DATE else "'from_row'"
        tuples.append('  (' + ', '.join(vals) + ', ' + rel + ', ' + mode + ')')
    lines.append(',\n'.join(tuples))
    lines.append('ON CONFLICT (series_id) DO UPDATE SET')
    lines.append('  title = EXCLUDED.title, importance = EXCLUDED.importance,')
    lines.append('  companion_series_id = EXCLUDED.companion_series_id,')
    lines.append('  dataset = EXCLUDED.dataset, release_id = EXCLUDED.release_id,')
    lines.append('  vintage_mode = EXCLUDED.vintage_mode;')
    lines.append('')
    lines.append('COMMIT;')

    open('/home/strawer/dashboards/macro/catalog.sql', 'w', encoding='utf-8').write(
        '\n'.join(lines) + '\n')
    print('wrote catalog.sql', file=sys.stderr)


if __name__ == '__main__':
    main()
