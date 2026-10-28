"""Daily/weekly features from completed candles; no model or trading instructions."""

from collections import defaultdict
from datetime import date, timedelta


def sma(values, n):
    out = [None] * len(values)
    for i in range(n - 1, len(values)):
        window = values[i - n + 1 : i + 1]
        if all(v is not None for v in window):
            out[i] = sum(window) / n
    return out


def wilder(values, n):
    out = [None] * len(values)
    if len(values) < n:
        return out
    out[n - 1] = sum(values[:n]) / n
    for i in range(n, len(values)):
        out[i] = (out[i - 1] * (n - 1) + values[i]) / n
    return out


def rsi(closes, n=14):
    if not closes:
        return []
    changes = [closes[i] - closes[i - 1] for i in range(1, len(closes))]
    gains = wilder([max(x, 0) for x in changes], n)
    losses = wilder([max(-x, 0) for x in changes], n)
    out = [None]
    for gain, loss in zip(gains, losses):
        if gain is None:
            out.append(None)
        elif loss == 0:
            out.append(50.0 if gain == 0 else 100.0)
        else:
            out.append(100 - 100 / (1 + gain / loss))
    return out


def weekly(bars):
    buckets = defaultdict(list)
    for b in bars:
        d = date.fromisoformat(b["time"])
        buckets[(d - timedelta(days=d.weekday())).isoformat()].append(b)
    return [
        dict(
            time=t,
            open=bs[0]["open"],
            high=max(x["high"] for x in bs),
            low=min(x["low"] for x in bs),
            close=bs[-1]["close"],
            volume=sum(x["volume"] for x in bs),
        )
        for t, bs in sorted(buckets.items())
    ]


def enrich(bars):
    closes = [x["close"] for x in bars]
    rs = rsi(closes, 14)
    long_rs = rsi(closes, 15)
    rsi_average = sma(long_rs, 14)
    raw = [None] * len(bars)
    for i in range(13, len(bars)):
        win = rs[i - 13 : i + 1]
        if all(v is not None for v in win):
            lo, hi = min(win), max(win)
            raw[i] = 50.0 if hi == lo else 100 * (rs[i] - lo) / (hi - lo)
    k = sma(raw, 3)
    d = sma(k, 3)
    tr = [
        max(
            b["high"] - b["low"],
            abs(b["high"] - bars[i - 1]["close"]),
            abs(b["low"] - bars[i - 1]["close"]),
        )
        if i
        else b["high"] - b["low"]
        for i, b in enumerate(bars)
    ]
    atr = wilder(tr, 14)
    ma20, ma50, ma200 = [sma(closes, p) for p in (20, 50, 200)]
    result = []
    for i, b in enumerate(bars):
        prior_vol = [v["volume"] for v in bars[max(0, i - 20) : i]]
        ratio = (
            b["volume"] / (sum(prior_vol) / 20) if len(prior_vol) == 20 and sum(prior_vol) else None
        )
        result.append(
            dict(
                b,
                rsi=long_rs[i],
                rsi14=rs[i],
                rsi_average=rsi_average[i],
                k=k[i],
                d=d[i],
                atr=atr[i],
                sma20=ma20[i],
                sma50=ma50[i],
                sma200=ma200[i],
                volume_ratio=ratio,
            )
        )
    return result


def candidate_zones(bars, timeframe="1d"):
    from .zones import discover

    return discover(bars, timeframe)


def summarize(bars, zones):
    if not bars:
        return {}
    b = bars[-1]
    prev = bars[-2] if len(bars) > 1 else b
    demand = sorted(
        [z for z in zones if z["kind"] == "demand" and z["low"] <= b["close"]],
        key=lambda z: max(0, b["close"] - z["high"]),
    )
    near = demand[0] if demand else None
    distance = 100 * max(0, b["close"] - near["high"]) / b["close"] if near else None
    improving = b.get("rsi") is not None and prev.get("rsi") is not None and b["rsi"] > prev["rsi"]
    turning = (
        b.get("k") is not None
        and b.get("d") is not None
        and prev.get("k") is not None
        and b["k"] > b["d"]
        and b["k"] > prev["k"]
    )
    volume = (b.get("volume_ratio") or 0) >= 1.3
    near_zone = distance is not None and distance <= 3
    flags = [
        {"label": "Near demand", "met": near_zone},
        {"label": "RSI rising", "met": improving},
        {"label": "Stoch RSI turning", "met": turning},
        {"label": "Volume ≥ 1.3×", "met": volume},
    ]
    state = (
        "Confluence"
        if near_zone and improving and turning
        else "At demand"
        if near_zone
        else "Momentum rising"
        if improving and turning
        else "Observing"
    )
    return dict(
        price=b["close"],
        change=(b["close"] / prev["close"] - 1) * 100 if prev["close"] else 0,
        rsi=b.get("rsi"),
        rsi_delta=(b["rsi"] - prev["rsi"])
        if b.get("rsi") is not None and prev.get("rsi") is not None
        else None,
        k=b.get("k"),
        d=b.get("d"),
        volume_ratio=b.get("volume_ratio"),
        atr=b.get("atr"),
        sma20=b.get("sma20"),
        sma50=b.get("sma50"),
        sma200=b.get("sma200"),
        trend="Above 50 DMA"
        if b.get("sma50") and b["close"] > b["sma50"]
        else "Below 50 DMA"
        if b.get("sma50")
        else "Short history",
        demand=near,
        distance=distance,
        flags=flags,
        state=state,
        sparkline=[x["close"] for x in bars[-35:]],
        candle_date=b["time"],
        change_3d=(b["close"] / bars[-4]["close"] - 1) * 100 if len(bars) > 3 else None,
        change_20d=(b["close"] / bars[-21]["close"] - 1) * 100 if len(bars) > 20 else None,
    )
