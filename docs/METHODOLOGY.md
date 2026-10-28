# Signal calculations and interpretation

## Price versus signal candles

A latest quote is independent of the completed daily OHLCV used for signals. A polled quote does not fabricate or update an unfinished candle. Stock prices, histories and index/sector proxies come from Yahoo Finance. Quote source/time, retrieval time and candle date are all displayed. Missing candles stay missing and suspend directional labels when detected. On the explicit switch to Yahoo, the prior source’s generated history may be replaced by older Yahoo bars; subsequent Yahoo refreshes retain newer cached Yahoo history.

NSE sessions use Asia/Kolkata; US uses the provider’s America/New_York timezone, including DST; crypto candles close at UTC midnight. Daily candles in progress are excluded. Weekly bars group by Monday-start week: first open, maximum high, minimum low, last close, sum volume. The latest week can be provisional and changes as completed daily bars arrive. A partly observed weekly volume ratio is not directly comparable to a completed week; the UI marks the weekly read provisional.

Stale or provider-gap history suspends the directional label as **Check data first**. The underlying values remain inspectable, with their date. This does not guarantee every historical gap or corporate-action issue has been discovered.

## Indicator definitions

- **RSI 15:** Wilder smoothing of 15 gains/losses. First result after 16 closes. Initial arithmetic mean; subsequent `(previous × 14 + current) / 15`. The yellow line is a 14-period SMA of this RSI; Stoch RSI separately uses RSI 14. No losses with gains gives 100; no gains with losses gives 0; both zero gives 50.
- **Stoch RSI 14/14/3/3:** 14 valid RSI values normalised between their min/max; SMA 3 produces K and another SMA 3 produces D. Display 0–100. A flat RSI range gives 50. Warm-up gaps stay missing.
- **SMA 20/50/200:** chart lines use the selected timeframe. The mean-reversion signal always uses 200 completed daily closes, including in weekly view. Two years of daily data does not supply 200 weeks.
- **ATR 14:** Wilder smoothing of true range = max(high−low, |high−previous close|, |low−previous close|). First bar uses high−low.
- **Volume ratio:** latest completed bar volume / arithmetic mean of the preceding 20 bars, excluding the latest. Zero/absent baseline is unknown.
- **Period move:** `(latest close / preceding close − 1) × 100`. Daily uses daily closes; weekly uses weekly closes. It is not change from the open or the latest live quote.
- **Trailing 3/20 moves:** descriptive close-to-close returns across 3/20 selected bars, not forecasts.

## Eight custom screening conditions

Green means the user's condition matched. Contrarian conditions can match while price or momentum is falling. They are not confirmation that buying has begun, and their count is not a probability. Each component contributes at most one point; demand confluence affects shortlist order without adding duplicate points.

| Component                | Green (+1)                                                                                                                         | Red (−1)                                    | Neutral / unavailable                                                                     |
| ------------------------ | ---------------------------------------------------------------------------------------------------------------------------------- | ------------------------------------------- | ----------------------------------------------------------------------------------------- |
| RSI 15 recovery          | RSI was strictly below 35 in the previous 30 selected-timeframe bars; current RSI is strictly above 40 and above the preceding RSI | RSI falling and below 40                    | Other cases 0; no current/prior valid RSI unavailable                                     |
| Stoch RSI 14/14/3/3      | K ≤20 OR K lower than preceding K                                                                                                  | No automatic negative vote                  | Other cases 0; missing K/D/prior values unavailable                                       |
| Volume                   | Ratio ≥1.3 and positive close change                                                                                               | Ratio ≥1.3 and negative close change        | Otherwise 0; unusable volume unavailable                                                  |
| 200-day mean reversion   | Latest completed daily close below 200-day SMA                                                                                     | No automatic negative vote                  | At/above 0; fewer than 200 daily closes unavailable                                       |
| Supply & demand          | Inside valid demand or ≤3% above its upper edge                                                                                    | Near supply within 3% with no nearby demand | Both nearby stays green with a supply warning; distant bands 0; no valid band unavailable |
| 3 / 7 / 14 rising        | Any available window has a positive net close change                                                                               | All three available and negative            | Otherwise 0; no usable window unavailable                                                 |
| >1% move                 | Strictly greater than +1% from preceding completed close                                                                           | Strictly below −1%                          | Otherwise 0; no preceding close unavailable                                               |
| Support retest & rebound | Fresh confirmed pattern (details below)                                                                                            | Later support failure                       | Forming, absent or expired 0; insufficient history unavailable                            |

