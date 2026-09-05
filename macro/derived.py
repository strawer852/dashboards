"""Derived series, computed server-side and shipped as ordinary series.

A derived measure enters the bundle looking exactly like a fetched one, so the
page renders it with the existing panel types and `brb-dash.js` needs no new
maths. That keeps the rule in CLAUDE.md intact: a new dashboard is a spec plus a
panel list, and per-dashboard arithmetic never leaks into the engine.

Anything combining two vintages, or two series, belongs here rather than in the
browser. The precedent is `first_reported_diff` in export.py: derived in SQL
because differencing first prints on the page reads two different vintages and
gets the answer wrong.

Multi-input measures align their inputs BY DATE. Two series in one bundle can
start in different years -- CLF16OV in 1948, UNRATE in 1948, JTSJOL in 2000 --
and zipping them positionally would silently pair one year's value with
another's. CLAUDE.md trap 6.

Every derived entry carries `derived: true` and a `formula` string. The page is
required to label them; a reader must never mistake an analyst construct for a
published statistic.
"""
from __future__ import annotations


# ---------------------------------------------------------------- date axes --
def axis(entry: dict) -> list[str]:
    """The entry's own observation dates as YYYY-MM(-DD) strings."""
    if "dates" in entry:
        return list(entry["dates"])
    start, step = entry["start"], entry["step"]
    y, m = int(start[:4]), int(start[5:7])
    k = {"M": 1, "Q": 3, "A": 12}.get(step)
    if k is None:                      # weekly or daily: dates are explicit
        raise ValueError(f"cannot rebuild a {step} axis without explicit dates")
    out = []
    for i in range(len(entry["values"])):
        mm = (m - 1) + i * k
        out.append(f"{y + mm // 12:04d}-{mm % 12 + 1:02d}")
    return out


def on_axis(entry: dict, dates: list[str]) -> list[float | None]:
    """Line an entry's values up against `dates`, matched exactly by date."""
    have = dict(zip(axis(entry), entry["values"]))
    return [have.get(d) for d in dates]


# ------------------------------------------------------------- small helpers --
def _diff(values, periods: int = 1, drop_month: int | None = None,
          dates: list[str] | None = None):
    """Change over `periods`. Nulls propagate: a published gap stays a gap.

    `drop_month` suppresses the change into a given calendar month. January's
    civilian labour force carries new population controls and BLS does not
    revise prior months, so the January change is a level break rather than a
    flow -- 2026 shows -1,030k where nothing of the kind happened. CLAUDE.md
    trap 14.
    """
    out: list[float | None] = [None] * min(periods, len(values))
    for i in range(periods, len(values)):
        a, b = values[i], values[i - periods]
        v = None if a is None or b is None else a - b
        if v is not None and drop_month is not None and dates is not None \
                and int(dates[i][5:7]) == drop_month:
            v = None
        out.append(v)
    return out


def _trailing_mean(values, window: int, min_obs: int | None = None):
    """Rolling mean tolerating a few holes -- one per year, by construction."""
    need = window if min_obs is None else min_obs
    out: list[float | None] = []
    for i in range(len(values)):
        if i < window - 1:
            out.append(None)
            continue
        got = [v for v in values[i - window + 1: i + 1] if v is not None]
        out.append(round(sum(got) / len(got), 3) if len(got) >= need else None)
    return out


# ------------------------------------------------------------------- kinds ---
def revision(srcs, **_):
    """Latest change minus the change as first reported.

    Both inputs are already correct: `values` is the current vintage and
    `first_reported_diff` was computed in SQL reading both periods at the
    vintage of the later one's first print. Differencing `first_print` levels
    here instead would subtract across two vintages -- CLAUDE.md trap 2.
    """
    e = srcs[0]
    frd = e.get("first_reported_diff")
    if not frd:
        raise ValueError("revision needs first_reported_diff on the source series")
    cur = _diff(e["values"])
    return [None if (a is None or b is None) else round(a - b, 3)
            for a, b in zip(cur, frd)]


