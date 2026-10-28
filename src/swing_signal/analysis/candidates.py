"""Deterministic long-candidate qualification, scoring and ranking."""

def long_candidates(assets, timeframe="1d"):
    key = "weekly_swing" if timeframe == "1w" else "daily_swing"
    other = "daily_swing" if timeframe == "1w" else "weekly_swing"
    candidates = []
    excluded = 0
    for asset in assets:
        reading = asset.get(key) or {}
        positive = [s for s in reading.get("signals", []) if (s.get("score") or 0) > 0]
        negative = [s for s in reading.get("signals", []) if (s.get("score") or 0) < 0]
        demand = any(s["key"] == "zones" for s in positive)
        if (
            not asset.get("available")
            or asset.get("stale")
            or asset.get("quality_note")
            or (
                not demand
                and (reading.get("direction") == "unavailable" or reading.get("coverage", 0) < 5)
            )
        ):
            excluded += 1
            continue
        if not positive:
            continue
        rising = any(s["key"] == "highs" for s in positive)
        move = any(s["key"] == "move" for s in positive)
        priority = 1 + int(rising) + int(move) if demand else 0
        setup = (
            "Demand + rising trend + >1% move"
            if demand and rising and move
            else "Demand + >1% move"
            if demand and move
            else "Demand + rising trend"
            if demand and rising
            else "At demand"
            if demand
            else "Other rule matched"
        )
        aligned = (
            reading.get("direction") == "bullish"
            and (asset.get(other) or {}).get("direction") == "bullish"
        )
        balance = reading.get("score") or 0
        points = dict(
            demand=45 if demand else 0,
            trend_with_demand=20 if demand and rising else 0,
            move_with_demand=20 if demand and move else 0,
            rule_balance=10 * (max(-8, min(8, balance)) + 8) / 16,
            daily_weekly_alignment=5 if aligned else 0,
        )
        positive.sort(
            key=lambda s: (
                [
                    "zones",
                    "move",
                    "highs",
                    "retest",
                    "rsi",
                    "stoch",
                    "ma",
                    "volume",
                ].index(s["key"])
                if s["key"] in ["zones", "move", "highs", "retest", "rsi", "stoch", "ma", "volume"]
                else 9
            )
        )
        candidates.append(
            dict(
                symbol=asset["symbol"],
                matched=positive,
                counterpoints=negative,
                score=reading.get("score", 0),
                priority=priority,
                setup=setup,
                warnings=reading.get("warnings", []),
                overall_score=round(sum(points.values()), 1),
                score_breakdown=points,
                label=reading.get("label"),
                retest=reading.get("retest"),
                other_aligned=(asset.get(other) or {}).get("direction") == "bullish",
                strong_alignment=aligned,
            )
        )
    candidates.sort(
        key=lambda c: (
            -c["overall_score"],
            -c["score"],
            -int((c.get("retest") or {}).get("status") == "confirmed"),
            -len(c["matched"]),
            c["symbol"],
        )
    )
    for rank, candidate in enumerate(candidates, 1):
        candidate["rank"] = rank
    return dict(
        items=candidates,
        excluded=excluded,
        rule="Setup score /100: demand 45, demand + rising 3/7/14 period 20, demand + >1% move 20, eight-rule balance scaled from −8…+8 to 0…10, both daily/weekly buy-side leans 5. Sorted highest first. These are custom screening points, not a probability. Fresh usable history is required; green demand qualifies automatically. Other green rules require five available components.",
    )
