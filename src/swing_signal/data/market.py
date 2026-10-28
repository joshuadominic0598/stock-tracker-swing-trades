"""Network adapters. Retain last good responses; never synthesize market candles."""

import concurrent.futures
import copy
import email.utils
import hashlib
import json
import math
import threading
import time
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from datetime import date, datetime, timedelta, timezone
from zoneinfo import ZoneInfo

from swing_signal.ai import settings
from swing_signal.analysis.candidates import long_candidates
from swing_signal.analysis.indicators import candidate_zones, enrich, summarize, weekly
from swing_signal.analysis.signals import assess, financial_meanings
from swing_signal.config import BENCHMARKS, CRYPTO_PAIRS, US_SECTORS, research_group
from swing_signal.data import attention, storage

UTC = timezone.utc
IST = timezone(timedelta(hours=5, minutes=30))
HEADERS = {"User-Agent": "Mozilla/5.0 (compatible; SignalDesk/1.0; personal research)"}
state = dict(running=False, completed=0, total=0, errors={}, started_at=None, finished_at=None)
state_lock = threading.Lock()

def now():
    return datetime.now(UTC).isoformat()

def request(url, json_body=None, timeout=15):
    headers = dict(HEADERS)
    data = None
    if json_body is not None:
        headers["Content-Type"] = "application/json"
        data = json.dumps(json_body).encode()
    req = urllib.request.Request(url, data=data, headers=headers)
    with urllib.request.urlopen(req, timeout=timeout) as response:
        return response.read()

def get_json(url):
    return json.loads(request(url))

def yahoo_recent_days(symbol, missing, zone, daily_volumes=None):
    """Resample only complete regular NSE sessions from Yahoo's own hourly bars."""
    today = datetime.now(zone).date()
    wanted = {day for day in missing if 0 <= (today - date.fromisoformat(day)).days <= 30}
    if not wanted:
        return {}
    raw = get_json(
        "https://query1.finance.yahoo.com/v8/finance/chart/"
        + urllib.parse.quote(symbol)
        + "?range=1mo&interval=60m"
    )["chart"]["result"][0]
    fields = raw["indicators"]["quote"][0]
    groups = {}
    for i, stamp in enumerate(raw.get("timestamp", [])):
        dt = datetime.fromtimestamp(stamp, zone)
        day = dt.date().isoformat()
        if day not in wanted:
            continue
        if dt.date() == today and (
            datetime.now(zone).hour,
            datetime.now(zone).minute,
        ) < (15, 40):
            continue
        try:
            values = [fields[k][i] for k in ("open", "high", "low", "close", "volume")]
        except (KeyError, IndexError):
            continue
        if any(v is None or not math.isfinite(v) for v in values):
            continue
        o, h, low, c, v = values
        if min(o, h, low, c) <= 0 or v < 0 or low > min(o, c) or h < max(o, c):
            continue
        if (dt.hour * 60 + dt.minute - 555) % 60 or not 555 <= dt.hour * 60 + dt.minute <= 915:
            continue
        groups.setdefault(day, []).append((dt.hour * 60 + dt.minute, values))
    result = {}
    expected = {555 + 60 * i for i in range(7)}
    for day, parts in groups.items():
        if len(parts) != 7 or {t for t, _ in parts} != expected:
            continue
        parts.sort()
        values = [v for _, v in parts]
        reported_volume = (daily_volumes or {}).get(day)
        if (
            symbol.endswith(".NS")
            and reported_volume is None
            and any(v[4] == 0 and v[1] > v[2] for v in values)
        ):
            continue
        result[day] = dict(
            time=day,
            open=values[0][0],
            high=max(v[1] for v in values),
            low=min(v[2] for v in values),
            close=values[-1][3],
            volume=reported_volume if reported_volume is not None else sum(v[4] for v in values),
            volume_basis="Yahoo daily reported volume"
            if reported_volume is not None
            else "Yahoo hourly sum",
            resampled_from="Yahoo hourly regular-session candles",
        )
    return result

