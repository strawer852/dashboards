#!/usr/bin/env python3
"""Reconcile a news release table against macro_observations, by value.

The method that verified the 174 payroll industries (CLAUDE.md trap 36),
written down so it can be re-run at any release: take the table the agency
actually published, read every catalogued series in that release AS OF the
vintage that published it (trap 18), and find, for every published row, the
series that reproduce its figures. A title is never evidence; a row is matched
only if every number it prints is reproduced by the same series.

    tools/reconcile.py cpi  --asof 2026-09-08 --items cu.item T1.htm T2.htm T3.htm
    tools/reconcile.py ppi  --asof 2026-09-08 T1.htm T3.htm [T2.htm]
    tools/reconcile.py eci  --asof 2026-09-08 T1.htm ... T13.htm
    tools/reconcile.py prod --asof 2026-09-02 T1.htm ... T5.htm
    tools/reconcile.py prod --asof 2026-09-08 T6.htm

`--asof` is any date on or after the publication and before the next one:
the values read are those the release printed, whatever has been revised
since. Tables are the BLS news-release HTML pages, saved locally. bls.gov
refuses this VPS outright (403 to curl, to a full browser header set and to
headless Chromium alike), so fetch them through the Wayback Machine:

    curl -sL --compressed -o cpi.t02.htm \\
      "https://web.archive.org/web/2026id_/https://www.bls.gov/news.release/cpi.t02.htm"

and check the caption's month is the release you mean. CPI, PPI and ECI
tables are HTML (`<table class="regular">`); Productivity and Costs is
preformatted text in a `<pre>` block, and the parser here handles both.

What a failure looks like, per row:
  NONE      no catalogued series reproduces the row -- absent from the
            database, or its values disagree with the publication
  MULTI     more than one series reproduces it (usually a parent and a
            single child that move identically; look, then decide)
  ID?       the series that reproduces it is not the one BLS's own code
            says it should be (CPI via cu.item, PPI via the table's own
            group and item codes), i.e. an id filed under the wrong row --
            the trap-36 case

Percent changes are recomputed from the stored indexes and compared with the
published one-decimal figure at a tolerance of 0.051, so a rounding edge is
never reported as a mismatch and a real disagreement (>= 0.06) always is.
Index levels are compared to three decimals.
"""
from __future__ import annotations

import argparse
import html as H
import os
import re
import sys
from collections import defaultdict
from datetime import date
from html.parser import HTMLParser

import psycopg

DSN = os.environ["MACRO_DSN"]
TOL = 0.051          # percent-change tolerance: a rounding edge, never a revision
IDX_TOL = 0.0005     # index levels are published to three decimals

MONTHS = {m: i for i, m in enumerate(
    ["jan", "feb", "mar", "apr", "may", "jun", "jul", "aug", "sep", "oct", "nov", "dec"], 1)}
ROMAN = {"I": 1, "II": 2, "III": 3, "IV": 4}


# ------------------------------------------------------------------ parsing --