A recent RSI dip uses 30 preceding daily bars in daily view and 30 preceding weekly bars in weekly view. The Stoch low threshold is K ≤20; falling K can turn green even when above 20 or below D. Read actual direction alongside the match. The 200-day gap is `(daily SMA200 / latest daily close − 1) × 100`, the upward gap to the current moving reference when below it, not a forecast target. The line and price can both continue down.

Floating-point tolerance excludes a mathematically exact +1% move. The balance ≥+2 is **Buy-side lean**, ≤−2 **Sell-side lean**, otherwise **Mixed / wait**. Five components are required for the lean; fewer gives **Limited evidence**. Green demand independently qualifies for the long shortlist even when fewer components are available. Missing, stale or known-incomplete history always excludes candidates and suspends the lean.

**Period-trend meaning:** daily compares the latest close with the close at or before 3/7/14 calendar days earlier. Baselines more than seven days before an anchor are unavailable. Weekly uses 3/7/14 weekly bars. A red final candle does not cancel a positive net move; missing windows stay unknown. Actual 7/14-window high touches, closing highs and breakouts remain separate contextual data, without changing this vote.

## Automatic demand and supply bands

The app searches up to 180 selected-timeframe bars and offers two complementary methods. There is no learned imitation of the user’s manual examples and no proof of resting buy/sell liquidity.

**Base + departure:**

1. Find a 2–4-bar compact base whose high-low range ≤1.3 origin ATR and mean candle body ≤0.55 ATR.
2. Confirm using the next three known bars. A demand departure must close at least 1.4 ATR above the base high at some point; supply must close at least 1.4 ATR below the base low. At least one departure candle body must move in that direction by ≥0.8 ATR.
3. Demand spans the base’s lowest wick to its highest body edge. Supply spans its lowest body edge to highest wick. Very narrow bands receive 0.05 ATR padding on each side. Reject widths >1.5 ATR.
4. The band is not confirmed until all three following bars are known. A displayed confirmation date records this delay.
5. Invalidate if any later close after the origin, including confirmation bars, crosses >0.25 origin ATR beyond the far edge. Demand currently wholly above price or supply wholly below price is excluded.

**Repeated reactions:**

1. Confirm local low/high pivots with three bars on either side. The latest three bars cannot be confirmed pivots.
2. Cluster by price within 0.7 latest ATR (minimum 0.1% of latest close), using each cluster’s lowest pivot as the bound.
3. Require at least two reactions spaced five bars apart; pad the cluster price range by 0.15 latest ATR.
4. Confirm at the last pivot +3 bars. Apply historical invalidation and current-side rules as above. For invalidation the pivot-origin ATR is used.

**Evidence and selection:** retests are episodes of candle-range overlap after confirmation, not individual bars; consecutive overlaps count once. Fresh means zero later retest episodes. Quality rank = min(departure ATR,4)×1.5 + min(separated pivot count,3) + max(0,2−bars since confirmation/90) + 1 if fresh, minus a retest penalty `min(retests, 0.5×retests+1)`. Non-overlapping candidates are selected per kind, prioritising candidates within 8% before quality and distance, up to three demand and three supply. This rank is not a probability. Repeated-pivot touch counts and later retest episodes are different measurements.

SMA overlaps within 0.15 origin ATR are listed. Overlaps between separately calculated daily and weekly bands are annotated without adding another directional point. The chart overlays up to two candidates of each kind and all manual levels. Price bands start at their origin; horizontal edge guides are current reference levels. No claim of point-in-time backtest performance is made. ATR clustering tolerances can change as history grows.

Manual bands are saved independently. They are crossed when current close is below demand’s low or above supply’s high, and excluded while crossed. They can reactivate on recovery; they do not adopt the automatic bands’ historical invalidation rule.