def yahoo(symbol):
    encoded = urllib.parse.quote(symbol)
    url = f"https://query1.finance.yahoo.com/v8/finance/chart/{encoded}?range=2y&interval=1d&events=div%2Csplits"
    raw = get_json(url)["chart"]
    if raw.get("error") or not raw.get("result"):
        raise ValueError("No price history returned by Yahoo Finance")
    data = raw["result"][0]
    meta = data["meta"]
    q = data["indicators"]["quote"][0]
    bars = {}
    missing = []
    daily_volumes = {}
    zone = ZoneInfo(meta.get("exchangeTimezoneName", "Asia/Kolkata"))
    today = datetime.now(zone).date()
    session_end = meta.get("currentTradingPeriod", {}).get("regular", {}).get("end", 0)
    for i, ts in enumerate(data.get("timestamp", [])):
        day = datetime.fromtimestamp(ts, zone).date()
        # Today is included only after the provider's regular session has ended.
        if day > today or (day == today and (not session_end or time.time() < session_end)):
            continue
        vals = [q.get(k, [])[i] for k in ("open", "high", "low", "close", "volume")]
        if vals[-1] is not None and math.isfinite(vals[-1]) and vals[-1] >= 0:
            daily_volumes[day.isoformat()] = vals[-1]
        if any(v is None or not math.isfinite(v) for v in vals) or vals[3] <= 0:
            missing.append(day.isoformat())
            continue
        bars[day.isoformat()] = dict(
            time=day.isoformat(),
            **dict(zip(("open", "high", "low", "close", "volume"), vals)),
        )
    repaired = {}
    if (symbol.endswith(".NS") or symbol in ("^NSEI", "^NSEBANK")) and missing:
        try:
            repaired = yahoo_recent_days(symbol, missing, zone, daily_volumes)
        except Exception:
            repaired = {}
        bars.update(repaired)
        missing = [day for day in missing if day not in repaired]
    if not bars:
        raise ValueError("No completed daily candles available")
    ordered = [bars[k] for k in sorted(bars)]
    events = []
    for kind, values in data.get("events", {}).items():
        for v in values.values():
            events.append(
                dict(
                    kind=kind,
                    date=datetime.fromtimestamp(v["date"], zone).date().isoformat(),
                    value=v.get("amount") if kind == "dividends" else v.get("splitRatio"),
                )
            )
    recent_missing = [
        day
        for day in missing
        if day >= (date_from_string(ordered[-1]["time"]) - timedelta(days=14)).isoformat()
    ]
    quality_note = (
        (
            "Provider has missing completed candle data through "
            + max(recent_missing)
            + ". Calculations use available history through "
            + ordered[-1]["time"]
            + "."
        )
        if recent_missing
        else None
    )
    return dict(
        bars=ordered,
        quality_note=quality_note,
        missing_dates=missing,
        quote=quote_from_yahoo(data),
        source="Yahoo Finance",
        source_url=f"https://finance.yahoo.com/quote/{encoded}/",
        provider_symbol=symbol,
        currency=meta.get("currency", "INR"),
        events=sorted(events, key=lambda e: e["date"], reverse=True)[:12],
        as_of=datetime.fromisoformat(
            ordered[-1]["time"] + ("T15:30:00" if meta.get("currency") == "INR" else "T16:00:00")
        )
        .replace(tzinfo=zone)
        .isoformat(),
        fetched_at=now(),
        resampled_dates=sorted(repaired),
        methodology="Yahoo daily OHLCV; when recent daily values are missing, only complete 7-bar Yahoo hourly NSE regular sessions are aggregated. Reported daily volume is preferred to the hourly sum when available; auction/official daily conventions can differ. Not a total-return series.",
    )

def crypto(asset):
    pair = CRYPTO_PAIRS.get(asset["symbol"], asset["symbol"])
    url = f"https://data-api.binance.vision/api/v3/klines?symbol={urllib.parse.quote(pair)}&interval=1d&limit=730"
    raw = get_json(url)
    if not isinstance(raw, list):
        raise ValueError("Binance returned no candle history")
    bars = [
        dict(
            time=datetime.fromtimestamp(r[0] / 1000, UTC).date().isoformat(),
            open=float(r[1]),
            high=float(r[2]),
            low=float(r[3]),
            close=float(r[4]),
            volume=float(r[5]),
        )
        for r in raw
        if r[6] / 1000 < time.time()
    ]
    if not bars:
        raise ValueError("No completed UTC candles returned")
    return dict(
        bars=bars,
        source="Binance public market data",
        source_url=f"https://www.binance.com/en/trade/{pair.removesuffix('USDT')}_USDT",
        provider_symbol=pair,
        currency="USDT",
        events=[],
        as_of=(
            datetime.fromisoformat(bars[-1]["time"]).replace(tzinfo=UTC) + timedelta(days=1)
        ).isoformat(),
        fetched_at=now(),
        methodology="USDT spot pair. Completed UTC daily candles; USDT is not USD.",
    )

def fetch_asset(asset):
    data = (
        crypto(asset)
        if asset["market"] == "CRYPTO"
        else yahoo(asset["symbol"] + (".NS" if asset["market"] == "NSE" else ""))
    )
    save_price("price:" + asset["symbol"], data, allow_source_change=True)
    if data.get("quote"):
        save_quote(asset["symbol"], data["quote"])