class _Table(HTMLParser):
    """The first <table class="regular"> on a BLS release page.

    Header cells carry rowspan/colspan, so the header is laid out on a grid
    and each body column gets the label of the lowest cell above it plus the
    label of the cell above that (`cols` = list of (parent, leaf))."""

    def __init__(self):
        super().__init__()
        self.in_table = self.in_thead = self.in_caption = False
        self.rows, self.caption = [], ""
        self.hcells = []           # (row, colspan, rowspan, text) in thead order
        self.hrow = -1
        self.cur = self.cell = None
        self.span = (1, 1)
        self.txt = ""

    def handle_starttag(self, t, a):
        a = dict(a)
        if t == "table" and "regular" in (a.get("class") or ""):
            self.in_table = True
        if not self.in_table:
            return
        if t == "caption":
            self.in_caption = True
        if t == "thead":
            self.in_thead = True
        if t == "tr":
            self.cur = {"level": 0, "name": None, "vals": []}
            if self.in_thead:
                self.hrow += 1
        if t in ("th", "td"):
            self.cell, self.txt = t, ""
            self.span = (int(a.get("colspan", 1)), int(a.get("rowspan", 1)))
        if t == "p" and self.cell == "th":
            m = re.match(r"sub(\d+)", a.get("class") or "")
            if m:
                self.cur["level"] = int(m.group(1))
        if t == "br" and self.cell:
            self.txt += " "

    def handle_endtag(self, t):
        if not self.in_table:
            return
        if t == "caption":
            self.in_caption = False
        if t == "thead":
            self.in_thead = False
        if t in ("th", "td") and self.cell:
            v = re.sub(r"\s+", " ", H.unescape(self.txt)).strip()
            if self.in_thead:
                self.hcells.append((self.hrow, self.span[0], self.span[1], v))
            elif self.cell == "th" and self.cur["name"] is None:
                self.cur["name"] = v
            else:
                self.cur["vals"].append(v)
            self.cell = None
        if t == "tr":
            if not self.in_thead and self.cur and self.cur["name"] is not None:
                self.rows.append(self.cur)
            self.cur = None
        if t == "table":
            self.in_table = False

    def handle_data(self, d):
        if self.in_caption:
            self.caption += d
        if self.cell is not None:
            self.txt += d

    def columns(self) -> list[tuple[str, str]]:
        """(parent, leaf) label per body column, stub column excluded."""
        nrows = self.hrow + 1
        grid: dict[tuple[int, int], str] = {}
        next_col = [0] * nrows
        for r, cs, rs, text in self.hcells:
            c = next_col[r]
            while (r, c) in grid:
                c += 1
            for dr in range(rs):
                for dc in range(cs):
                    grid[(r + dr, c + dc)] = text
            next_col[r] = c + cs
        if not grid:
            return []
        ncols = max(c for _, c in grid) + 1
        out = []
        for c in range(ncols):
            labels = [grid.get((r, c), "") for r in range(nrows)]
            leaf = labels[-1]
            parent = next((x for x in reversed(labels[:-1]) if x and x != leaf), "")
            out.append((parent, leaf))
        return out[1:]


def parse_table(path: str) -> _Table:
    p = _Table()
    p.feed(open(path, encoding="utf-8", errors="replace").read())
    p.caption = re.sub(r"\s+", " ", p.caption).strip()
    p.rows = [r for r in p.rows if any(v not in ("", "-") for v in r["vals"])]
    return p


def clean_name(s: str) -> str:
    return re.sub(r"(\(\d+\))+$", "", s).strip()


def num(s: str) -> float | None:
    s = s.replace(",", "").strip()
    if s in ("", "-", "(NA)", "NA", "n.a."):
        return None
    try:
        return float(s)
    except ValueError:
        return None


def month_of(label: str, default_year: int | None = None) -> date | None:
    """'Jul. 2026' -> 2026-07-01; 'June' with default_year -> that year."""
    m = re.search(r"([A-Za-z]{3})[a-z.]*\s*(\d{4})?", label)
    if not m:
        return None
    mon = MONTHS.get(m.group(1).lower()[:3])
    if not mon:
        return None
    year = int(m.group(2)) if m.group(2) else default_year
    return None if year is None else date(year, mon, 1)


def quarter_of(label: str) -> date | None:
    """ECI labels name the quarter's last month: 'Jun. 2026' -> 2026-04-01."""
    d = month_of(label)
    if d and d.month in (3, 6, 9, 12):
        return date(d.year, d.month - 2, 1)
    return None


# --------------------------------------------------------------------- data --

def load_asof(release: str, asof: str, since: str) -> tuple[dict, dict]:
    """series -> {observation_dt: value} at the latest vintage <= asof (trap 18:
    `vintage_dt::date <= asof` so a fetch-time vintage on the day counts), and
    series -> (title, seasonal_adjustment, source, vintage_mode)."""
    with psycopg.connect(DSN) as conn, conn.cursor() as cur:
        cur.execute("""
            SELECT DISTINCT ON (o.series_id, o.observation_dt)
                   o.series_id, o.observation_dt, o.value::float8
            FROM macro_observations o
            JOIN macro_series_meta m USING (series_id)
            WHERE m.release_id = %s
              AND o.vintage_dt::date <= %s
              AND o.observation_dt >= %s
            ORDER BY o.series_id, o.observation_dt, o.vintage_dt DESC""",
                    (release, asof, since))
        obs: dict[str, dict[date, float | None]] = defaultdict(dict)
        for sid, d, v in cur.fetchall():
            obs[sid][d] = v
        cur.execute("SELECT series_id, title, seasonal_adjustment, source, vintage_mode "
                    "FROM macro_series_meta WHERE release_id = %s", (release,))
        meta = {r[0]: r[1:] for r in cur.fetchall()}
    return obs, meta


