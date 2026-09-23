# futspread

Seasonal backtest harness for futures calendar spreads and butterflies,
sourced from WRDS `trdstrm` (`wrds_contract_info` + `wrds_fut_contract`).

Study a pattern like "GC[X][Z1] over [LTD-40, LTD-15]" by overlaying every
historical instance of that spread on a common expiry-relative axis.

---

## Notation

```

Recall your contract letters:

F ~ Jan
G ~ Feb
H ~ Mar
J ~ Apr
K ~ May
M ~ Jun
N ~ Jul
Q ~ Aug
U ~ Sep
V ~ Oct
X ~ Nov
Z ~ Dec


CL[J][K0]        long 1 CL April, short 1 CL May
GC[X][Z1]        long 1 GC Nov, short 1 GC Dec of the NEXT year
NG[J][X0][Z0]    long 1 Apr, short 2 Nov, long 1 Dec   (1, -2, 1)
GC[Z][Z0]        the Dec/Dec twelve-month spread
```

Month codes are the standard `F G H J K M N Q U V X Z` = Jan..Dec.

The trailing digit is the **year offset**, capped at 2. Offset 0 means the
first occurrence of that month strictly after the **previous** leg; offset *n*
adds *n* further years. Resolving against the previous leg (not the front)
keeps butterflies monotonic — `NG[F][Z0][H0]` is Jan Y, Dec Y, Mar Y+1. For a
two-leg spread the previous leg *is* the front, so it reduces to the plain rule.

---

## Quickstart

```bash
python -m futspread download --username <wrds_user>     # ~25-40 min, all 46 series
python -m futspread build "GC[X][Z1]" "NG[H][J0]"
python -m futspread report "GC[X][Z1]" --window=-40,-15
python -m futspread plot   "GC[X][Z1]" --window=-40,-15 --outfile gc.png
```

Data lands in `$FUTSPREAD_ROOT`, default `~/futspread_data`. Every command
also takes `--root PATH`.

---

## Commands

| | |
|---|---|
| `universe` | list the 46 curated series |
| `describe [TICKERS...]` | ticker → description, lot size, **liquid vs illiquid months** |
| `catalog --username U` | **all 3,666** series in the feed, for discovery |
| `download --username U` | pull metadata + bars into the raw tree |
| `months TICKER` | which months a series lists, and which of those trade |
| `liquidity TICKER` | per-month open interest, to see what is really on the board |
| `build ...` | construct combo instances |
| `prune` | delete built combos whose legs are not liquid months |
| `report COMBO` | per-instance P&L and aggregate stats |
| `plot COMBO` | instance overlay + condensed average |

**`download`** `--tickers CL NG` · `--sectors energy metals` · `--min-ltd 2000-01-01`
Partial runs merge: only the contrcodes in the run are refreshed, the rest of
`contracts.parquet` is kept.

**`describe`** is the first thing to run before picking a combo to plot. It
lists the contract months that actually trade (`liquidity TICKER` shows
the per-month open-interest numbers behind the split):

```
ticker sector  exch             description  lot_size                  liquid first_contract last_ltd
    GC metals COMEX           GOLD (100 OZ)    100 oz             G J M Q V Z        1979-01  2032-06
    SI metals COMEX        SILVER (5000 OZ)  5,000 oz               H K N U Z        1973-01  2030-12
    PL metals NYMEX                PLATINUM     50 oz                 F J N V        1973-07  2029-04
    CL energy NYMEX CRUDE OIL (LIGHT SWEET) 1,000 bbl F G H J K M N Q U V X Z        1983-05  2037-01
```

`first_contract` is the earliest LTD in WRDS for the series regardless of
`--min-ltd`, from `raw/series.parquet` (written by `download`); without that
file it falls back to the earliest contract actually downloaded. Where the
vendor LTD is null the last bar date stands in (see Data quirks).

`lot_size` is curated in `universe.py` (trdstrm carries only the unit name).
`--sort sector` · `--liquid-only` · `--min-share 0.05` · `--refresh`
(recompute after a re-download). The scan is cached at
`raw/liquidity.parquet`, so it is instant after the first run.

**`catalog`** `--search WHEAT COCOA` (matches `contrname` or exact ticker) ·
`--min-contracts N` · `--active-since DATE` (filters the *series*, not its
contracts) · `--prefixes N C I` (dsmnem exchange letter: `N` NYMEX/COMEX/ICE-US,
`C` CME/CBOT, `I` CME-IMM, `L` ICE Europe) · `--out cat.csv` · `--limit N`.
Every row carries `in_universe`. To adopt a series, add its `contrcode` to
`_ROWS` in `universe.py` and re-download.