def save_price(key, data, allow_source_change=False):
    previous = storage.cache_get(key)
    changing_to_yahoo = (
        allow_source_change
        and data.get("source") == "Yahoo Finance"
        and previous
        and previous["value"].get("source") != "Yahoo Finance"
    )
    if previous and not changing_to_yahoo:
        old = previous["value"].get("bars", [])
        if old and data["bars"][-1]["time"] < old[-1]["time"]:
            raise ValueError(
                "Provider returned older history; retained cached candles through "
                + old[-1]["time"]
            )
    storage.cache_set(key, data, now())

def fetch_context():
    value = get_json("https://api.coingecko.com/api/v3/global")["data"]
    storage.cache_set("global", value, now())

def refresh():
    with state_lock:
        if state["running"]:
            return False
        assets = storage.rows("SELECT * FROM assets")
        state.update(
            running=True,
            completed=0,
            total=len(assets) + len(BENCHMARKS) + len(US_SECTORS) + 2,
            errors={},
            started_at=now(),
            phase="Refreshing Yahoo Finance and crypto data",
        )

    def run():
        def sector(code):
            save_price("us-sector:" + code, yahoo(code))

        jobs = [(a["symbol"], lambda a=a: fetch_asset(a)) for a in assets]
        jobs += [
            (
                key,
                lambda code=code, key=key, name=name: save_price(
                    "benchmark:" + key, yahoo(code), allow_source_change=True
                ),
            )
            for key, code, name in BENCHMARKS
        ]
        jobs += [("US:" + code, lambda code=code: sector(code)) for code, _ in US_SECTORS]
        jobs += [
            ("TOTAL", fetch_context),
            ("QUOTES", lambda: refresh_quotes(force=True)),
        ]
        with state_lock:
            state["phase"] = "Refreshing market histories and quotes"
        with concurrent.futures.ThreadPoolExecutor(max_workers=4) as pool:
            futures = {pool.submit(fn): key for key, fn in jobs}
            for future in concurrent.futures.as_completed(futures):
                key = futures[future]
                try:
                    future.result()
                except Exception as exc:
                    with state_lock:
                        state["errors"][key] = str(exc)[:180]
                finally:
                    with state_lock:
                        state["completed"] += 1
        with state_lock:
            state.update(running=False, finished_at=now(), phase="Complete")

    threading.Thread(target=run, daemon=True).start()
    return True

def get_state():
    with state_lock:
        return dict(state, errors=dict(state["errors"]))

ANALYSIS_CACHE = {}

def analysis(data, manual, timeframe):
    key = (
        data["provider_symbol"],
        data.get("fetched_at"),
        data["as_of"],
        timeframe,
        json.dumps(manual, sort_keys=True),
    )
    if key in ANALYSIS_CACHE:
        return copy.deepcopy(ANALYSIS_CACHE[key])
    bars = enrich(weekly(data["bars"]) if timeframe == "1w" else data["bars"])
    candidates = candidate_zones(bars, timeframe)
    levels = copy.deepcopy(manual)
    for z in levels:
        z.update(
            source="manual",
            evidence=["Your manually marked level"],
            broken=bars[-1]["close"] < z["low"]
            if z["kind"] == "demand"
            else bars[-1]["close"] > z["high"],
        )
    valid = [z for z in levels if not z["broken"]] + candidates
    summary = summarize(bars, valid)
    if timeframe == "1w" and summary.get("trend"):
        summary["trend"] = summary["trend"].replace("50 DMA", "50-week SMA")
    swing = assess(bars, valid, timeframe, data["bars"])
    summary["flags"] = [
        dict(label=s["title"], met=(s.get("score") or 0) > 0)
        for s in swing["signals"]
        if s["key"] in ("rsi", "stoch", "ma", "zones")
    ]
    result = dict(bars=bars, candidates=candidates, zones=levels, summary=summary, swing=swing)
    if len(ANALYSIS_CACHE) > 250:
        ANALYSIS_CACHE.clear()
    ANALYSIS_CACHE[key] = copy.deepcopy(result)
    return result

