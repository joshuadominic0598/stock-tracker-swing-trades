"""Inspectable swing evidence, not probabilities or execution instructions."""

from datetime import date, timedelta

from swing_signal.analysis.patterns import support_retest

def highs(bars, periods=(7, 14), calendar=True):
    result = {}
    if not bars:
        return result
    end = date.fromisoformat(bars[-1]["time"])
    last = bars[-1]
    for n in periods:
        window = (
            [b for b in bars if date.fromisoformat(b["time"]) >= end - timedelta(days=n - 1)]
            if calendar
            else bars[-n:]
        )
        full = bool(window) and (
            (end - date.fromisoformat(bars[0]["time"])).days >= n - 1
            if calendar
            else len(bars) >= n
        )
        prior = window[:-1]
        if not full or len(window) < 2:
            result[str(n)] = dict(available=False)
            continue
        peak = max(b["high"] for b in window)
        closing = max(b["close"] for b in window)
        result[str(n)] = dict(
            available=True,
            high=peak,
            highest_close=closing,
            from_date=window[0]["time"],
            through=last["time"],
            samples=len(window),
            reached=last["high"] >= peak,
            at_high=last["close"] >= peak,
            closing_high=last["close"] >= closing,
            new_closing_high=last["close"] > max(b["close"] for b in prior),
            breakout=last["close"] > max(b["high"] for b in prior),
            distance_pct=100 * (peak - last["close"]) / last["close"],
        )
    return result

def period_trend(bars, n, calendar=True):
    if not bars:
        return dict(available=False)
    last = bars[-1]
    if calendar:
        target = date.fromisoformat(last["time"]) - timedelta(days=n)
        prior = [b for b in bars[:-1] if date.fromisoformat(b["time"]) <= target]
        if not prior:
            return dict(available=False)
        base = prior[-1]
        if (target - date.fromisoformat(base["time"])).days > 7:
            return dict(available=False)
    else:
        if len(bars) <= n:
            return dict(available=False)
        base = bars[-n - 1]
    change = (last["close"] / base["close"] - 1) * 100
    return dict(
        available=True,
        rising=change > 0,
        change=change,
        from_date=base["time"],
        through=last["time"],
    )

