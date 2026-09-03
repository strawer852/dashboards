"""Stamp content hashes onto asset URLs in the dashboard pages.

Cache-busting has to live in the URL, not in a response header. A browser that
was once told an asset is `immutable` will not revalidate it — Chrome holds it
for the full year even across a normal reload — so changing the header on the
server cannot reach a client that already cached the old file. Changing the URL
can, because it is a different cache key.

Run after any change to site/assets/*. Idempotent: existing ?v= stamps are
stripped and rewritten, so it can run on every deploy.
"""
from __future__ import annotations

import hashlib
import pathlib
import re
import sys

SITE = pathlib.Path.home() / "dashboards" / "site"
ASSETS = ["brb-dash.js", "brb-dash.css"]


def short_hash(p: pathlib.Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()[:10]


def main() -> int:
    stamps = {}
    for name in ASSETS:
        f = SITE / "assets" / name
        if not f.exists():
            print(f"missing {f}", file=sys.stderr)
            return 1
        stamps[name] = short_hash(f)

    pages = sorted(SITE.rglob("*.html"))
    changed = 0
    for page in pages:
        text = original = page.read_text(encoding="utf-8")
        for name, h in stamps.items():
            # Strip any existing stamp, then apply the current one.
            text = re.sub(rf"(/assets/{re.escape(name)})(\?v=[0-9a-f]+)?",
                          rf"\1?v={h}", text)
        if text != original:
            page.write_text(text, encoding="utf-8")
            changed += 1
        print(f"  {'updated' if text != original else 'unchanged'}  "
              f"{page.relative_to(SITE)}")

    print()
    for name, h in stamps.items():
        print(f"  {name:<16} v={h}")
    print(f"\n{changed}/{len(pages)} pages rewritten")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