def level_revision(srcs, **_):
    """Current published level minus the level as first reported.

    The sibling `revision` works on month-on-month CHANGES and needs
    `first_reported_diff`, because differencing two first prints reads two
    different vintages. A level has no such problem: `first_print` is what was
    published for that observation, full stop.
    """
    e = srcs[0]
    fp = e.get("first_print")
    if not fp:
        raise ValueError("level_revision needs first_print; the exporter drops it "
                         "when no observation was ever revised")
    return [None if (a is None or b is None) else round(a - b, 3)
            for a, b in zip(e["values"], fp)]


def revision_mean(srcs, window: int = 12, **_):
    """Rolling mean revision: the bias, rather than any month's surprise."""
    rev = revision(srcs)
    return _trailing_mean(rev, window, min_obs=window)


def abs_revision_mean(srcs, window: int = 12, **_):
    """Rolling mean ABSOLUTE revision: the size of the typical correction.

    First-to-latest, so it includes the annual benchmark rewrite and runs far
    above the first-to-final figure usually quoted (87.5k against about 51k over
    the full history). Both are true of different questions; the page must say
    which one it is showing.
    """
    rev = revision(srcs)
    return _trailing_mean([None if v is None else abs(v) for v in rev],
                          window, min_obs=window)


def signif_share(srcs, threshold: float = 122.0, window: int = 24, **_):
    """Share of the trailing window whose change exceeds a sampling interval.

    The release states a 90% confidence interval of +/-122,000 on the monthly
    change in total nonfarm employment. This asks how often the published figure
    is large enough to be distinguishable from no change at all.
    """
    ch = _diff(srcs[0]["values"])
    out: list[float | None] = []
    for i in range(len(ch)):
        if i < window - 1:
            out.append(None)
            continue
        win = [v for v in ch[i - window + 1: i + 1] if v is not None]
        if len(win) < window:
            out.append(None)
            continue
        out.append(round(100.0 * sum(1 for v in win if abs(v) > threshold) / window, 3))
    return out


def breakeven(srcs, window: int = 6, drop_month: int = 1,
              min_obs: int | None = None, **_):
    """Employment growth that would hold the unemployment rate flat.

    of: [civilian labour force, unemployment rate]

    An accounting identity, not a model. Unemployment is unchanged when
    employment grows with the labour force, so the monthly employment gain
    required is the labour force's own growth net of the share that stays
    unemployed:

        breakeven = mean(dLF over `window` months) x (1 - u)

    January's change is dropped: it carries new population controls that BLS
    does not apply to prior months, so it is a level break and not a flow.
    The trailing mean therefore averages the months it has -- eleven in any
    window that spans a January.

    On the household concept, since the labour force and the unemployment rate
    are both household-survey measures. Comparing it with a payroll figure is
    indicative rather than exact: CES counts jobs and CPS counts people.
    """
    lf, ur = srcs[0], srcs[1]
    dates = axis(lf)
    d_lf = _diff(lf["values"], drop_month=drop_month, dates=dates)
    # October 2025 costs two months of change on its own -- the household
    # survey was not collected -- and January is dropped every year, so a
    # twelve-month window needs a lower floor than an eleven-of-twelve one.
    trend = _trailing_mean(d_lf, window,
                           min_obs=min_obs if min_obs else window - 1)
    u = on_axis(ur, dates)
    return [None if (t is None or x is None) else round(t * (1 - x / 100.0), 3)
            for t, x in zip(trend, u)]


def residual(srcs, **_):
    """First input minus every other, on the first input's date axis.

    Components are seasonally adjusted independently, so a residual of adjusted
    series is an approximation rather than an identity. Label it derived and do
    not present it as a published aggregate.
    """
    dates = axis(srcs[0])
    base = on_axis(srcs[0], dates)
    subs = [on_axis(e, dates) for e in srcs[1:]]
    out = []
    for i in range(len(dates)):
        vals = [base[i]] + [sub[i] for sub in subs]
        out.append(None if any(v is None for v in vals)
                   else round(vals[0] - sum(vals[1:]), 3))
    return out


