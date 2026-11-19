"""GTA VI trophy-rarity forecaster (gta6-trophy-rarity-forecast-01).

Forecasts, for every trophy of Grand Theft Auto VI on PlayStation 5, its earn
rate on Exophase at the case's target, as five quantiles, scored by pinball
loss on the logit scale.

Method
------
A trophy's earn rate is the share of tracked players who have earned it: a
saturating curve over time, as players progress through the game and new
players keep joining. The model fits, per trophy, a line of logit(rate)
against x = ln(1 + hours since the release day began, 2026-11-19T00:00:00Z):

* logit(rate) is linear in log-time for a log-logistic time-to-earn
  distribution, which is the natural shape for "share of players who have
  reached this point by now". A linear fit in log-time therefore
  extrapolates far more honestly than a linear fit in time, and it
  saturates: the rate approaches 100% asymptotically instead of blowing
  past it.
* The fit runs over the case's distinct reads only (consecutive identical
  reads are Exophase's frozen cache, not new information), recency-weighted
  with a 24 h half-life, and only over the last 24 hours of reads: the
  launch's shape bends as it ages (a trophy's rate saturates in log-time,
  and the player mix changes), so the most recent day is the best guide to
  the next four. It is anchored at the last read: the level comes from the
  last observed rate, the slope from the fit. The slope is shrunk toward
  the median slope of the trophy's tier (platinum/gold/silver/bronze),
  prior weight 3 reads, and clamped to [-1.5, 3]. With fewer than 2
  distinct reads in the window the slope is 0 (persistence).
* Median rate at the target: inv_logit(logit(last rate) + slope * (x_target
  - x_last)), clamped to [0.01, 99.99].

Spread (logit units): sqrt(random_walk^2 + resid^2 + jump^2), where the
random walk is the house baseline's 0.5 * sqrt(horizon in days), resid is
the trophy's fit residual (floored at 0.05), and jump is the pooled median
absolute logit change between consecutive distinct reads (a refresh-jump
allowance; 0.35 when the history shows no refresh at all, as on launch
night). Quantiles are inv_logit(logit(median) + z_tau * spread), rounded to
4 decimals half-up like the kit's starter.

Python 3.13 standard library only, no network, no randomness: two runs on
the same case write byte-identical output.
"""

import json
import math
import os
import sys
from pathlib import Path

# The grader's -P leaves /bot off sys.path: put it back first, so `import model`
# finds a module shipped beside this file (none is shipped; kept for safety).
sys.path.insert(0, str(Path(__file__).resolve().parent))

INPUT_DIR = Path(os.environ.get("MAKEFUN_INPUT_DIR", "/input"))
OUTPUT_DIR = Path(os.environ.get("MAKEFUN_OUTPUT_DIR", "/output"))

LEVELS = [0.05, 0.25, 0.5, 0.75, 0.95]
Z = [-1.645, -0.674, 0, 0.674, 1.645]

# Release day began 2026-11-19T00:00:00Z; x = ln(1 + hours since then).
T0 = 1795046400  # epoch seconds of 2026-11-19T00:00:00Z

HALF_LIFE_H = 24.0   # recency half-life of a read's weight
WINDOW_H = 24.0      # only the last 24 h of reads enter the fit (see docstring)
SHRINK_PRIOR = 3.0   # prior weight (in reads) of the tier-median slope
SLOPE_MIN = -1.5
SLOPE_MAX = 3.0
JUMP_PRIOR = 0.35    # refresh-jump allowance when no refresh is observed
RESID_FLOOR = 0.05
RESID_DEFAULT = 0.15
SPREAD_CAP = 2.5


def parse_time(s: str) -> float:
    """ISO 8601 UTC timestamp to epoch seconds."""
    from datetime import datetime, timezone
    dt = datetime.fromisoformat(s.replace("Z", "+00:00"))
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.timestamp()


def clamp_rate(x: float) -> float:
    return min(99.99, max(0.01, x))


def logit(pct: float) -> float:
    p = clamp_rate(pct)
    return math.log(p / (100 - p))


def inv_logit(lg: float) -> float:
    if lg >= 0:
        return 100 / (1 + math.exp(-lg))
    e = math.exp(lg)
    return 100 * e / (1 + e)


def round4(x: float) -> float | int:
    """x rounded to 4 decimals, half up, as JavaScript's
    Math.round(x * 10000) / 10000 rounds it."""
    scaled = x * 10000
    whole = math.floor(scaled)
    if scaled - whole >= 0.5:
        whole += 1
    value = whole / 10000
    return int(value) if value.is_integer() else value


def wls(xs, ys, ws):
    """Weighted least squares of y on x. Returns (intercept, slope)."""
    sw = sum(ws)
    if sw <= 0:
        return (sum(ys) / len(ys) if ys else 0.0), 0.0
    mx = sum(w * x for w, x in zip(ws, xs)) / sw
    my = sum(w * y for w, y in zip(ws, ys)) / sw
    sxx = sum(w * (x - mx) ** 2 for w, x in zip(ws, xs))
    if sxx <= 1e-12:
        return my, 0.0
    sxy = sum(w * (x - mx) * (y - my) for w, x, y in zip(ws, xs, ys))
    slope = sxy / sxx
    return my - slope * mx, slope


