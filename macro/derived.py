"""Derived series, computed server-side and shipped as ordinary series.

A derived measure enters the bundle looking exactly like a fetched one, so the
page renders it with the existing panel types and `brb-dash.js` needs no new
maths. That keeps the rule in CLAUDE.md intact: a new dashboard is a spec plus a
panel list, and per-dashboard arithmetic never leaks into the engine.

Anything combining two vintages, or two series of different length, belongs
here rather than in the browser. The precedent is `first_reported_diff` in
export.py: derived in SQL because differencing first prints on the page reads
two different vintages and gets the answer wrong.

Every derived entry carries `derived: true` and a `formula` string. The page is
required to label them; a reader must never mistake an analyst construct for a
published statistic.
"""
from __future__ import annotations


def _diff(values: list[float | None]) -> list[float | None]:
    """Month-on-month change. Nulls propagate: a published gap stays a gap."""
    out: list[float | None] = [None]
    for i in range(1, len(values)):
        a, b = values[i], values[i - 1]
        out.append(None if a is None or b is None else a - b)
    return out


def revision(entry: dict) -> list[float | None]:
    """Latest change minus the change as first reported.

    Both inputs are already correct: `values` is the current vintage and
    `first_reported_diff` was computed in SQL reading both periods at the
    vintage of the later one's first print. Differencing `first_print` levels
    here instead would subtract across two vintages -- the mistake CLAUDE.md
    trap 2 records having been made twice.
    """
    frd = entry.get("first_reported_diff")
    if not frd:
        raise ValueError("revision needs first_reported_diff on the source series")
    cur = _diff(entry["values"])
    return [None if (a is None or b is None) else round(a - b, 3)
            for a, b in zip(cur, frd)]


def revision_mean(entry: dict, window: int = 12) -> list[float | None]:
    """Rolling mean revision. The bias, rather than any single month's surprise."""
    rev = revision(entry)
    out: list[float | None] = []
    for i in range(len(rev)):
        if i < window - 1:
            out.append(None)
            continue
        win = rev[i - window + 1: i + 1]
        got = [v for v in win if v is not None]
        # A rolling mean over a partly-unrevised window would drift towards zero
        # as the newest months carry no revision yet. Require the whole window.
        out.append(round(sum(got) / len(got), 3) if len(got) == window else None)
    return out


def signif_share(entry: dict, threshold: float, window: int = 24) -> list[float | None]:
    """Share of the trailing window whose change exceeds a sampling interval.

    The release states a 90% confidence interval of +/-122,000 on the monthly
    change in total nonfarm employment. This asks how often the published figure
    is large enough to be distinguishable from no change at all.
    """
    ch = _diff(entry["values"])
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


def abs_revision_mean(entry: dict, window: int = 12) -> list[float | None]:
    """Rolling mean ABSOLUTE revision: the size of the typical correction.

    First-to-latest, so it includes the annual benchmark rewrite and runs far
    above the first-to-final figure usually quoted (87.5k against about 51k over
    the full history). Both are true of different questions; the page must say
    which one it is showing.
    """
    rev = revision(entry)
    out: list[float | None] = []
    for i in range(len(rev)):
        if i < window - 1:
            out.append(None)
            continue
        win = rev[i - window + 1: i + 1]
        got = [abs(v) for v in win if v is not None]
        out.append(round(sum(got) / len(got), 3) if len(got) == window else None)
    return out


KINDS = {
    "revision":         (revision,         "latest monthly change minus the change as first reported"),
    "revision_mean":    (revision_mean,    "rolling {window}-month mean revision, first reported to latest"),
    "abs_revision_mean":(abs_revision_mean,"rolling {window}-month mean absolute revision, first reported to latest"),
    "signif_share":     (signif_share,     "share of the trailing {window} months whose change exceeds +/-{threshold}k"),
}

_PASS = {"revision": (), "revision_mean": ("window",),
         "abs_revision_mean": ("window",), "signif_share": ("threshold", "window")}


def build(spec: dict, series_out: dict) -> list[str]:
    """Append every `derived:` entry in the spec to series_out. Returns the ids added."""
    added = []
    for d in spec.get("derived", []) or []:
        kind = d["kind"]
        if kind not in KINDS:
            raise SystemExit(f"unknown derived kind {kind!r} in {spec['id']}")
        src_id = d["of"]
        src = series_out.get(src_id)
        if src is None:
            raise SystemExit(f"{spec['id']}: derived {d['id']} needs {src_id}, "
                             "which the bundle does not carry")
        fn, formula = KINDS[kind]
        kwargs = {k: d[k] for k in _PASS[kind] if k in d}
        values = fn(src, **kwargs)

        entry = {
            "title": d["title"],
            "frequency": src["frequency"],
            "sa": src["sa"],
            "release": d.get("release", src["release"]),
            "importance": d.get("importance", 3),
            "source_url": src.get("source_url"),
            "values": values,
            "derived": True,
            "formula": formula.format(**{**{"window": "", "threshold": ""}, **kwargs}),
            "derived_from": [src_id],
        }
        if d.get("unit"):
            entry["unit"] = d["unit"]
        # Carry the source's own date axis: a derived series is defined on the
        # same observations, so a separate axis could only ever disagree.
        for k in ("start", "step", "dates"):
            if k in src:
                entry[k] = src[k]
        series_out[d["id"]] = entry
        added.append(d["id"])
    return added