## Markets, groups and correlation

Your NSE research groups are personal groupings, not formal NSE industry classifications. Group movement is an equal-weight average of the latest completed session changes among loaded tracked names; coverage and mixed dates are exposed. It is not investable sector-index performance, full-exchange breadth or a market-cap-weighted return. Buy/sell counts use the daily technical lean; missing/stale data cannot count as a confirmed directional lean.

US context uses S&P 500, Nasdaq Composite and Invesco XLG as an ETF proxy for the S&P 500 Top 50 Index. The ten company list is curated, not a live top-ten ranking. Sector ETFs provide high-level US sector movement. Crypto TOTAL is a global market-cap snapshot; its 24h change is different from a completed UTC daily candle return.

Cross-market correlation is Pearson correlation of simple daily close returns. Match both return-ending dates and preceding candle dates so missing bars cannot silently pair a multi-day return with a one-day return. Use up to 60 matched intervals, with ≥20 observations and nonzero variances required. No interpolation, filled holiday prices, currency conversion, statistical significance claim or causality inference. Close times differ across NSE, US and crypto, so matched date labels do not imply simultaneous returns or a lead/lag trading relationship. Start/end dates and sample count are shown.

## Financial explanations and AI

Annual figures preserve currency and fiscal end dates. YoY is comparable only with a positive previous base, matching currency and 300–430 days between annual period ends. Revenue, profit/EPS, equity, operating cash, free cash and borrowings each receive a deterministic plain-language explanation and conditional implications for a price thesis. Debt is not automatically bad, especially for financial firms. Growth can already be priced in; valuation, expectations, earnings quality and original filings still matter. These are not earnings-surprise measurements, fair-value estimates or standalone buy/sell signals.

Optional AI receives the selected-timeframe technical facts, both daily/weekly readings, annual company figures/explanations, matched headlines, sampled attention and the stock’s tracked sector context. Positions, costs and journal text are excluded. Ollama, Gemini, OpenAI and Groq share the same fact catalog and server validation. Ollama defaults to Qwen3 8B and offers other installed chat models only when the user enables them. Embedding-only and cloud-hosted tags are excluded; there are no automatic model downloads or claims of specialist finance validation.

Gemini uses generateContent with a JSON response schema; OpenAI uses Responses with strict structured outputs and store=false; Groq uses its own OpenAI-compatible Chat Completions endpoint with strict structured outputs on the supported catalog. Each request uses the exact provider/model selected on the stock. Free/paid preferences do not change provider billing; a Gemini free preference hides paid-only models. Account quotas, region access and actual billing apply. There are no automatic retries, cross-provider fallbacks, background generation calls or search/tool charges from the app. Usage token counts are stored when returned; no estimated monetary charge is fabricated. Metadata-only connection checks cannot confirm available billing credit or future generation access.

Models select IDs from an app-rendered fact catalog, counterpoints, unknowns and follow-ups. Schema enums and server validation reject unsupported IDs. The app renders every factual sentence and figure, preventing the model from rewriting units, dates or price-to-zone direction. Selection can still be incomplete or unhelpful. Source/headline claims are not independently verified. Headline text is untrusted evidence, not instructions. A saved analysis records provider/model, generation time, timeframe, candle date, selected IDs and source inputs; it never updates silently.

Reference sources and setup links: [DATA_SOURCES.md](DATA_SOURCES.md).

## Attention and wording

News and Reddit RSS samples compare rolling 7-day matched-item counts with the preceding 7 days. Duplicate titles/post IDs are removed; entity matching and selected investing communities reduce irrelevant results. They cannot establish completeness, unique users, the number of comments, bots or consensus. Feed caps and failed fetches are disclosed. A zero baseline gives no percentage ratio. UTC date bars include partial edges.

Sentiment is presented as title wording, with visible positive/negative/mixed/unclear counts. Explicit English phrases are used; questions and locally negated phrases remain unclear. This is a rough reading aid with no validated accuracy or sentiment model, and does not change technical signal scores. No claim of an exploitable trading edge is made.

