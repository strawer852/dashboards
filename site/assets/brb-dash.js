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
      const o = ctx.series(sp.over);
      const den = new Map(axis(o).map((d, i) => [d, o.values[i]]));
      values = cats.map((d, i) => {
        const n = values[i], q = den.get(d);
        return (n == null || q == null || !q) ? null : +(n / q).toFixed(4);
      });
    }
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
    const P = ctx.P, fmt = fmtFor(p);
    const first = ctx.series(p.series[0].id);
    const cats = tail(axis(first), p.window);
    const opt = Object.assign(base(P), {
      grid: { left: p.left || 46, right: p.right || 14, top: 12, bottom: 24 },
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
        axisLabel: { color: P.muted, fontSize: 9.5, interval: p.tick || "auto",
                     formatter: v => label(v, first.frequency) },
        axisLine: { lineStyle: { color: P.ruleHi } }, axisTick: { show: false },
      },
      yAxis: p.axis2
        ? [yAxis(P, fmt), Object.assign(yAxis(P, fmtFor({ format: p.format2 })), { splitLine: { show: false } })]
        : yAxis(P, fmt),
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
          lineStyle: { color: P[sp.color || ["pos", "alt", "neg"][i] || "muted"],
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
        lineStyle: { color: P[sp.color || ["ink", "alt", "muted"][i] || "muted"],
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
        axisLabel: { color: P.muted, fontSize: 9.5, interval: p.tick || "auto",
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
        // value, so it cannot be confused with the terracotta of a loss.
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
    const rows = p.series.map(sp => {
      const s = ctx.series(sp.id);
      const v = derive(s, { transform: "diff" });
      return [sp.label || shortName(s.title), v[v.length - 1]];
    }).filter(r => r[1] != null).sort((a, b) => a[1] - b[1]);
    mount(el, Object.assign(base(P), {
      grid: { left: p.left || 132, right: 46, top: 8, bottom: 24 },
      tooltip: Object.assign(base(P).tooltip, {
        trigger: "item", formatter: x => `<b>${x.name}</b><br>${sgn(x.value, 1)}k` }),
      xAxis: { type: "value", splitNumber: 5,
        axisLabel: { color: P.muted, fontSize: 9.5, formatter: v => sgn(v) },
        splitLine: { lineStyle: { color: P.grid } } },
      yAxis: { type: "category", data: rows.map(r => r[0]),
        axisLabel: { color: P.ink2, fontSize: 10, fontFamily: P.mono },
        axisLine: { lineStyle: { color: P.ruleHi } }, axisTick: { show: false } },
      series: [{
        type: "bar", data: rows.map(r => r[1]), barMaxWidth: 13,
        itemStyle: { color: x => (x.value < 0 ? P.neg : P.pos) },
        label: { show: true, position: x => (x.value < 0 ? "left" : "right"),
                 formatter: x => sgn(x.value, 1), color: P.muted,
                 fontFamily: P.mono, fontSize: 9.5 },
      }],
    }));
  };

  PANELS.heatmap = (el, ctx, p) => {
    const P = ctx.P;
    const months = p.months || 24;
    const names = [], data = [];
    let cats = null;
    p.series.forEach((sp, yi) => {
      const s = ctx.series(sp.id);
      const v = derive(s, { transform: "diff" }).slice(-months);
      if (!cats) cats = axis(s).slice(-months);
      names.push(sp.label || shortName(s.title));
      v.forEach((val, xi) => { if (val != null) data.push([xi, yi, val]); });
    });
    const cap = p.cap || 45;
    mount(el, Object.assign(base(P), {
      grid: { left: p.left || 132, right: 20, top: 8, bottom: 48 },
      tooltip: Object.assign(base(P).tooltip, {
        formatter: x => `<b>${names[x.data[1]]}</b><br>${label(cats[x.data[0]], "M")}  ${sgn(x.data[2], 1)}k` }),
      xAxis: { type: "category", data: cats, splitArea: { show: false },
        axisLabel: { color: P.muted, fontSize: 9, interval: 2, formatter: v => label(v, "M") },
        axisLine: { lineStyle: { color: P.ruleHi } }, axisTick: { show: false } },
      yAxis: { type: "category", data: names, splitArea: { show: false },
        axisLabel: { color: P.ink2, fontSize: 10, fontFamily: P.mono },
        axisLine: { lineStyle: { color: P.ruleHi } }, axisTick: { show: false } },
      visualMap: { min: -cap, max: cap, calculable: false, orient: "horizontal",
        left: p.left || 132, bottom: 2, itemWidth: 11, itemHeight: 96,
        textStyle: { color: P.muted, fontFamily: P.mono, fontSize: 9 },
        text: [`≥ +${cap}k`, `≤ −${cap}k`], inRange: { color: P.hm } },
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
    axisLabel: { color: P.muted, fontSize: 9.5, formatter: fmt },
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
    if (f === "pct2") return v => v.toFixed(2) + "%";
    if (f === "pt") return v => sgn(v, 1);
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
    return v => String(Math.round(v * 100) / 100);
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
      const period = rel.cadence === "weekly"
        ? `week to ${fmtDate(rel.ref_period)}`
        : `${MFULL[+rp[1] - 1]} ${rp[0]}`;
      const bits = [`<span><b>${rel.name}</b> &middot; ${period}</span>`,
                    `<span>Released ${fmtDate(rel.released_at)}</span>`];
      if (rel.next_at) bits.push(`<span>Next ${fmtDate(rel.next_at)}</span>`);
      stamp.innerHTML = bits.join("");
    }

    if (cfg.summary) summary(document.getElementById("summary"), ctx, cfg.summary);

    cfg.panels.forEach(p => {
      const el = document.getElementById(p.el);
      if (!el) { console.warn("no element for panel", p.el); return; }
      const fn = PANELS[p.type];
      if (!fn) { console.warn("unknown panel type", p.type); return; }
      try { fn(el, ctx, p); }
      catch (e) { console.error("panel " + p.el + " failed:", e);
                  el.innerHTML = `<div class="panel-error">${p.el}: ${e.message}</div>`; }
    });

    const gen = document.getElementById("generated");
    if (gen) gen.textContent = "Data generated " + fmtDate(bundle.generated_at);
  }

  const fmtDate = iso => {
    const d = new Date(iso.length === 10 ? iso + "T00:00:00Z" : iso);
    return `${d.getUTCDate()} ${MN[d.getUTCMonth()]} ${d.getUTCFullYear()}`;
  };

  global.BRB = { render, axis, label, derive, resolve, T, PANELS, palette, spark };
})(window);
