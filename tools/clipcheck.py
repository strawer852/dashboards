"""Two things only a browser can settle: whether any axis label overflows
its chart, and whether every in-page link points at something that exists.

A character-width guess is how the PPI heatmap was set to 210px in the first
place. This asks the browser: for every text node in every chart, is its
rendered box inside the chart's own box? Anything starting left of the chart's
left edge is clipped, and the clipped part is the START of the word -- the part
that identifies it.
"""
import subprocess
import sys

from playwright.sync_api import sync_playwright

import glob
import os
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
# The pages, from the specs rather than a typed list: a dashboard added
# tomorrow is checked without anyone remembering to add it here. Trap 32.
import yaml
PAGES = [yaml.safe_load(open(f))["path"]
         for f in sorted(glob.glob(str(ROOT / "dashboards" / "*.yml")))]

ip = subprocess.run(["docker", "inspect", "-f",
                     "{{range .NetworkSettings.Networks}}{{.IPAddress}} {{end}}",
                     "dashboards-web"], capture_output=True, text=True
                    ).stdout.split()[0]

JS = """() => {
  const out = [];
  document.querySelectorAll('.chart').forEach(el => {
    const cb = el.getBoundingClientRect();
    let worst = 0, worstText = '';
    el.querySelectorAll('text').forEach(t => {
      const b = t.getBoundingClientRect();
      const over = cb.left - b.left;          // >0 means it starts outside
      if (over > worst) { worst = over; worstText = t.textContent; }
    });
    if (worst > 0.5) out.push({id: el.id, over: Math.round(worst), text: worstText});
  });
  return out;
}"""


# An in-page link whose target does not exist scrolls nowhere and says nothing.
# A page cloned from another carries the ORIGINAL's contents list until every
# entry is replaced, which is how the PCE page shipped with eleven tables and
# twenty-three entries, twelve of them pointing at anchors from the PPI page.
ANCHORS = """() => {
  const bad = [];
  document.querySelectorAll('a[href^="#"]').forEach(a => {
    const id = a.getAttribute('href').slice(1);
    if (id && !document.getElementById(id)) bad.push(a.getAttribute('href'));
  });
  return bad;
}"""

bad = 0
with sync_playwright() as pw:
    b = pw.chromium.launch()
    pg = b.new_page(viewport={"width": 1280, "height": 1000})
    for path in PAGES:
        pg.goto("http://%s/%s/" % (ip, path), wait_until="networkidle",
                timeout=45000)
        pg.wait_for_timeout(3500)
        for r in pg.evaluate(JS):
            bad += 1
            print("CLIPPED  %-26s %-12s %3dpx of %r"
                  % (path.split("/")[-1], r["id"], r["over"], r["text"]))
        dangling = pg.evaluate(ANCHORS)
        if dangling:
            bad += len(dangling)
            print("DANGLING %-26s %d link(s) point nowhere: %s"
                  % (path.split("/")[-1], len(dangling), ", ".join(dangling[:8])))
    b.close()

print("\n%s" % ("no label overflows its chart, and every in-page link resolves"
                if not bad else "%d problem(s)" % bad))
sys.exit(1 if bad else 0)