def pct(a, b):
    return None if a in (None, 0) or b is None else (b / a - 1.0) * 100.0


def prev_month(d: date, n: int = 1) -> date:
    y, m = d.year, d.month - n
    while m <= 0:
        y, m = y - 1, m + 12
    return date(y, m, 1)


# ----------------------------------------------------------------- matching --
# A "fact" is (kind, when, published_value). A series satisfies a fact if the
# same quantity computed from its stored observations agrees within tolerance.

def evaluate(kind: str, when: date, series: dict[date, float | None]):
    if kind in ("idx", "val"):
        return series.get(when)
    if kind == "pc1":
        return pct(series.get(prev_month(when)), series.get(when))
    if kind == "pc12":
        return pct(series.get(prev_month(when, 12)), series.get(when))
    if kind == "pc3q":      # 3-month change ended this quarter, quarterly series
        return pct(series.get(prev_month(when, 3)), series.get(when))
    if kind == "pc12q":     # 12-month change, quarterly series
        return pct(series.get(prev_month(when, 12)), series.get(when))
    raise ValueError(kind)


def satisfies(facts, series) -> bool:
    for kind, when, want in facts:
        got = evaluate(kind, when, series)
        if got is None:
            return False
        if abs(got - want) > (IDX_TOL if kind == "idx" else TOL):
            return False
    return True


def match(facts, obs, candidates=None) -> list[str]:
    if not facts:
        return []
    ids = candidates if candidates is not None else obs.keys()
    return sorted(s for s in ids if satisfies(facts, obs[s]))


# ------------------------------------------------------------------ reports --

class Report:
    """Verdict per row. With an expected id (from the agency's own code):
         OK       the expected series reproduces every figure (others that
                  happen to as well are listed after "also:")
         VALUE!   the expected series is held and does NOT reproduce them --
                  the serious case: our data disagrees with the publication
         ABSENT   the expected series is not catalogued; anything listed
                  reproduced the row by coincidence
       Without one: OK / MULTI / NONE on the value match alone."""

    def __init__(self):
        self.lines, self.ok = [], 0
        self.bad: dict[str, list] = {"VALUE!": [], "ABSENT": [], "NONE": [], "MULTI": []}

    def row(self, table, name, level, facts, hits, expected=None, meta=None, held=None):
        also = ""
        if not facts:
            tag = "n/a"
        elif expected:
            if expected in hits:
                tag = "OK"
                extra = [h for h in hits if h != expected]
                also = f"  also: {','.join(extra)}" if extra else ""
            elif held and expected in held:
                tag = "VALUE!"
            else:
                tag = "ABSENT"
        elif not hits:
            tag = "NONE"
        elif len(hits) > 1:
            tag = "MULTI"
        else:
            tag = "OK"
        if tag == "OK":
            self.ok += 1
        elif tag in self.bad:
            self.bad[tag].append((table, name, expected, hits))
        shown = expected if tag in ("OK", "VALUE!", "ABSENT") and expected else ",".join(hits) or "-"
        title = (meta.get(shown) or ("",))[0] if meta and shown in (meta or {}) else ""
        pad = max(1, 62 - 2 * level)
        self.lines.append(f"{tag:6} {table:<9} {'  ' * level}{name[:pad]:<{pad}} "
                          f"n={len(facts)} -> {shown}{also}  {title[:70]}")

    def dump(self, verbose):
        if verbose:
            print("\n".join(self.lines))
        print(f"\nrows reproduced: {self.ok}   " +
              "   ".join(f"{k}: {len(v)}" for k, v in self.bad.items()))
        for k in ("VALUE!", "ABSENT", "NONE", "MULTI"):
            for t, n, e, h in self.bad[k]:
                print(f"  {k:6} {t:<9} {n}" + (f"  expected {e}" if e else "") +
                      (f"  reproduced by {','.join(h)}" if h and k != "OK" else ""))


def tname(caption: str) -> str:
    m = re.match(r"Table\s*(\d+)", caption)
    return f"T{m.group(1)}" if m else "T?"


# ---------------------------------------------------------------------- CPI --

def norm(s: str) -> str:
    s = clean_name(s).lower().replace("’", "'")
    return re.sub(r"[^a-z0-9']+", " ", s).strip()


