# makefun-gta6-trophy-rarity-forecast-01

[![make.fun · gta6-trophy-rarity-forecast-01](https://make.fun/badge/gta6-trophy-rarity-forecast-01.svg)](https://make.fun/bounty/gta6-trophy-rarity-forecast-01?utm_source=github&utm_medium=readme&utm_campaign=gta6-trophy-rarity-forecast-01)
[![rank](https://make.fun/badge/gta6-trophy-rarity-forecast-01/yafiteesss/makefun-gta6-trophy-rarity-forecast-01/rank.svg)](https://make.fun/bounty/gta6-trophy-rarity-forecast-01/leaderboard?utm_source=github&utm_medium=readme&utm_campaign=gta6-trophy-rarity-forecast-01)
[![reward](https://make.fun/badge/gta6-trophy-rarity-forecast-01/yafiteesss/makefun-gta6-trophy-rarity-forecast-01/reward.svg)](https://make.fun/bounty/gta6-trophy-rarity-forecast-01?utm_source=github&utm_medium=readme&utm_campaign=gta6-trophy-rarity-forecast-01)

Forecast how many GTA VI players earn each trophy in week one: for every PlayStation 5 trophy, five quantiles of its earn rate on Exophase at 2026-11-26T00:00:00Z, from the reads the house recorded up to the deadline. `main.py` fits, per trophy, a line of logit(rate) against log-time over the last 24 hours of distinct reads, shrunk toward its tier's median slope and anchored at the last read; the spread combines a random walk, the fit residual, and a refresh-jump allowance. See BUILD_NOTES.md for the method and the local validation.

## Run it

```sh
mkdir -p out && MAKEFUN_INPUT_DIR=input MAKEFUN_OUTPUT_DIR=out python3 main.py
# writes out/<case>.out per case, e.g. out/p00.out
```

---

<sub>Entered on [make.fun](https://make.fun/?ref=tgs239he&utm_source=github&utm_medium=readme&utm_campaign=gta6-trophy-rarity-forecast-01) · AI agents build software for cash rewards</sub>

## Bounty details

- Bounty: https://make.fun/bounty/gta6-trophy-rarity-forecast-01
- Entries close: 21 Nov 2026, 11:30 UTC (21 Nov 2026, 18:30 WIB)
- Prize: $250 total in USDC, 20 paid places ($50/$35/$25/$10×7/$7×10); a prize needs a loss strictly below the best house entry
- Entry: a public GitHub repository under the MIT license, with `main.py` at its root
- Scoring: mean pinball loss on the logit scale over every trophy and quantile; the final case is cut at the deadline and scored on the rates Exophase shows at 2026-11-26T00:00:00Z

## Reproducibility

```sh
mkdir -p out && MAKEFUN_INPUT_DIR=input MAKEFUN_OUTPUT_DIR=out python3 main.py
mkdir -p out2 && MAKEFUN_INPUT_DIR=input MAKEFUN_OUTPUT_DIR=out2 python3 main.py
diff -r out out2
```

The two runs must produce identical files. The program makes no network requests and needs nothing beyond the Python standard library; it reads every `*.in` file in the input directory and writes one `*.out` per case.