def epop_participation_effect(srcs, periods: int = 12, **_):
    """The part of the employment-population move that participation explains.

    of: [participation rate, unemployment rate]

    EPOP = participation x (1 - u) exactly, so the change over `periods`
    separates into

        participation effect = dP  x (1 - u0)
        unemployment effect  = -P0 x du

    with a small interaction left over. Reported in percentage points.
    """
    p, u = on_axis(srcs[0], axis(srcs[0])), on_axis(srcs[1], axis(srcs[0]))
    out: list[float | None] = [None] * min(periods, len(p))
    for i in range(periods, len(p)):
        p1, p0, u0 = p[i], p[i - periods], u[i - periods]
        out.append(None if None in (p1, p0, u0)
                   else round((p1 - p0) * (1 - u0 / 100.0), 3))
    return out


def epop_unemployment_effect(srcs, periods: int = 12, **_):
    """The part of the employment-population move that unemployment explains.

    of: [participation rate, unemployment rate]. See the sibling above.
    """
    p, u = on_axis(srcs[0], axis(srcs[0])), on_axis(srcs[1], axis(srcs[0]))
    out: list[float | None] = [None] * min(periods, len(p))
    for i in range(periods, len(p)):
        p0, u1, u0 = p[i - periods], u[i], u[i - periods]
        out.append(None if None in (p0, u1, u0)
                   else round(-(p0 / 100.0) * (u1 - u0), 3))
    return out


def contribution(srcs, weight: float = 0.0, weight_date: str = "",
                 periods: int = 12, **_):
    """A component's contribution to the aggregate's change, in percentage points.

    of: [component index, aggregate index]

    BLS publishes a *relative importance* -- the component's share of the
    basket -- and re-drifts it every month for relative prices:

        RI_i(t) = RI_i(t0) * [I_i(t)/I_i(t0)] / [I_agg(t)/I_agg(t0)]

    so one published anchor carries itself forward from the indexes already in
    the database rather than being retyped every month. Only the annual
    reweight breaks it, and the decomposition residual is what catches that.

    The contribution to the change over `periods` uses the share at the START
    of the window, not the end:

        c_i(t) = RI_i(t-n) * [I_i(t)/I_i(t-n) - 1]

    That is what makes the parts sum to the whole. Measured on July 2026, the
    four-way split (food, energy, core goods, core services) closes on headline
    CPI to 0.007pp this way; carrying end-of-window weights instead leaves
    0.093pp, thirteen times worse. Reported in percentage points.
    """
    if not weight_date:
        raise SystemExit("contribution needs weight_date, the month the "
                         "published relative importance refers to")
    dates = axis(srcs[0])
    comp = on_axis(srcs[0], dates)
    agg = on_axis(srcs[1], dates)

    # The anchor must exist on both series, or the measure is silently scaled
    # by the wrong number and nothing about the chart would look wrong.
    try:
        a = dates.index(weight_date)
    except ValueError:
        raise SystemExit("contribution: weight_date %s is not on the axis of %s"
                         % (weight_date, srcs[0].get("title", "?")))
    if comp[a] is None or agg[a] is None:
        raise SystemExit("contribution: no observation at %s" % weight_date)
    ci, ai = comp[a], agg[a]

    ri = [None if (c is None or g is None) else weight * (c / ci) / (g / ai)
          for c, g in zip(comp, agg)]

    out: list[float | None] = [None] * min(periods, len(comp))
    for i in range(periods, len(comp)):
        c1, c0, w0 = comp[i], comp[i - periods], ri[i - periods]
        out.append(None if None in (c1, c0, w0)
                   else round(w0 * (c1 / c0 - 1), 4))
    return out