def asset_detail(asset, timeframe="1d", include_bars=True):
    cached = storage.cache_get("price:" + asset["symbol"])
    manual = storage.rows("SELECT * FROM zones WHERE symbol=? ORDER BY id", (asset["symbol"],))
    journal = storage.rows("SELECT * FROM journal WHERE symbol=?", (asset["symbol"],))
    position = storage.rows("SELECT * FROM positions WHERE symbol=?", (asset["symbol"],))
    quote = storage.cache_get("quote:" + asset["symbol"])
    base = dict(
        asset,
        group=research_group(asset),
        zones=manual,
        journal=journal[0] if journal else {},
        position=position[0] if position else {},
        available=bool(cached),
        quote=quote["value"] if quote else None,
    )
    if not cached:
        return dict(
            base,
            bars=[],
            summary={},
            swing=assess([], []),
            daily_swing=assess([], []),
            weekly_swing=assess([], []),
            candidates=[],
            error=get_state()["errors"].get(asset["symbol"]),
        )
    data = cached["value"]
    computed = analysis(data, manual, timeframe)
    daily = computed if timeframe == "1d" else analysis(data, manual, "1d")
    week = computed if timeframe == "1w" else analysis(data, manual, "1w")
    # Annotate overlap without counting the same price evidence as an independent signal.
    for z in computed["candidates"]:
        other = week["candidates"] if timeframe == "1d" else daily["candidates"]
        if any(
            o["kind"] == z["kind"] and max(o["low"], z["low"]) <= min(o["high"], z["high"])
            for o in other
        ):
            z["evidence"].append(
                "Overlaps a " + ("weekly" if timeframe == "1d" else "daily") + " candidate"
            )
    age = (datetime.now(UTC) - datetime.fromisoformat(data["as_of"])).total_seconds() / 3600
    stale = age > (48 if asset["market"] == "CRYPTO" else 96)
    for c in (computed, daily, week):
        if stale or data.get("quality_note"):
            c["swing"].update(
                raw_label=c["swing"]["label"],
                label="Check data first",
                direction="unavailable",
                data_warning=True,
            )
    latest = date_from_string(data["bars"][-1]["time"])
    current = datetime.now(
        IST
        if asset["market"] == "NSE"
        else ZoneInfo("America/New_York")
        if asset["market"] == "US"
        else UTC
    )
    monday = current.date() - timedelta(days=current.weekday())
    week_partial = latest >= monday and (
        latest < monday + timedelta(days=6)
        if asset["market"] == "CRYPTO"
        else current.weekday() < 4
        or current.weekday() == 4
        and (current.hour, current.minute) < ((15, 30) if asset["market"] == "NSE" else (16, 0))
    )
    base.update(
        **computed,
        source=data["source"],
        source_url=data["source_url"],
        provider_symbol=data["provider_symbol"],
        currency=data["currency"],
        fetched_at=cached["fetched_at"],
        as_of=data["as_of"],
        stale=stale,
        refresh_error=get_state()["errors"].get(asset["symbol"]),
        events=data.get("events", []),
        quality_note=data.get("quality_note"),
        resampled_dates=data.get("resampled_dates", []),
        methodology=data.get("methodology"),
        timeframe=timeframe,
        daily_swing=daily["swing"],
        weekly_swing=week["swing"],
        week_partial=week_partial,
    )
    base["analysis_fingerprint"] = hashlib.sha256(
        json.dumps(
            dict(
                version=5,
                summary=computed["summary"],
                daily=daily["swing"],
                weekly=week["swing"],
                as_of=data["as_of"],
            ),
            sort_keys=True,
        ).encode()
    ).hexdigest()
    if include_bars:
        ai = storage.cache_get("ai:" + asset["symbol"] + ":" + timeframe)
        base["ai_brief"] = ai["value"] if ai else None
    else:
        base["bars"] = []
    return base

def date_from_string(value):
    return datetime.fromisoformat(value).date()