def assess(bars, zones, timeframe="1d", daily_bars=None):
    if not bars:
        return dict(
            label="No history",
            direction="unavailable",
            score=None,
            coverage=0,
            signals=[],
            highs={},
            daily_highs={},
        )
    b = bars[-1]
    p = bars[-2] if len(bars) > 1 else b
    c = b["close"]
    period = "week" if timeframe == "1w" else "session"
    windows = highs(bars, calendar=timeframe == "1d")
    items = []

    def add(key, title, value, reading, score=None):
        items.append(
            dict(
                key=key,
                title=title,
                value=value,
                reading=reading,
                score=score,
                direction="bullish"
                if score and score > 0
                else "bearish"
                if score and score < 0
                else "neutral",
            )
        )

    r = b.get("rsi")
    rp = p.get("rsi")
    delta = r - rp if r is not None and rp is not None else None
    recent_rsi = [x["rsi"] for x in bars[-31:-1] if x.get("rsi") is not None]
    dip = min(recent_rsi) if recent_rsi else None
    recovery = bool(
        dip is not None
        and dip < 35
        and r is not None
        and r > 40
        and delta is not None
        and delta > 0
    )
    if delta is None:
        add(
            "rsi",
            "RSI (15)",
            "Unavailable",
            "Needs RSI 15 and a preceding completed RSI value.",
        )
    else:
        score = 1 if recovery else -1 if delta < 0 and r < 40 else 0
        level = (
            "Your recovery rule matched: RSI dipped below 35 in the previous 30 bars and is now above 40 and rising."
            if recovery
            else "Waiting for your recovery rule: a dip below 35 in the previous 30 bars, then RSI above 40 and rising."
        )
        avg = b.get("rsi_average")
        old_avg = p.get("rsi_average")
        if avg is not None:
            level += (
                f" RSI SMA 14 is {avg:.1f}; RSI is "
                + ("above" if r > avg else "below" if r < avg else "at")
                + " its average."
            )
            if old_avg is not None and rp is not None:
                if rp <= old_avg and r > avg:
                    level += " New cross above the RSI average."
                elif rp >= old_avg and r < avg:
                    level += " New cross below the RSI average."
        add(
            "rsi",
            "RSI (15)",
            f"{r:.1f} ({delta:+.1f})",
            ("Rising. " if delta > 0 else "Falling. " if delta < 0 else "Flat. ") + level,
            score,
        )
    k, d, kp, dp = b.get("k"), b.get("d"), p.get("k"), p.get("d")
    if any(v is None for v in (k, d, kp, dp)):
        add(
            "stoch",
            "Stoch RSI",
            "Unavailable",
            "Needs a full RSI and smoothing history.",
        )
    else:
        crossup = kp <= dp and k > d
        crossdown = kp >= dp and k < d
        score = 1 if k <= 20 or k < kp else 0
        reading = (
            "Low K (≤20)"
            if k <= 20
            else "K is falling"
            if k < kp
            else "K is neither low nor falling"
        ) + (
            ": your pullback watch is green. "
            if score
            else ": your pullback condition is not met. "
        )
        reading += (
            ("K is falling. " if k < kp else "K is rising. " if k > kp else "K is flat. ")
            + ("New K-over-D cross. " if crossup else "New K-under-D cross. " if crossdown else "")
            + "A rebound is not confirmed by this condition alone."
        )
        add("stoch", "Stoch RSI", f"K {k:.1f} / D {d:.1f}", reading, score)
    ratio = b.get("volume_ratio")
    move = (c / p["close"] - 1) * 100 if p["close"] else 0
    if ratio is None or b.get("volume", 0) <= 0:
        add(
            "volume",
            "Volume",
            "Unavailable",
            "No usable volume baseline. Index volume may be unavailable.",
        )
    else:
        score = (1 if move > 0 else -1 if move < 0 else 0) if ratio >= 1.3 else 0
        add(
            "volume",
            "Volume",
            f"{ratio:.2f}× prior 20",
            (
                "High participation on an up bar supports the advance."
                if score > 0
                else "High participation on a down bar adds selling pressure."
                if score < 0
                else "Below the 1.3× confirmation threshold; participation is unconfirmed."
            ),
            score,
        )
    daily_source = daily_bars if daily_bars is not None else bars if timeframe == "1d" else []
    ma200 = sum(x["close"] for x in daily_source[-200:]) / 200 if len(daily_source) >= 200 else None
    daily_close = daily_source[-1]["close"] if daily_source else None
    gap200 = 100 * (ma200 / daily_close - 1) if ma200 is not None and daily_close else None
    below200 = gap200 is not None and gap200 > 0
    if ma200 is None:
        add(
            "ma",
            "200-day mean reversion",
            "Unavailable",
            "Needs 200 completed daily closes. The chart averages remain selected-timeframe context.",
        )
    else:
        value = f"{abs(gap200):.1f}% " + ("up to 200D SMA" if below200 else "from 200D SMA")
        reading = (
            f"Below the 200-day SMA ({ma200:,.2f}): your mean-reversion watch is green. A return to this moving line would be {gap200:.1f}% above the latest daily close."
            if below200
            else f"At or above the 200-day SMA ({ma200:,.2f}); your below-average condition is not met."
        )
        reading += " This is a reference, not a price target; the average can fall and price can keep declining."
        add("ma", "200-day mean reversion", value, reading, 1 if below200 else 0)
    demand = sorted(
        [z for z in zones if z["kind"] == "demand" and not z.get("broken") and z["low"] <= c],
        key=lambda z: max(0, c - z["high"]),
    )
    supply = sorted(
        [z for z in zones if z["kind"] == "supply" and not z.get("broken") and z["high"] >= c],
        key=lambda z: max(0, z["low"] - c),
    )
    dn = demand[0] if demand else None
    sp = supply[0] if supply else None
    dd = 100 * max(0, c - dn["high"]) / c if dn else None
    sd = 100 * max(0, sp["low"] - c) / c if sp else None
    near_d = dd is not None and dd <= 3
    near_s = sd is not None and sd <= 3
    if not dn and not sp:
        add(
            "zones",
            "Supply & demand",
            "No valid band",
            "No current band was identified; it does not mean there is no support or resistance.",
        )
    else:
        score = 1 if near_d else -1 if near_s else 0
        value = (
            ("Demand " + f"{dd:.1f}%" if dn else "Demand —")
            + " / "
            + ("Supply " + f"{sd:.1f}%" if sp else "Supply —")
        )
        title = "Demand zone" if near_d else "Supply zone" if near_s else "Supply & demand"
        if near_d:
            value = "Inside zone" if dd == 0 else f"{dd:.1f}% above zone"
        elif near_s:
            value = "Inside zone" if sd == 0 else f"{sd:.1f}% below zone"
        add(
            "zones",
            title,
            value,
            (
                "Near valid demand: qualifies for your long shortlist. Nearby supply limits room above."
                if near_s
                else "Near valid demand: qualifies for your long shortlist. Watch whether buyers hold this band."
            )
            if near_d
            else "Near supply: upside may encounter resistance; review the response."
            if near_s
            else "Away from the nearest identified bands.",
            score,
        )
    suffix = "W" if timeframe == "1w" else "D"
    trends = {str(n): period_trend(bars, n, calendar=timeframe == "1d") for n in (3, 7, 14)}
    usable = [t for t in trends.values() if t["available"]]
    any_up = any(t["rising"] for t in usable)
    trend_title = f"3{suffix} / 7{suffix} / 14{suffix} rising"
    if not usable:
        add(
            "highs",
            trend_title,
            "Unavailable",
            "Needs a usable closing-price baseline for at least one lookback period.",
        )
    else:
        value = " / ".join(
            f"{n}{suffix}: "
            + (
                f"{'Yes' if trends[str(n)]['rising'] else 'No'} ({trends[str(n)]['change']:+.1f}%)"
                if trends[str(n)]["available"]
                else "—"
            )
            for n in (3, 7, 14)
        )
        score = (
            1 if any_up else -1 if len(usable) == 3 and all(t["change"] < 0 for t in usable) else 0
        )
        reading = "Any positive period turns this condition green; with demand it strengthens your long shortlist. Red days do not cancel a net rise. Missing windows stay unknown; this is not a highest-price test."
        add("highs", trend_title, value, reading, score)
    items[-1].update(periods=trends, period_unit=suffix)
    if len(bars) < 2:
        add(
            "move",
            "Move above +1%",
            "Unavailable",
            "Needs a preceding completed close.",
        )
    else:
        add(
            "move",
            "Move above +1%",
            f"{move:+.2f}% / {period}",
            "More than +1% from the preceding close."
            if move > 1.000000001
            else "More than −1% from the preceding close."
            if move < -1.000000001
            else "The +1% upward-move condition is not met.",
            1 if move > 1.000000001 else -1 if move < -1.000000001 else 0,
        )
    retest = support_retest(bars, timeframe)
    add(
        "retest",
        "Support retest & rebound",
        retest["label"],
        retest["reading"],
        None
        if not retest["available"]
        else 1
        if retest["status"] == "confirmed"
        else -1
        if retest["status"] == "failed"
        else 0,
    )
    coverage = sum(x["score"] is not None for x in items)
    score = sum(x["score"] or 0 for x in items)
    direction = "bullish" if score >= 2 else "bearish" if score <= -2 else "neutral"
    label = (
        "Buy-side lean"
        if direction == "bullish"
        else "Sell-side lean"
        if direction == "bearish"
        else "Mixed / wait"
    )
    if coverage < 5:
        label = "Limited evidence"
        direction = "unavailable"
    warnings = []
    if r is not None and r > 70:
        warnings.append(
            "RSI is extended; strength can continue, but a late entry can have less room."
        )
    if sp and sd is not None and sd <= 3:
        warnings.append("Nearby supply is a counterpoint to an upside setup.")
    if dn is None:
        warnings.append(
            "No valid demand band: a clear structure-based invalidation level is missing."
        )
    if ratio is None or ratio < 1.3:
        warnings.append("Volume confirmation is absent.")
    if below200:
        warnings.append(
            "Price is below its 200-day average; your mean-reversion watch can still face a continuing downtrend."
        )
    return dict(
        label=label,
        direction=direction,
        score=score,
        coverage=coverage,
        signals=items,
        highs=windows,
        daily_highs=highs(daily_bars or bars),
        period_trend=trends,
        demand=dn,
        supply=sp,
        demand_distance=dd,
        supply_distance=sd,
        near_demand=near_d,
        any_period_up=any_up,
        rsi_recovery=recovery,
        daily_ma200=ma200,
        below_200d=below200,
        gap_to_200d_pct=gap200,
        up_over_one=move > 1.000000001,
        change=move,
        warnings=warnings,
        retest=retest,
        basis="Eight custom screening conditions. Green means your rule matched, including contrarian pullback watches. A balance of +2 leans buy-side, −2 sell-side; it is not a rebound forecast. Demand independently qualifies for the long shortlist.",
    )