def relative_importance(srcs, weight: float = 0.0, weight_date: str = "", **_):
    """The component's share of the aggregate's basket, per cent.

    of: [component index, aggregate index]

    The same drift rule `contribution` uses, published by BLS for exactly this
    purpose: a relative importance moves with relative prices between the
    annual reweights, so one anchor keeps itself current from the indexes
    already in the database.

        RI_i(t) = RI_i(t0) * [I_i(t)/I_i(t0)] / [I_agg(t)/I_agg(t0)]

    The aggregate decides what the share is OF: passing CPIAUCSL gives the
    share of the whole basket, passing CPILFESL the share of core. The anchor
    must be stated on the same basis -- shelter is 35.304% of the CPI and
    44.662% of core, and they are not interchangeable.
    """
    if not weight_date:
        raise SystemExit("relative_importance needs weight_date")
    dates = axis(srcs[0])
    comp = on_axis(srcs[0], dates)
    agg = on_axis(srcs[1], dates)
    try:
        a = dates.index(weight_date)
    except ValueError:
        raise SystemExit("relative_importance: weight_date %s is not on the "
                         "axis of %s" % (weight_date, srcs[0].get("title", "?")))
    if comp[a] is None or agg[a] is None:
        raise SystemExit("relative_importance: no observation at %s" % weight_date)
    ci, ai = comp[a], agg[a]
    return [None if (c is None or g is None)
            else round(weight * (c / ci) / (g / ai), 4)
            for c, g in zip(comp, agg)]


def above_trailing_min(srcs, window: int = 52, **_):
    """How far above its own trailing minimum a series sits, in per cent.

    The classic claims recession rule is stated as a rise off the cycle low
    rather than a level, because the level that matters has drifted down for
    forty years as covered employment changed shape. Expressed against the
    trailing window's own minimum, the measure is comparable across eras.

    A null anywhere in the window yields a null: a minimum computed over a
    window with holes is not the minimum.
    """
    v = srcs[0]["values"]
    out: list[float | None] = []
    for i in range(len(v)):
        if i < window - 1 or v[i] is None:
            out.append(None)
            continue
        win = v[i - window + 1: i + 1]
        if any(x is None for x in win):
            out.append(None)
            continue
        lo = min(win)
        out.append(None if not lo else round(100.0 * (v[i] / lo - 1.0), 3))
    return out


def share_above_year_ago(srcs, periods: int = 52, **_):
    """Share of the input series standing above their own value a year ago.

    Breadth, not level. One state doubling moves the national total and leaves
    this unchanged; forty states drifting up moves this and may barely show
    nationally. Comparing each series with ITSELF a year earlier is also what
    makes it usable on unadjusted data, which is all the states publish -- the
    same week last year carries the same seasonal position.

    Series are counted only where both ends exist, and the denominator is the
    count actually compared, so a state whose history starts late dilutes
    nothing.
    """
    n = max(len(s["values"]) for s in srcs)
    out: list[float | None] = []
    for i in range(n):
        up = tot = 0
        for s in srcs:
            v = s["values"]
            if i >= len(v) or i < periods:
                continue
            a, b = v[i], v[i - periods]
            if a is None or b is None:
                continue
            tot += 1
            up += 1 if a > b else 0
        out.append(round(100.0 * up / tot, 3) if tot >= 20 else None)
    return out


