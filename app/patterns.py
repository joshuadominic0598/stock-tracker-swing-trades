"""A causal support-retest screen with explicit, unvalidated default thresholds."""


def support_retest(bars, timeframe="1d"):
    if len(bars) < 60:
        return dict(
            available=False,
            status="unavailable",
            label="Needs 60 bars",
            reading="Needs SMA 50, its prior slope and two confirmed troughs.",
        )
    n = len(bars)
    weekly = timeframe == "1w"
    minimum = 3 if weekly else 5
    maximum = 26 if weekly else 60
    lookback = 52 if weekly else 120
    recent = 6 if weekly else 15
    fresh = 2 if weekly else 5
    last = bars[-1]

    def trend_at(k):
        if k < 5:
            return False
        last, slope = bars[k], bars[k - 5]
        return (
            all(
                v is not None
                for v in (
                    last.get("sma20"),
                    last.get("sma50"),
                    slope.get("sma20"),
                    slope.get("sma50"),
                )
            )
            and last["close"] > last["sma50"]
            and last["sma20"] > slope["sma20"]
            and last["sma50"] > slope["sma50"]
        )

    trend_up = trend_at(n - 1)
    pivots = []
    for i in range(max(2, n - lookback), n - 2):
        low = bars[i]["low"]
        left = [b["low"] for b in bars[i - 2 : i]]
        right = [b["low"] for b in bars[i + 1 : i + 3]]
        if low <= min(left + right) and low < max(left) and low < max(right):
            pivots.append(i)
    for j in reversed(pivots):
        if n - 1 - j > recent:
            continue
        for i in reversed(pivots):
            if not minimum <= j - i <= maximum:
                continue
            first, second = bars[i], bars[j]
            floor = min(first["low"], second["low"])
            atr = second.get("atr") or floor * 0.02
            tolerance = min(floor * 0.03, max(floor * 0.01, atr * 0.5))
            if abs(first["low"] - second["low"]) > tolerance:
                continue
            neckline = max(b["high"] for b in bars[i + 1 : j])
            prior_peak = max(b["high"] for b in bars[max(0, i - 10) : i])
            if prior_peak - first["low"] < max(
                first["low"] * 0.03, 1.5 * (first.get("atr") or atr)
            ):
                continue
            if neckline - max(first["low"], second["low"]) < max(floor * 0.03, 1.5 * atr):
                continue
            if any(b["close"] < floor - tolerance * 0.25 for b in bars[i + 1 : j]):
                continue
            failed = any(b["close"] < floor - tolerance * 0.25 for b in bars[j + 1 :])
            strong = []
            for k in range(j + 1, n):
                b = bars[k]
                a = b.get("atr") or atr
                span = b["high"] - b["low"]
                if (
                    span > 0
                    and b["close"] - b["open"] >= 0.8 * a
                    and b["close"] >= b["low"] + 0.75 * span
                    and b["close"] > bars[k - 1]["close"]
                ):
                    strong.append(k)
            rebound = (last["close"] / second["low"] - 1) * 100
            response = bool(
                strong
                and (n - 1 - strong[-1] <= 3)
                and last["close"] >= bars[strong[-1]]["close"]
                and last["close"] - second["low"] >= max(second["low"] * 0.02, atr)
            )
            # A trough becomes identifiable only after its two right-hand bars have closed.
            breakout = next(
                (
                    k
                    for k in range(j + 2, n)
                    if bars[k]["close"] > neckline + 0.1 * atr
                    and trend_at(k)
                    and any(s <= k and k - s <= 3 for s in strong)
                ),
                None,
            )
            age = n - 1 - breakout if breakout is not None else None
            current_breakout = last["close"] > neckline + 0.1 * atr
            confirmed = (
                not failed
                and response
                and current_breakout
                and trend_up
                and age is not None
                and age <= fresh
            )
            status = (
                "failed"
                if failed
                else "confirmed"
                if confirmed
                else "expired"
                if age is not None and age > fresh
                else "rebounding"
                if response
                else "forming"
            )
            label = {
                "failed": "Support failed",
                "confirmed": "Retest + rebound confirmed",
                "expired": "Older breakout",
                "rebounding": "Rebound; needs confirmation",
                "forming": "Retest forming",
            }[status]
            missing = []
            if not response:
                missing.append("a recent strong upward candle")
            if not current_breakout:
                missing.append("a close above the intervening high")
            if not trend_up:
                missing.append("rising SMA 20 / 50 and price above SMA 50")
            reading = f"Lows {first['low']:.2f} and {second['low']:.2f}; intervening high {neckline:.2f}. "
            reading += (
                "A later close broke the support floor."
                if failed
                else "Two troughs held a similar floor, a strong rebound cleared the intervening high, and the broader averages are rising."
                if confirmed
                else "Needs " + ", ".join(missing) + "."
                if missing
                else "The breakout is older than the current signal window."
            )
            return dict(
                available=True,
                status=status,
                label=label,
                reading=reading,
                trend_up=trend_up,
                first_low=dict(time=first["time"], price=first["low"]),
                second_low=dict(time=second["time"], price=second["low"]),
                support_low=floor,
                support_high=max(first["low"], second["low"]) + tolerance,
                neckline=neckline,
                tolerance=tolerance,
                rebound_pct=rebound,
                strong_at=bars[strong[-1]]["time"] if strong else None,
                confirmed_at=bars[breakout]["time"] if breakout is not None else None,
                confirmation_age=age,
                volume_confirmed=bool(
                    strong and (bars[strong[-1]].get("volume_ratio") or 0) >= 1.3
                ),
                basis="Two troughs confirmed with 2 later bars; 1%–3%/0.5 ATR price tolerance; meaningful dip and intervening rebound; strong 0.8 ATR upward body; close above intervening high; rising SMA 20/50. Heuristic, not a measured success rate.",
            )
    return dict(
        available=True,
        status="none",
        label="No recent retest pattern",
        trend_up=trend_up,
        reading="No recent pair of confirmed troughs met the dip, spacing and same-floor rules. Absence is not a sell signal.",
    )
