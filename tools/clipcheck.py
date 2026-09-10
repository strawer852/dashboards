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
      if (!b.width) return;
      // >0 means it starts outside on the left or ends outside on the right.
      // The right edge matters since the newest period's label sits there.
      const over = Math.max(cb.left - b.left, b.right - cb.right);
      if (over > worst) { worst = over; worstText = t.textContent; }
    });
    if (worst > 0.5) out.push({id: el.id, over: Math.round(worst), text: worstText});
  });
  return out;
}"""


# Axis labels that run into each other are unreadable and overflow nothing:
# the weekly claims axes did it for weeks in half-width cells and over ten
# years, with `tick` set for a five-year full-width chart, and the overflow
# test above was green throughout. Found by looking, 9 September 2026.
# Measured as rendered: the text boxes along the bottom of each chart, sorted
# left to right, and any pair whose boxes intersect horizontally.
OVERLAP = """() => {
  const out = [];
  document.querySelectorAll('.chart').forEach(el => {
    const cb = el.getBoundingClientRect();
    const boxes = [];
    el.querySelectorAll('text').forEach(t => {
      const b = t.getBoundingClientRect();
      if (b.width > 0 && b.top > cb.bottom - 34) boxes.push({l: b.left, r: b.right, t: b.top, s: t.textContent});
    });
    boxes.sort((a, b) => a.l - b.l);
    let n = 0, eg = '';
    // Same baseline only: the lowest value-axis label sits beside the first
    // date label and shares its horizontal span without touching it.
    for (let i = 1; i < boxes.length; i++) {
      const a = boxes[i - 1], b = boxes[i];
      // Touching is failing too: two monospace labels with no gap read as one.
      if (b.l < a.r + 4 && Math.abs(b.t - a.t) < 3) { n++; if (!eg) eg = a.s + ' | ' + b.s; }
    }
    if (n) out.push({id: el.id, n: n, eg: eg});
  });
  return out;
}"""


# The newest period must carry a label. The engine spaced date labels from the
# LEFT edge, so on 10 September 2026 159 of 164 charts left their last period
# unlabelled: Weekly Claims Table 7 ended at 29 August 2026 under a last label
# of 4 October 2025, and William reported the table as not updating. The data
# was current; the axis said otherwise. The overflow and collision tests above
# were green throughout, because an absent label overflows nothing.
END_LABEL = """() => {
  const iso = /^\\d{4}-\\d{2}-\\d{2}$/;
  const out = [];
  document.querySelectorAll('.chart').forEach(el => {
    const inst = window.echarts && echarts.getInstanceByDom(el);
    if (!inst) return;
    const xa = (inst.getOption().xAxis || [])[0];
    if (!xa || xa.type !== 'category' || !xa.data || xa.data.length < 8) return;
    const cats = xa.data.map(d => (d && d.value !== undefined) ? d.value : d);
    const last = String(cats[cats.length - 1]);
    if (!iso.test(last)) return;
    const fmt = xa.axisLabel && xa.axisLabel.formatter;
    const want = typeof fmt === 'function' ? fmt(last) : last;
    const shown = [...el.querySelectorAll('text')]
      .some(t => t.textContent === want && t.getBoundingClientRect().width > 0);
    if (!shown) out.push({id: el.id, want: want});
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
  // 2nd-98th percentile, so a single spike cannot set the scale. JOLTS rates
  // was flagged for one COVID layoffs point while being perfectly readable.
  const pct = (a, q) => {
    if (!a.length) return null;
    const i = (a.length - 1) * q;
    const lo = Math.floor(i), hi = Math.ceil(i);
    return a[lo] + (a[hi] - a[lo]) * (i - lo);
  };
  document.querySelectorAll('.chart').forEach(el => {
    const inst = echarts.getInstanceByDom(el);
    if (!inst) return;
    const opt = inst.getOption();
    const ser = opt.series || [];
    if (ser.length < 2 || ser.some(s => s.type !== 'line')) return;
    // Grouped by axis. A dual-axis panel draws two independent scales and a
    // series is only ever squashed relative to the one it is plotted against.
    const byAxis = {};
    ser.forEach(s => {
      const vals = [];
      (s.data || []).forEach(d => {
        const v = Array.isArray(d) ? d[d.length - 1]
                : (d && typeof d === 'object' ? d.value : d);
        const n = Number(v);
        if (v === null || v === undefined || Number.isNaN(n)) return;
        vals.push(n);
      });
      if (vals.length < 8) return;
      vals.sort((a, b) => a - b);
      const lo = pct(vals, 0.02), hi = pct(vals, 0.98);
      const k = String(s.yAxisIndex || 0);
      (byAxis[k] = byAxis[k] || []).push(
        { name: s.name || '?', lo: lo, hi: hi, span: hi - lo });
    });
    Object.keys(byAxis).forEach(k => {
      const rows = byAxis[k];
      if (rows.length < 2) return;
      // The axis a reader sees, estimated the same robust way.
      const axis = Math.max.apply(null, rows.map(r => r.hi))
                 - Math.min.apply(null, rows.map(r => r.lo));
      if (!(axis > 0)) return;
      const share = r => r.span / axis;
      const squashed = rows.filter(r => share(r) < 0.20)
                           .sort((a, b) => share(a) - share(b));
      // One smooth line among readable ones is normal, and is usually the
      // finding. Two or more is a panel whose small series cannot be read.
      if (squashed.length < 2) return;
      out.push({ id: el.id, ok: !!el.dataset.span,
                 n: squashed.length, of: rows.length,
                 names: squashed.map(r => r.name + ' ' +
                          Math.round(share(r) * 100) + '%').join(', ') });
    });
  });
  return out;
}"""

bad = 0
flat = 0    # reported, not failed: a wide ratio is sometimes the point
acked = 0   # panels whose dominant series is recorded as deliberate
with sync_playwright() as pw:
    b = pw.chromium.launch()
    # Labels that fit at 1280px collided at 430px on nearly every panel, so
    # the two label tests run at both widths; the span test needs only one.
    phone = b.new_page(viewport={"width": 430, "height": 900})
    pg = b.new_page(viewport={"width": 1280, "height": 1000})
    for path in PAGES:
        for page, width in ((pg, 1280), (phone, 430)):
            page.goto("http://%s/%s/" % (ip, path), wait_until="networkidle",
                      timeout=45000)
            page.wait_for_timeout(3500)
            for r in page.evaluate(JS):
                bad += 1
                print("CLIPPED  %-26s %-12s @%-4d %3dpx of %r"
                      % (path.split("/")[-1], r["id"], width, r["over"], r["text"]))
            for r in page.evaluate(OVERLAP):
                bad += 1
                print("OVERLAP  %-26s %-12s @%-4d %d colliding label pair(s), e.g. %r"
                      % (path.split("/")[-1], r["id"], width, r["n"], r["eg"]))
            for r in page.evaluate(END_LABEL):
                bad += 1
                print("UNDATED  %-26s %-12s @%-4d newest period %r has no label"
                      % (path.split("/")[-1], r["id"], width, r["want"]))
        for r in pg.evaluate(SPANS):
            if r["ok"]:
                acked += 1
                continue
            flat += 1
            print("FLATTENED %-25s %-12s %d of %d series under a fifth of "
                  "the axis: %s" % (path.split("/")[-1], r["id"], r["n"],
                                    r["of"], r["names"]))

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

print("\n%s" % ("no label overflows its chart or collides with its neighbour, every date axis labels its newest period, and every in-page link resolves"
                if not bad else "%d problem(s)" % bad))
sys.exit(1 if bad else 0)
