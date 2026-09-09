#!/usr/bin/env python3
"""Static checks on the pages that need no browser and no data.

Each of these caught a real defect on 9 September 2026 that every browser
check had passed over, because none of them is about rendering:

* a legend swatch class the stylesheet never defines (`kink`, on 24 legends)
  falls back to the inherited grey and looks like a design choice;
* a table numbered 6 sitting after Table 10, and a source footer with two
  tables below it, are both valid HTML;
* a `<div class="row">` opened inside another panel's cell renders, mostly;
* a chart div no panel names, or a panel naming a div that is not there, is
  a blank space that `shoot.py` counts as zero marks and moves on.

Usage:  python3 tools/keycheck.py        # exit 1 on any finding
"""
from __future__ import annotations

import glob
import re
import sys
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parent.parent
SITE = ROOT / "site"
CSS = (SITE / "assets" / "brb-dash.css").read_text(encoding="utf-8")
PAGES = [SITE / yaml.safe_load(open(f))["path"] / "index.html"
         for f in sorted(glob.glob(str(ROOT / "dashboards" / "*.yml")))]

KEY_CLASSES = set(re.findall(r"\.key \.(k[a-z0-9]+)", CSS))


def check(page: Path) -> list[str]:
    s = page.read_text(encoding="utf-8")
    name = page.parent.name
    out = []
    main_a = s.index("<main")
    main_b = s.index("</main>")
    main = s[main_a:main_b]

    # 1. every legend swatch class has a rule
    for cls in re.findall(r'<p class="key">(.*?)</p>', main, flags=re.S):
        for k in re.findall(r'<i class="([a-z0-9]+)">', cls):
            if k not in KEY_CLASSES:
                out.append(f"{name}: legend class .{k} is not in brb-dash.css")

    # 2. tables numbered 1..N in document order
    nums = [int(n) for n in re.findall(r'<span class="n">Table (\d+)</span>', main)]
    if nums != list(range(1, len(nums) + 1)):
        out.append(f"{name}: table numbers out of order: {nums}")

    # 3. the source footer is the last block in <main>
    if 'class="src"' in main:
        after = main[main.index('class="src"'):]
        if 'class="t"' in after or 'class="t ' in after:
            out.append(f"{name}: a table sits below the source footer")
    else:
        out.append(f"{name}: no source footer")

    # 4. divs balance inside <main>
    opened, closed = main.count("<div"), main.count("</div>")
    if opened != closed:
        out.append(f"{name}: {opened} <div> opened, {closed} closed inside <main>")

    # 5. chart divs and panel `el:` entries match one to one
    divs = set(re.findall(r'<div class="chart" id="([A-Za-z0-9_]+)"', main))
    script = s[main_b:]
    els = set(re.findall(r'\bel:\s*"([A-Za-z0-9_]+)"', script))
    # A panel built through a helper -- monthAndYear("cCpiMY", ...) -- still
    # quotes the id, so any quoted occurrence in the script counts.
    quoted = set(re.findall(r'"(c[A-Za-z0-9_]+)"', script))
    els |= (quoted & divs)
    for d in sorted(divs - els):
        out.append(f"{name}: chart div #{d} has no panel")
    for e in sorted(els - divs):
        out.append(f"{name}: panel el \"{e}\" has no chart div")

    # 6. the in-page contents list resolves, and lists every numbered table
    ids = set(re.findall(r' id="(t\d+)"', main))
    hrefs = re.findall(r'href="#(t\d+)"', s)
    for h in hrefs:
        if h not in ids:
            out.append(f"{name}: contents link #{h} points nowhere")
    for t in sorted(ids, key=lambda x: int(x[1:])):
        if t not in hrefs:
            out.append(f"{name}: {t} is not in the contents list")

    # 7. a forecast record beside the page is well formed, and every call in
    #    it was made BEFORE the release it calls. A record dated after its
    #    release is not a forecast, and nothing in the browser would say so
    #    beyond a red word in the header.
    fc = page.parent / "forecasts.json"
    if fc.exists():
        out += check_forecasts(name, fc, s)
    return out


def check_forecasts(name: str, fc: Path, page_html: str) -> list[str]:
    import json
    from datetime import date
    out = []
    try:
        doc = json.loads(fc.read_text(encoding="utf-8"))
    except ValueError as e:
        return [f"{name}: forecasts.json does not parse: {e}"]
    if doc.get("schema") != 1:
        out.append(f"{name}: forecasts.json schema {doc.get('schema')!r} is not 1")
    if "forecasts.json" not in page_html:
        out.append(f"{name}: forecasts.json exists but the page does not load it")
    seen = set()
    for i, rec in enumerate(doc.get("forecasts", [])):
        tag = f"{name}: forecast[{i}]"
        try:
            made = date.fromisoformat(rec["made"])
            due = date.fromisoformat(rec["release_at"][:10])
            ref = date.fromisoformat(rec["for"])
        except (KeyError, ValueError) as e:
            out.append(f"{tag}: made/for/release_at missing or malformed ({e})")
            continue
        if made >= due:
            out.append(f"{tag}: made {made} is not before its release {due}")
        if ref >= due:
            out.append(f"{tag}: reference period {ref} is not before its release {due}")
        if rec["for"] in seen:
            out.append(f"{tag}: a second record for {rec['for']}")
        seen.add(rec["for"])
        keys = set()
        for it in rec.get("items", []):
            for f in ("key", "label", "series", "value"):
                if f not in it:
                    out.append(f"{tag}: item missing {f!r}")
            if it.get("key") in keys:
                out.append(f"{tag}: item key {it.get('key')!r} repeated")
            keys.add(it.get("key"))
            if not isinstance(it.get("value"), (int, float)):
                out.append(f"{tag}: item {it.get('key')!r} value is not a number")
        if not rec.get("reasons"):
            out.append(f"{tag}: no reasons given")
    return out


def main() -> int:
    findings = []
    for page in PAGES:
        findings += check(page)
    for f in findings:
        print("  " + f)
    print(f"\n{len(PAGES)} pages checked, {len(findings)} finding(s)")
    return 1 if findings else 0


if __name__ == "__main__":
    raise SystemExit(main())
