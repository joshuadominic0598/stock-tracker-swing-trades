"""Plain-language stock views built from cited evidence and explicit model selections."""

SIGNAL_NOTES = {
    "rsi": (
        "Momentum recovery",
        "Momentum has recovered from a weak patch.",
        "Momentum is weakening again.",
        "A clear recovery from weakness has not formed yet.",
    ),
    "stoch": (
        "Short-term pullback",
        "Your pullback rule matches. This is a watch flag; buyers have not necessarily returned.",
        "Short-term momentum is losing strength.",
        "The short-term pullback rule is not matched.",
    ),
    "volume": (
        "Trading activity",
        "The rise has stronger-than-usual trading activity behind it.",
        "Heavier trading is accompanying a fall, which adds selling pressure.",
        "Trading activity does not yet confirm a strong move.",
    ),
    "ma": (
        "Long-run price average",
        "Price is below its long-run average. That leaves room for recovery, but does not prove one is starting.",
        "Price and its averages show pressure.",
        "Being near or above the long-run average is not a bargain signal in your rules.",
    ),
    "zones": (
        "Demand area",
        "Price is near an area where past buying appeared. Watch whether buyers defend it again.",
        "Price is near an area where past selling could slow a rise.",
        "Price is away from the marked buying and selling areas.",
    ),
    "highs": (
        "Recent price direction",
        "At least one recent period is up; the separate period flags show how broad the rise is.",
        "All three measured periods are down. The wider slide is still visible.",
        "Recent periods do not show a clear upward direction.",
    ),
    "move": (
        "Latest price move",
        "The latest completed price move is up more than 1%.",
        "The latest completed price move is down more than 1%.",
        "The latest completed move is smaller than your 1% trigger.",
    ),
    "retest": (
        "Second test of the floor",
        "Price tested a similar low twice, then broke upward with a stronger recovery.",
        "The rebound pattern failed; the old floor did not hold.",
        "A completed second-test-and-rebound pattern is not confirmed.",
    ),
}
NEWS_IMPACTS = {
    "positive": "Could help buyer confidence if the reported development is confirmed.",
    "negative": "Could keep buyers cautious or add selling pressure if confirmed.",
    "mixed": "Contains competing positives and negatives; the price effect is unclear.",
    "unclear": "The headline alone does not establish a clear effect on the share price.",
}

def technical_view(technical, timeframe):
    reading = technical.get("swing") or {}
    facts = technical["facts"]
    periods = reading.get("period_trend") or {}

    def rising(period):
        return bool(periods.get(str(period), {}).get("rising"))

    falling = all(
        periods.get(str(n), {}).get("available") and periods[str(n)].get("change", 0) < 0
        for n in (3, 7, 14)
    )
    change = facts.get("change") or 0
    rsi = facts.get("rsi")
    delta = facts.get("rsi_delta")
    volume = facts.get("volume_ratio")
    active_buying = change > 0 and volume is not None and volume >= 1.3
    recovering = reading.get("rsi_recovery") and change > 0 and any(rising(n) for n in (3, 7, 14))
    weekly = technical.get("weekly_swing") or {}
    if technical.get("data_warning") or reading.get("direction") == "unavailable" or not reading:
        title, tone = "Not enough reliable data for a clear view", "unknown"
        text = "Refresh the missing or old price history before judging whether buyers or sellers are taking control."
    elif falling and change < 0 and delta is not None and delta < 0:
        title, tone = "Sellers still have the upper hand", "negative"
        text = "Recent price direction and momentum are both weak. Green pullback flags do not yet show a reversal."
    elif (
        rising(7)
        and rising(14)
        and active_buying
        and rsi is not None
        and rsi >= 50
        and delta is not None
        and delta > 0
        and weekly.get("direction") == "bullish"
        and not technical.get("week_partial")
    ):
        title, tone = "Strong evidence buyers are in control", "positive"
        text = "The rise is supported by improving momentum, stronger trading activity and the wider weekly view. This describes the evidence now, not a guaranteed next move."
    elif recovering or (active_buying and reading.get("near_demand") and rising(3)):
        title, tone = "Early signs of a turn upward", "positive"
        text = "Buyers are pushing back after weakness. The next test is whether the price holds its buying area and keeps making progress."
        if not rising(14):
            text += " The longer recent trend has not fully recovered."
    elif rising(7) and rising(14) and change > 0:
        title, tone = "Buyers are gaining ground", "positive"
        text = "The recent rise is broadening, although stronger trading activity and continued momentum would make the case clearer."
    elif reading.get("direction") == "bearish":
        title, tone = "Selling pressure still needs to ease", "negative"
        text = "More of the measured conditions point to weakness. A convincing turn upward is not visible yet."
    else:
        title, tone = "Buyers and sellers are still competing", "neutral"
        text = "Some conditions are improving, but the evidence does not yet show a clear takeover by buyers or sellers."
    if timeframe == "1w" and technical.get("week_partial") and tone != "unknown":
        title, tone = "This week's direction is still forming", "neutral"
        text = "The weekly candle is unfinished. Treat this week's signals as an early indication until the week closes."
    signals = reading.get("signals", [])
    points = []
    for signal in signals:
        key = signal["key"]
        label, positive, negative, neutral = SIGNAL_NOTES[key]
        score = signal.get("score")
        text_note = (
            "Not enough history to read this signal."
            if score is None
            else positive
            if score > 0
            else negative
            if score < 0
            else neutral
        )
        points.append(
            dict(
                label=label,
                text=text_note,
                flag="positive"
                if score and score > 0
                else "negative"
                if score and score < 0
                else "neutral",
                source_ids=["T1"],
            )
        )
    return dict(
        key="signals",
        title="What the price signals say",
        headline=title,
        tone=tone,
        text=text,
        points=points,
        source_ids=["T1"],
        green_flags=sum((s.get("score") or 0) > 0 for s in signals),
        red_flags=sum((s.get("score") or 0) < 0 for s in signals),
    )

