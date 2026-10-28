"""Free public attention samples. Counts are observations, never people or forecasts."""

import csv
import html
import io
import math
import re
import threading
import urllib.parse
import xml.etree.ElementTree as ET
from datetime import date, datetime, timedelta, timezone
from zoneinfo import ZoneInfo

from . import storage

UTC = timezone.utc
ATOM = "{http://www.w3.org/2005/Atom}"
TREND_NS = "{https://trends.google.com/trending/rss}"
TREND_LOCK = threading.Lock()
ALIASES = {
    "HINDUNILVR": ["Hindustan Unilever", "HUL"],
    "DRREDDY": ["Dr Reddy", "Dr Reddys", "Dr Reddy's"],
    "PIDILITIND": ["Pidilite"],
    "NESTLEIND": ["Nestle India"],
    "COLPAL": ["Colgate Palmolive"],
    "ITCHOTELS": ["ITC Hotels"],
    "HCG": ["Healthcare Global", "HCG"],
    "PRICOLLTD": ["Pricol"],
    "IDFCFIRSTB": ["IDFC First Bank"],
    "JIOFIN": ["Jio Financial"],
    "INFY": ["Infosys"],
    "BTCUSDT": ["Bitcoin", "BTC"],
    "ETHUSD": ["Ethereum", "ETH"],
    "SOLUSD": ["Solana", "SOL"],
    "ADAUSDT": ["Cardano", "ADA"],
    "XLMUSDT": ["Stellar", "XLM"],
    "XRPUSD": ["XRP", "Ripple"],
}
POSITIVE = (
    "bullish",
    "undervalued",
    "strong buy",
    "buy opportunity",
    "outperform",
    "upgrade",
    "upgraded",
    "beats estimates",
    "profit jumps",
    "profit rises",
    "profit grows",
    "record profit",
    "earnings beat",
    "revenue rises",
    "revenue grows",
    "rallies",
    "surges",
)
NEGATIVE = (
    "bearish",
    "overvalued",
    "avoid this stock",
    "underperform",
    "downgrade",
    "downgraded",
    "misses estimates",
    "profit falls",
    "profit drops",
    "loss widens",
    "earnings miss",
    "revenue falls",
    "revenue drops",
    "plunges",
    "fraud",
    "scam",
    "selloff",
    "sell off",
)


def now():
    return datetime.now(UTC)


def normalize(text):
    return re.sub(r"[^a-z0-9]+", " ", text.lower()).strip()


def aliases(asset):
    return list(dict.fromkeys([asset["name"], asset["symbol"], *ALIASES.get(asset["symbol"], [])]))


def matches(text, asset):
    text = " " + normalize(text) + " "
    for alias in aliases(asset):
        needle = normalize(alias)
        if needle and " " + needle + " " in text:
            return True
    # Company suffixes vary between Yahoo names and publisher headlines.
    words = set(normalize(asset["name"]).split()) - {
        "india",
        "limited",
        "ltd",
        "industries",
        "enterprises",
        "technologies",
        "company",
        "corporation",
        "services",
        "inc",
        "the",
        "etf",
    }
    return bool(words and len(words & set(text.split())) >= min(2, len(words)))


def wording(title):
    text = normalize(title)
    if "?" in title:
        return dict(label="Unclear / question", direction="unclear", positive=[], negative=[])

    def hits(phrases):
        found = []
        for phrase in phrases:
            for match in re.finditer(r"\b" + re.escape(phrase) + r"\b", text):
                before = text[: match.start()].split()[-3:]
                if not set(before) & {
                    "not",
                    "no",
                    "never",
                    "isnt",
                    "isn",
                    "wasnt",
                    "wasn",
                }:
                    found.append(phrase)
        return sorted(set(found))

    positive = hits(POSITIVE)
    negative = hits(NEGATIVE)
    direction = (
        "mixed"
        if positive and negative
        else "positive"
        if positive
        else "negative"
        if negative
        else "unclear"
    )
    return dict(
        label={
            "mixed": "Mixed wording",
            "positive": "Positive wording",
            "negative": "Negative wording",
            "unclear": "Unclear wording",
        }[direction],
        direction=direction,
        positive=positive,
        negative=negative,
    )


def activity(items, clock=None, capped=False):
    clock = clock or now()
    start = clock - timedelta(days=14)
    split = clock - timedelta(days=7)
    recent = []
    previous = []
    bins = {(clock.date() - timedelta(days=i)).isoformat(): 0 for i in reversed(range(15))}
    for item in items:
        try:
            ts = datetime.fromisoformat(
                (item.get("published_at") or "").replace("Z", "+00:00")
            ).astimezone(UTC)
        except (ValueError, TypeError):
            continue
        if not start <= ts <= clock:
            continue
        (recent if ts > split else previous).append(item)
        day = ts.date().isoformat()
        if day in bins:
            bins[day] += 1
    a = len(recent)
    b = len(previous)
    change = (a / b - 1) * 100 if b else None
    label = (
        "More mentions"
        if a > b
        else "Fewer mentions"
        if a < b
        else "Same sampled count"
        if a
        else "No recent matches"
    )
    if not b and a:
        label = "New sampled mentions"
    tone = {
        key: sum((v.get("tone") or wording(v.get("title", "")))["direction"] == key for v in recent)
        for key in ("positive", "negative", "mixed", "unclear")
    }
    return dict(
        recent=a,
        previous=b,
        change=change,
        label=label,
        window="Last 7 days vs preceding 7 days",
        capped=capped,
        daily=[dict(date=d, count=n) for d, n in bins.items()],
        tone=tone,
        note="Counts of matched items in a limited RSS sample, not unique people, all mentions or a buy/sell signal.",
    )


