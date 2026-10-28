"""Curated starter watchlist. New workspaces never assume a personal holding."""

ASSETS = [
    ("HINDUNILVR", "Hindustan Unilever", "NSE", "Consumer staples", False),
    ("COALINDIA", "Coal India", "NSE", "Energy", False),
    ("GOLDBEES", "Nippon India Gold ETF", "NSE", "Gold ETF", False),
    ("SILVERBEES", "Nippon India Silver ETF", "NSE", "Silver ETF", False),
    ("ASIANPAINT", "Asian Paints", "NSE", "Consumer discretionary", False),
    ("COLPAL", "Colgate-Palmolive India", "NSE", "Consumer staples", False),
    ("NIFTYBEES", "Nippon India Nifty 50 ETF", "NSE", "Index ETF", False),
    ("IDFCFIRSTB", "IDFC First Bank", "NSE", "Banking", False),
    ("HDFCBANK", "HDFC Bank", "NSE", "Banking", False),
    ("THYROCARE", "Thyrocare Technologies", "NSE", "Healthcare", False),
    ("HCG", "Healthcare Global Enterprises", "NSE", "Healthcare", False),
    ("PRICOLLTD", "Pricol", "NSE", "Auto components", False),
    ("AXISBANK", "Axis Bank", "NSE", "Banking", False),
    ("JIOFIN", "Jio Financial Services", "NSE", "Financial services", False),
    ("TATAPOWER", "Tata Power", "NSE", "Power", False),
    ("LEMONTREE", "Lemon Tree Hotels", "NSE", "Hospitality", False),
    ("ITCHOTELS", "ITC Hotels", "NSE", "Hospitality", False),
    ("BTCUSDT", "Bitcoin", "CRYPTO", "Layer 1", False),
    ("ETHUSD", "Ethereum", "CRYPTO", "Layer 1", False),
    ("SOLUSD", "Solana", "CRYPTO", "Layer 1", False),
    ("ADAUSDT", "Cardano", "CRYPTO", "Layer 1", False),
    ("XLMUSDT", "Stellar", "CRYPTO", "Payments", False),
    ("XRPUSD", "XRP", "CRYPTO", "Payments", False),
]
BENCHMARKS = [("NIFTY50", "^NSEI", "Nifty 50"), ("BANKNIFTY", "^NSEBANK", "Nifty Bank")]
CRYPTO_PAIRS = {"ETHUSD": "ETHUSDT", "SOLUSD": "SOLUSDT", "XRPUSD": "XRPUSDT"}
COIN_IDS = {
    "BTCUSDT": "bitcoin",
    "ETHUSD": "ethereum",
    "SOLUSD": "solana",
    "ADAUSDT": "cardano",
    "XLMUSDT": "stellar",
    "XRPUSD": "ripple",
}

