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


# A series whose range dwarfs its neighbours' turns them into a flat band. The
# four-line price decomposition on the labour costs page was unreadable this
# way: unit profits ranged -20% to +51% while two of the others stayed inside
# ten points. It was found by looking, which is not a check.
#
# Measured from the rendered chart rather than from the bundle, because what
# matters is the axis a reader actually sees. Line panels only: a heatmap has
# no shared value axis and paired bars are meant to differ in length.
#
# 4x is chosen against the two versions that were wrong -- the original panel
# at 8.7x and the half-fixed one at 5.0x -- and the two that are right, at 1.2x
# and 1.7x. It REPORTS rather than fails: a wide ratio is sometimes correct and
# sometimes the point. What it must not be is unnoticed.
SPANS = """() => {
  const out = [];
  if (!window.echarts) return out;
  document.querySelectorAll('.chart').forEach(el => {
    const inst = echarts.getInstanceByDom(el);
    if (!inst) return;
    const opt = inst.getOption();
    const ser = opt.series || [];
    if (ser.length < 2 || ser.some(s => s.type !== 'line')) return;
    const spans = [];
    ser.forEach(s => {
      let lo = Infinity, hi = -Infinity;
      (s.data || []).forEach(d => {
        const v = Array.isArray(d) ? d[d.length - 1]
                : (d && typeof d === 'object' ? d.value : d);
        const n = Number(v);
        if (v === null || v === undefined || Number.isNaN(n)) return;
        if (n < lo) lo = n;
        if (n > hi) hi = n;
      });
      if (lo <= hi) spans.push({ name: s.name || '?', span: hi - lo });
    });
    if (spans.length < 2) return;
    spans.sort((a, b) => b.span - a.span);
    const wide = spans[0], thin = spans[spans.length - 1];
    if (thin.span > 0 && wide.span / thin.span >= 4) {
      // data-span on the chart div records a judgement already made. It is
      // not a threshold override: the panel is still measured, still counted,
      // just not listed again every run.
      out.push({ id: el.id, wide: wide.name, thin: thin.name,
                 ok: !!el.dataset.span,
                 ws: Math.round(wide.span * 10) / 10,
                 ts: Math.round(thin.span * 10) / 10,
                 ratio: Math.round(wide.span / thin.span * 10) / 10 });
    }
  });
  return out;
}"""

bad = 0
flat = 0    # reported, not failed: a wide ratio is sometimes the point
acked = 0   # panels whose dominant series is recorded as deliberate
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
        for r in pg.evaluate(SPANS):
            if r["ok"]:
                acked += 1
                continue
            flat += 1
            print("FLATTENED %-25s %-12s %s spans %s vs %s at %s -- %sx"
                  % (path.split("/")[-1], r["id"], r["wide"], r["ws"],
                     r["thin"], r["ts"], r["ratio"]))

        dangling = pg.evaluate(ANCHORS)
        if dangling:
            bad += len(dangling)
            print("DANGLING %-26s %d link(s) point nowhere: %s"
                  % (path.split("/")[-1], len(dangling), ", ".join(dangling[:8])))
    b.close()

if flat:
    print("\n%d panel(s) above have one series flattening the rest. Not a "
          "failure -- look at each and decide. When the answer is that the "
          "small series being small IS the point, record it on the chart div "
          "as data-span=\"intended: <why>\" and it will not be listed again."
          % flat)
if acked:
    print("%d further panel(s) have a dominant series recorded as deliberate."
          % acked)

print("\n%s" % ("no label overflows its chart, and every in-page link resolves"
                if not bad else "%d problem(s)" % bad))
sys.exit(1 if bad else 0)
