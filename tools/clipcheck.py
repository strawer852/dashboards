"""Does any axis label actually overflow its chart? Measured, not estimated.

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
    b.close()

print("\n%s" % ("no label overflows its chart" if not bad
                else "%d labels overflow" % bad))
sys.exit(1 if bad else 0)