Google trending RSS reports limited topics with approximate traffic labels. A missing stock match is not a zero-search observation. Optional Google Trends CSV imports show normalized 0–100 series. They require one identifiable company term, finite 0–100 values, no duplicate dates, and at least 14 completed daily or 8 completed weekly periods. Below-1 values are unknown rather than filled. Missing intervals or stale data suspend the trend label. Mean interest over the latest 7 daily/4 weekly points is compared with the prior equal window. Different exports have different normalization and cannot be compared as absolute volumes.

## Support retest and rebound

The eighth component requires 60 selected-timeframe bars. Two local troughs are confirmed only after two later bars, with strict variation to reject flat floors. Daily spacing is 5–60 bars; weekly spacing 3–26. The latest trough must be within 15 daily/6 weekly bars. Low-price tolerance is max(1% of the floor, 0.5 ATR), capped at 3%. The prior dip and intervening rally each need at least max(3% of the floor, 1.5 ATR).

A strong response has an upward body ≥0.8 ATR, closes in the upper quarter of its range, and exceeds the previous close. Current rebound must be at least max(2%, 1 ATR) above the second low with recent upward participation in price. Confirmation also requires a close above the intervening high +0.1 ATR, price above SMA 50, and SMA 20/50 above their values five bars earlier. The first bar meeting confirmation is recorded only when its required right-hand trough bars exist. A daily trigger stays current for five bars, a weekly one for two. Later closes below the support floor −0.25 tolerance fail the pattern. Confirmed +1; failed −1; forming/absent/expired 0; insufficient history unknown. Volume confirmation is reported separately and is not required twice. These defaults have no validated predictive performance.

## Long candidates and stock-centered sector context

The shortlist excludes stale/missing/known-incomplete history. Green demand qualifies automatically. Demand plus both a positive 3/7/14 trend and a >1% move ranks first; either extra match ranks next; demand alone follows. Other green rules require five available components and follow demand setups. The overall setup score below combines daily/weekly alignment and rule balance with those demand preferences. Raw rule balance, confirmed retest and matched count break score ties. Supply warnings remain visible even when demand is green. These rankings are the user’s research preferences, not measured expected returns.

AI is generated only for the selected stock. Its sector comparison uses same-market tracked industry peers when at least three are tracked, otherwise its personal research group. A numeric comparison requires the target and at least two peers with fresh, complete history on the target candle date. Equal-weight daily changes include the target, so the comparison is descriptive and not independent evidence. Exact source dates, sample size, custom grouping and missing context are disclosed. Mandatory sector and available attention facts remain in the concise stock brief.

The primary RSI chart uses Wilder RSI 15 with its 14-period SMA smoothing line, matching the chosen chart setup. Stoch RSI continues to use its own RSI 14 / stochastic 14 / K 3 / D 3 calculation. RSI relative to the smoothing line and new crosses remain context; the RSI vote uses the below-35, above-40 recovery rule described above.

NSE daily repairs use Yahoo hourly data only: seven unique valid regular-session start times at 09:15 through 15:15 IST, no missing OHLCV values, nonnegative volume and valid OHLC bounds. No present-day session is aggregated before 15:40 IST. Only explicitly missing recent daily values are replaced. Session open/maximum high/minimum low/final close are recorded. Yahoo’s reported daily volume is preferred; otherwise valid hourly volume is summed (non-flat stock hours with zero volume are rejected). All repairs have provenance, with provenance and auction/final-provider differences disclosed. Incomplete session sets remain missing.

### Candidate setup score

Candidates are sorted by the overall setup score out of 100, descending. Demand contributes 45 points; any positive 3/7/14 period with demand contributes 20; a >1% move with demand contributes 20; the eight-rule balance maps −8…+8 to 0…10; daily and weekly buy-side alignment contributes 5. These are user-preference screening weights, not calibrated probabilities or expected returns. Rank numbers refer to the current market/filter view. The score breakdown is expandable on each card.

Compact period labels show each 3D/7D/14D result in green or red separately (weekly uses W). Flat and missing periods are neutral; percentages and baseline dates are available in hover descriptions. A green zone match is labelled Demand zone and shows only demand distance; supply remains a separate warning.