def overview():
    assets = [
        asset_detail(a, include_bars=False)
        for a in storage.rows("SELECT * FROM assets ORDER BY rowid")
    ]
    benchmarks = []
    for key, _, name in BENCHMARKS:
        cached = storage.cache_get("benchmark:" + key)
        if cached:
            data = cached["value"]
            bars = data["bars"]
            last = bars[-1]
            prev = bars[-2]
            weeks = weekly(bars)
            week_change = (
                (weeks[-1]["close"] / weeks[-2]["close"] - 1) * 100 if len(weeks) > 1 else None
            )
            benchmarks.append(
                dict(
                    symbol=key,
                    name=name,
                    price=last["close"],
                    change=(last["close"] / prev["close"] - 1) * 100,
                    week_change=week_change,
                    currency="USD" if key == "US50" else None,
                    sparkline=[b["close"] for b in bars[-25:]],
                    as_of=data["as_of"],
                    source=data["source"],
                    source_url=data["source_url"],
                    quality_note=data.get("quality_note"),
                )
            )
        else:
            benchmarks.append(dict(symbol=key, name=name, price=None, change=None, sparkline=[]))
    btc = next((a for a in assets if a["symbol"] == "BTCUSDT"), None)
    if btc and btc["available"]:
        benchmarks.append(
            dict(
                symbol="BTC",
                name="Bitcoin · USDT",
                week_change=btc["weekly_swing"]["change"],
                **{k: btc["summary"][k] for k in ("price", "change", "sparkline")},
                as_of=btc["as_of"],
                source=btc["source"],
                source_url=btc["source_url"],
            )
        )
    global_cache = storage.cache_get("global")
    if global_cache:
        g = global_cache["value"]
        benchmarks.append(
            dict(
                symbol="TOTAL",
                name="Crypto market cap · USD",
                price=g["total_market_cap"]["usd"],
                change=g.get("market_cap_change_percentage_24h_usd"),
                sparkline=[],
                as_of=datetime.fromtimestamp(g["updated_at"], UTC).isoformat(),
                source="CoinGecko",
                source_url="https://www.coingecko.com/en/global-charts",
                dominance=g["market_cap_percentage"].get("btc"),
            )
        )
    else:
        benchmarks.append(
            dict(
                symbol="TOTAL",
                name="Crypto market cap · USD",
                price=None,
                change=None,
                sparkline=[],
            )
        )
    return dict(
        assets=assets,
        benchmarks=benchmarks,
        refresh=get_state(),
        global_data=global_cache,
        server_time=now(),
        sectors=sector_overview(assets),
        us_sectors=us_sectors(),
        correlations=correlations(),
        connections=settings.public(),
        quote_state=dict(QUOTE_STATE),
        long_candidates={tf: long_candidates(assets, tf) for tf in ("1d", "1w")},
    )

FUND_TYPES = [
    "TotalRevenue",
    "NetIncome",
    "DilutedEPS",
    "TotalDebt",
    "StockholdersEquity",
    "OperatingCashFlow",
    "FreeCashFlow",
]

def fundamentals(asset):
    if (
        asset["market"] == "CRYPTO"
        or "ETF" in asset["sector"].upper()
        or "ETF" in asset["name"].upper()
    ):
        return dict(available=False, reason="Company financials do not apply to this asset.")
    key = "fundamentals:" + asset["symbol"]
    cached = storage.cache_get(key)
    if (
        cached
        and (datetime.now(UTC) - datetime.fromisoformat(cached["fetched_at"])).total_seconds()
        < 86400
    ):
        return cached["value"]
    types = ",".join("annual" + t for t in FUND_TYPES)
    code = asset["symbol"] + (".NS" if asset["market"] == "NSE" else "")
    url = f"https://query1.finance.yahoo.com/ws/fundamentals-timeseries/v1/finance/timeseries/{code}?type={types}&period1=1577836800&period2={int(time.time())}"
    try:
        raw = get_json(url)["timeseries"]
        metrics = {}
        for item in raw.get("result", []):
            metric = item["meta"]["type"][0]
            values = [
                dict(
                    date=v["asOfDate"],
                    value=v["reportedValue"]["raw"],
                    currency=v.get("currencyCode"),
                )
                for v in item.get(metric, [])
                if v.get("reportedValue", {}).get("raw") is not None
            ]
            if values:
                metrics[metric.removeprefix("annual")] = sorted(values, key=lambda x: x["date"])
        value = dict(
            available=bool(metrics),
            metrics=metrics,
            source="Yahoo Finance · annual reported financials",
            source_url=f"https://finance.yahoo.com/quote/{code}/financials/",
            fetched_at=now(),
        )
        if not metrics:
            value["reason"] = "No reported fundamentals returned by this provider."
        storage.cache_set(key, value, now())
        return value
    except Exception as exc:
        return (
            dict(cached["value"], error=str(exc), cached=True)
            if cached
            else dict(available=False, reason=str(exc))
        )