def cpi_item_codes(path: str) -> dict[str, str]:
    """BLS cu.item, item_code<TAB>item_name<TAB>... -> {normalised name: code}."""
    out = {}
    for line in open(path, encoding="utf-8", errors="replace"):
        parts = line.rstrip("\n").split("\t")
        if len(parts) >= 2 and parts[0] != "item_code":
            out[norm(parts[1])] = parts[0].strip()
    return out


def run_cpi(args):
    obs, meta = load_asof("bls.cpi", args.asof, "2024-01-01")
    codes = cpi_item_codes(args.items) if args.items else {}
    nsa = [s for s in obs if meta[s][1] == "NSA"]
    sa = [s for s in obs if meta[s][1] == "SA"]
    rep = Report()
    no_code = set()
    for path in args.tables:
        t = parse_table(path)
        print(f"{t.caption}")
        tn = tname(t.caption)
        cols = t.columns()
        for r in t.rows:
            name = clean_name(r["name"])
            facts_nsa, facts_sa = [], []
            for (parent, leaf), v in zip(cols, r["vals"]):
                x = num(v)
                if x is None or parent.startswith("Relative") or leaf.startswith("Relative"):
                    continue
                if parent == "Unadjusted indexes":
                    facts_nsa.append(("idx", month_of(leaf), x))
                elif parent == "Unadjusted percent change":
                    start, end = month_of(leaf.split("-")[0]), month_of(leaf.split("-")[-1])
                    facts_nsa.append(("pc12" if start == prev_month(end, 12) else "pc1", end, x))
                elif parent == "Seasonally adjusted percent change":
                    facts_sa.append(("pc1", month_of(leaf.split("-")[-1]), x))
            code = codes.get(norm(name))
            if codes and not code:
                no_code.add(name)
            exp_nsa = f"CUUR0000{code}" if code else None
            exp_sa = f"CUSR0000{code}" if code else None
            rep.row(tn + "/NSA", name, r["level"], facts_nsa, match(facts_nsa, obs, nsa), exp_nsa, meta, obs)
            if facts_sa:
                hits = match(facts_sa, obs, sa)
                # BLS prints SA changes for items we hold unadjusted only; an
                # SA row is reported only when an SA series exists or matched.
                if hits or (exp_sa and exp_sa in obs):
                    rep.row(tn + "/SA", name, r["level"], facts_sa, hits, exp_sa, meta, obs)
    rep.dump(args.verbose)
    if no_code:
        print(f"\n{len(no_code)} row name(s) not found in cu.item, matched by value only:")
        for n in sorted(no_code):
            print(f"  {n}")


# ---------------------------------------------------------------------- PPI --

def run_ppi(args):
    obs, meta = load_asof("bls.ppi", args.asof, "2024-01-01")
    sa = [s for s in obs if meta[s][1] == "SA"]
    nsa = [s for s in obs if meta[s][1] == "NSA"]
    rep = Report()
    for path in args.tables:
        t = parse_table(path)
        print(f"{t.caption}")
        tn = tname(t.caption)
        year = int(re.search(r"(\d{4})", t.caption).group(1))
        cols = t.columns()
        for r in t.rows:
            name = clean_name(r["name"])
            d = {leaf: v for (parent, leaf), v in zip(cols, r["vals"])}
            code = (d.get("Group code", "") + d.get("Item code", "")).strip()
            facts_sa, facts_nsa = [], []
            for (parent, leaf), v in zip(cols, r["vals"]):
                x = num(v)
                if x is None or leaf in ("Group code", "Item code") or "Relative" in parent + leaf or "base" in leaf.lower():
                    continue
                if parent.startswith("Unadjusted 12-month"):
                    facts_nsa.append(("pc12", month_of(leaf.split(" to ")[-1]), x))
                elif parent.startswith("Seasonally adjusted 1-month"):
                    facts_sa.append(("pc1", month_of(leaf.split(" to ")[-1], year), x))
                elif parent.startswith("Seasonally adjusted index"):
                    facts_sa.append(("idx", month_of(leaf), x))
            if facts_sa:
                rep.row(tn + "/SA", name, r["level"], facts_sa, match(facts_sa, obs, sa),
                        "WPS" + code if code else None, meta, obs)
            if facts_nsa:
                rep.row(tn + "/NSA", name, r["level"], facts_nsa, match(facts_nsa, obs, nsa),
                        "WPU" + code if code else None, meta, obs)
    rep.dump(args.verbose)


# ---------------------------------------------------------------------- ECI --

