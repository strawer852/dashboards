# Findings: derived measures for the employment dashboards

Written 3 September 2026, after reviewing two external proposals for the nonfarm
payroll dashboard (one from Codex, one from Gemini) and testing every candidate
measure against the `macro` database rather than accepting it on theory.

**Everything below was computed, not asserted.** Where a proposal's number is
reproduced here it reproduced exactly; where it failed, the failure is recorded
with the figures. Helpers live in `tools/research/lib.py` — read-only, plain
Python (this venv has no numpy), safe to re-run.

Companion documents: `CLAUDE.md` (traps), `~/bigricebowl/FINDINGS_revision_handling.md`
(the retired stack's vintage lessons).

---

## 1. Series the catalog is missing

Two absences block most of the derived work:

| Series | Why it is needed |
|---|---|
| `CLF16OV`, `CNP16OV` | Civilian labour force and population **levels**. The catalog holds participation and EPOP — the rates — but not the quantities they are computed from. Breakeven payroll growth is impossible without them |
| `JTSTSL`, `JTSOSL` | JOLTS total and other separations. Without them the hires-minus-separations identity cannot be closed |

Available on FRED and cheap to add: `LNS11300060` / `LNS12300060` (prime-age
participation and EPOP), `CES6562000001` (health care and social assistance —
**not** `USEHS`, which also contains private education), `TEMPHELPS`,
`AWHAEMAN`, `CES3000000004` (manufacturing hours and overtime, all employees),
`AWHAE` and `CES0500000017` (aggregate weekly hours and payrolls indexes),
`LNS12032194`, `LNS13023653`, `LNS13026638`, `LNS13023705`, `UEMPMED`,
`LNS13025703` (household slack decomposition).

### Series that exist only on the BLS API

Verified absent from FRED, present on BLS:

| Series | July 2026 | What it is |
|---|---:|---|
| `LNS16000000` | 156,497k | **Research series, CPS employment adjusted to CES concepts.** A published series, not a web table — no scraping needed |
| `CES0500000012` | $387.72 | Real average weekly earnings, 1982-84 dollars, deflated by BLS |
| `CES0500000013` | $11.30 | Real average hourly earnings, 1982-84 dollars |
| `CES0500000021/22/23` | 51.8 / 50.8 / 55.0 | Private diffusion indexes, 1/3/6-month spans, seasonally adjusted |
| `CEU0500000024` | 51.8 | Private diffusion, **12-month span — not seasonally adjusted.** The SA form does not exist |
| `CES0500000016` | 116.7 | Aggregate weekly hours index, all employees |
| `LNS15026642` | 1,806k | Marginally attached, **seasonally adjusted**. FRED carries only the NSA version |

Two consequences. First, a BLS adapter is not diffusion's private cost — it is
the entry price for six things already wanted, so it should be built once and
early rather than deferred. Second, **ALFRED supplies vintages and the BLS API
does not**: any BLS-sourced series enters with no revision history and can only
accumulate vintages from the day ingestion starts. `macro_series_meta` already
has `source` and `vintage_mode`, but `ingest.py` selects `WHERE source='fred'`,
so that must become a dispatch — and the page must never offer a revision
overlay on a series that structurally cannot have one.

The real-earnings series carry a further trap: they are published with the
**CPI**, not the Employment Situation. On payroll release morning the newest
month has no real-earnings value. Under the one-release-per-dashboard rule they
need their own stamp.

---

## 2. Breakeven payroll growth

**The single most valuable derived number, and it inverts the headline.**

The civilian labour force is contracting. Over February to July 2026 it fell
**-228.5k per month**; at u = 4.1% that puts the household employment gain
needed to hold the unemployment rate flat at **-219k per month**, or roughly
**-200k per month** in payroll terms (the CES/CPS level ratio is 0.9629, so the
translation is approximate). July's -23k print is therefore *above* breakeven,
and U-3 duly fell 0.2pp over three months.

```
LF monthly change, 2026:  Jan -1030   Feb  +18   Mar -396
                          Apr   -92   May  +83   Jun -720   Jul -264
```

> **Trap — January is a level break, not a flow.** BLS introduces new population
> controls each January and does not revise prior months. The -1,030k shown for
> January 2026 is that break. A twelve-month labour force change spanning January
> mixes the break into the flow: it reads -109.8k/month against the -228.5k/month
> the post-control window actually shows. The correct input is the
> population-control-smoothed research series at
> `https://www.bls.gov/cps/smoothed_emp.xlsx`, which exists for exactly this reason.

Monthly CPS sampling error on the labour force runs to several hundred thousand,
so six months is the shortest defensible window.

**Amended 3 September 2026, on building the panel.** The estimate is far more
window-sensitive than this first pass recorded. At July 2026, with January
dropped throughout:

| Trailing window | Usable months | Mean ΔLF | Breakeven |
|---|---:|---:|---:|
| 3 months | 3 | −300.3k | −288.0k |
| 6 months | 6 | −228.5k | −219.1k |
| 9 months | 7 | −202.4k | −194.1k |
| 12 months | 9 | −63.1k | −60.5k |
| 18 months | 15 | −56.8k | −54.5k |
| 24 months | 20 | −37.0k | −35.5k |

The step between nine and twelve months is August and September 2025 entering
the window at +338k and +511k. **Negative on every window — the conclusion is
robust and the magnitude is not**, so the dashboard plots six and twelve
together rather than choosing one silently. October 2025 costs two months of
change on its own, because a null level nulls the changes on both sides of it. Population grew +1,497k over
the year while the labour force fell — participation, not employment, is doing
the work.

## 3. Cross-survey consistency, Okun form

Regressing the three-month change in U-3 on three-month annualised payroll growth,
1960-2026 excluding 2020-21:

```
d(U-3, 3-mo) = +0.196 - 0.1197 * payroll growth (3-mo annualised %)
n = 771    R2 = 0.541
```

The regression's implied flat-unemployment growth rate is **1.64% annualised,
about +217k/month** — the *historical* breakeven, and now badly stale for the
reason in section 2. The residual is the useful part:

| | payroll growth | actual dU | implied dU | residual |
|---|---:|---:|---:|---:|
| Mar 2026 | +0.55% | -0.10pp | +0.13pp | -0.23pp |
| May 2026 | +1.07% | -0.10pp | +0.07pp | -0.17pp |
| **Jul 2026** | +0.15% | -0.20pp | +0.18pp | **-0.38pp** |

Unemployment is falling far faster than the payroll move implies. That is the
shrinking denominator showing up a second, independent way — the accounting
identity in section 2 and this regression agree.

## 4. How often the headline means anything

The release states a 90% confidence interval of **+/-122,000** on the monthly
change in total nonfarm employment (July 2026 technical note, verbatim). Applying
it to the whole history:

| Window | n | Distinguishable from zero |
|---|---:|---:|
| Full history (1939-) | 1050 | 69.4% |
| Since 1990 | 439 | 70.8% |
| Last 10 years | 120 | 73.3% |
| **Last 24 months** | 24 | **33.3%** |

Two-thirds of recent prints cannot be distinguished from no change, against
roughly 70% historically. The rolling share is a chart in its own right.

**The household-survey figure is not in the release.** The technical note gives
+/-425,000 for the monthly change in the unemployment *level* and +/-0.3pp for the
*rate*. The +/-650,000 for household employment that circulates in both external
proposals is not sourced from this document and must not be displayed until it is.

## 5. Revisions, from the vintage matrix

`PAYEMS` carries 858 vintages from 6 May 1955, so genuine first prints run from
February 1955. A month only has a real first print if its earliest vintage is
within three months of the observation — older months' "first" vintage is a much
later one and produces nonsense revisions if not filtered.

| Window | n | Mean revision | Mean **absolute** revision |
|---|---:|---:|---:|
| All (1955-) | 858 | +18.3k | 87.5k |
| Last 10 years | 127 | -11.9k | 88.7k |
| Last 12 months | 12 | -30.9k | 47.4k |
| 2026 to date | 7 | -15.9k | 44.1k |

**Mean absolute revision first-to-latest is 87.5k, not the ~51k quoted in the
Codex note.** The difference is the annual benchmark: 51k is roughly
first-to-final (two sample-based revisions), 87.5k includes the benchmark rewrite.
Both belong on the page, distinctly labelled, or the uncertainty is understated.

2026 reproduces exactly from the vintages, and the rolling 12-month mean revision
is now **-31k**, having been -52k in March:

| Month | First reported | Latest | Revision |
|---|---:|---:|---:|
| Jan | +130k | +160k | +30k |
| Feb | -92k | -156k | -64k |
| Mar | +178k | +214k | +36k |
| Apr | +115k | +148k | +33k |
| May | +172k | +63k | -109k |
| Jun | +57k | +20k | -37k |
| Jul | -23k | -23k | not yet revised |
| **Total** | **+537k** | **+426k** | **-111k** |

Is the revision predictable? Weakly. Consecutive revisions autocorrelate
**+0.205** (n=857, real at that sample size but ~4% of variance). Revisions do
**not** depend on the size of the first print: `revision = 19.2 - 0.008 * first
print`, **R2 = 0.003**. The claim that initial estimates systematically overshoot
at cycle tops does not hold as a linear function of the print, so an
expected-revision band may use the rolling mean but must not be scaled by the
headline.

## 6. Wage growth against tightness, not unemployment

Correlation with year-over-year average hourly earnings, n=208, excluding 2020-21:

```
V/U ratio   +0.848        U-3   -0.676
AHE yoy = 1.62 + 1.76 * V/U      R2 = 0.719
```

Vacancies per unemployed person explains wage growth far better than the
unemployment rate — the post-2020 result, reproduced here on this data. July's
residual is **-0.32pp**: wage growth running below what tightness implies.

This panel reads JOLTS on the payroll page, so it must carry the JOLTS release
date, not the Employment Situation stamp.

## 7. The employment-population ratio is entirely participation

EPOP = participation x (1 - u) is an identity, so the move decomposes exactly:

```
Jul 2025 -> Jul 2026:   EPOP 59.6 -> 58.9   (-0.70pp)
    participation  -0.77pp    unemployment  +0.12pp    residual  -0.06pp

Jul 2024 -> Jul 2026:   EPOP 60.0 -> 58.9   (-1.10pp)
    participation  -1.25pp    unemployment  +0.06pp    residual  +0.08pp
```

The whole decline is participation. Costs nothing: all three series are already
on the page. Add prime-age (80.4% in July 2026 *and* July 2025, against total
EPOP 59.6 -> 58.9) and the demographic reading is unavoidable.

## 8. Churn against net change

July's -23k is the residual of **233.5k of gross sector movement**:

| Month | Net | Gross | HHI | Three largest moves |
|---|---:|---:|---:|---|
| Feb 2026 | -156.0k | 201.8k | 1620 | USEHS -49, transport -46, leisure -31 |
| Mar 2026 | +214.0k | 280.9k | 1718 | USEHS +95, leisure +44, USPBS +28 |
| Apr 2026 | +148.0k | 191.5k | 1982 | USEHS +67, transport +39, retail +24 |
| May 2026 | +63.0k | 117.1k | 2085 | leisure +42, USEHS +24, finance -20 |
| Jun 2026 | +20.0k | 194.6k | 1717 | USEHS +54, leisure -43, USPBS +34 |
| Jul 2026 | -23.0k | 233.5k | 1240 | **government -53**, leisure -40, USEHS +25 |

HHI is over the shares of gross movement, x10,000. July is the *least*
concentrated month of the six — the weakness is broad, and invisible in a
net-change chart.

## 9. The JOLTS flow identity is a slow check, not a monthly one

Hires minus total separations against the CES payroll change, n=308:

```
correlation  +0.657      mean gap  +3.6k      sd of gap  936k
```

Essentially unbiased and hopelessly noisy month to month. Useful only as a 3- or
12-month consistency check. July happens to align: -18k against -23k.

---

## 10. Tested and rejected

### The claims-based payroll nowcast does not work

Fitted 1990-2026 excluding 2020-21, n=415:

```
level IC                  R2 = 0.336
level IC + dCC            R2 = 0.487
dIC + dCC                 R2 = 0.263
level IC + level CC       R2 = 0.337
dIC + dCC + level IC      R2 = 0.488   <- best in sample
```

Out of sample it is not merely weak, it is inverted:

```
2026-05   claims-implied +270k    actual  +63k
2026-06   claims-implied +217k    actual  +20k
2026-07   claims-implied +300k    actual  -23k
```

The relationship has structurally broken. Correlation of the insured claims rate
with payroll growth, by decade:

```
1970s -0.557   1980s -0.608   1990s -0.691   2000s -0.832   2010s -0.151   2020s -0.023
```

A scale-free specification (payroll growth as a percent of employment on the
claims rate) gives **R2 = 0.053** over n=643. The best level model has a residual
sd of 144k, i.e. a 90% band of +/-237k — *wider than the +/-122k sampling interval
it was meant to reduce*. **Do not build this panel.**

### But its residual is a real signal

Actual minus claims-implied, level model, n=415, sd 143k. The most negative
readings on record:

```
2009-07  -570k      2009-12  -495k      2026-02  -415k      2025-10  -363k
2025-08  -319k      2008-11  -317k      2026-07  -314k      2025-12  -312k
```

Five of the eight are from the last fourteen months; the other three are the
trough of the financial crisis. 2026 by month:

| | residual | z | percentile |
|---|---:|---:|---:|
| Jan | -137k | -0.96 | 15.7 |
| Feb | -415k | -2.89 | 0.5 |
| Mar | -83k | -0.58 | 26.5 |
| Apr | -152k | -1.06 | 13.5 |
| May | -210k | -1.46 | 7.5 |
| Jun | -201k | -1.40 | 7.7 |
| **Jul** | **-314k** | **-2.19** | **1.4** |

This is the quantitative signature of a low-firing, low-hiring market: weakness
that never passes through unemployment insurance. **Build the wedge as a
diagnostic; never the forecast.**

### Do not derive the unit-labour-cost wedge

(AHE growth - productivity growth) correlates only **+0.732** with published
`ULCNFB` growth, n=77 — different compensation concept, different sector coverage.
Plot the published series against wage growth instead. It also finally consumes
`OPHNFB` and `ULCNFB`, which are fetched, validated and displayed nowhere.

```
2026-04   wage +3.57%   productivity +2.24%   derived wedge +1.33pp   published ULC +1.43%
```

### The free diffusion proxy tracks direction but not level

Breadth across the 13 private supersectors already in the catalog, against the
BLS 250-industry index, 2007-01 to 2026-07, n=235:

```
count breadth              corr +0.883
employment-weighted        corr +0.845
both smoothed to 3 months  corr +0.925
```

Good enough for direction. But the level is badly biased, because 13 large
aggregates almost always move:

```
2026-04  proxy 69.2   BLS 54.6        2026-06  proxy 38.5   BLS 53.2
2026-05  proxy 76.9   BLS 54.2        2026-07  proxy 69.2   BLS 51.8
```

So the proxy is usable immediately as a z-scored direction measure, and the real
series is still required to say "51.8, just above the neutral 50 line".

### The Sahm rule is not worth a panel

It is a pure transformation of `UNRATE`, already on the page; it reads **-0.03**
for July 2026 and will say nothing until a downturn; and it has a documented
false positive on this very series — real-time 0.53 in July 2024 rising to 0.57
in August, with no recession following. A threshold badge would assert what the
number does not support. The real-time against current-vintage comparison, the
one version that fits this system's thesis, diverges by at most about 0.08 points.

---

## 11. Benchmark status

The preliminary March 2026 benchmark revision, published 28 August 2026, is
**-79,000 total nonfarm and -178,000 total private**. Official estimates are
*not* updated for it; the final benchmark arrives with the January 2027
Employment Situation in February 2027. Until then it is a pending annotation with
no series behind it, and the page needs a generic annotation layer to carry it —
not a per-dashboard branch.

## 12. Build order implied by all of the above

1. Add the FRED series in section 1. No engine work, unblocks most of the rest.
2. Revision and uncertainty panel — every vintage is already stored.
3. Breakeven growth and the EPOP decomposition, with the January break handled.
4. BLS adapter, then `LNS16000000`, real earnings, diffusion, SA marginal attachment.
5. V/U wage curve, claims wedge, churn/HHI, JOLTS identity as a 12-month check.
6. Annotation layer for the benchmark and population-control markers.