def news(asset):
    key = "news:v3:" + asset["symbol"]
    cached = storage.cache_get(key)
    if (
        cached
        and (datetime.now(UTC) - datetime.fromisoformat(cached["fetched_at"])).total_seconds()
        < 1800
    ):
        return cached["value"]
    terms = " OR ".join('"' + a.replace('"', "") + '"' for a in attention.aliases(asset))
    query = (
        "("
        + terms
        + ") "
        + (
            "(crypto OR price)"
            if asset["market"] == "CRYPTO"
            else "(stock OR shares OR earnings OR NSE)"
        )
        + " when:14d"
    )
    url = "https://news.google.com/rss/search?" + urllib.parse.urlencode(
        dict(q=query, hl="en-IN", gl="IN", ceid="IN:en")
    )
    try:
        root = ET.fromstring(request(url))
        articles = []
        seen = set()
        for item in root.findall("./channel/item"):
            headline = item.findtext("title", "")
            normalized = " ".join(headline.lower().split())
            if normalized in seen:
                continue
            seen.add(normalized)
            published = item.findtext("pubDate", "")
            try:
                published = email.utils.parsedate_to_datetime(published).isoformat()
            except (TypeError, ValueError):
                published = None
            source = item.findtext("source", "Publisher")
            title = headline.rsplit(" - " + source, 1)[0]
            # RSS search may match a passing mention in a broad market article.
            # Keep headlines that identify this asset rather than presenting those as company news.
            if not attention.matches(title, asset):
                continue
            articles.append(
                dict(
                    title=title,
                    url=item.findtext("link", ""),
                    source=source,
                    published_at=published,
                    tone=attention.wording(title),
                )
            )
        articles.sort(key=lambda a: a["published_at"] or "", reverse=True)
        value = dict(
            available=True,
            articles=articles[:100],
            activity=attention.activity(
                articles[:100], capped=len(root.findall("./channel/item")) >= 100
            ),
            fetched_at=now(),
            source="Google News RSS",
            query=query,
        )
        storage.cache_set(key, value, now())
        return value
    except Exception as exc:
        return (
            dict(cached["value"], error=str(exc), cached=True)
            if cached
            else dict(available=False, articles=[], error=str(exc))
        )

def research(asset):
    with concurrent.futures.ThreadPoolExecutor(max_workers=4) as pool:
        f = pool.submit(fundamentals, asset)
        n = pool.submit(news, asset)
        c = pool.submit(attention.community, asset, request)
        t = pool.submit(attention.trends, asset, request)
        financial = f.result()
        meanings = financial_meanings(financial.get("metrics", {}), asset["sector"])
        return dict(
            fundamentals=dict(financial, explanations=meanings),
            news=n.result(),
            social_sentiment=c.result(),
            search_interest=t.result(),
        )

QUOTE_STATE = {"running": False, "errors": {}, "finished_at": None}
QUOTE_LOCK = threading.Lock()

def quote_from_yahoo(data):
    meta = data["meta"]
    price = meta.get("regularMarketPrice")
    timestamp = meta.get("regularMarketTime")
    if price is None or not timestamp:
        return None
    zone = ZoneInfo(meta.get("exchangeTimezoneName", "Asia/Kolkata"))
    day = datetime.fromtimestamp(timestamp, zone).date()
    q = data["indicators"]["quote"][0]
    prior = []
    for i, ts in enumerate(data.get("timestamp", [])):
        value = q.get("close", [])[i]
        if value and datetime.fromtimestamp(ts, zone).date() < day:
            prior.append(value)
    previous = (
        prior[-1] if prior else meta.get("previousClose") or meta.get("regularMarketPreviousClose")
    )
    return dict(
        price=price,
        change=(price / previous - 1) * 100 if previous else None,
        as_of=datetime.fromtimestamp(timestamp, UTC).isoformat(),
        fetched_at=now(),
        source="Yahoo quote metadata",
        currency=meta.get("currency"),
        kind="Provider snapshot",
        delay_note="Delay is not guaranteed. Check the actual quote timestamp; indicators use completed candles.",
    )

def save_quote(symbol, value):
    if not value or value.get("price") is None:
        return
    previous = storage.cache_get("quote:" + symbol)
    changing_to_yahoo = (
        value.get("source") == "Yahoo quote metadata"
        and previous
        and previous["value"].get("source") != "Yahoo quote metadata"
    )
    if (
        previous
        and not changing_to_yahoo
        and previous["value"].get("as_of")
        and value.get("as_of")
        and datetime.fromisoformat(previous["value"]["as_of"])
        > datetime.fromisoformat(value["as_of"])
    ):
        return
    storage.cache_set("quote:" + symbol, value, now())

def public_quote(asset):
    if asset["market"] == "CRYPTO":
        pair = CRYPTO_PAIRS.get(asset["symbol"], asset["symbol"])
        q = get_json(
            "https://data-api.binance.vision/api/v3/ticker/24hr?symbol=" + urllib.parse.quote(pair)
        )
        return dict(
            price=float(q["lastPrice"]),
            change=float(q["priceChangePercent"]),
            as_of=datetime.fromtimestamp(q["closeTime"] / 1000, UTC).isoformat(),
            fetched_at=now(),
            source="Binance 24h ticker",
            currency="USDT",
            kind="24h ticker snapshot",
            delay_note="Rolling 24h change; separate from UTC daily candle signals.",
        )
    symbol = asset["symbol"] + (".NS" if asset["market"] == "NSE" else "")
    data = get_json(
        "https://query1.finance.yahoo.com/v8/finance/chart/"
        + urllib.parse.quote(symbol)
        + "?range=5d&interval=1d"
    )["chart"]["result"][0]
    return quote_from_yahoo(data)

