"""Base/departure and repeated-pivot zones with explicit, causal confirmation dates."""

def discover(bars, timeframe="1d"):
    if len(bars) < 30:
        return []
    price = bars[-1]["close"]
    zones = []
    start = max(4, len(bars) - 180)

    def append(kind, low, high, origin, confirmed, label, evidence, touches=0, departure=0):
        atr = bars[origin].get("atr") or price * 0.02
        after = bars[confirmed + 1 :]
        if any(
            b["close"] < low - 0.25 * atr if kind == "demand" else b["close"] > high + 0.25 * atr
            for b in bars[origin + 1 :]
        ):
            return
        if (kind == "demand" and low > price) or (kind == "supply" and high < price):
            return
        revisits = 0
        inside = False
        for b in after:
            intersects = b["low"] <= high and b["high"] >= low
            if intersects and not inside:
                revisits += 1
            inside = intersects
        distance = 100 * max(low - price, price - high, 0) / price
        age = len(bars) - 1 - confirmed
        score = round(
            min(departure, 4) * 1.5
            + min(touches, 3)
            + max(0, 2 - age / 90)
            + (1 if revisits == 0 else 0)
            - min(revisits, 0.5 * revisits + 1),
            2,
        )
        overlaps = [
            f"SMA {n}"
            for n in (20, 50, 200)
            if bars[-1].get("sma" + str(n)) is not None
            and low - atr * 0.15 <= bars[-1]["sma" + str(n)] <= high + atr * 0.15
        ]
        zones.append(
            dict(
                kind=kind,
                low=round(low, 5),
                high=round(high, 5),
                source="algorithm",
                label=label,
                timeframe=timeframe,
                origin=bars[origin]["time"],
                confirmed_at=bars[confirmed]["time"],
                last_touch=bars[origin]["time"],
                touches=touches,
                retests=revisits,
                departure_atr=round(departure, 2),
                fresh=revisits == 0,
                quality_score=score,
                distance=round(distance, 2),
                evidence=evidence
                + [
                    f"{revisits} later retest episodes",
                    "Unretested since departure"
                    if revisits == 0
                    else "Retested after confirmation",
                ]
                + overlaps,
            )
        )

    # Compact 2–4-bar bases followed by a strong, confirmed three-bar departure.
    for end in range(start, len(bars) - 3):
        for length in (2, 3, 4):
            base = bars[end - length + 1 : end + 1]
            atr = bars[end].get("atr")
            if not atr or len(base) != length:
                continue
            lo = min(b["low"] for b in base)
            hi = max(b["high"] for b in base)
            body_lo = min(min(b["open"], b["close"]) for b in base)
            body_hi = max(max(b["open"], b["close"]) for b in base)
            if (
                hi - lo > 1.3 * atr
                or sum(abs(b["close"] - b["open"]) for b in base) / length > 0.55 * atr
            ):
                continue
            next3 = bars[end + 1 : end + 4]
            for kind in ("demand", "supply"):
                departure = (
                    (max(b["close"] for b in next3) - hi) / atr
                    if kind == "demand"
                    else (lo - min(b["close"] for b in next3)) / atr
                )
                impulse = any(
                    (b["close"] - b["open"] if kind == "demand" else b["open"] - b["close"])
                    >= 0.8 * atr
                    for b in next3
                )
                if departure < 1.4 or not impulse:
                    continue
                low, high = (lo, body_hi) if kind == "demand" else (body_lo, hi)
                if high - low < 0.1 * atr:
                    low -= 0.05 * atr
                    high += 0.05 * atr
                if high - low > 1.5 * atr:
                    continue
                ratios = [b.get("volume_ratio") or 0 for b in next3]
                evidence = [
                    f"{length}-bar compact base",
                    f"{departure:.1f} ATR departure in the next 3 bars",
                    f"Departure volume up to {max(ratios):.2f}×",
                ]
                append(
                    kind,
                    low,
                    high,
                    end,
                    end + 3,
                    "Base + strong departure",
                    evidence,
                    departure=departure,
                )
    # Repeated reactions supplement single-origin bases.
    atr = bars[-1].get("atr") or price * 0.02
    tolerance = max(0.7 * atr, 0.001 * price)
    for kind, field in [("demand", "low"), ("supply", "high")]:
        pivots = []
        for i in range(start, len(bars) - 3):
            value = bars[i][field]
            window = [b[field] for b in bars[i - 3 : i + 4]]
            if value == (min(window) if kind == "demand" else max(window)):
                pivots.append((i, value))
        clusters = []
        for pivot in sorted(pivots, key=lambda x: x[1]):
            if clusters and pivot[1] - clusters[-1][0][1] <= tolerance:
                clusters[-1].append(pivot)
            else:
                clusters.append([pivot])
        for cluster in clusters:
            spaced = []
            for pivot in sorted(cluster):
                if not spaced or pivot[0] - spaced[-1][0] >= 5:
                    spaced.append(pivot)
            if len(spaced) < 2:
                continue
            low = min(v for _, v in cluster) - 0.15 * atr
            high = max(v for _, v in cluster) + 0.15 * atr
            origin = max(i for i, _ in cluster)
            # Every close after the pivot, including its confirmation bars, must respect the band.
            if any(
                b["close"] < low - 0.25 * atr
                if kind == "demand"
                else b["close"] > high + 0.25 * atr
                for b in bars[origin + 1 :]
            ):
                continue
            append(
                kind,
                low,
                high,
                origin,
                origin + 3,
                "Repeated pivot reactions",
                [f"{len(spaced)} separated pivot reactions"],
                touches=len(spaced),
            )
    selected = []
    for kind in ("demand", "supply"):
        pool = sorted(
            [z for z in zones if z["kind"] == kind],
            key=lambda z: (z["distance"] > 8, -z["quality_score"], z["distance"]),
        )
        kept = []
        for z in pool:
            if any(max(z["low"], k["low"]) <= min(z["high"], k["high"]) for k in kept):
                continue
            kept.append(z)
            if len(kept) == 3:
                break
        selected.extend(kept)
    return sorted(selected, key=lambda z: z["distance"])