def median(vals):
    s = sorted(vals)
    n = len(s)
    if n == 0:
        return 0.0
    return s[n // 2] if n % 2 else 0.5 * (s[n // 2 - 1] + s[n // 2])


def forecast_case(case: dict, name: str) -> dict:
    if case["levels"] != LEVELS:
        raise ValueError(f"{name} asks for levels {case['levels']}, not {LEVELS}")
    history = case["history"]
    if not history:
        raise ValueError(f"{name} has no history")
    trophies = case["trophies"]
    n = len(trophies)
    horizon_days = case["horizon_minutes"] / 1440.0
    target_x = math.log(1 + (parse_time(case["target"]) - T0) / 3600.0)

    # Distinct reads only: consecutive identical rate vectors carry no news.
    distinct = []
    prev_rates = None
    for read in history:
        rates = tuple(read["rates"])
        if rates != prev_rates:
            distinct.append(read)
            prev_rates = rates
    # Only the last WINDOW_H hours enter the fit (the shape bends with age).
    cutoff = parse_time(distinct[-1]["at"]) - WINDOW_H * 3600.0
    distinct = [r for r in distinct if parse_time(r["at"]) >= cutoff]
    last = distinct[-1]
    last_t = parse_time(last["at"])
    last_x = math.log(1 + (last_t - T0) / 3600.0)

    xs, ws = [], []
    for read in distinct:
        t = parse_time(read["at"])
        xs.append(math.log(1 + (t - T0) / 3600.0))
        ws.append(0.5 ** ((last_t - t) / (HALF_LIFE_H * 3600.0)))

    # --- refresh jumps: pooled median |logit change| between distinct reads
    jumps = []
    for a, b in zip(distinct, distinct[1:]):
        for i in range(n):
            ra, rb = a["rates"][i], b["rates"][i]
            if ra is None or rb is None:
                continue
            jumps.append(abs(logit(rb) - logit(ra)))
    jump = median(jumps) if len(jumps) >= 5 else JUMP_PRIOR
    jump = min(jump, 1.0)

    # --- per trophy: logit(rate) vs x ------------------------------------
    fits = []
    for i, trophy in enumerate(trophies):
        series = []  # (x, w, logit rate)
        for j, read in enumerate(distinct):
            r = read["rates"][i]
            if r is None:
                continue
            series.append((xs[j], ws[j], logit(r)))
        if len(series) >= 2 and len({s[0] for s in series}) >= 2:
            sx = [s[0] for s in series]
            sy = [s[2] for s in series]
            sw = [s[1] for s in series]
            intercept, slope = wls(sx, sy, sw)
            resid = math.sqrt(
                sum(w * (y - (intercept + slope * x)) ** 2 for x, w, y in series)
                / max(sum(sw), 1e-9)
            )
            resid = min(max(resid, RESID_FLOOR), 1.0)
            n_pts = len(series)
        else:
            slope = 0.0
            resid = RESID_DEFAULT
            n_pts = len(series)
        last_rate = None
        for read in reversed(distinct):
            if read["rates"][i] is not None:
                last_rate = read["rates"][i]
                break
        fits.append((trophy, slope, resid, n_pts, last_rate if last_rate is not None else 0.0))

    # Tier-median slopes, for shrinkage.
    tier_med = {}
    for tier in {t["tier"] for t, _, _, _, _ in fits}:
        tier_med[tier] = median([s for t, s, _, _, _ in fits if t["tier"] == tier])

    rw = 0.5 * math.sqrt(horizon_days)
    rows = []
    for trophy, slope, resid, n_pts, last_rate in fits:
        slope_adj = (n_pts * slope + SHRINK_PRIOR * tier_med[trophy["tier"]]) / (
            n_pts + SHRINK_PRIOR
        )
        slope_adj = min(SLOPE_MAX, max(SLOPE_MIN, slope_adj))
        med_logit = logit(last_rate) + slope_adj * (target_x - last_x)
        med = clamp_rate(inv_logit(med_logit))
        spread = math.sqrt(rw * rw + resid * resid + jump * jump)
        spread = min(spread, SPREAD_CAP)
        lg = logit(med)
        qs = [round4(min(99.99, max(0.01, inv_logit(lg + z * spread)))) for z in Z]
        for k in range(1, 5):
            if qs[k] < qs[k - 1]:
                qs[k] = qs[k - 1]
        rows.append({"id": trophy["id"], "q": qs})
    return {"trophies": rows}


def main() -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    for path in sorted(INPUT_DIR.glob("*.in")):
        case = json.loads(path.read_text(encoding="utf-8"))
        forecast = forecast_case(case, path.name)
        (OUTPUT_DIR / f"{path.stem}.out").write_text(
            json.dumps(forecast, separators=(",", ":")) + "\n", encoding="utf-8"
        )


if __name__ == "__main__":
    main()