def refresh_quotes(force=False):
    if not QUOTE_LOCK.acquire(blocking=False):
        return False
    QUOTE_STATE.update(running=True, errors={})
    try:
        assets = storage.rows("SELECT * FROM assets")
        jobs = []
        for a in assets:
            cached = storage.cache_get("quote:" + a["symbol"])
            if not force and cached:
                elapsed = (
                    datetime.now(UTC) - datetime.fromisoformat(cached["fetched_at"])
                ).total_seconds()
                if elapsed < 120:
                    continue
                zone = IST if a["market"] == "NSE" else ZoneInfo("America/New_York")
                clock = datetime.now(zone)
                closed = a["market"] != "CRYPTO" and (
                    clock.weekday() >= 5 or clock.hour < 9 or clock.hour > 16
                )
                if closed and elapsed < 900:
                    continue
            jobs.append(a)
        with concurrent.futures.ThreadPoolExecutor(max_workers=4) as pool:
            futures = {pool.submit(public_quote, a): a["symbol"] for a in jobs}
            for f in concurrent.futures.as_completed(futures):
                symbol = futures[f]
                try:
                    save_quote(symbol, f.result())
                except Exception as exc:
                    QUOTE_STATE["errors"][symbol] = str(exc)[:160]
        QUOTE_STATE["finished_at"] = now()
        return True
    finally:
        QUOTE_STATE["running"] = False
        QUOTE_LOCK.release()

def sector_overview(assets):
    result = []
    for group in dict.fromkeys(a["group"] for a in assets if a["market"] == "NSE"):
        members = [a for a in assets if a["market"] == "NSE" and a["group"] == group]
        ready = [a for a in members if a["available"]]
        changes = [a["summary"]["change"] for a in ready]
        fresh = [a for a in ready if not a.get("stale") and not a.get("quality_note")]
        result.append(
            dict(
                name=group,
                count=len(members),
                available=len(ready),
                fresh_count=len(fresh),
                change=sum(changes) / len(changes) if changes else None,
                advancing=sum(v > 0 for v in changes),
                buy_side=sum(a["daily_swing"]["direction"] == "bullish" for a in ready),
                sell_side=sum(a["daily_swing"]["direction"] == "bearish" for a in ready),
                symbols=[a["symbol"] for a in members],
                dates=sorted(set(a["summary"]["candle_date"] for a in ready)),
                note="Equal-weight move of your tracked names; not an official sector index.",
            )
        )
    return result

def us_sectors():
    result = []
    for code, name in US_SECTORS:
        cached = storage.cache_get("us-sector:" + code)
        if not cached:
            result.append(dict(symbol=code, name=name, available=False))
            continue
        d = cached["value"]
        bars = d["bars"]
        s = summarize(enrich(bars), [])
        result.append(
            dict(
                symbol=code,
                name=name,
                available=True,
                change=s["change"],
                change_20d=s["change_20d"],
                as_of=d["as_of"],
                source=d["source"],
                source_url=d["source_url"],
                stale=(datetime.now(UTC) - datetime.fromisoformat(d["as_of"])).total_seconds()
                > 96 * 3600,
            )
        )
    return result

def correlations():
    """Pearson daily returns on matching local session dates; no forward filling."""
    series = {}
    for label, key in [
        ("NSE · Nifty 50", "benchmark:NIFTY50"),
        ("US · S&P 500", "benchmark:SP500"),
        ("Crypto · Bitcoin", "price:BTCUSDT"),
    ]:
        cached = storage.cache_get(key)
        if cached:
            bars = cached["value"].get("bars", [])
            # Keep each return interval, so a missing candle cannot create a mismatched multi-day return.
            series[label] = {
                b["time"]: (b["close"] / bars[i - 1]["close"] - 1, bars[i - 1]["time"])
                for i, b in enumerate(bars)
                if i and bars[i - 1]["close"]
            }
    result = []
    labels = ["NSE · Nifty 50", "US · S&P 500", "Crypto · Bitcoin"]
    for i, left in enumerate(labels):
        for right in labels[i + 1 :]:
            a = series.get(left, {})
            b = series.get(right, {})
            common = sorted(d for d in a.keys() & b.keys() if a[d][1] == b[d][1])[-60:]
            x = [a[d][0] for d in common]
            y = [b[d][0] for d in common]
            n = len(x)
            rho = None
            if n >= 20:
                mx = sum(x) / n
                my = sum(y) / n
                vx = sum((v - mx) ** 2 for v in x)
                vy = sum((v - my) ** 2 for v in y)
                if vx and vy:
                    rho = sum((v - mx) * (w - my) for v, w in zip(x, y)) / math.sqrt(vx * vy)
            result.append(
                dict(
                    left=left,
                    right=right,
                    value=rho,
                    samples=n,
                    from_date=common[0] if common else None,
                    through=common[-1] if common else None,
                    note="Up to 60 matched daily return intervals; ≥20 required. Different close times remain; association is not causation or a lead/lag signal.",
                )
            )
    return result