**`build`** takes explicit combo codes, or:
`--ticker GC` (every combo for one series) · `--all` (every downloaded series) ·
`--kind spread|butterfly` · `--max-offset 0..2` · `--consecutive-only`
(butterflies: adjacent months only) · `--dry-run` (count, build nothing) ·
`--all-months` / `--min-share` (see Liquid months) · `--lookback-years 2` ·
`--min-year 2008`

Enumeration sizes across all 46 series, using liquid months:

| `--max-offset` | spreads | butterflies `--consecutive-only` |
|---|---|---|
| 0 | 2,546 | 310 |
| 2 | 7,638 | 2,790 |

`--all-months` takes spreads to 10,668. Unrestricted butterflies reach 340,362
at offset 2 — don't. Always `--dry-run` first; the full spread build is
~15-25 min.

### Liquid months

Existence and liquidity are different things. Gold lists all twelve months,
but the six serial ones (F H K N U X) only list about three months before
expiry and carry ~0.7% of the December contract's open interest. Enumerating
against them produces hundreds of untradeable spreads.

`build` therefore enumerates against **liquid** months by default: for each
contract take its peak open interest, take the median across contracts of the
same month, and keep months at or above `--min-share` (0.05) of the busiest.
The split is unambiguous everywhere checked —

```
GC lists : F G H J K M N Q U V X Z      GC liquid: G J M Q V Z
SI lists : F G H J K M N Q U V X Z      SI liquid: H K N U Z
CL lists : F G H J K M N Q U V X Z      CL liquid: F G H J K M N Q U V X Z
PL liquid: F J N V      HG liquid: H K N U Z      HE liquid: G J M N Q V Z
```

Gold's weakest real month (V, October) sits at 0.126 against a serial ceiling
of 0.009; crude, where all twelve are genuine, floors at 0.67 and loses
nothing. `--all-months` restores the old behaviour. `liquidity TICKER` prints
the table the decision is made from.

The filter applies at **build** time only. `report` and `plot` read whatever
parquet you name, so combos built before the filter existed still work — they
just print a warning first:

```
WARNING: leg month(s) X are not liquid in GC (liquid: G J M Q V Z).
         This spread is unlikely to be tradeable.
```

`prune` clears the stale ones. It is a dry run unless you pass `--yes`:

```bash
python -m futspread prune --tickers GC          # show what would go
python -m futspread prune --yes                 # delete across the universe
```

**`report` / `plot`** `--window` is optional — omit it (or pass `--window=all`)
for the full range, which is the deepest offset that 90% of instances still
reach, out to expiry. Give `--window=-40,-15` to study a specific entry/exit.
Also `--axis td_to_ltd|cal_to_ltd`; `plot` takes `--outfile x.png` and
`--together` (average drawn on the overlay instead of a panel below).

```bash
python -m futspread report "NG[H][J0]"                  # full range
python -m futspread report "NG[H][J0]" --window=-60,-5   # a specific window
```

---

## Python API

```python
from futspread import (build_combo, load_combo, condense, summary, stats,
                       plot_combo, universe, enumerate_specs, parse_combo)

build_combo('GC[X][Z1]')                        # once, after download
df         = load_combo('GC[X][Z1]')
cond, wide = condense(df, window=(-40, -15))    # mean/median/std/se/p_up by offset
per        = summary(df, window=(-40, -15))     # per-instance P&L
stats(per)                                      # n, mean, hit_rate, t_stat
plot_combo(df, window=(-40, -15))
```

---

## Layout

```
$FUTSPREAD_ROOT/
  raw/contracts.parquet             contract metadata for the universe
  raw/prices/<contrcode>.parquet    daily bars, all contracts of one series
  raw/series.parquet                full WRDS span per series (first/last LTD, count)
  combos/<TICKER>/<COMBO>.parquet   every instance of one combo, stacked
```

A combo file holds `instance` (front contract year), `date`, `td_to_ltd`,
`cal_to_ltd`, `settlement`, `volume`, `oi`, `ltd`, `ltd_is_fnd`, `fnd_is_rule`,
`ltd_source`, `ltd_gap_days`, and the untouched per-leg fields `l1_*`, `l2_*`, `l3_*`.

---

## Conventions that matter

- **`contrcode` is the key, not the ticker.** 3,193 tickers cover 3,666 series;
  several US series exist twice (Composite vs Electronic). `universe.py` pins
  the composite where both exist.
- **LTD = min(last trading day, first notice day).** For metals and grains the
  notice date leads by up to a month — GC Jan-24 has FND 2023-12-29 against LTD
  2024-01-29. Livestock, equity and FX are cash-settled, so LTD falls back to
  last trading day.