def community(asset, fetch):
    key = "community:v1:" + asset["symbol"]
    cached = storage.cache_get(key)
    if cached and (now() - datetime.fromisoformat(cached["fetched_at"])).total_seconds() < 1800:
        return cached["value"]
    terms = " OR ".join('"' + a.replace('"', "") + '"' for a in aliases(asset))
    groups = (
        ["IndianStockMarket", "IndianStreetBets", "IndiaInvestments", "NSEbets"]
        if asset["market"] == "NSE"
        else ["stocks", "investing", "wallstreetbets"]
        if asset["market"] == "US"
        else ["CryptoCurrency", "Bitcoin", "ethereum"]
    )
    query = "(" + terms + ") AND (" + " OR ".join("subreddit:" + s for s in groups) + ")"
    url = "https://www.reddit.com/search.rss?" + urllib.parse.urlencode(
        dict(q=query, sort="new", t="month", type="link", limit=100)
    )
    try:
        root = ET.fromstring(fetch(url))
        posts = []
        seen = set()
        entries = root.findall(ATOM + "entry")
        for row in entries:
            identity = row.findtext(ATOM + "id", "")
            link = row.find(ATOM + "link")
            href = link.get("href", "") if link is not None else ""
            if not identity.startswith("t3_") or "/comments/" not in href or identity in seen:
                continue
            if urllib.parse.urlparse(href).hostname not in (
                "www.reddit.com",
                "reddit.com",
                "old.reddit.com",
            ):
                continue
            title = row.findtext(ATOM + "title", "")
            content = html.unescape(re.sub("<[^>]+>", " ", row.findtext(ATOM + "content", "")))
            if not matches(title + " " + content, asset):
                continue
            category = row.find(ATOM + "category")
            subreddit = category.get("label", "") if category is not None else ""
            if subreddit.lower().removeprefix("r/") not in {s.lower() for s in groups}:
                continue
            try:
                published = (
                    datetime.fromisoformat(
                        (
                            row.findtext(ATOM + "published") or row.findtext(ATOM + "updated", "")
                        ).replace("Z", "+00:00")
                    )
                    .astimezone(UTC)
                    .isoformat()
                )
            except ValueError:
                continue
            seen.add(identity)
            posts.append(
                dict(
                    id=identity,
                    title=title,
                    url=href,
                    source=subreddit or "Reddit",
                    published_at=published,
                    tone=wording(title),
                )
            )
        posts.sort(key=lambda r: r["published_at"], reverse=True)
        value = dict(
            available=True,
            posts=posts,
            activity=activity(posts, capped=len(entries) >= 100),
            source="Reddit public RSS",
            query=query,
            source_url="https://www.reddit.com/search/?"
            + urllib.parse.urlencode(dict(q=query, sort="new", t="month", type="link")),
            fetched_at=now().isoformat(),
            reason="Post titles/body mentions in selected investing communities. Comments, votes, unique users and other social sites are not counted. Wording is a simple English phrase check, not a measured investor consensus.",
        )
        storage.cache_set(key, value, now().isoformat())
        return value
    except Exception:
        reason = "Reddit public discussion feed is unavailable. No sentiment or mention count is inferred from this failure."
        value = (
            dict(cached["value"], cached=True, error=reason)
            if cached
            else dict(available=False, posts=[], reason=reason)
        )
        storage.cache_set(key, value, now().isoformat())
        return value