CATALOG_LOCK = threading.Lock()

def search_catalog(query):
    query = query.strip()
    if len(query) < 2:
        return dict(results=[])
    tracked = {a["symbol"]: a for a in storage.rows("SELECT * FROM assets")}
    key = "yahoo-search:" + query.upper()
    cached = storage.cache_get(key)
    if (
        not cached
        or (datetime.now(UTC) - datetime.fromisoformat(cached["fetched_at"])).total_seconds()
        > 86400
    ):
        try:
            raw = get_json(
                "https://query1.finance.yahoo.com/v1/finance/search?"
                + urllib.parse.urlencode(dict(q=query, quotesCount=30, newsCount=0))
            )
            records = []
            for q in raw.get("quotes", []):
                symbol = q.get("symbol", "")
                if not symbol.endswith(".NS"):
                    continue
                records.append(
                    dict(
                        symbol=symbol.removesuffix(".NS"),
                        name=q.get("longname") or q.get("shortname") or symbol,
                        market="NSE",
                        sector="Custom watchlist",
                    )
                )
            storage.cache_set(key, records, now())
            cached = dict(value=records)
        except Exception:
            if not cached:
                records = [
                    dict(a)
                    for a in tracked.values()
                    if a["market"] == "NSE"
                    and (query.upper() in a["symbol"] or query.lower() in a["name"].lower())
                ]
                return dict(
                    results=[dict(r, tracked=True) for r in records[:12]],
                    error="Yahoo search is unavailable. You can still add an exact NSE symbol.",
                    source="Saved watchlist",
                )
    results = cached["value"]
    results.sort(
        key=lambda r: (
            r["symbol"] != query.upper(),
            not r["symbol"].startswith(query.upper()),
            r["symbol"],
        )
    )
    return dict(
        results=[dict(r, tracked=r["symbol"] in tracked) for r in results[:12]],
        source="Yahoo Finance NSE search",
    )

def sector_context(asset):
    group = research_group(asset)
    all_peers = storage.rows("SELECT * FROM assets WHERE market=?", (asset["market"],))
    industry = [a for a in all_peers if a["sector"] == asset["sector"]]
    peers = industry if len(industry) >= 3 else [a for a in all_peers if research_group(a) == group]
    basis = "Tracked industry peers" if len(industry) >= 3 else "Your tracked research group"
    label = asset["sector"] if len(industry) >= 3 else group
    details = [asset_detail(a, include_bars=False) for a in peers]
    usable = [
        a
        for a in details
        if a.get("available") and not a.get("stale") and not a.get("quality_note")
    ]
    target = next((a for a in details if a["symbol"] == asset["symbol"]), None)
    latest = target.get("summary", {}).get("candle_date") if target else None
    same_day = [a for a in usable if a["summary"].get("candle_date") == latest]
    available = bool(target and target in same_day and len(same_day) >= 3)
    mean = sum(a["summary"]["change"] for a in same_day) / len(same_day) if available else None
    return dict(
        available=available,
        stock=asset["symbol"],
        industry=asset["sector"],
        research_group=group,
        label=label,
        basis=basis,
        sample_size=len(same_day),
        tracked_size=len(peers),
        as_of=latest,
        change=mean,
        relative_change=target["summary"]["change"] - mean if available else None,
        daily_buy=sum(a["daily_swing"]["direction"] == "bullish" for a in same_day),
        weekly_buy=sum(a["weekly_swing"]["direction"] == "bullish" for a in same_day),
        peers=[
            dict(
                symbol=a["symbol"],
                change=a["summary"]["change"],
                date=a["summary"]["candle_date"],
            )
            for a in same_day
        ],
        note="Equal-weight daily changes of at least three fresh tracked peers on the same candle date, including this stock. It is not a full-sector index. No reading is inferred from missing/stale peers.",
    )