def news_view(sources, selected):
    by_id = {source["id"]: source for source in sources}
    points = []
    for item in selected:
        source = by_id[item["source_id"]]
        points.append(
            dict(
                label=source["title"],
                text=NEWS_IMPACTS[item["impact"]],
                flag=item["impact"],
                source_ids=[source["id"]],
            )
        )
    directions = {item["impact"] for item in selected}
    tone = (
        "positive"
        if directions == {"positive"}
        else "negative"
        if directions == {"negative"}
        else "neutral"
        if points
        else "unknown"
    )
    title = (
        "Headlines could support buyers"
        if tone == "positive"
        else "Headlines add a reason for caution"
        if tone == "negative"
        else "The news picture is mixed or unclear"
        if points
        else "No usable stock-specific headlines"
    )
    return dict(
        key="news",
        title="What the news says",
        headline=title,
        tone=tone,
        text="AI reviewed the supplied headlines for possible price relevance. Open the original reports before acting; article bodies and claims are not verified."
        if points
        else "No conclusion about news can be drawn from the available feed.",
        points=points,
        source_ids=[p["source_ids"][0] for p in points],
    )

def attention_view(sources, asset):
    by_id = {source["id"]: source for source in sources}
    points = []
    social = by_id.get("C1")
    if social:
        counts = social["facts"]
        recent, previous = counts["recent"], counts["previous"]
        direction = (
            "More discussion"
            if recent > previous
            else "Less discussion"
            if recent < previous
            else "Discussion is steady"
        )
        points.append(
            dict(
                label=direction,
                text=f"{recent} matched public posts in the latest seven days, versus {previous} before. These are sampled posts, not a count of people.",
                source_ids=["C1"],
            )
        )
        tone = counts.get("tone", {})
        positive, negative = tone.get("positive", 0), tone.get("negative", 0)
        wording = (
            "Positive wording appears more often"
            if positive > negative
            else "Negative wording appears more often"
            if negative > positive
            else "No clear positive or negative wording lead"
        )
        points.append(
            dict(
                label=wording,
                text=f"{positive} positive and {negative} negative post titles. Title wording is a rough clue, not a measure of all investors' opinions.",
                source_ids=["C1"],
            )
        )
    else:
        points.append(
            dict(
                label="Public discussion unavailable",
                text="No usable public-post sample was retrieved. This does not mean people are not talking about the stock.",
                source_ids=[],
            )
        )
    trend = by_id.get("G1")
    values = trend.get("facts", {}) if trend else {}
    if values.get("complete") and not values.get("stale"):
        direction = (
            "Search interest is rising"
            if values["recent"] > values["previous"]
            else "Search interest is falling"
            if values["recent"] < values["previous"]
            else "Search interest is steady"
        )
        points.append(
            dict(
                label=direction,
                text=f"Average relative search interest: {values['recent']:.1f} now versus {values['previous']:.1f} before. This is an interest index, not an exact search count.",
                source_ids=["G1"],
            )
        )
    else:
        points.append(
            dict(
                label="Google search trend not measured",
                text="Import a current Google Trends series to compare interest over time. Missing search data is not a negative signal.",
                source_ids=["G1"] if trend else [],
            )
        )
    return dict(
        key="attention",
        title="What sentiment and search interest say",
        headline="Attention is context, not proof of buying",
        tone="neutral" if social or trend else "unknown",
        text=f"Discussion and searches can show whether {asset['name']} is attracting attention. More attention can accompany either a rise or a fall.",
        points=points,
        source_ids=[s for s in ("C1", "G1") if s in by_id],
    )

def build_report(sources, news_selection, asset, timeframe):
    technical = technical_view(sources[0], timeframe)
    news = news_view(sources, news_selection)
    attention = attention_view(sources, asset)
    sector = next((s for s in sources if s["id"] == "S1"), None)
    if sector and sector["facts"].get("available"):
        values = sector["facts"]
        relative = values["relative_change"]
        technical["points"].append(
            dict(
                label="Against its tracked sector",
                text=f"The stock is {'outperforming' if relative > 0 else 'underperforming' if relative < 0 else 'moving with'} its tracked peers by {abs(relative):.2f} percentage points. The peer group is {'rising' if values['change'] > 0 else 'falling' if values['change'] < 0 else 'flat'} overall; this is a sample, not the whole sector.",
                source_ids=["S1"],
            )
        )
    summary = dict(
        title=technical["headline"],
        tone=technical["tone"],
        text=technical["text"],
        source_ids=["T1"],
        green_flags=technical["green_flags"],
        red_flags=technical["red_flags"],
    )
    facts = sources[0]["facts"]
    unit = "INR" if asset["market"] == "NSE" else "USD" if asset["market"] == "US" else "USDT"
    summary["price_note"] = (
        f"Latest completed close: {unit} {facts['price']:,.2f} ({facts['change']:+.2f}%)."
    )
    if news["tone"] == "negative":
        summary["text"] += " The selected headlines also add a reason for caution."
        summary["source_ids"] += news["source_ids"]
        if summary["tone"] == "positive":
            summary["title"] = "Buyers are improving, but the news adds caution"
            summary["tone"] = "neutral"
    elif news["tone"] == "positive":
        summary["text"] += " The selected headlines may help buyer confidence."
        summary["source_ids"] += news["source_ids"]
    if sources[0].get("week_partial"):
        technical["points"].append(
            dict(
                label="Weekly check",
                text="The current week is unfinished, so its weekly reading can still change.",
                source_ids=["T1"],
            )
        )
    return summary, [technical, news, attention]
