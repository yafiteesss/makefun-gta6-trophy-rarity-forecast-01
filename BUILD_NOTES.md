# Build notes — gta6-trophy-rarity-forecast-01

## Method

`main.py` (Python 3.13 stdlib only, no network, no randomness) forecasts each
trophy's Exophase earn rate at the case's target as five quantiles:

1. **Shape.** A trophy's earn rate is the share of tracked players who have
   earned it — a saturating curve as players progress and new players keep
   joining. Per trophy, a weighted least-squares line of `logit(rate)` on
   `x = ln(1 + hours since 2026-11-19T00:00:00Z)`: logit-linear in log-time
   is the log-logistic time-to-earn shape, so it extrapolates far more
   honestly than a line in time and saturates toward 100% instead of
   blowing past it.
2. **Reads.** Only the case's *distinct* reads enter the fit (consecutive
   identical reads are Exophase's frozen cache, not new information), only
   the last 24 hours of them (the shape bends as the launch ages, so the
   most recent day is the best guide to the next four), recency-weighted
   with a 24 h half-life.
3. **Level + slope.** Anchored at the last read: the level comes from the
   last observed rate, the slope from the fit. The slope is shrunk toward
   the median slope of the trophy's tier (platinum/gold/silver/bronze),
   prior weight 3 reads, clamped to [-1.5, 3]. Fewer than 2 distinct reads
   in the window → slope 0 (persistence). Anchoring matters: the unanchored
   (fitted-intercept) variant scored 3.15 on the linear-time world vs 0.82
   anchored.
4. **Spread** (logit units): `sqrt(random_walk^2 + resid^2 + jump^2)` —
   random walk `0.5 * sqrt(horizon in days)` (the house baseline's), the
   trophy's fit residual (floored 0.05), and a refresh-jump allowance: the
   pooled median absolute logit change between consecutive distinct reads
   (0.35 when the history shows no refresh at all, as on launch night —
   the 04:30Z refresh moved every rate but the one at 100%).

## Local validation

Scoring is the contest's mean pinball loss on the logit scale. Synthetic
backtest: plausible Exophase worlds (players tracked grows logistically,
each trophy's earners follow a saturating curve, reads freeze between
refreshes every 3–9 h), a deadline-like case cut at t=60 h, target t=168 h.
Two world shapes — saturation in log-time (favouring the logit-linear
model) and in linear time (favouring nothing in the entry) — 5 seeds each
(the shipped `main.py` itself is run, so these numbers describe the code
as submitted):

| | log-time worlds | linear-time worlds | mean |
|---|---|---|---|
| This entry | **0.217** | **0.756** | **0.487** |
| House persistence baseline (kit starter) | 0.723 | 1.871 | 1.289 |
| House curve baseline (logit-linear, last 24 h) | 0.215 | 1.068 | 0.648 |

The entry beats the persistence baseline everywhere and the curve baseline
in the aggregate (and by 29% on the linear-time worlds, where it is tied on
the log-time worlds). The house model forecast (superbot) is not public,
so it cannot be compared locally.

Practice cases (p00/p01): both outputs valid shape (55 rows, five finite
non-decreasing quantiles in (0, 100]), byte-identical across two runs,
~0.05 s per case-set (limit 8 s per case). Practice pays nothing and its
answers are not in the kit, so they are checked for validity/determinism/
runtime only — except one aggregate sanity check: the p00 medians imply
5,716 trophies earned at 3,868 players, vs the actual 4,276 after the
launch-night refresh. A flat history cannot foresee a refresh; the entry
does not distort its final-case model to chase the practice.

## Improvement iteration

- **v1** (E/P decomposition: separate log-linear fits of earners and
  players tracked): synthetic loss 4.62 — the log-linear extrapolation of
  a saturating count blows past 100%. Rejected. The bug hunt also caught
  a wrong epoch constant for 2026-11-19T00:00:00Z in v1.
- **v2** (logit-linear on all history, jump term): 0.222 / 1.255.
- **v3** (shipped; 24 h fit window): 0.217 / 0.756. The sweep behind it
  (10 seeds × 2 shapes): window 24 h beat 36 h (0.508 vs 0.548 overall)
  and 48 h (0.633); keeping the jump term beat dropping it (0.508 vs
  0.518); narrowing the random walk to 0.7× won the log-time worlds
  (0.151) but lost the linear-time ones badly (1.38) — rejected, the real
  world is misspecified and a narrow spread is punished for it.

## Known weaknesses

- The model only sees the case file; it cannot use any live Exophase read
  past the deadline, and the final case's history (2.5 days, 10-minute
  reads) is richer than the practice's — the 24 h window and the jump
  allowance are tuned on synthetic worlds, not on real final data.
- If Exophase's refresh cadence changes (e.g. no refresh in the last 24 h
  before the deadline), the fit falls back toward persistence and the
  spread leans on the 0.35 prior.
- Trophy 2 sits at 100% in the practice history; the model keeps it near
  99.99% with a tight spread. If new players dilute it below 100% by the
  target, that row will miss.