def run_eci(args):
    obs, meta = load_asof("bls.eci", args.asof, "2023-01-01")
    sa = [s for s in obs if meta[s][1] == "SA"]
    nsa = [s for s in obs if meta[s][1] == "NSA"]
    rep = Report()
    for path in args.tables:
        t = parse_table(path)
        print(f"{t.caption}")
        tn = tname(t.caption)
        pool = nsa if "Not seasonally" in t.caption else sa
        cols = t.columns()
        if not cols:
            print(f"  (no parseable header; {len(t.rows)} rows skipped)")
            continue
        for r in t.rows:
            facts = []
            for (parent, leaf), v in zip(cols, r["vals"]):
                x = num(v)
                q = quarter_of(leaf)
                if x is None or q is None:
                    continue
                if parent.startswith("Indexes"):
                    facts.append(("idx", q, x))
                elif "3-month" in parent or "3-months" in parent:
                    facts.append(("pc3q", q, x))
                elif "12-month" in parent:
                    facts.append(("pc12q", q, x))
            rep.row(tn, clean_name(r["name"]), r["level"], facts, match(facts, obs, pool), None, meta)
    rep.dump(args.verbose)


# ------------------------------------------------------------- Productivity --

def parse_pre(path: str):
    """Productivity and Costs tables: a <pre> block with a column header, then
    three sections (annual-rate changes, year-ago changes, indexes), each a
    run of 'YYYY II  v v v ...' rows. Returns (title, columns, sections) where
    sections maps section title -> {quarter date: [values]}."""
    h = open(path, encoding="utf-8", errors="replace").read()
    m = re.search(r"<pre>(.*?)</pre>", h, re.S)
    txt = H.unescape(re.sub(r"<[^>]+>", "", m.group(1)))
    lines = txt.split("\n")
    title = " ".join(l.strip() for l in lines[:6] if l.strip().startswith("Table") or l.strip().endswith(".") and "Table" not in l)[:120]
    title = re.sub(r"\s+", " ", " ".join(l.strip() for l in lines[:8] if l.strip())[:160])
    sections: dict[str, dict[date, list[float]]] = {}
    cur = None
    year = None
    for l in lines:
        s = l.strip()
        if not s or s.startswith("---") or s.startswith("See footnotes"):
            continue
        if s.startswith("Percent change") or s.startswith("Indexes"):
            cur = s
            sections[cur] = {}
            continue
        if cur is None:
            continue
        m = re.match(r"^(\d{4})?\s*(I{1,3}V?|IV|ANNUAL)\s+(.*)$", s)
        if not m:
            continue
        if m.group(1):
            year = int(m.group(1))
        if m.group(2) == "ANNUAL" or year is None:
            continue
        q = ROMAN[m.group(2)]
        vals = [float(x) for x in re.findall(r"-?\d+\.\d+", m.group(3))]
        sections[cur][date(year, 3 * q - 2, 1)] = vals
    return title, sections


def run_prod(args):
    obs, meta = load_asof("bls.productivity", args.asof, "2023-01-01")
    rep = Report()
    for path in args.tables:
        title, sections = parse_pre(path)
        print(title)
        tn = tname(title)
        for sec, rows in sections.items():
            ncol = max(len(v) for v in rows.values())
            short = {"Percent change from previous quarter at annual rate": "ar",
                     "Percent change from corresponding quarter of previous year": "yoy"}.get(
                re.sub(r"\s*\(\d+\)$", "", sec), "idx")
            for c in range(ncol):
                facts = [("val", q, v[c]) for q, v in rows.items() if len(v) > c]
                hits = match(facts, obs)
                rep.row(f"{tn}/{short}", f"column {c + 1}", 0, facts, hits, None, meta)
    rep.dump(args.verbose)


# --------------------------------------------------------------------- main --

def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("kind", choices=["cpi", "ppi", "eci", "prod"])
    ap.add_argument("--asof", required=True, help="a date on or after the publication, YYYY-MM-DD")
    ap.add_argument("--items", help="cpi: BLS cu.item file, to derive the expected id from the row name")
    ap.add_argument("-v", "--verbose", action="store_true", help="print every row")
    ap.add_argument("tables", nargs="+", help="saved news-release table HTML files")
    args = ap.parse_args()
    {"cpi": run_cpi, "ppi": run_ppi, "eci": run_eci, "prod": run_prod}[args.kind](args)
    return 0


if __name__ == "__main__":
    sys.exit(main())