KINDS = {
    "revision":          (revision, 1,
                          "latest monthly change minus the change as first reported"),
    "level_revision":    (level_revision, 1,
                          "current published level minus the level as first reported"),
    "revision_mean":     (revision_mean, 1,
                          "rolling {window}-month mean revision, first reported to latest"),
    "abs_revision_mean": (abs_revision_mean, 1,
                          "rolling {window}-month mean absolute revision, first reported to latest"),
    "signif_share":      (signif_share, 1,
                          "share of the trailing {window} months whose change exceeds +/-{threshold}k"),
    "breakeven":         (breakeven, 2,
                          "trailing {window}-month mean change in the labour force, "
                          "January excluded as a population-control break, times (1 - u)"),
    "residual":          (residual, 2,
                          "first series minus the second, both seasonally adjusted "
                          "independently so the difference is approximate"),
    "epop_participation_effect": (epop_participation_effect, 2,
                          "change in participation over {periods} months times (1 - u) at the start"),
    "epop_unemployment_effect":  (epop_unemployment_effect, 2,
                          "minus participation at the start times the change in u over {periods} months"),
    "contribution":      (contribution, 2,
                          "relative importance of {weight}% at {weight_date}, re-drifted with relative prices, times the component's own change over {periods} months"),
    "above_trailing_min": (above_trailing_min, 1,
                          "per cent above the lowest value of the trailing {window} periods"),
    "share_above_year_ago": (share_above_year_ago, None,
                          "share of the listed series standing above their own "
                          "value {periods} periods earlier"),
    "relative_importance": (relative_importance, 2,
                          "share of the basket, {weight}% at {weight_date}, re-drifted with relative prices"),
}

_PASS = {
    "revision": (),
    "level_revision": (),
    "revision_mean": ("window",),
    "abs_revision_mean": ("window",),
    "signif_share": ("threshold", "window"),
    "breakeven": ("window", "drop_month", "min_obs"),
    "residual": (),
    "epop_participation_effect": ("periods",),
    "epop_unemployment_effect": ("periods",),
    "contribution": ("weight", "weight_date", "periods"),
    "relative_importance": ("weight", "weight_date"),
    "above_trailing_min": ("window",),
    "share_above_year_ago": ("periods",),
}

_DEFAULTS = {"window": 12, "threshold": 122, "periods": 12, "drop_month": 1}


def build(spec: dict, series_out: dict) -> list[str]:
    """Append every `derived:` entry in the spec to series_out. Returns ids added."""
    added = []
    for d in spec.get("derived", []) or []:
        kind = d["kind"]
        if kind not in KINDS:
            raise SystemExit(f"unknown derived kind {kind!r} in {spec['id']}")
        fn, arity, formula = KINDS[kind]

        of = d["of"]
        src_ids = [of] if isinstance(of, str) else list(of)
        # arity None means "however many the spec lists" -- a breadth measure
        # is defined over a set, not over a fixed number of inputs.
        if arity is not None and len(src_ids) != arity:
            raise SystemExit(f"{spec['id']}: {d['id']} ({kind}) takes {arity} "
                             f"input(s), got {len(src_ids)}")
        if arity is None and len(src_ids) < 2:
            raise SystemExit(f"{spec['id']}: {d['id']} ({kind}) is a measure "
                             f"over a set and needs at least 2 inputs")
        srcs = []
        for sid in src_ids:
            if sid not in series_out:
                raise SystemExit(f"{spec['id']}: derived {d['id']} needs {sid}, "
                                 "which the bundle does not carry")
            srcs.append(series_out[sid])

        kwargs = {k: d[k] for k in _PASS[kind] if k in d}
        values = fn(srcs, **kwargs)
        shown = {**{k: _DEFAULTS.get(k, "") for k in _PASS[kind]}, **kwargs}

        entry = {
            "title": d["title"],
            "frequency": srcs[0]["frequency"],
            "sa": srcs[0]["sa"],
            "release": d.get("release", srcs[0]["release"]),
            "importance": d.get("importance", 3),
            "source_url": srcs[0].get("source_url"),
            "values": values,
            "derived": True,
            "formula": formula.format(**shown),
            "derived_from": src_ids,
        }
        if d.get("unit"):
            entry["unit"] = d["unit"]
        # Carry the first input's date axis: a derived series is defined on those
        # observations, so a separate axis could only ever disagree.
        for k in ("start", "step", "dates"):
            if k in srcs[0]:
                entry[k] = srcs[0][k]
        series_out[d["id"]] = entry
        added.append(d["id"])
    return added
