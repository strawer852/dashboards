"""Screenshot a dashboard as it actually renders.

The standing gap this closes: every check in this repo reads a file or a
database, and trap 13 is explicit that a DOM probe is not looking. Four green
checks once passed over a chart that drew nothing. Nobody could look, because
the site is behind Authelia and there was no browser on the box.

There is no auth problem from HERE. Caddy and Authelia sit in FRONT of the
nginx container; going straight to the container's own address inside the
docker network serves exactly what a logged-in reader gets, with no login. The
address is discovered from docker rather than typed, because a container's IP
changes when it is recreated.

It also counts what each chart actually drew. That is not a substitute for the
picture -- it is the thing that tells you WHICH chart to look at when one of
forty-six is empty.

Usage:
  ~/.venvs/shot/bin/python tools/shoot.py                       # the payroll page
  ~/.venvs/shot/bin/python tools/shoot.py --path us/inflation/cpi
  ~/.venvs/shot/bin/python tools/shoot.py --element cSubMfg     # just one chart
"""
from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CONTAINER = "dashboards-web"


def container_url() -> str:
    out = subprocess.run(
        ["docker", "inspect", "-f",
         "{{range .NetworkSettings.Networks}}{{.IPAddress}} {{end}}", CONTAINER],
        capture_output=True, text=True)
    ip = (out.stdout or "").split()
    if not ip:
        raise SystemExit("could not find %s's address: %s"
                         % (CONTAINER, (out.stderr or "").strip()[:200]))
    return "http://%s" % ip[0]


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--path", default="us/employment/nonfarm-payroll")
    ap.add_argument("--base", default=None, help="default: the container's own address")
    ap.add_argument("--out", default=str(ROOT / "logs" / "shots"))
    ap.add_argument("--element", help="screenshot one chart div instead of the page")
    ap.add_argument("--width", type=int, default=1280)
    ap.add_argument("--wait", type=int, default=4000, help="ms after load")
    args = ap.parse_args()

    from playwright.sync_api import sync_playwright

    base = args.base or container_url()
    url = "%s/%s/" % (base.rstrip("/"), args.path.strip("/"))
    outdir = Path(args.out)
    outdir.mkdir(parents=True, exist_ok=True)
    name = args.element or args.path.strip("/").replace("/", "-")
    dest = outdir / ("%s.png" % name)

    errors: list[str] = []
    with sync_playwright() as pw:
        b = pw.chromium.launch()
        pg = b.new_page(viewport={"width": args.width, "height": 1000},
                        device_scale_factor=2)
        pg.on("console", lambda m: errors.append("console.%s: %s" % (m.type, m.text))
              if m.type == "error" else None)
        pg.on("pageerror", lambda e: errors.append("pageerror: %s" % e))
        resp = pg.goto(url, wait_until="networkidle", timeout=45000)
        print("GET %s -> %s" % (url, resp.status if resp else "no response"))
        pg.wait_for_timeout(args.wait)

        # What each chart actually drew. An ECharts panel that mounted but got
        # no series still has axes, so counting every node would call an empty
        # chart healthy -- count the marks instead.
        counts = pg.evaluate("""() => {
          const out = [];
          document.querySelectorAll('.chart').forEach(el => {
            const svg = el.querySelector('svg');
            out.push({
              id: el.id,
              h: Math.round(el.getBoundingClientRect().height),
              svg: !!svg,
              // Data marks only. Axes and gridlines are <line>, so counting
              // them made a healthy one-line small multiple (11) sit right on
              // the same threshold as an empty panel -- the check cried wolf
              // on two charts with 308 observations each.
              marks: svg ? svg.querySelectorAll('path,rect,circle').length : 0,
              rules: svg ? svg.querySelectorAll('line').length : 0,
              text: svg ? svg.querySelectorAll('text').length : 0,
            });
          });
          return out;
        }""")

        if args.element:
            el = pg.query_selector("#%s" % args.element)
            if not el:
                raise SystemExit("no element #%s on the page" % args.element)
            el.screenshot(path=str(dest))
        else:
            pg.screenshot(path=str(dest), full_page=True)
        b.close()

    # A panel that mounted with no series still draws its axes, so the test is
    # whether it drew any DATA mark, not whether it drew anything.
    empty = [c for c in counts if c["marks"] < 3 or c["h"] < 40 or not c["svg"]]
    print("%d charts; %d suspicious" % (len(counts), len(empty)))
    print("%-12s %6s %6s %6s %6s" % ("chart", "height", "svg", "marks", "text"))
    for c in counts:
        flag = "  <-- LOOK" if c in empty else ""
        print("%-12s %6d %6s %6d %6d%s"
              % (c["id"], c["h"], "yes" if c["svg"] else "NO", c["marks"],
                 c["text"], flag))
    if errors:
        print("\n%d page errors:" % len(errors))
        for e in errors[:10]:
            print("  " + e[:160])
    print("\nwrote %s" % dest)
    return 1 if (empty or errors) else 0


if __name__ == "__main__":
    raise SystemExit(main())