def trends(asset, fetch):
    geo = "IN" if asset["market"] == "NSE" else "US"
    query = (ALIASES.get(asset["symbol"]) or [asset["name"]])[0] + (
        " share price"
        if asset["market"] == "NSE"
        else " stock"
        if asset["market"] == "US"
        else " price"
    )
    result = dict(
        available=False,
        query=query,
        geo=geo,
        unit="Relative search interest (0–100)",
        explore_url="https://trends.google.com/trends/explore?"
        + urllib.parse.urlencode(dict(date="today 3-m", geo=geo, q=query)),
        reason="Google Trends is free to view. Per-stock automatic history is not connected: Google’s official API is limited-access alpha. Import its free CSV to see a local history. A Trends index is not an exact search count.",
    )
    imported = storage.cache_get("trends:" + asset["symbol"])
    if imported:
        result.update(imported["value"])
    key = "google-trending:" + geo
    cached = storage.cache_get(key)
    try:
        with TREND_LOCK:
            cached = storage.cache_get(key)
            if (
                not cached
                or (now() - datetime.fromisoformat(cached["fetched_at"])).total_seconds() > 1800
            ):
                root = ET.fromstring(fetch("https://trends.google.com/trending/rss?geo=" + geo))
                topics = []
                for row in root.findall("./channel/item"):
                    topics.append(
                        dict(
                            title=row.findtext("title", ""),
                            traffic=row.findtext(TREND_NS + "approx_traffic", ""),
                            published_at=row.findtext("pubDate", ""),
                        )
                    )
                storage.cache_set(key, topics, now().isoformat())
                cached = dict(value=topics, fetched_at=now().isoformat())
        matches_now = [r for r in cached["value"] if matches(r["title"], asset)]
        result["trending_now"] = dict(
            available=True,
            matches=matches_now,
            topic_count=len(cached["value"]),
            fetched_at=cached["fetched_at"],
            note="Limited current trending-topic feed. No match does not mean low searches. Traffic is an approximate topic label, not a count for this exact stock search term.",
        )
    except Exception:
        result["trending_now"] = dict(
            available=False,
            matches=[],
            note="Google’s public trending-topic feed is unavailable.",
        )
    return result


def import_trends(asset, text, clock=None):
    clock = clock or now()
    if not isinstance(text, str) or len(text) > 500_000:
        raise ValueError("Choose a Google Trends CSV smaller than 500 KB")
    rows = list(csv.reader(io.StringIO(text.lstrip("\ufeff"))))
    header = None
    points = []
    for row in rows:
        if row and row[0].strip().lower() in ("day", "week"):
            header = row
            break
    if header is None or len(header) != 2:
        raise ValueError("Export one search term from Google Trends with Day or Week rows")
    if not matches(header[1], asset):
        raise ValueError(
            "The CSV search term does not identify "
            + asset["symbol"]
            + ". Export a single company search term for this stock."
        )
    interval = header[0].strip().lower()
    seen = set()
    local_today = clock.astimezone(
        ZoneInfo("Asia/Kolkata" if asset["market"] == "NSE" else "America/New_York")
    ).date()
    for row in rows[rows.index(header) + 1 :]:
        if not row or not row[0].strip():
            continue
        if len(row) != 2:
            raise ValueError("Use a single-term Google Trends CSV")
        try:
            day = date.fromisoformat(row[0].strip())
        except ValueError:
            raise ValueError("Google Trends dates must use YYYY-MM-DD") from None
        if str(day) in seen:
            raise ValueError("The CSV contains a duplicate date")
        seen.add(str(day))
        raw = row[1].strip()
        if raw in ("<1", "< 1", ""):
            value = None
        else:
            try:
                value = float(raw)
            except ValueError:
                raise ValueError("Search interest must be 0–100 or <1") from None
            if not math.isfinite(value) or not 0 <= value <= 100:
                raise ValueError("Search interest must be between 0 and 100")
        if day + timedelta(days=7 if interval == "week" else 1) > local_today:
            continue
        points.append(dict(date=str(day), value=value, low_volume=raw in ("<1", "< 1")))
    points.sort(key=lambda r: r["date"])
    count = 4 if interval == "week" else 7
    if len(points) < count * 2:
        raise ValueError("Import at least 14 completed daily points or 8 completed weekly points")
    recent = points[-count:]
    previous = points[-2 * count : -count]
    latest = points[-2 * count :]
    step = 7 if interval == "week" else 1
    contiguous = all(
        (date.fromisoformat(b["date"]) - date.fromisoformat(a["date"])).days == step
        for a, b in zip(latest, latest[1:])
    )
    valid = contiguous and all(p["value"] is not None for p in latest)
    a = sum(p["value"] for p in recent) / count if valid else None
    b = sum(p["value"] for p in previous) / count if valid else None
    change = (a / b - 1) * 100 if valid and b else None
    stale = (local_today - date.fromisoformat(points[-1]["date"])).days > (
        14 if interval == "week" else 3
    )
    label = (
        "Check imported data"
        if stale or not valid
        else "Search interest rising"
        if a > b
        else "Search interest falling"
        if a < b
        else "Search interest flat"
    )
    value = dict(
        available=True,
        points=points[-120:],
        query=header[1],
        source="Your Google Trends CSV",
        unit="Relative search interest (0–100)",
        interval=interval,
        comparison=dict(
            recent=a,
            previous=b,
            change=change,
            label=label,
            window="Latest 4 completed weeks vs preceding 4"
            if interval == "week"
            else "Latest 7 completed days vs preceding 7",
            complete=valid,
            stale=stale,
        ),
        as_of=points[-1]["date"],
        fetched_at=clock.isoformat(),
        note="One query, region and export period. Each CSV is scaled within its own selected range; scores from different exports/stocks are not directly comparable. Zero can mean low data, and <1 is not replaced by a fabricated value.",
    )
    storage.cache_set("trends:" + asset["symbol"], value, clock.isoformat())
    return value