# Personal research groups, deliberately distinct from formal exchange sector classifications.
NSE_GROUPS = [
    "Materials & commodity ETFs",
    "Healthcare",
    "Entertainment & leisure",
    "Oil, gas & energy",
    "Technology",
    "Consumer",
    "Banking & finance",
    "Other NSE",
]
GROUP_SYMBOLS = {
    "Materials & commodity ETFs": ["GOLDBEES", "SILVERBEES", "METALIETF"],
    "Healthcare": ["HCG", "THYROCARE"],
    "Entertainment & leisure": ["ITCHOTELS", "LEMONTREE", "INDHOTEL"],
    "Oil, gas & energy": [
        "COALINDIA",
        "TATAPOWER",
        "ONGC",
        "OIL",
        "IOC",
        "BPCL",
        "HINDPETRO",
        "RELIANCE",
        "PETRONET",
    ],
    "Technology": ["INFY", "WIPRO", "TCS", "HCLTECH", "TECHM"],
    "Consumer": [
        "COLPAL",
        "HINDUNILVR",
        "GILLETTE",
        "ASIANPAINT",
        "BRITANNIA",
        "DRREDDY",
        "PRICOLLTD",
        "PIDILITIND",
        "NESTLEIND",
    ],
    "Banking & finance": [
        "HDFCBANK",
        "KOTAKBANK",
        "IDFCFIRSTB",
        "AXISBANK",
        "JIOFIN",
        "ICICIBANK",
        "SBIN",
    ],
}
ADDITIONS = [
    (
        "METALIETF",
        "ICICI Prudential Nifty Metal ETF",
        "NSE",
        "Metal producers equity ETF",
        False,
    ),
    ("INDHOTEL", "Indian Hotels Company", "NSE", "Hospitality", False),
    ("ONGC", "Oil and Natural Gas Corporation", "NSE", "Oil & gas", False),
    ("OIL", "Oil India", "NSE", "Oil & gas", False),
    ("IOC", "Indian Oil Corporation", "NSE", "Oil & gas", False),
    ("BPCL", "Bharat Petroleum", "NSE", "Oil & gas", False),
    ("HINDPETRO", "Hindustan Petroleum", "NSE", "Oil & gas", False),
    ("RELIANCE", "Reliance Industries", "NSE", "Diversified energy", False),
    ("PETRONET", "Petronet LNG", "NSE", "Oil & gas", False),
    ("INFY", "Infosys", "NSE", "Technology", False),
    ("WIPRO", "Wipro", "NSE", "Technology", False),
    ("TCS", "Tata Consultancy Services", "NSE", "Technology", False),
    ("HCLTECH", "HCL Technologies", "NSE", "Technology", False),
    ("TECHM", "Tech Mahindra", "NSE", "Technology", False),
    ("GILLETTE", "Gillette India", "NSE", "Consumer staples", False),
    ("BRITANNIA", "Britannia Industries", "NSE", "Consumer staples", False),
    ("KOTAKBANK", "Kotak Mahindra Bank", "NSE", "Banking", False),
    ("ICICIBANK", "ICICI Bank", "NSE", "Banking", False),
    ("SBIN", "State Bank of India", "NSE", "Banking", False),
    ("NVDA", "NVIDIA", "US", "Technology", False),
    ("MSFT", "Microsoft", "US", "Technology", False),
    ("AAPL", "Apple", "US", "Technology", False),
    ("GOOGL", "Alphabet", "US", "Communication services", False),
    ("AMZN", "Amazon", "US", "Consumer discretionary", False),
    ("META", "Meta Platforms", "US", "Communication services", False),
    ("AVGO", "Broadcom", "US", "Technology", False),
    ("TSLA", "Tesla", "US", "Consumer discretionary", False),
    ("BRK-B", "Berkshire Hathaway", "US", "Financials", False),
    ("LLY", "Eli Lilly", "US", "Healthcare", False),
]
BENCHMARKS += [
    ("SP500", "^GSPC", "S&P 500"),
    ("NASDAQ", "^IXIC", "Nasdaq Composite"),
    ("US50", "XLG", "US largest 50 · XLG ETF"),
]
US_SECTORS = [
    ("XLK", "Technology"),
    ("XLF", "Financials"),
    ("XLV", "Healthcare"),
    ("XLE", "Energy"),
    ("XLY", "Consumer discretionary"),
    ("XLP", "Consumer staples"),
    ("XLB", "Materials"),
    ("XLI", "Industrials"),
    ("XLU", "Utilities"),
    ("XLRE", "Real estate"),
    ("XLC", "Communication services"),
]


def research_group(asset):
    if asset["market"] != "NSE":
        return asset["sector"]
    for group, symbols in GROUP_SYMBOLS.items():
        if asset["symbol"] in symbols:
            return group
    if asset.get("sector") in NSE_GROUPS:
        return asset["sector"]
    sector = asset.get("sector", "").lower()
    for terms, group in [
        (["health", "pharma", "hospital"], "Healthcare"),
        (
            ["hotel", "hospitality", "leisure", "entertainment"],
            "Entertainment & leisure",
        ),
        (["bank", "financ"], "Banking & finance"),
        (["technology", "software", "it services"], "Technology"),
        (["oil", "gas", "energy", "power", "petroleum"], "Oil, gas & energy"),
        (["consumer", "paint", "staple"], "Consumer"),
        (["gold", "silver", "metal", "commodity"], "Materials & commodity ETFs"),
    ]:
        if any(t in sector for t in terms):
            return group
    return "Other NSE"


CONSUMER_ADDITIONS = [
    ("DRREDDY", "Dr Reddy's Laboratories", "NSE", "Healthcare", False),
    ("PIDILITIND", "Pidilite Industries", "NSE", "Consumer materials", False),
    ("NESTLEIND", "Nestle India", "NSE", "Consumer staples", False),
]
