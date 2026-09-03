"""Shared helpers for exploratory analysis. Read-only: never writes to the DB."""
import os, csv, io, json, urllib.request, urllib.parse, datetime as dt

def db_current(series_ids):
    """Latest-vintage monthly series -> {sid: {'YYYY-MM': value}}."""
    import psycopg
    out = {s: {} for s in series_ids}
    with psycopg.connect(os.environ["MACRO_DSN"]) as c, c.cursor() as cur:
        cur.execute("""
            SELECT DISTINCT ON (series_id, observation_dt) series_id, observation_dt, value
            FROM macro_observations WHERE series_id = ANY(%s)
            ORDER BY series_id, observation_dt, vintage_dt DESC
        """, (list(series_ids),))
        for sid, d, v in cur.fetchall():
            out[sid][d.strftime("%Y-%m")] = float(v) if v is not None else None
    return out

def db_first_print(series_id):
    """First published value and its vintage, per observation."""
    import psycopg
    with psycopg.connect(os.environ["MACRO_DSN"]) as c, c.cursor() as cur:
        cur.execute("""
            SELECT DISTINCT ON (observation_dt) observation_dt, value, vintage_dt
            FROM macro_observations WHERE series_id=%s AND value IS NOT NULL
            ORDER BY observation_dt, vintage_dt ASC
        """, (series_id,))
        return {d.strftime("%Y-%m"): (float(v), vd) for d, v, vd in cur.fetchall()}

def db_at_vintage(series_id, obs_month, vintage):
    import psycopg
    with psycopg.connect(os.environ["MACRO_DSN"]) as c, c.cursor() as cur:
        cur.execute("""SELECT value FROM macro_observations WHERE series_id=%s
                       AND observation_dt=%s AND vintage_dt<=%s AND value IS NOT NULL
                       ORDER BY vintage_dt DESC LIMIT 1""", (series_id, obs_month, vintage))
        r = cur.fetchone()
        return float(r[0]) if r and r[0] is not None else None

def fred_csv(sid):
    """Keyless FRED CSV -> {'YYYY-MM': value}. For series not yet in the catalog."""
    u = f"https://fred.stlouisfed.org/graph/fredgraph.csv?id={sid}"
    t = urllib.request.urlopen(u, timeout=45).read().decode()
    rows = list(csv.reader(io.StringIO(t)))[1:]
    return {r[0][:7]: float(r[1]) for r in rows if len(r) > 1 and r[1] not in (".", "")}

def bls(ids, y0, y1):
    key = os.environ["BLS_API_KEY"]
    body = json.dumps({"seriesid": list(ids), "startyear": str(y0), "endyear": str(y1),
                       "registrationkey": key}).encode()
    req = urllib.request.Request("https://api.bls.gov/publicAPI/v2/timeseries/data/",
                                 data=body, headers={"Content-Type": "application/json"})
    d = json.load(urllib.request.urlopen(req, timeout=90))
    out = {}
    for s in (d.get("Results") or {}).get("series", []):
        out[s["seriesID"]] = {f'{x["year"]}-{x["period"][1:]}': float(x["value"])
                              for x in s["data"] if x["period"].startswith("M")}
    return out

# ---- plain-python statistics (no numpy in this venv) ----
def mean(xs): return sum(xs) / len(xs)

def ols(y, X):
    """y: list; X: list of lists (rows, no intercept). Returns (coefs incl intercept, r2)."""
    n = len(y); k = len(X[0]) + 1
    A = [[1.0] + list(r) for r in X]
    XtX = [[sum(A[i][a] * A[i][b] for i in range(n)) for b in range(k)] for a in range(k)]
    Xty = [sum(A[i][a] * y[i] for i in range(n)) for a in range(k)]
    # gaussian elimination
    M = [XtX[i] + [Xty[i]] for i in range(k)]
    for c in range(k):
        p = max(range(c, k), key=lambda r: abs(M[r][c])); M[c], M[p] = M[p], M[c]
        d = M[c][c]
        if abs(d) < 1e-12: return None, None
        M[c] = [v / d for v in M[c]]
        for r in range(k):
            if r != c and M[r][c]:
                f = M[r][c]; M[r] = [a - f * b for a, b in zip(M[r], M[c])]
    beta = [M[i][k] for i in range(k)]
    yb = mean(y)
    fit = [sum(beta[j] * A[i][j] for j in range(k)) for i in range(n)]
    ssr = sum((y[i] - fit[i]) ** 2 for i in range(n))
    sst = sum((v - yb) ** 2 for v in y)
    return beta, (1 - ssr / sst if sst else None)

def corr(a, b):
    n = len(a); ma, mb = mean(a), mean(b)
    ca = sum((a[i]-ma)*(b[i]-mb) for i in range(n))
    va = sum((v-ma)**2 for v in a); vb = sum((v-mb)**2 for v in b)
    return ca / (va*vb) ** 0.5 if va and vb else None

def months(a, b):
    """Inclusive month keys from 'YYYY-MM' a to b."""
    y0, m0 = map(int, a.split("-")); y1, m1 = map(int, b.split("-"))
    out = []
    while (y0, m0) <= (y1, m1):
        out.append(f"{y0:04d}-{m0:02d}")
        m0 += 1
        if m0 == 13: y0, m0 = y0 + 1, 1
    return out

def diff(s):
    ks = sorted(s); return {ks[i]: s[ks[i]] - s[ks[i-1]] for i in range(1, len(ks))
                            if _consec(ks[i-1], ks[i])}

def _consec(a, b):
    ya, ma = map(int, a.split("-")); yb, mb = map(int, b.split("-"))
    return (yb - ya) * 12 + (mb - ma) == 1

def ma(s, w):
    ks = sorted(s); out = {}
    for i in range(w - 1, len(ks)):
        win = ks[i-w+1:i+1]
        if all(_consec(win[j-1], win[j]) for j in range(1, w)):
            out[ks[i]] = mean([s[k] for k in win])
    return out
