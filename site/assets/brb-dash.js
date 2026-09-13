/* BigRiceBowl dashboards — shared engine.
 *
 * Loads a bundle, reconstructs date axes, derives series, and renders panels.
 * Nothing here is specific to a dashboard: a page supplies a bundle URL and a
 * list of panels, and gets a rendered report. If a new dashboard needs a change
 * in this file, that is a defect in the engine rather than a special case.
 */
(function (global) {
  "use strict";

  const MN = ["Jan","Feb","Mar","Apr","May","Jun","Jul","Aug","Sep","Oct","Nov","Dec"];

  /* ---------- date axis ---------------------------------------------------
   * The exporter emits start+step only when it has VERIFIED the spacing is
   * regular, and an explicit dates array otherwise. Honour both; never assume.
   */
  function axis(s) {
    if (s.dates) return s.dates.slice();
    const out = [];
    const [y0, m0, d0] = s.start.split("-").map(Number);
    const n = s.values.length;
    if (s.step === "M" || s.step === "Q" || s.step === "A") {
      const k = { M: 1, Q: 3, A: 12 }[s.step];
      for (let i = 0; i < n; i++) {
        const m = m0 - 1 + i * k;
        const y = y0 + Math.floor(m / 12);
        out.push(`${y}-${String((m % 12) + 1).padStart(2, "0")}-${String(d0).padStart(2, "0")}`);
      }
    } else {
      const days = { D: 1, W: 7 }[s.step];
      const t0 = Date.UTC(y0, m0 - 1, d0);
      for (let i = 0; i < n; i++) {
        const d = new Date(t0 + i * days * 86400000);
        out.push(d.toISOString().slice(0, 10));
      }
    }
    return out;
  }

  const label = (iso, freq) => {
    const [y, m, d] = iso.split("-");
    if (freq === "W" || freq === "D") return `${+d} ${MN[+m - 1]} ${y.slice(2)}`;
    if (freq === "Q") return `Q${Math.floor((+m - 1) / 3) + 1} ${y.slice(2)}`;
    return `${MN[+m - 1]} ${y.slice(2)}`;
  };
  const sgn = (v, dp) => (v > 0 ? "+" : "") + (dp == null ? v : v.toFixed(dp));

  // The label interval a chart can afford, from the width it actually has and
  // the width its labels actually measure. `tick` is the page's choice for a
  // desktop cell and stays the floor; a narrower chart gets the smallest
  // multiple of it whose labels fit with a gap, so the cadence a reader
  // learned on a wide screen survives on a phone with every other label
  // dropped rather than every label overprinted. Measured with canvas
  // measureText in the axis font, after the webfonts are in -- a character
  // width guessed once is what trap 13 is about. hideOverlap on the axis
  // stays as the backstop.
  const labelInterval = (el, cats, freq, tick, gutter, size, font) => {
    // Counted back from the NEWEST period, not forward from the oldest. The
    // first version kept ECharts' left anchor, so the last label could sit up
    // to a spacing short of the end: on 10 September 2026 159 of 164 charts
    // left their newest period unlabelled, Weekly Claims Table 7 ran to
    // 29 August 2026 under a last label of 4 October 2025, and a current
    // table was reported as not updating. The newest period is the one a
    // reader looks for. Returned as ECharts' function form of `interval`.
    const n = cats.length;
    const base = tick == null ? 1 : tick + 1;   // categories from one label to the next
    const plot = el.clientWidth - gutter;
    let step = base;
    if (plot > 0 && n) {
      const c = labelInterval.ctx ||
        (labelInterval.ctx = document.createElement("canvas").getContext("2d"));
      c.font = `${size}px ${font}`;
      let w = 0;
      for (const v of cats) w = Math.max(w, c.measureText(label(v, freq)).width);
      // One and a half label widths, not one: the newest label is right-
      // aligned (alignMaxLabel), which moves it half a width towards its
      // neighbour, and where the two touched hideOverlap dropped the LATER
      // label -- the newest, the one this spacing exists to keep. It did on a
      // phone on Weekly Claims Table 9 and the PPI heatmap.
      const fit = Math.max(1, Math.floor(plot / (1.5 * w + 8)));
      const need = Math.ceil(n / fit);
      step = Math.max(base, Math.ceil(need / base) * base);
    } else if (tick == null) {
      return "auto";
    }
    return i => (n - 1 - i) % step === 0;
  };
  // Rendered width of a label in the axis font. The right-hand labels below
  // are placed from it rather than from a margin typed once.
  const textWidth = (text, size, font) => {
    const c = labelInterval.ctx ||
      (labelInterval.ctx = document.createElement("canvas").getContext("2d"));
    c.font = `${size}px ${font}`;
    return c.measureText(String(text)).width;
  };
  // The same question for a value axis, answered as an explicit tick step:
  // ECharts treats splitNumber as a hint and kept six labels on a phone
  // where four fit. The step is the smallest "nice" one (1, 2, 2.5, 5 x a
  // power of ten) that puts no more labels of `sample`'s measured width
  // across the plot than fit with a gap.
  const valueInterval = (el, gutter, sample, size, font, maxAbs) => {
    const plot = el.clientWidth - gutter;
    if (!(plot > 0) || !(maxAbs > 0)) return undefined;
    const c = labelInterval.ctx ||
      (labelInterval.ctx = document.createElement("canvas").getContext("2d"));
    c.font = `${size}px ${font}`;
    const fit = Math.max(2, Math.min(5, Math.floor(plot / (c.measureText(sample).width + 12))));
    const raw = maxAbs / fit, mag = Math.pow(10, Math.floor(Math.log10(raw)));
    for (const m of [1, 2, 2.5, 5, 10]) if (maxAbs / (m * mag) <= fit) return m * mag;
    return 10 * mag;
  };

  /* ---------- transforms --------------------------------------------------
   * Every one preserves nulls. A gap in the source (October 2025 in the
   * household survey) must stay a gap, never become a zero or an interpolation.
   */
  const T = {
    level: v => v.slice(),
    diff: (v, per) => { const n = per || 1;
      return v.map((x, i) => (i < n || x == null || v[i - n] == null
        ? null : +(x - v[i - n]).toFixed(3))); },
    yoy: (v, per) => v.map((x, i) => {
      const p = v[i - per];
      return (i < per || x == null || p == null || !p) ? null : +((x / p - 1) * 100).toFixed(3);
    }),
    ma: (v, w) => v.map((_, i) => {
      if (i < w - 1) return null;
      const win = v.slice(i - w + 1, i + 1);
      return win.some(x => x == null) ? null : +(win.reduce((a, b) => a + b, 0) / w).toFixed(3);
    }),
    // delta0 and index100 baseline on the first value of the WHOLE series, and
    // transforms run BEFORE the trailing window. On a panel with a window --
    // which is nearly all of them -- what you almost certainly want is the
    // series option `rebase`, which baselines inside the window instead. Both
    // of these have already produced a chart whose caption did not match it.
    delta0: v => { const b = v.find(x => x != null);
      return b == null ? v.map(() => null) : v.map(x => (x == null ? null : +(x - b).toFixed(3))); },
    index100: v => { const b = v.find(x => x != null);
      return !b ? v.map(() => null) : v.map(x => (x == null ? null : +(x / b * 100).toFixed(3))); },
  };

  function derive(series, spec) {
    let v = series.values.slice();
    const t = spec.transform;
    if (!t || t === "level") return v;
    if (t === "diff") return T.diff(v, spec.periods || 1);
    if (t === "yoy") return T.yoy(v, spec.periods || perYear(series.frequency));
    if (t === "ma") return T.ma(v, spec.window || 3);
    if (t === "delta0") return T.delta0(v);
    if (t === "index100") return T.index100(v);
    if (t === "diff_ma") return T.ma(T.diff(v, spec.periods || 1), spec.window || 3);
    throw new Error("unknown transform: " + t);
  }
  const perYear = f => ({ M: 12, Q: 4, W: 52, D: 365, A: 1 }[f] || 12);

  /* Trailing window. Applied after transforms, so a 3-month average at the
     left edge of the window is still computed from real prior data rather
     than starting null. Without a window a panel plots the whole history and
     1939-2026 payrolls make the recent years a flat line at the axis. */
  const tail = (arr, w) => (w && arr.length > w ? arr.slice(-w) : arr);

  /* Resolve one series reference to {series, cats, values}, honouring an
     optional `over` denominator. Aligned BY DATE rather than by index: two
     series in the same bundle can start in different years, and zipping them
     positionally would silently pair 2000 with 1948. */
  function resolve(ctx, sp) {
    const s = ctx.series(sp.id);
    const cats = axis(s);
    let values = derive(s, sp);
    if (sp.over) {
      // alignAsOf, not an exact date match. The denominator is frequently
      // coarser than the numerator -- insured unemployment is weekly and the
      // unemployment level it is divided by is monthly -- and an exact lookup
      // misses on every date, yielding a chart that draws nothing and reports
      // nothing wrong. Trap 6: align by date, and a coarser series means the
      // most recent value at or before this one. Where the dates do match this
      // is identical to what it replaced.
      const o = ctx.series(sp.over);
      const den = alignAsOf(cats, axis(o), o.values);
      values = cats.map((d, i) => {
        const n = values[i], q = den[i];
        return (n == null || q == null || !q) ? null : +(n / q).toFixed(4);
      });
    }
    // Last, after any transform and any `over`. Units differ by source --
    // claims arrive in persons, the unemployment level in thousands -- and a
    // ratio across that gap is wrong by a thousand while looking perfectly
    // healthy to every check. Trap 7.
    if (sp.scale != null)
      values = values.map(v => (v == null ? null : +(v * sp.scale).toFixed(6)));
    return { s, cats, values };
  }

  /* ---------- palette, read from CSS so the stylesheet stays authoritative -- */
  function palette() {
    const cs = getComputedStyle(document.documentElement);
    const g = n => cs.getPropertyValue(n).trim();
    return {
      panel: g("--panel"), ink: g("--ink"), ink2: g("--ink-2"), muted: g("--muted"),
      rule: g("--rule"), ruleHi: g("--rule-hi"), grid: g("--grid"),
      pos: g("--pos"), neg: g("--neg"), alt: g("--alt"), cursor: g("--cursor"),
      band: g("--band"),
      s1: g("--s1"), s2: g("--s2"), s3: g("--s3"), s4: g("--s4"),
      s5: g("--s5"), s6: g("--s6"),
      mono: g("--mono").replace(/["']/g, "") + ", ui-monospace, monospace",
      hm: [g("--hm-3"), g("--hm-1"), g("--hm-0"), g("--hm1"), g("--hm3")],
    };
  }

  const charts = [];
  function mount(el, option) {
    const c = echarts.init(el, null, { renderer: "svg" });
    c.setOption(option);
    charts.push(c);
    new ResizeObserver(() => c.resize()).observe(el);
    return c;
  }
  const base = P => ({
    animation: false,
    textStyle: { fontFamily: P.mono, color: P.muted, fontSize: 10 },
    tooltip: {
      backgroundColor: P.panel, borderColor: P.ruleHi, borderWidth: 1,
      textStyle: { color: P.ink, fontFamily: P.mono, fontSize: 11.5 },
      extraCssText: "border-radius:0;box-shadow:none",
    },
  });

  /* ---------- panel types ------------------------------------------------- */
  const PANELS = {};

  PANELS.line = (el, ctx, p) => {
    // PANELS.line supports axisFormat, as bars, contribution and stacked already
    // did. A monthly rate wants two decimals in the tooltip and none of that
    // noise repeated down the axis; without this the two were forced to agree.
    const P = ctx.P, fmt = fmtFor(p);
    const axisFmt = p.axisFormat ? fmtFor({ format: p.axisFormat }) : fmt;
    const first = ctx.series(p.series[0].id);
    const cats = tail(axis(first), p.window);
    const opt = Object.assign(base(P), {
      // The hline label sits past the line's end; a 14px margin left "50" 1px
      // over the edge on every breadth chart once clipcheck looked at the
      // right side. Room is measured from the label itself.
      grid: { left: p.left || 46, top: 12, bottom: 24,
              right: p.right || (p.hline != null
                ? Math.max(14, Math.ceil(textWidth(p.hlineLabel || String(p.hline), 9, P.mono)) + 12)
                : 14) },
      tooltip: Object.assign(base(P).tooltip, {
        trigger: "axis",
        formatter: ps => {
          let s = "<b>" + label(ps[0].axisValue, first.frequency) + "</b>";
          ps.forEach(x => { s += "<br>" + x.seriesName + " " +
            (x.data == null ? "not collected" : fmt(x.data)); });
          return s;
        },
      }),
      xAxis: {
        type: "category", data: cats, boundaryGap: false,
        // `tick` is the label interval the page chose for its desktop width.
        // hideOverlap drops whichever labels would still collide -- measured at
        // render, so a 430px phone gets fewer labels, not overprinted ones.
        // Every weekly and every ten-year axis collided on a phone before this;
        // clipcheck.py measures label overlap at both widths (9 September 2026).
        axisLabel: { color: P.muted, fontSize: 9.5, hideOverlap: true,
                     interval: labelInterval(el, cats, first.frequency, p.tick, (p.left || 46) + 14, 9.5, P.mono), alignMaxLabel: "right",
                     formatter: v => label(v, first.frequency) },
        axisLine: { lineStyle: { color: P.ruleHi } }, axisTick: { show: false },
      },
      yAxis: p.axis2
        ? [yAxis(P, axisFmt), Object.assign(yAxis(P, fmtFor({ format: p.format2 })), { splitLine: { show: false } })]
        : yAxis(P, axisFmt),
      series: p.series.map((sp, i) => {
        const r = resolve(ctx, sp);
        // Align every series onto the FIRST series' date axis by date, never by
        // index. Zipping positionally is correct only by luck — when the series
        // share a frequency and end on the same date. It breaks outright when a
        // panel mixes weekly claims with monthly payrolls, and would quietly
        // plot monthly values against weekly dates.
        let data = tail(alignAsOf(cats, r.cats, r.values), p.window);
        // Rebase AFTER the window. `delta0` subtracts the first value of the
        // whole series, which for a 1948 series is not the change this panel
        // claims to show. Series far apart in level -- participation 61,
        // employment-population 59, prime-age 80 -- only become comparable
        // when each starts the window at zero.
        if (sp.rebase) {
          const b = data.find(x => x != null);
          const idx = sp.rebase === "index";
          data = (b == null || (idx && !b)) ? data
               : data.map(x => (x == null ? null
                   : +(idx ? (x / b * 100) : (x - b)).toFixed(3)));
        }
        return {
          name: sp.label || r.s.title, type: "line", data,
          connectNulls: !!sp.connect, symbol: "none", yAxisIndex: sp.axis || 0,
          // Categorical slots, in the validated order. The previous ladder
          // ran slate -> gold -> oxblood: slate is a near-black against ink
          // at the same weight, and oxblood means "loss", not "series 3".
          // The full ladder, in the validated order. This stopped at three and
          // fell back to s4 for everything after, so a fourth, fifth and sixth
          // unnamed series would all have been the same colour.
          lineStyle: { color: P[sp.color || ["s1", "s2", "s3", "s4", "s5", "s6"][i] || "muted"],
                       width: sp.width || 1.6, type: sp.dash ? "dashed" : "solid" },
          markPoint: i === 0 ? endMarker(P, cats, data) : undefined,
          // A reference level the series is read against -- 50 on a diffusion
          // index, where more industries add than shed. Hairline and unlabelled
          // in the plot: it is a constant, not a value.
          markLine: (i === 0 && p.hline != null) ? {
            silent: true, symbol: "none",
            lineStyle: { color: P.ruleHi, width: 1, type: "dashed" },
            label: { show: true, position: "end", color: P.muted,
                     fontFamily: P.mono, fontSize: 9,
                     formatter: () => p.hlineLabel || String(p.hline) },
            data: [{ yAxis: p.hline }],
          } : undefined,
        };
      }),
    });
    mount(el, opt);
  };

  PANELS.bars = (el, ctx, p) => {
    const P = ctx.P, fmt = fmtFor(p);
    const s = ctx.series(p.series.id);
    const cats = tail(axis(s), p.window);
    const full = derive(s, p.series);
    const vals = tail(full, p.window);
    const extra = [];
    if (p.average) extra.push({
      name: `${p.average}-period average`, type: "line",
      data: tail(T.ma(full, p.average), p.window), symbol: "none",
      lineStyle: { color: P.muted, width: 1.3 }, z: 3,
    });
    // "As first reported" comes precomputed from the exporter, which reads both
    // periods at the SAME vintage. Deriving it here by differencing first_print
    // levels would subtract values from two different vintages and overstate
    // the swings badly - it gave -126k for July where the release says -23k.
    if (p.first_reported && s.first_reported_diff) {
      extra.push({ name: "as first reported", type: "line",
        data: tail(s.first_reported_diff, p.window), symbol: "none",
        connectNulls: false,
        lineStyle: { color: P.alt, width: 1.2, type: "dashed" }, z: 4 });
    } else if (p.first_reported) {
      console.warn("panel asked for first_reported but the bundle has no "
                   + "first_reported_diff for " + p.series.id);
    }
    // Overlay lines from other series in the bundle, aligned BY DATE onto the
    // bars' own axis. Used for a rolling mean that is itself a named derived
    // series, so the chart and any printed figure read the same definition.
    (p.overlay || []).forEach((sp, i) => {
      const r = resolve(ctx, sp);
      extra.push({
        name: sp.label || r.s.title, type: "line", symbol: "none",
        data: tail(alignAsOf(cats, r.cats, r.values), p.window),
        connectNulls: !!sp.connect,
        lineStyle: { color: P[sp.color || ["ink", "s2", "s3"][i] || "muted"],
                     width: sp.width || 1.4, type: sp.dash ? "dashed" : "solid" },
        z: 5,
      });
    });
    mount(el, Object.assign(base(P), {
      grid: { left: p.left || 46, right: 14, top: 14, bottom: 26 },
      tooltip: Object.assign(base(P).tooltip, {
        trigger: "axis", axisPointer: { type: "shadow" },
        formatter: ps => {
          let out = "<b>" + label(ps[0].axisValue, s.frequency) + "</b>";
          ps.forEach(x => { if (x.data != null) out += "<br>" + x.seriesName + " " + fmt(x.data); });
          return out;
        },
      }),
      xAxis: {
        type: "category", data: cats,
        axisLabel: { color: P.muted, fontSize: 9.5, hideOverlap: true,
                     interval: labelInterval(el, cats, s.frequency, p.tick, (p.left || 46) + 14, 9.5, P.mono), alignMaxLabel: "right",
                     formatter: v => label(v, s.frequency) },
        axisLine: { lineStyle: { color: P.ruleHi } }, axisTick: { show: false },
      },
      yAxis: yAxis(P, p.axisFormat ? fmtFor({ format: p.axisFormat }) : fmt),
      series: [{
        name: p.label || "Change", type: "bar", data: vals, barMaxWidth: p.width || 13,
        itemStyle: { color: pr => (vals[pr.dataIndex] < 0 ? P.neg : P.pos) },
        // A symmetric band for a published sampling interval. Paper-toned and
        // behind everything: it bounds what the figure can support and is not
        // itself a value, so it must never read as a series.
        markArea: p.band ? {
          silent: true, itemStyle: { color: P.band },
          data: [[{ yAxis: -p.band.value }, { yAxis: p.band.value }]],
          // No label: inside the plot it sits behind the bars and cannot be
          // read. The panel's note carries the interval instead.
          label: { show: false },
        } : undefined,
        // The cursor is ink and marks the latest period. It never encodes a
        // value, so it cannot be confused with the oxblood of a loss.
        markLine: {
          silent: true, symbol: "none", lineStyle: { color: P.cursor, width: 1 },
          label: { show: true, position: "end", color: P.cursor,
                   fontFamily: P.mono, fontSize: 9,
                   formatter: () => label(cats[cats.length - 1], s.frequency).split(" ")[0].toUpperCase() },
          data: [{ xAxis: cats.length - 1 }],
        },
      }].concat(extra),
    }));
  };

  PANELS.contribution = (el, ctx, p) => {
    const P = ctx.P;
    // The measure and its unit were both hard-wired: every input was
    // differenced one period and every label suffixed "k". That is a payroll
    // answer, not a general one -- a series that already IS a contribution
    // (a CPI weight times the item's own 12-month change, in percentage
    // points) came out differenced a second time and labelled as thousands of
    // jobs. Both are panel options now. The defaults are the old behaviour, so
    // the payroll page is unchanged; pass transform: "none" for values that
    // arrive ready-made from the exporter.
    const tf = p.transform === undefined ? "diff" : p.transform;
    const fmt = p.format ? fmtFor(p) : (v => sgn(v, 1) + "k");
    const axisFmt = p.axisFormat ? fmtFor({ format: p.axisFormat })
                                 : (v => sgn(v));
    const rows = p.series.map(sp => {
      const s = ctx.series(sp.id);
      // The LAST value, never the last non-null one: an item with no reading
      // for the latest month has no bar, rather than a bar quietly carrying
      // some earlier month's number alongside its neighbours' current ones.
      const v = tf === "none" ? s.values
                              : derive(s, { transform: tf, periods: p.periods });
      return [sp.label || shortName(s.title), v[v.length - 1]];
    }).filter(r => r[1] != null).sort((a, b) => a[1] - b[1]);
    mount(el, Object.assign(base(P), {
      grid: { left: p.left || 132, right: 46, top: 8, bottom: 24 },
      tooltip: Object.assign(base(P).tooltip, {
        trigger: "item", formatter: x => `<b>${x.name}</b><br>${fmt(x.value)}` }),
      xAxis: { type: "value",
        interval: valueInterval(el, (p.left || 132) + 46,
                                axisFmt(Math.max(...rows.map(r => Math.abs(r[1])))), 9.5, P.mono,
                                Math.max(...rows.map(r => Math.abs(r[1])))),
        axisLabel: { color: P.muted, fontSize: 9.5, formatter: axisFmt, hideOverlap: true },
        splitLine: { lineStyle: { color: P.grid } } },
      yAxis: { type: "category", data: rows.map(r => r[0]),
        axisLabel: { color: P.ink2, fontSize: 10, fontFamily: P.mono },
        axisLine: { lineStyle: { color: P.ruleHi } }, axisTick: { show: false } },
      series: [{
        type: "bar", data: rows.map(r => r[1]), barMaxWidth: 13,
        itemStyle: { color: x => (x.value < 0 ? P.neg : P.pos) },
        // ECharts takes a string here, not a callback: the callback was
        // ignored and every label fell back to "inside", printing muted
        // grey on a dark slate bar. "right" sits it just past the bar end,
        // on paper, for positive and negative alike.
        label: { show: true, position: "right",
                 formatter: x => fmt(x.value), color: P.muted,
                 fontFamily: P.mono, fontSize: 9.5 },
      }],
    }));
  };

  /* Contributions to an aggregate, stacked, with the aggregate itself drawn over
     them as a line. Stacking is only honest when the parts are a PARTITION of
     the whole -- which is why the four-way CPI split earns it and a list of
     twelve overlapping items does not. The line is the sum, so a reader can see
     at once whether the parts account for it: any daylight between the line and
     the top of the stack is the residual, visible rather than asserted.

     Segments are separated by a hairline of surface, per the mark spec, so
     adjacent categories never bleed into one another. */
  PANELS.stacked = (el, ctx, p) => {
    const P = ctx.P, fmt = fmtFor(p);
    const first = ctx.series(p.series[0].id);
    const cats = tail(axis(first), p.window);
    const SLOT = ["s1", "s2", "s3", "s4", "s5", "s6"];
    if (p.series.length > SLOT.length)
      console.warn("stacked: " + p.series.length + " series exceeds the "
                   + SLOT.length + "-slot categorical palette; fold the tail "
                   + "into an 'other' bucket rather than cycling hues");

    const bars = p.series.map((sp, i) => {
      const r = resolve(ctx, sp);
      return {
        name: sp.label || r.s.title, type: "bar", stack: "c",
        data: tail(alignAsOf(cats, r.cats, r.values), p.window),
        barMaxWidth: p.width || 13,
        itemStyle: { color: P[sp.color || SLOT[i] || "muted"],
                     borderColor: P.panel, borderWidth: 0.5 },
      };
    });

    // The aggregate, over the stack. Ink, because it is the total rather than
    // another category -- the categorical slots are reserved for the parts.
    const extra = [];
    if (p.total) {
      const r = resolve(ctx, p.total);
      extra.push({
        name: p.total.label || "Total", type: "line", symbol: "none",
        data: tail(alignAsOf(cats, r.cats, r.values), p.window),
        connectNulls: false, z: 6,
        // The series colour too, not only the line's: the tooltip swatch
        // reads it, and without it the total showed ECharts' default blue.
        color: P.ink,
        lineStyle: { color: P.ink, width: p.total.width || 1.8 },
      });
    }

    mount(el, Object.assign(base(P), {
      grid: { left: p.left || 46, right: p.right || 14, top: 12, bottom: 26 },
      tooltip: Object.assign(base(P).tooltip, {
        trigger: "axis", axisPointer: { type: "shadow" },
        formatter: ps => {
          let out = "<b>" + label(ps[0].axisValue, first.frequency) + "</b>";
          // A swatch in each series' own colour, so a row in the tooltip is
          // matched to its bar without going back to the legend: a square for
          // a stacked part, a short rule for the total line.
          const sw = x => x.seriesType === "line"
            ? `<span style="display:inline-block;width:12px;height:2px;background:${x.color};vertical-align:middle;margin-right:7px"></span>`
            : `<span style="display:inline-block;width:9px;height:9px;background:${x.color};vertical-align:-1px;margin-right:7px"></span>`;
          ps.forEach(x => { if (x.data != null)
            out += "<br>" + sw(x) + x.seriesName + " " + fmt(x.data); });
          return out;
        },
      }),
      xAxis: {
        type: "category", data: cats,
        axisLabel: { color: P.muted, fontSize: 9.5, hideOverlap: true,
                     interval: labelInterval(el, cats, first.frequency, p.tick, (p.left || 46) + 14, 9.5, P.mono), alignMaxLabel: "right",
                     formatter: v => label(v, first.frequency) },
        axisLine: { lineStyle: { color: P.ruleHi } }, axisTick: { show: false },
      },
      // scale: true lets the axis start wherever the data does, which is
      // right for a line and wrong for a stack -- a truncated baseline makes
      // every segment's height a lie about its share. Forcing it off keeps
      // zero on the axis; ECharts still spans both ways when parts go
      // negative, as CPI contributions do.
      yAxis: Object.assign(
        yAxis(P, p.axisFormat ? fmtFor({ format: p.axisFormat }) : fmt),
        { scale: false }),
      series: bars.concat(extra),
    }));
  };

  /* Two baskets, one row per category, values stated in the spec. The only
     panel here that does not read a series: a composition is a fact about a
     moment and has no history to plot. Bars are drawn from a common zero and
     the axis is forced to include it, because these are shares and a truncated
     baseline would make every length a lie about its size. */
  PANELS.compare = (el, ctx, p) => {
    const P = ctx.P, fmt = fmtFor(p);
    const items = p.items || [];
    const cats = items.map(i => i.label);
    const mk = (key, name, slot) => ({
      name, type: "bar", data: items.map(i => i[key]),
      barMaxWidth: p.width || 9, barGap: "10%",
      itemStyle: { color: P[slot] },
      label: { show: p.labels !== false, position: "right",
               formatter: x => fmt(x.value), color: P.muted,
               fontFamily: P.mono, fontSize: 9.5 },
    });
    mount(el, Object.assign(base(P), {
      grid: { left: p.left || 150, right: p.right || 54, top: 8, bottom: 24 },
      tooltip: Object.assign(base(P).tooltip, {
        trigger: "axis", axisPointer: { type: "shadow" },
        formatter: ps => "<b>" + ps[0].axisValue + "</b>" +
          ps.map(x => "<br>" + x.seriesName + " " + fmt(x.data)).join(""),
      }),
      xAxis: Object.assign(yAxis(P, fmt), { type: "value", scale: false,
        interval: valueInterval(el, (p.left || 150) + (p.right || 54),
                                fmt(Math.max(...items.map(i => Math.max(i.a, i.b)))), 9.5, P.mono,
                                Math.max(...items.map(i => Math.max(i.a, i.b)))) }),
      yAxis: { type: "category", data: cats, inverse: true,
        axisLabel: { color: P.ink2, fontSize: 10, fontFamily: P.mono },
        axisLine: { lineStyle: { color: P.ruleHi } }, axisTick: { show: false } },
      series: [mk("a", p.labelA || "A", p.colorA || "s1"),
               mk("b", p.labelB || "B", p.colorB || "s2")],
    }));
  };

  PANELS.heatmap = (el, ctx, p) => {
    const P = ctx.P;
    // As with PANELS.contribution: the transform and the unit were both
    // hard-wired to a one-month change in thousands, so the panel could draw a
    // payroll decomposition and nothing else. Values that already carry their
    // own meaning -- a CPI contribution in percentage points -- pass
    // transform: "none". Defaults are the previous behaviour.
    const tf = p.transform === undefined ? "diff" : p.transform;
    const fmt = p.format ? fmtFor(p) : (v => sgn(v, 1) + "k");
    const months = p.months || 24;
    const names = [], data = [];
    // The frequency comes from the series, not from an assumption. Taken from
    // the same series the date axis is taken from, so the two cannot disagree.
    let cats = null, freq = "M";
    p.series.forEach((sp, yi) => {
      const s = ctx.series(sp.id);
      const v = (tf === "none" ? s.values
                               : derive(s, { transform: tf, periods: p.periods }))
                .slice(-months);
      if (!cats) { cats = axis(s).slice(-months); freq = s.frequency || "M"; }
      // `share`: a series whose latest value is the row's share of the whole
      // (a relative importance), printed after the name in a fixed width so
      // the figures line up down the right edge of the labels.
      let nm = sp.label || shortName(s.title);
      if (sp.share) {
        let w = null;
        try { w = lastNonNull(ctx.series(sp.share).values); } catch (e) { w = null; }
        nm += "  " + (w == null ? "    –" : (w.toFixed(1) + "%").padStart(5));
      }
      names.push(nm);
      v.forEach((val, xi) => { if (val != null) data.push([xi, yi, val]); });
    });
    const cap = p.cap || 45;
    mount(el, Object.assign(base(P), {
      grid: { left: p.left || 132, right: 20, top: 8, bottom: 48 },
      tooltip: Object.assign(base(P).tooltip, {
        formatter: x => `<b>${names[x.data[1]]}</b><br>${label(cats[x.data[0]], freq)}  ${fmt(x.data[2])}` }),
      xAxis: { type: "category", data: cats, splitArea: { show: false },
        // `tick` like every other panel type. Hard-coded at 2 this collided
        // into unreadable overlap the moment a heatmap was put in a half-width
        // cell rather than across the page.
        axisLabel: { color: P.muted, fontSize: 9, hideOverlap: true,
                     interval: labelInterval(el, cats, freq, p.tick == null ? 2 : p.tick, (p.left || 132) + 20, 9, P.mono), alignMaxLabel: "right",
                     formatter: v => label(v, freq) },
        axisLine: { lineStyle: { color: P.ruleHi } }, axisTick: { show: false } },
      // Rows read top-down in the order the page lists them, the same order
      // as its key and its prose. ECharts puts category 0 at the BOTTOM, so
      // without `inverse` a 33-row table read upwards, and two panels had
      // been hand-reversed to compensate while the rest had not.
      // `em` on a series row: "top" (bold ink) or "sub" (bold series blue),
      // for the main-category rows of a hierarchy, so the structure reads
      // before the detail does.
      yAxis: { type: "category", data: names, inverse: true, splitArea: { show: false },
        axisLabel: { color: P.ink2, fontSize: 10, fontFamily: P.mono,
          formatter: (v, i) => {
            const em = p.series[i] && p.series[i].em;
            return em ? `{${em === "top" ? "top" : "sub"}|${v}}` : v;
          },
          rich: {
            top: { color: P.ink, fontWeight: 700, fontSize: 10, fontFamily: P.mono },
            sub: { color: P.s1, fontWeight: 700, fontSize: 10, fontFamily: P.mono },
          } },
        axisLine: { lineStyle: { color: P.ruleHi } }, axisTick: { show: false } },
      // The scale starts under the row labels, but not so far right that its
      // end text leaves the chart: on a phone "≥ +15%" was cut by 3px.
      visualMap: { min: -cap, max: cap, calculable: false, orient: "horizontal",
        left: Math.max(4, Math.min(p.left || 132, el.clientWidth - 8 - (96 + 2 * 10 + 10
          + (p.capText || [`≥ +${cap}k`, `≤ −${cap}k`]).reduce((w, t) => w + textWidth(t, 9, P.mono), 0)))),
        bottom: 2, itemWidth: 11, itemHeight: 96,
        textStyle: { color: P.muted, fontFamily: P.mono, fontSize: 9 },
        text: p.capText || [`≥ +${cap}k`, `≤ −${cap}k`], inRange: { color: P.hm } },
      series: [{ type: "heatmap", data,
        itemStyle: { borderColor: P.panel, borderWidth: 1 },
        emphasis: { itemStyle: { borderColor: P.ink, borderWidth: 1.5 } } }],
    }));
  };

  /* Two series against each other as a traced path — the Beveridge curve is
     the canonical case. Points are joined in time order and the most recent is
     marked in ink, so the shape shows regime change rather than level. */
  PANELS.scatter = (el, ctx, p) => {
    const P = ctx.P;
    const rx = resolve(ctx, p.x), ry = resolve(ctx, p.y);
    const byDate = new Map(ry.cats.map((d, i) => [d, ry.values[i]]));
    let pts = rx.cats.map((d, i) => [rx.values[i], byDate.get(d), d])
                     .filter(t => t[0] != null && t[1] != null);
    if (p.window) pts = pts.slice(-p.window);
    if (!pts.length) throw new Error("scatter: no overlapping observations");
    const last = pts[pts.length - 1];
    const fx = fmtFor({ format: p.formatX }), fy = fmtFor({ format: p.formatY });
    mount(el, Object.assign(base(P), {
      grid: { left: p.left || 48, right: 20, top: 14, bottom: 32 },
      tooltip: Object.assign(base(P).tooltip, {
        trigger: "item",
        formatter: o => `<b>${label(o.data[2], "M")}</b><br>` +
                        `${p.labelX} ${fx(o.data[0])}<br>${p.labelY} ${fy(o.data[1])}` }),
      xAxis: { type: "value", scale: true, name: p.labelX, nameLocation: "middle",
        nameGap: 20, nameTextStyle: { color: P.muted, fontSize: 9.5, fontFamily: P.mono },
        axisLabel: { color: P.muted, fontSize: 9.5, formatter: fx },
        splitLine: { lineStyle: { color: P.grid } } },
      yAxis: { type: "value", scale: true, name: p.labelY, nameLocation: "middle",
        nameGap: 34, nameTextStyle: { color: P.muted, fontSize: 9.5, fontFamily: P.mono },
        axisLabel: { color: P.muted, fontSize: 9.5, formatter: fy },
        splitLine: { lineStyle: { color: P.grid } } },
      series: [
        { type: "line", data: pts, symbol: "circle", symbolSize: 3.5, showSymbol: true,
          lineStyle: { color: P.pos, width: 1, opacity: 0.55 },
          itemStyle: { color: P.pos, opacity: 0.55 } },
        // A plain scatter, not effectScatter: the ripple needs animation, which
        // this kit disables, and it draws nothing at all under the SVG renderer.
        { type: "scatter", data: [last], symbolSize: 8, silent: true,
          itemStyle: { color: P.ink },
          label: { show: true, position: "right", formatter: () => label(last[2], "M"),
                   color: P.ink, fontFamily: P.mono, fontSize: 9.5 } },
      ],
    }));
  };

  /* Align a series onto another axis by "most recent value at or before this
     date". For two series of the same frequency this is exact matching. For a
     coarser series on a finer axis (monthly payrolls against weekly claims) it
     forward-fills, which is what a reader expects — exact matching found only
     8 of 260 weekly dates and drew a near-empty line.

     A published null survives: the lookup lands on the observation itself, so
     October 2025 in the household survey stays a gap rather than being filled
     with September's value. */
  function alignAsOf(axisDates, srcDates, srcValues) {
    const out = new Array(axisDates.length).fill(null);
    let j = -1;
    for (let i = 0; i < axisDates.length; i++) {
      while (j + 1 < srcDates.length && srcDates[j + 1] <= axisDates[i]) j++;
      out[i] = j >= 0 ? srcValues[j] : null;
    }
    return out;
  }

  /* ---------- helpers ----------------------------------------------------- */
  const yAxis = (P, fmt) => ({
    type: "value", scale: true,
    axisLabel: { color: P.muted, fontSize: 9.5, formatter: fmt, hideOverlap: true },
    splitLine: { lineStyle: { color: P.grid } },
  });
  const endMarker = (P, cats, vals) => {
    for (let i = vals.length - 1; i >= 0; i--) if (vals[i] != null)
      return { symbol: "circle", symbolSize: 5, silent: true, itemStyle: { color: P.ink },
               label: { show: false }, data: [{ coord: [cats[i], vals[i]] }] };
    return undefined;
  };
  function fmtFor(p) {
    const f = (p && p.format) || "num";
    if (f === "pct") return v => v.toFixed(1) + "%";
    // A signed rate, as a release prints a monthly change: "+0.4%".
    if (f === "spct") return v => sgn(v, 1) + "%";
    if (f === "pct2") return v => v.toFixed(2) + "%";
    if (f === "pt") return v => sgn(v, 1);
    // Index points, where the whole quantity is a hundredth or two: one
    // decimal rounds every CPI revision to +0.0 and says nothing.
    if (f === "pt2") return v => sgn(v, 2);
    // Percentage points of an aggregate, for a contribution: two
    // decimals because the whole point is that the parts add up.
    if (f === "pp") return v => sgn(v, 2) + " pp";
    if (f === "signed") return v => (v > 0 ? "+" : v < 0 ? "−" : "") +
      Math.abs(Math.round(v) * 1000).toLocaleString("en-GB");
    if (f === "k") return v => v.toFixed(0) + "k";
    if (f === "hours") return v => v.toFixed(1);
    if (f === "weeks") return v => v.toFixed(0) + "w";
    if (f === "ratio") return v => v.toFixed(2);
    // Units differ by source and it matters: JOLTS levels arrive in thousands
    // (7271 = 7.27m) while weekly claims arrive in persons (203000 = 203k).
    if (f === "millions") return v => (v / 1000).toFixed(2) + "m";   // input: thousands
    if (f === "k_units") return v => (v / 1000).toFixed(0) + "k";    // input: persons
    if (f === "m_units") return v => (v / 1e6).toFixed(2) + "m";     // input: persons
    if (f === "count") return v => Math.round(v).toLocaleString("en-GB");
    // Signed, and in the units given. "signed" above multiplies by 1000 because
    // it takes thousands; claims arrive in persons and must not be rescaled.
    if (f === "signed_count") return v => (v > 0 ? "+" : v < 0 ? "\u2212" : "") +
      Math.abs(Math.round(v)).toLocaleString("en-GB");
    if (f === "num") return v => String(Math.round(v * 100) / 100);
    // No silent default. `derive` throws on an unknown transform and this must
    // behave the same way: a format name that does not exist here used to fall
    // through to the line above and render a chart with the wrong decimals,
    // reporting nothing (trap 46). Every panel call is wrapped in try/catch, so
    // this breaks one panel loudly instead of mis-formatting all of it quietly.
    throw new Error("unknown format: " + f);
  }
  const shortName = t => t.replace(/^All Employees,\s*/, "")
                          .replace(/Private Education and Health Services/, "Educ & health")
                          .replace(/Professional and Business Services/, "Prof & business")
                          .replace(/Transportation and Warehousing/, "Transport/whse")
                          .replace(/Leisure and Hospitality/, "Leisure/hosp")
                          .replace(/Mining and Logging/, "Mining/logging")
                          .replace(/Financial Activities/, "Financial")
                          .replace(/(Wholesale|Retail) Trade/, "$1");

  /* ---------- sparklines, plain SVG --------------------------------------- */
  function spark(el, values, P) {
    const v = values.filter(x => x != null);
    if (!v.length) return;
    const lo = Math.min(...v), hi = Math.max(...v);
    const mean = v.reduce((a, b) => a + b, 0) / v.length;
    // Floor the range at 2% of the level, so a near-flat series (average weekly
    // hours moves 34.2-34.3) reads flat instead of amplifying rounding into
    // apparent volatility.
    const rng = Math.max(hi - lo, Math.abs(mean) * 0.02) || 1;
    const mid = (lo + hi) / 2, mn = mid - rng / 2;
    const W = 100, H = 22, n = values.length;
    let d = "", pen = false;
    values.forEach((y, i) => {
      if (y == null) { pen = false; return; }
      const X = (i / (n - 1)) * W, Y = H - ((y - mn) / rng) * (H - 3) - 1.5;
      d += (pen ? "L" : "M") + X.toFixed(2) + " " + Y.toFixed(2) + " "; pen = true;
    });
    const last = values[values.length - 1];
    const ly = last == null ? null : H - ((last - mn) / rng) * (H - 3) - 1.5;
    const zero = (mn < 0 && mn + rng > 0) ? H - ((0 - mn) / rng) * (H - 3) - 1.5 : null;
    el.innerHTML =
      `<svg viewBox="0 0 ${W} ${H}" preserveAspectRatio="none" aria-hidden="true">` +
      (zero !== null ? `<line x1="0" y1="${zero.toFixed(2)}" x2="${W}" y2="${zero.toFixed(2)}" stroke="${P.rule}" stroke-width="1" vector-effect="non-scaling-stroke"/>` : "") +
      `<path d="${d.trim()}" fill="none" stroke="${P.muted}" stroke-width="1.2" vector-effect="non-scaling-stroke" stroke-linejoin="round"/>` +
      (ly !== null ? `<circle cx="${W}" cy="${ly.toFixed(2)}" r="2" fill="${P.ink}"/>` : "") +
      "</svg>";
  }

  /* ---------- summary figures --------------------------------------------- */
  function summary(host, ctx, figs) {
    host.innerHTML = figs.map((f, i) => {
      const r = resolve(ctx, { id: f.series, over: f.over, transform: f.transform,
                               window: f.maWindow, periods: f.periods });
      const s = r.s, v = r.values;
      const last = lastNonNull(v);
      const fmt = fmtFor(f);
      const cls = f.signed && last != null && last < 0 ? " dn" : "";
      return `<div class="s"><div class="lb"><span>${f.label}</span>` +
             `<i>${f.source || s.release.split(".").pop().toUpperCase()}</i></div>` +
             `<div class="vl${cls}">${last == null ? "&mdash;" : fmt(last)}</div>` +
             `<div class="spark" id="sp${i}"></div>` +
             `<div class="dl"><span>${f.note1 || ""}</span><span>${f.note2 || ""}</span></div></div>`;
    }).join("");
    figs.forEach((f, i) => {
      const r = resolve(ctx, { id: f.series, over: f.over, transform: f.transform,
                               window: f.maWindow, periods: f.periods });
      spark(document.getElementById("sp" + i), r.values.slice(-(f.spark || 24)), ctx.P);
    });
  }
  const lastNonNull = v => { for (let i = v.length - 1; i >= 0; i--) if (v[i] != null) return v[i]; return null; };

  /* ---------- per-table date ----------------------------------------------
   * Every table carries the newest period it actually draws, beside its
   * units. It is read from the series the table's panels name, never copied
   * from the page stamp, because a table fed by a slower release -- the ECI
   * on the payroll page -- is older than the page it sits on. A table whose
   * newest period ends before the page's own reference period is marked
   * .lag, so old data never passes for new. Generic: it walks each panel's
   * config for any string naming a bundle series, whatever the panel type
   * calls the field, so a new panel type is dated without a line here.
   */
  const MLONG = ["January","February","March","April","May","June","July",
                 "August","September","October","November","December"];
  const FREQ_OF_CADENCE = { weekly: "W", quarterly: "Q", annual: "A", daily: "D" };
  const UNIT_OF_FREQ = { M: "month", Q: "quarter", W: "week", D: "day", A: "year" };
  const periodEnd = (iso, freq) => {
    if (freq === "W" || freq === "D") return iso;
    const [y, m] = iso.split("-").map(Number);
    const first = freq === "Q" ? Math.floor((m - 1) / 3) * 3 : freq === "A" ? 0 : m - 1;
    const len = freq === "Q" ? 3 : freq === "A" ? 12 : 1;
    return new Date(Date.UTC(y, first + len, 0)).toISOString().slice(0, 10);
  };
  const periodLong = (iso, freq) => {
    const [y, m] = iso.split("-").map(Number);
    if (freq === "W") return `the week ending ${fmtDate(iso)}`;
    if (freq === "D") return fmtDate(iso);
    if (freq === "Q") return `${y} Q${Math.floor((m - 1) / 3) + 1}`;
    if (freq === "A") return String(y);
    return `${MLONG[m - 1]} ${y}`;
  };
  function seriesIn(ctx, p) {
    const ids = new Set();
    const walk = v => {
      if (typeof v === "string") { if (ctx.bundle.series[v]) ids.add(v); }
      else if (Array.isArray(v)) v.forEach(walk);
      else if (v && typeof v === "object") Object.values(v).forEach(walk);
    };
    walk(p);
    return [...ids];
  }
  function tableStamps(ctx, panels) {
    const B = ctx.bundle, page = B.releases[B.release];
    const pf = page ? (FREQ_OF_CADENCE[page.cadence] || "M") : null;
    const pageEnd = page ? periodEnd(page.ref_period, pf) : null;
    // Newest period per table AND per frequency. Taking only the newest
    // overall let a monthly series hide a quarterly one in the same chart:
    // the payroll page's ECI table read "Aug 26" while its ECI line ended in
    // June. A mixed table shows each frequency's period, each dated on its own.
    const newest = new Map();              // .t -> Map(freq -> candidate)
    const keep = (t, c) => {
      if (!newest.has(t)) newest.set(t, new Map());
      const byF = newest.get(t), cur = byF.get(c.freq);
      if (!cur || c.end > cur.end) byF.set(c.freq, c);
    };
    panels.forEach(p => {
      const el = document.getElementById(p.el);
      const t = el && el.closest(".t");
      if (!t) return;
      seriesIn(ctx, p).forEach(id => {
        const s = B.series[id], cats = axis(s), v = s.values;
        for (let i = v.length - 1; i >= 0; i--) if (v[i] != null) {
          const freq = s.frequency || s.step || "M";
          keep(t, { end: periodEnd(cats[i], freq), iso: cats[i], freq, s });
          break;
        }
      });
    });
    // A numbered table with no chart of its own heads the unnumbered small
    // multiples beneath it (JOLTS Table 9), so it takes their newest period.
    let head = null;
    document.querySelectorAll("main .t").forEach(t => {
      if (t.querySelector(".th .n")) head = t.querySelector(".chart") ? null : t;
      else if (head && newest.has(t)) newest.get(t).forEach(c => keep(head, c));
    });
    const ORDER = { D: 0, W: 1, M: 2, Q: 3, A: 4 };
    newest.forEach((byF, t) => {
      const th = t.querySelector(".th");
      // `tdate`, not `stamp`: .stamp is the masthead's release line, a flex
      // row in capitals, and a table date wearing it inherited both.
      if (!th || th.querySelector(".tdate")) return;
      const parts = [...byF.values()].sort((a, b) => (ORDER[a.freq] ?? 9) - (ORDER[b.freq] ?? 9));
      const tags = [], lines = [];
      let anyLag = false;
      parts.forEach(c => {
        const lag = pageEnd != null && c.end < pageEnd;
        anyLag = anyLag || lag;
        const rel = B.releases[c.s.release];
        const tag = c.freq === "W" ? "Wk " + label(c.iso, "W") : label(c.iso, c.freq);
        tags.push(`<span class="${lag ? "old" : "new"}">${tag}</span>`);
        lines.push(`<b>${periodLong(c.iso, c.freq)}</b> is the newest ${UNIT_OF_FREQ[c.freq] || "period"} drawn` +
          (rel ? `: ${rel.name}${rel.released_at ? `, released ${fmtDate(rel.released_at)}` : ""}` : "") + ".");
      });
      if (anyLag) lines.push(`Oxblood is older than the page itself, which runs to ${periodLong(page.ref_period, pf)}.`);
      const sp = document.createElement("span");
      sp.className = "tdate" + (anyLag ? " lag" : "") + (th.querySelector(".u") ? "" : " solo");
      sp.tabIndex = 0;
      sp.innerHTML = tags.join(`<i aria-hidden="true"> &middot; </i>`) +
                     `<span class="pop" role="tooltip">${lines.join("<br>")}</span>`;
      th.appendChild(sp);
    });
  }

  // A table's note, under its chart, becomes a list of dash points, one per
  // sentence (William's choice, 13 Sept 2026, over numbers: the sentences are
  // one explanation, not a sequence). On a full-width table the points flow
  // across two columns, and a point never breaks across them, so no sentence
  // is ever cut -- the fault in both the CSS-column note and the split-at-
  // the-middle one before this. Sentences are found in the note's HTML
  // outside any tag, so bold and links survive; a full stop counts only when
  // whitespace and a capital (or opening tag, quote, bracket or digit)
  // follow, never after an abbreviation the notes use. A sentence under 50
  // characters joins the next (the last joins the one before), because
  // "The same construction on core." read abrupt as a point of its own. A
  // short closing "Analyst-derived." or "Source: ..." becomes a tag under the
  // list rather than a point. The authored HTML keeps its paragraph; this is
  // presentation only.
  const NOTE_ABBR = /(?:\bs\.a|\bn\.s\.a|\bU\.S|\be\.g|\bi\.e|\bvs|\bNo|\bJan|\bFeb|\bAug|\bSept?|\bOct|\bNov|\bDec|\bSt|\bMr|\bDr)$/;
  const plainOf = h => h.replace(/<[^>]+>/g, "").replace(/&[a-z#0-9]+;/gi, "x").trim();
  function sentencesOf(src) {
    const out = [];
    let inTag = false, start = 0, text = "";
    for (let i = 0; i < src.length; i++) {
      const ch = src[i];
      if (ch === "<") { inTag = true; continue; }
      if (ch === ">") { inTag = false; continue; }
      if (inTag) continue;
      if (ch === "&") {
        const j = src.indexOf(";", i);
        if (j > i && j - i < 9) { i = j; text += "x"; continue; }
      }
      text += ch;
      if (!".!?".includes(ch)) continue;
      let k = i + 1;
      for (let m; (m = src.slice(k).match(/^(<\/(b|em|i|strong|a)>|&rdquo;|”|\))/)); ) k += m[0].length;
      const rest = src.slice(k);
      if (!/^\s+/.test(rest) || NOTE_ABBR.test(text.slice(0, -1))) continue;
      if (/^\s+(<[^\/][^>]*>)*[A-Z“"(&0-9]/.test(rest)) {
        out.push(src.slice(start, k).trim()); start = k; i = k - 1;
      }
    }
    out.push(src.slice(start).trim());
    return out.filter(Boolean);
  }
  function pointNotes() {
    document.querySelectorAll("main .t > .chart ~ .note").forEach(n => {
      let parts = sentencesOf(n.innerHTML);
      const tags = [];
      while (parts.length > 1) {
        const last = plainOf(parts[parts.length - 1]);
        if (!/^(Analyst-derived|Source:)/i.test(last) || last.length > 60) break;
        tags.unshift(last.replace(/\.$/, ""));
        parts.pop();
      }
      const joined = [];
      parts.forEach(p => {
        const prev = joined[joined.length - 1];
        if (prev != null && plainOf(prev).length < 50) joined[joined.length - 1] = prev + " " + p;
        else joined.push(p);
      });
      if (joined.length > 1 && plainOf(joined[joined.length - 1]).length < 50)
        joined[joined.length - 2] += " " + joined.pop();
      const ul = document.createElement("ul");
      ul.className = "pts";
      ul.innerHTML = joined.map(p => `<li>${p}</li>`).join("");
      n.replaceWith(ul);
      if (tags.length) {
        const tg = document.createElement("p");
        tg.className = "pts-tag";
        tg.textContent = tags.join(" · ");
        ul.after(tg);
      }
    });
  }

  // Mark the table being read in the rail's contents list, and keep that
  // entry inside the rail's own scroll -- never by scrolling the page, which
  // scrollIntoView would do. The current table is the last one whose top has
  // passed a line 120px below the top of the window. Throttled to a frame.
  function railSpy() {
    const rail = document.querySelector(".rail");
    const links = [...document.querySelectorAll('.rail .inpage a[href^="#"]')];
    const pairs = links.map(a => [a, document.getElementById(a.getAttribute("href").slice(1))])
                       .filter(([, t]) => t);
    if (!rail || !pairs.length) return;
    let cur = null, queued = false;
    const update = () => {
      queued = false;
      let pick = pairs[0][0];
      for (const [a, t] of pairs) if (t.getBoundingClientRect().top <= 120) pick = a;
      if (pick === cur) return;
      if (cur) cur.classList.remove("here");
      pick.classList.add("here");
      cur = pick;
      if (rail.scrollHeight > rail.clientHeight) {
        const r = rail.getBoundingClientRect(), l = pick.getBoundingClientRect();
        if (l.top < r.top + 60 || l.bottom > r.bottom - 60)
          rail.scrollTop += (l.top - r.top) - rail.clientHeight / 2;
      }
    };
    const later = () => { if (!queued) { queued = true; requestAnimationFrame(update); } };
    addEventListener("scroll", later, { passive: true });
    addEventListener("resize", update);
    // A jump to a contents link did not reliably raise a scroll event in
    // testing, which left the highlight on the entry before the jump; the
    // hash change and the click cover it.
    addEventListener("hashchange", () => requestAnimationFrame(update));
    links.forEach(a => a.addEventListener("click", () => setTimeout(update, 60)));
    update();
  }

  // Two tables side by side are compared by eye, so their charts must start
  // at the same height. Everything above a chart -- heading, gist, legend --
  // takes the height of the taller one in its row, because any of the three
  // can wrap: a long title pushes the date onto a second heading line, and
  // a legend of three long names takes two. Aligning the gists alone left
  // payroll Tables 27 and 28 a heading line apart. Skipped once the row has
  // collapsed to one column.
  function alignGists() {
    document.querySelectorAll("main .row:not(.one)").forEach(row => {
      const cells = [...row.querySelectorAll(":scope > .t")];
      const single = getComputedStyle(row).gridTemplateColumns.split(" ").length < 2;
      [".th", ".gist", ".key"].forEach(sel => {
        const els = cells.map(t => t.querySelector(":scope > " + sel)).filter(Boolean);
        els.forEach(x => { x.style.minHeight = ""; });
        if (single || els.length < 2) return;
        const h = Math.max(...els.map(x => x.offsetHeight));
        els.forEach(x => { x.style.minHeight = h + "px"; });
      });
    });
  }

  /* ---------- forecast record ---------------------------------------------
   * A page may carry a forecasts.json beside it: calls made BEFORE a release,
   * each dated, each naming the series and transform it is a call on. The
   * engine scores every call against the bundle and renders the latest one
   * with its reasons under the masthead. Generic: nothing here knows what a
   * PPI is. The record is authored; the score never is.
   *
   * The actual is the figure AS FIRST PRINTED wherever the bundle carries it
   * (first_reported_pct / first_reported_yoy, exported for series the spec
   * names), because a call made the day before a release is a call on what
   * that release printed, not on the level after three revisions. Where the
   * bundle has no first print the latest vintage is used and the basis says
   * so. Compared at the precision the release prints, one decimal, since a
   * call of +0.4 against a print of +0.4 is a hit whatever the third decimal
   * of the index did.
   */
  function scoreForecasts(ctx, doc) {
    const recs = (doc.forecasts || []).slice().sort((a, b) => a.for < b.for ? -1 : 1);
    return recs.map(rec => {
      const items = (rec.items || []).map(it => {
        let s = null;
        try { s = ctx.series(it.series); } catch (e) { s = null; }
        let actual = null, basis = null;
        if (s) {
          const i = axis(s).indexOf(rec.for);
          const per = it.periods || 1;
          const key = per === 1 ? "first_reported_pct" : "first_reported_yoy";
          if (i >= 0) {
            if (s[key] && s[key][i] != null) { actual = s[key][i]; basis = "first print"; }
            else {
              const v = derive(s, { transform: it.transform || "yoy", periods: per });
              if (v[i] != null) { actual = v[i]; basis = "latest vintage"; }
            }
          }
        }
        const printed = actual == null ? null : Math.round(actual * 10) / 10;
        // Scored at the printed precision, but the unrounded figure travels
        // with it: a +0.35 called +0.3 is a coin flip, not a miss, and only
        // the second decimal says so.
        return { it, actual, printed, basis,
                 err: printed == null ? null : +(printed - it.value).toFixed(2),
                 errRaw: actual == null ? null : +(actual - it.value).toFixed(3) };
      });
      return { rec, items };
    });
  }

  function forecastBlock(host, ctx, scored, doc) {
    if (!host) return;
    if (!scored.length) { host.innerHTML = `<p class="fc-empty">No forecast recorded.</p>`; return; }
    const MFULL = ["January","February","March","April","May","June","July",
                   "August","September","October","November","December"];
    const period = iso => { const [y, m] = iso.split("-"); return `${MFULL[+m - 1]} ${y}`; };
    const cur = scored[scored.length - 1], rec = cur.rec;
    const made = new Date(rec.made + "T00:00:00Z");
    const due = new Date(rec.release_at.length === 10 ? rec.release_at + "T00:00:00Z" : rec.release_at);
    const lead = Math.round((Date.UTC(due.getUTCFullYear(), due.getUTCMonth(), due.getUTCDate()) - made.getTime()) / 86400000);
    const leadText = lead > 0 ? `${lead} day${lead === 1 ? "" : "s"} before release`
                   : `<span class="late">made ${-lead} day${lead === -1 ? "" : "s"} AFTER release</span>`;
    const esc = t => String(t).replace(/&/g, "&amp;").replace(/</g, "&lt;");
    // The unrounded print carries a sign only where the call does: +0.29 for
    // a monthly change, 3.40 for a twelve-month rate.
    const rawOf = x => (x.it.format || "spct") === "spct" ? sgn(x.actual, 2) : x.actual.toFixed(2);
    // Header (William, 13 Sept 2026): the data period once, then the two
    // dates the comparison rests on -- when the call was made, and when the
    // actual was released, as first printed, which is what the call is scored
    // on. The author moved from here into the call note below.
    const relInfo = ctx.bundle.releases[doc.release] || ctx.bundle.releases[ctx.bundle.release];
    const anyPrint = cur.items.some(x => x.printed != null);
    const dayMonth = iso => { const d = new Date(iso.length === 10 ? iso + "T00:00:00Z" : iso); return `${d.getUTCDate()} ${MN[d.getUTCMonth()]}`; };
    let h = `<div class="fc-h"><span><b>Forecast</b> &middot; ${period(rec.for)} data</span>` +
            `<span class="d-call">Called <b>${fmtDate(rec.made)}</b> &middot; ${leadText}</span>` +
            `<span class="d-act">${anyPrint ? "Actual released" : "Actual due"} <b>${fmtDate(rec.release_at)}</b>` +
            `${anyPrint ? " &middot; first print" : ""}${relInfo ? ` &middot; ${esc(relInfo.name)}` : ""}</span></div>`;
    // Each figure: the call and the actual side by side, the call in ink and
    // the actual in the series blue -- the same colours as the call note and
    // the comment on the release below, with red kept for grading (a miss).
    // Beneath, one fact to a line: consensus, the unrounded print, the error.
    h += `<div class="fc-figs">` + cur.items.map(x => {
      const it = x.it, fmt = fmtFor({ format: it.format || "spct" });
      const act = x.printed == null
        // "Due", not "Actual · due": five figures across a PPI row leave
        // each about 210px, and the longer label ran into the next figure.
        ? `<div class="fc-v act pend"><span class="k">Due &middot; ${dayMonth(rec.release_at)}</span><span class="n">&mdash;</span></div>`
        : `<div class="fc-v act"><span class="k">Actual &middot; ${dayMonth(rec.release_at)}</span><span class="n">${fmt(x.printed)}</span></div>`;
      const dl = [["Consensus", it.consensus == null ? `<span class="na">none</span>` : fmt(it.consensus)]];
      if (x.printed != null) {
        dl.push(["Unrounded", `<span class="uv">${rawOf(x)}</span>`]);
        dl.push(["Error", `<span class="${Math.abs(x.err) <= 0.1 ? "hit" : "miss"}">${sgn(x.err, 1)}</span>` +
                          (x.basis === "latest vintage" ? `<span class="raw">latest vintage</span>` : "")]);
      }
      return `<div class="fc-fig"><div class="lb">${esc(it.label)}${it.note ? ` <i>${esc(it.note)}</i>` : ""}</div>` +
             `<div class="fc-vs"><div class="fc-v call"><span class="k">Call &middot; ${dayMonth(rec.made)}</span>` +
             `<span class="n">${fmt(it.value)}</span></div>${act}</div>` +
             `<dl class="dl">${dl.map(([k, v]) => `<dt>${k}</dt><dd>${v}</dd>`).join("")}</dl></div>`;
    }).join("") + `</div>`;
    // The call and its review, side by side (William, 13 Sept 2026): what was
    // said before the release on the left, how it went on the right, so each
    // reason can be read against its grade without scrolling between them.
    // Top-aligned, not row-matched -- the review is organised by what moved,
    // not reason by reason. Before the release the right column is a dashed
    // placeholder naming when the review is due, so the pairing is visible
    // from the day the call is made. The COMMENT on the release is about the
    // data, not the call, so it sits apart underneath, full width. Each note
    // keeps its own colour and its own date: a sentence grading yesterday's
    // call is never read as a sentence about today's data.
    const list = items => `<ol>${items.map(t => `<li>${t}</li>`).join("")}</ol>`;
    const hasNote = n => n && n.text && n.text.length;
    if (rec.reasons && rec.reasons.length) {
      const call = `<section class="fc-call"><h4>The call</h4>` +
        `<div class="meta">${period(rec.for)} data &middot; made ${fmtDate(rec.made)}${doc.author ? ` by ${esc(doc.author)}` : ""}</div>${list(rec.reasons)}</section>`;
      const review = hasNote(rec.review)
        ? `<section class="fc-post-review"><h4>Review of the call</h4>` +
          `<div class="meta">against the ${fmtDate(rec.release_at)} print &middot; written ${fmtDate(rec.review.dated)}</div>` +
          `${list(rec.review.text)}</section>`
        : `<section class="fc-post-review pending"><h4>Review of the call</h4>` +
          `<div class="meta">due after the ${fmtDate(rec.release_at)} release</div>` +
          `<p class="wait">Written once the print is in: each part of the call graded against what the release showed.</p></section>`;
      h += `<div class="fc-pair">${call}${review}</div>`;
    }
    if (hasNote(rec.comment))
      h += `<div class="fc-post"><section class="fc-post-comment"><h4>Comment on the release</h4>` +
           `<div class="meta">${period(rec.for)} data &middot; released ${fmtDate(rec.release_at)} &middot; written ${fmtDate(rec.comment.dated)}</div>` +
           `${list(rec.comment.text)}</section></div>`;
    // Inputs as a two-column table and sources as a list, side by side: a
    // run-on line of label-value pairs gave the eye nothing to hold on to.
    const notes = [];
    if (rec.inputs && rec.inputs.length)
      notes.push(`<div class="fc-in"><h4>Inputs</h4><table>` +
        rec.inputs.map(i => `<tr><th>${esc(i.label)}</th><td>${esc(i.value)}</td></tr>`).join("") + `</table></div>`);
    if (rec.sources && rec.sources.length)
      notes.push(`<div class="fc-src"><h4>Sources</h4><ol>` +
        rec.sources.map(s_ => `<li><a href="${esc(s_.url)}">${esc(s_.label)}</a></li>`).join("") + `</ol></div>`);
    if (notes.length) h += `<div class="fc-notes">${notes.join("")}</div>`;
    // The record: every call so far, newest first. Measures are grouped by
    // horizon, because a label alone ("All items") names two different calls;
    // each measure gets call, print and error columns, and the running score
    // sits in the footer under the error it summarises.
    const keys = [], itemOf = {};
    scored.forEach(r => r.items.forEach(x => { if (!keys.includes(x.it.key)) { keys.push(x.it.key); itemOf[x.it.key] = x.it; } }));
    const horizon = p => p === 1 ? "Month on month" : p === 12 ? "Year over year" : `${p}-month change`;
    const groups = [];
    keys.forEach(k => {
      const p = itemOf[k].periods || 1, g = groups[groups.length - 1];
      if (g && g.p === p) g.n++; else groups.push({ p, n: 1 });
    });
    // Two calls on one measure at one horizon (PPI's s.a. and n.s.a. twelve-
    // month rates) differ only in their note, so the header takes the note,
    // less the horizon the group row already states.
    const headOf = k => {
      const it = itemOf[k], p = it.periods || 1;
      const twin = keys.some(j => j !== k && itemOf[j].label === it.label && (itemOf[j].periods || 1) === p);
      const rest = (it.note || "").replace(/^(month on month|year over year)[,;]?\s*/i, "");
      return esc(it.label) + (twin && rest ? `<i>${esc(rest)}</i>` : "");
    };
    h += `<div class="fc-rec"><h4>Record</h4><div class="tw"><table><thead>` +
         `<tr><th class="l" rowspan="3">Release</th><th class="l" rowspan="3">Made</th>` +
         groups.map(g => `<th class="grp b" colspan="${g.n * 3}">${horizon(g.p)}</th>`).join("") + `</tr>` +
         `<tr>` + keys.map(k => `<th class="m b" colspan="3">${headOf(k)}</th>`).join("") + `</tr>` +
         `<tr>` + keys.map(() => `<th class="sub b">Call</th><th class="sub">Print</th><th class="sub">Error</th>`).join("") +
         `</tr></thead><tbody>`;
    scored.slice().reverse().forEach(r => {
      h += `<tr><td class="l">${period(r.rec.for)}</td><td class="l">${fmtDate(r.rec.made)}</td>` + keys.map(k => {
        const x = r.items.find(z => z.it.key === k);
        if (!x) return `<td class="b pend" colspan="3">&mdash;</td>`;
        const fmt = fmtFor({ format: x.it.format || "spct" });
        if (x.printed == null) return `<td class="b">${fmt(x.it.value)}</td><td class="pend" colspan="2">pending</td>`;
        return `<td class="b">${fmt(x.it.value)}</td>` +
               `<td title="printed ${sgn(x.actual, 3)} unrounded, error ${sgn(x.errRaw, 2)}">${fmt(x.printed)}<span class="raw">${rawOf(x)}</span></td>` +
               `<td${Math.abs(x.err) > 0.1 ? ' class="miss"' : ""}>${sgn(x.err, 1)}</td>`;
      }).join("") + `</tr>`;
    });
    const tally = keys.map(k => {
      const errs = scored.map(r => r.items.find(z => z.it.key === k)).filter(x => x && x.err != null).map(x => x.err);
      if (!errs.length) return null;
      return { mae: errs.reduce((a, b) => a + Math.abs(b), 0) / errs.length,
               hits: errs.filter(e => Math.abs(e) <= 0.1).length, n: errs.length };
    });
    h += `</tbody>`;
    if (tally.some(Boolean)) {
      const foot = (name, cell) => `<tr><td class="l" colspan="2">${name}</td>` + tally.map(t =>
        t ? `<td class="b" colspan="2"></td><td>${cell(t)}</td>` : `<td class="b pend" colspan="3">&mdash;</td>`).join("") + `</tr>`;
      h += `<tfoot>` + foot("Mean absolute error", t => t.mae.toFixed(2)) +
           foot("Within &plusmn;0.1", t => `${t.hits} of ${t.n}`) + `</tfoot>`;
    }
    h += `</table></div><p class="note">` +
         (tally.some(Boolean) ? "Print is the figure as first released, its unrounded value beneath. Error is in points, scored at the one decimal the release prints."
                              : `${scored.length} call${scored.length === 1 ? "" : "s"} recorded, none scored yet.`) +
         `</p></div>`;
    host.innerHTML = h;
  }

  /* Forecast error by release, in the units of the call. Bars carry
     identity colours -- two measures, not two signs -- and the sign is read
     against the zero line, which is forced onto the axis. */
  PANELS.forecast = (el, ctx, p) => {
    const P = ctx.P, fmt = fmtFor(p);
    const keys = p.items.map(i => i.key);
    const recs = (ctx.forecasts || []).filter(r => r.items.some(x => keys.includes(x.it.key) && x.printed != null));
    if (!recs.length) {
      const pend = (ctx.forecasts || []).find(r => r.items.some(x => x.printed == null));
      el.innerHTML = `<p class="fc-empty">No release scored yet` +
        (pend ? `. The first call is graded when the ${fmtDate(pend.rec.release_at)} release lands and the bundle refreshes.` : ".") + `</p>`;
      return;
    }
    const cats = recs.map(r => r.rec.for);
    let maxAbs = 0.1;
    const series = p.items.map((pi, i) => {
      const data = recs.map(r => { const x = r.items.find(z => z.it.key === pi.key);
                                   return x && x.printed != null ? x.err : null; });
      data.forEach(v => { if (v != null) maxAbs = Math.max(maxAbs, Math.abs(v)); });
      return { name: pi.label, type: "bar", data, barMaxWidth: 16,
               itemStyle: { color: P[pi.color || ["s1", "s2", "s3", "s4", "s5", "s6"][i]] },
               markLine: i === 0 ? { silent: true, symbol: "none",
                 lineStyle: { color: P.ink, width: 1 }, label: { show: false },
                 data: [{ yAxis: 0 }] } : undefined };
    });
    // Ticks on whole tenths. Left to ECharts, a ±0.1 axis ticked at 0.05 and
    // the one-decimal format printed +0.1 twice.
    const step = Math.max(0.1, Math.ceil(maxAbs / 3 * 10) / 10);
    const lim = Math.ceil(maxAbs / step - 1e-9) * step;
    const opt = Object.assign(base(P), {
      grid: { left: p.left || 46, right: p.right || 14, top: 12, bottom: 24 },
      tooltip: Object.assign(base(P).tooltip, { trigger: "axis",
        formatter: ps => {
          const r = recs[ps[0].dataIndex];
          return "<b>" + label(ps[0].axisValue, "M") + "</b>" + ps.map(x => {
            const pi = p.items.find(i => i.label === x.seriesName);
            const sc = r && pi ? r.items.find(z => z.it.key === pi.key) : null;
            return "<br>" + x.seriesName + " " + (x.data == null ? "not scored"
              : fmt(x.data) + (sc ? ` (unrounded ${sgn(sc.errRaw, 2)}: called ${sgn(sc.it.value, 1)}, printed ${sgn(sc.actual, 2)})` : ""));
          }).join("");
        } }),
      xAxis: { type: "category", data: cats,
        axisLabel: { color: P.muted, fontSize: 9.5, hideOverlap: true,
                     interval: labelInterval(el, cats, "M", p.tick, (p.left || 46) + 14, 9.5, P.mono), alignMaxLabel: "right",
                     formatter: v => label(v, "M") },
        axisLine: { lineStyle: { color: P.ruleHi } }, axisTick: { show: false } },
      yAxis: Object.assign(yAxis(P, fmt), { scale: false, min: -lim, max: lim, interval: step }),
      series,
    });
    mount(el, opt);
  };

  /* ---------- boot -------------------------------------------------------- */
  async function render(cfg) {
    const status = document.getElementById("status");
    let bundle;
    try {
      const r = await fetch(cfg.bundle, { credentials: "same-origin", cache: "no-cache" });
      if (!r.ok) throw new Error(`${r.status} ${r.statusText}`);
      bundle = await r.json();
    } catch (e) {
      if (status) status.textContent = `Could not load data (${e.message}). The page is live; the bundle is not.`;
      if (status) status.hidden = false;
      return;
    }
    if (bundle.schema !== 1) {
      if (status) { status.textContent = `Bundle schema ${bundle.schema} is newer than this page understands.`; status.hidden = false; }
      return;
    }

    const ctx = {
      bundle, P: palette(),
      series(id) {
        const s = bundle.series[id];
        if (!s) throw new Error("series not in bundle: " + id);
        return s;
      },
    };

    // Stamp: the dashboard's own release, and only that one.
    const rel = bundle.releases[bundle.release];
    const stamp = document.getElementById("stamp");
    if (rel && stamp) {
      const MFULL = ["January","February","March","April","May","June","July",
                     "August","September","October","November","December"];
      const rp = rel.ref_period.split("-");
      // The reference period follows the release's cadence, which the
      // bundle carries: a quarterly release's ref_period is the quarter's
      // first month, and "April 2026" for 2026 Q2 was trap 52's shape.
      const period = rel.cadence === "weekly"
        ? `week to ${fmtDate(rel.ref_period)}`
        : rel.cadence === "quarterly"
        ? `${rp[0]} Q${Math.ceil(+rp[1] / 3)}`
        : `${MFULL[+rp[1] - 1]} ${rp[0]}`;
      const bits = [`<span><b>${rel.name}</b> &middot; ${period}</span>`];
      // A release the bundle cannot date prints no date. It reached here as
      // "Invalid Date" only because the field was assumed always present.
      if (rel.released_at)
        bits.push(`<span>Released ${fmtDate(rel.released_at)}</span>`);
      if (rel.next_at) bits.push(`<span>Next ${fmtDate(rel.next_at)}</span>`);
      stamp.innerHTML = bits.join("");
    }

    if (cfg.summary) summary(document.getElementById("summary"), ctx, cfg.summary);

    // The forecast record, if the page has one. Loaded before the panels so
    // the error panel can read the scored calls from ctx; a record that
    // fails to load leaves its block saying so rather than blank.
    if (cfg.forecast) {
      const host = document.getElementById(cfg.forecast.into || "fcBlock");
      try {
        const r = await fetch(cfg.forecast.url, { credentials: "same-origin", cache: "no-cache" });
        if (!r.ok) throw new Error(`${r.status} ${r.statusText}`);
        const doc = await r.json();
        ctx.forecasts = scoreForecasts(ctx, doc);
        forecastBlock(host, ctx, ctx.forecasts, doc);
      } catch (e) {
        console.error("forecast record failed:", e);
        if (host) host.innerHTML = `<p class="fc-empty">Forecast record could not be loaded (${e.message}).</p>`;
      }
    }

    // Measure with the font that will be drawn. ECharts sizes axis labels
    // when it lays out, and hideOverlap trusts those sizes; before the
    // webfonts arrive it measures the fallback monospace and the labels
    // then collide once JetBrains Mono paints. Capped so a blocked font
    // host delays a page by at most a second and a half.
    if (document.fonts && document.fonts.ready)
      await Promise.race([document.fonts.ready, new Promise(r => setTimeout(r, 1500))]);

    // Notes as points, and gists measured in the real font, before the charts mount.
    pointNotes();
    alignGists();
    let gistTimer;
    addEventListener("resize", () => { clearTimeout(gistTimer); gistTimer = setTimeout(alignGists, 150); });

    cfg.panels.forEach(p => {
      const el = document.getElementById(p.el);
      if (!el) { console.warn("no element for panel", p.el); return; }
      const fn = PANELS[p.type];
      if (!fn) { console.warn("unknown panel type", p.type); return; }
      try { fn(el, ctx, p); }
      catch (e) { console.error("panel " + p.el + " failed:", e);
                  el.innerHTML = `<div class="panel-error">${p.el}: ${e.message}</div>`; }
    });

    // Any element marked data-latest shows its series' newest value: the
    // share of the CPI in a stacked chart's heading, kept current by the
    // drifted weight rather than typed into the page.
    document.querySelectorAll("main [data-latest]").forEach(n => {
      try {
        const v = lastNonNull(ctx.series(n.dataset.latest).values);
        n.textContent = v == null ? "–" : fmtFor({ format: n.dataset.format || "pct" })(v);
      } catch (e) { n.textContent = "–"; }
    });

    try { railSpy(); }
    catch (e) { console.error("contents highlight failed:", e); }

    try { tableStamps(ctx, cfg.panels); }
    catch (e) { console.error("table dates failed:", e); }

    const gen = document.getElementById("generated");
    if (gen) gen.textContent = "Data generated " + fmtDate(bundle.generated_at);
  }

  const fmtDate = iso => {
    const d = new Date(iso.length === 10 ? iso + "T00:00:00Z" : iso);
    return `${d.getUTCDate()} ${MN[d.getUTCMonth()]} ${d.getUTCFullYear()}`;
  };

  // fmtFor is exported for the landing page's card, so a headline figure there
  // is formatted by the same code as the figure on the dashboard it links to.
  global.BRB = { render, axis, label, derive, resolve, T, PANELS, palette, spark, fmtFor };
})(window);