- **Contract year is not the LTD year.** CL Jan-2025 stops trading 2024-12-19.
  The year is decoded from `contrdate` (MMYY) with the century chosen to sit
  closest to the contract's own last trading date.
- **Only `settlement` is combined.** A spread has no meaningful open/high/low —
  differencing two legs' daily highs is not the spread's high — so raw per-leg
  OHLCV is carried through untouched. Combo `volume`/`oi` are the min across
  legs, a liquidity bound.
- **Alignment is `td_to_ltd`**, trading days relative to LTD, 0 at expiry.
  `cal_to_ltd` is there if you prefer calendar days.
- **Instances whose data stops before LTD are dropped** (`max_ltd_gap_days=7`).
  A live contract's offset 0 is mid-life, not expiry; including it would shift
  every other instance in the overlay.
- **The condenser rebases each instance to 0 at the window start**, so the
  overlay is P&L in price units from a common entry, not a level. Levels are
  not comparable across years; P&L from a common entry is what the trade earns.

---

## Data quirks found the hard way

- **`wrds_fut_contract` holds duplicate bars.** Several rows share one
  `(futcode, date)`, identical in every OHLCV field, differing only in the
  undocumented column `p`. KE, BRN, G, ES, ZN carry up to 5 copies per bar;
  GC, NG, DC, LBS, ARE carry none. `fetch_prices` uses `SELECT DISTINCT` over
  the projected columns — KE drops from 256,150 bars to 63,146. A naive query
  against this table returns a fivefold-duplicated series.
- **Older rows have bars but no dates.** ZW before 2007, ZL before 2007 and HE
  before 2001 (161, 89 and 192 contracts) have `startdate` and full price
  history, but `lasttrddate`, `firstnoticedate`, `sttlmntdate` are all null.
  A `WHERE lasttrddate >= ...` filter silently drops thirty years of wheat.
  `fetch_contract_info` falls back to the contract's last bar (`ltd_source =
  'last_bar'`), and `fetch_prices` selects by `futcode` rather than by LTD.
- **Vendor FND is patchy even where LTD exists.** ZC/KE/ZM/ZO/ZS carry no
  `firstnoticedate` before ~2007, so `ltd` used to fall back to the last
  trading day, 2-3 weeks late. For CBOT/KCBT grains the exchange rule is
  reconstructed instead — last business day of the month before the delivery
  month — and matches the vendor value on every populated row (ZC 112/112,
  ZW 112/112, ZL 164/164). Such rows carry `fnd_is_rule = True`. Holidays are
  ignored, so a rule FND can sit one day late. Metals, softs, rates and
  livestock have the same gap and no rule yet; their pre-~2010 `ltd` is the
  last trading day.
- **Serial months are thin.** Gold lists all twelve months, but F H K N U X
  only start trading ~2 months before expiry, so `GC[X][Z1]` instances are ~45
  trading days long. A window wider than that returns nothing.
- **Equity and rate futures are quarterly** (H M U Z only), so month-pair
  combinations are limited to four. What looks seasonal there is roll and
  cheapest-to-deliver behaviour, not a crop or weather cycle.
- **Lumber has a spec break.** LBS (361) is random-length lumber, 1978 to
  May-2023. LBR (4755) is the 2022 respec. Separate series, do not chain —
  all the seasonal history is in the dead one.

---

## Known gaps

- **Constructed cracks are not supported.** `ComboSpec` legs share one ticker,
  so a 3-2-1 crack (3 CL vs 2 RB vs 1 HO) cannot be expressed. The universe
  does carry exchange-listed crack instruments — ARE, RBB, HOB, GZ — which are
  ordinary series and work with everything here, including calendar spreads on
  the crack itself. Cross-ticker legs would need a per-leg ticker and weight on
  `Leg`, plus a leg-level date join.
- **No costs, no multipliers.** P&L is in quoted price units per 1 combo, not
  dollars. No bid/ask, no commission, no margin.
- **`t_stat` is weak evidence.** A one-sample t over ~20 yearly instances, and
  adjacent years overlap in the underlying curve. Use it to sort, not to test.
- **No minimum-instance gate at build time.** Combos with a single instance are
  written to disk; they show up as `instances: 1` at report time.
- **`6B` (GBP) and `6A` (AUD) are absent** — the feed names them ambiguously and
  I would not guess a contrcode. `ZL` uses the Electronic series (456, 169
  contracts); the composite (3269, 433 contracts back to 1974) is better and
  should probably replace it. `MWE` (1883, Minneapolis spring wheat, back to
  1979) is the obvious missing grain.