def financial_meanings(metrics, sector=""):
    definitions = {
        "TotalRevenue": (
            "Revenue",
            "Money earned from sales before expenses.",
            "Growth can support future earnings if margins hold; falling sales can weaken that support.",
        ),
        "NetIncome": (
            "Net income",
            "Profit after reported expenses and taxes.",
            "Sustained profit growth can support valuation; one-off gains and market expectations can change the price response.",
        ),
        "DilutedEPS": (
            "Diluted EPS",
            "Profit attributable to each share after potential dilution.",
            "EPS growth can support a valuation if the price has not already anticipated it; a rise is not proof the stock is cheap.",
        ),
        "TotalDebt": (
            "Total debt",
            "Reported borrowings, not the same as net debt.",
            "Rising debt can add financing risk; funding growth may justify it. For banks and financial firms, debt is part of the business model.",
        ),
        "StockholdersEquity": (
            "Shareholders’ equity",
            "Reported assets less liabilities attributable to shareholders.",
            "A larger book base may support resilience; it does not establish fair market value or short-term direction.",
        ),
        "OperatingCashFlow": (
            "Operating cash flow",
            "Cash generated or used by ongoing operations.",
            "Positive operating cash helps support reported earnings; profit without cash conversion deserves closer review.",
        ),
        "FreeCashFlow": (
            "Free cash flow",
            "Operating cash remaining after the provider’s capital-spending measure.",
            "Positive free cash may support dividends, investment or debt reduction. Negative cash flow can reflect expansion or financial strain.",
        ),
    }
    results = []
    for key, values in metrics.items():
        if key not in definitions or not values:
            continue
        last = values[-1]
        prior = values[-2] if len(values) > 1 else None
        comparable = (
            prior is not None
            and prior["value"] > 0
            and (date.fromisoformat(last["date"]) - date.fromisoformat(prior["date"])).days
            in range(300, 431)
            and last.get("currency") == prior.get("currency")
        )
        growth = (last["value"] / prior["value"] - 1) * 100 if comparable else None
        label, meaning, implication = definitions[key]
        if key == "TotalDebt":
            reading = (
                "Borrowings increased; inspect cash, interest costs and use of funds."
                if growth and growth > 0
                else "Borrowings decreased; inspect whether operating strength or asset sales funded the reduction."
                if growth and growth < 0
                else "Needs balance-sheet context."
            )
            direction = "context"
        else:
            direction = (
                "supportive"
                if growth is not None and growth > 0 and last["value"] > 0
                else "pressure"
                if last["value"] < 0 or growth is not None and growth < 0
                else "context"
            )
            reading = (
                "Improving annual figures offer business support, subject to valuation and expectations."
                if direction == "supportive"
                else "Weakening or negative figures add a business risk to review."
                if direction == "pressure"
                else "The available periods do not establish a clear improvement or deterioration."
            )
        results.append(
            dict(
                metric=key,
                label=label,
                meaning=meaning,
                price_implication=implication,
                reading=reading,
                direction=direction,
                yoy=growth,
                period=last["date"],
            )
        )
    return results
