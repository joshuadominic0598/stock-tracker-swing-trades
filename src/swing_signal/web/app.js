import { icon } from './icons.js';
import { createAssetChart, disposeChart } from './charts.js';

const $ = (s) => document.querySelector(s);
const esc = (v) =>
  String(v ?? '').replace(
    /[&<>"']/g,
    (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' })[c],
  );
const fmt = (v, d = 2) =>
  v == null
    ? '—'
    : Number(v).toLocaleString('en-IN', { minimumFractionDigits: d, maximumFractionDigits: d });
const num = (v) => fmt(v, v != null && Math.abs(v) < 1 ? 4 : 2);
const signed = (v, d = 2) => (v == null ? '—' : `${v >= 0 ? '+' : ''}${fmt(v, d)}%`);
const tone = (v) => (v >= 0 ? 'positive' : 'negative');
const compact = (v) =>
  v == null
    ? '—'
    : Math.abs(v) >= 1e12
      ? `${fmt(v / 1e12)}T`
      : Math.abs(v) >= 1e9
        ? `${fmt(v / 1e9)}B`
        : Math.abs(v) >= 1e6
          ? `${fmt(v / 1e6)}M`
          : num(v);
const when = (s, full = false) =>
  !s
    ? 'Not fetched'
    : new Date(s).toLocaleString('en-IN', {
        timeZone: 'Asia/Kolkata',
        day: '2-digit',
        month: 'short',
        ...(full ? { year: 'numeric' } : {}),
        hour: '2-digit',
        minute: '2-digit',
        hour12: true,
      }) + ' IST';
const quoteStamp = (q) =>
  q ? (q.as_of ? '' : 'Received ') + when(q.as_of || q.received_at || q.fetched_at) : 'No quote';
const dateOnly = (s) =>
  s
    ? new Date(s + 'T12:00:00Z').toLocaleDateString('en-IN', {
        day: 'numeric',
        month: 'short',
        year: 'numeric',
      })
    : '—';
const state = {
  candidateMarket: 'NSE',
  candidateCriterion: 'any',
  candidateTimeframe: '1d',
  data: null,
  view: 'overview',
  filter: 'all',
  query: '',
  setup: 'all',
  sort: 'default',
  detail: null,
  research: null,
  tab: 'brief',
  timeframe: '1d',
  range: 180,
  candidates: true,
  scanTimeframe: '1d',
  sector: '',
  aiProvider: null,
  showAll: false,
  loadId: 0,
  loading: false,
  models: null,
  aiRunning: false,
};
const colors = ['#9dbaff', '#b7a6e7', '#96bed4', '#d6a5ab', '#a7b5d9', '#d3b584'];
const assetColor = (s) =>
  colors[Array.from(s).reduce((a, c) => a + c.charCodeAt(0), 0) % colors.length];
const short = (s) =>
  s === 'BTCUSDT'
    ? '₿'
    : s === 'ETHUSD'
      ? 'Ξ'
      : s.replace('USDT', '').replace('USD', '').slice(0, 2);
const avatar = (a) =>
  `<span class="asset-avatar" style="--asset:${assetColor(a.symbol)}">${esc(short(a.symbol))}</span>`;
const currency = (a) =>
  a.currency === 'INR' ? '₹' : a.market === 'CRYPTO' ? '₮' : a.market === 'US' ? '$' : '₹';
const tv = (a) =>
  `https://www.tradingview.com/chart/?symbol=${encodeURIComponent(a.market === 'NSE' ? 'NSE:' + a.symbol : a.market === 'US' ? a.symbol : 'BINANCE:' + (a.provider_symbol || a.symbol))}`;
const change = (v) =>
  `<span class="change ${v == null ? '' : tone(v)}">${v == null ? '—' : `${v >= 0 ? '↗' : '↘'} ${signed(v)}`}</span>`;
function spark(values, color = '#4fc795', fill = false) {
  if (!values?.length) return `<span class="no-spark">24h aggregate</span>`;
  color = values.at(-1) >= values[0] ? '#4fc795' : '#e78284';
  const w = 150,
    h = 45,
    p = 3,
    min = Math.min(...values),
    max = Math.max(...values),
    span = max - min || 1;
  const points = values
    .map(
      (v, i) =>
        `${p + (i / (values.length - 1 || 1)) * (w - 2 * p)},${h - p - ((v - min) / span) * (h - 2 * p)}`,
    )
    .join(' ');
  return `<svg viewBox="0 0 ${w} ${h}" class="sparkline" preserveAspectRatio="none" aria-hidden="true">${fill ? `<polygon points="${p},${h} ${points} ${w - p},${h}" fill="${color}" opacity=".07"/>` : ''}<polyline points="${points}" fill="none" stroke="${color}" stroke-width="1.7" vector-effect="non-scaling-stroke" stroke-linejoin="round"/></svg>`;
}
function trendPeriods(signal) {
  const unit = signal.period_unit || 'D';
  return `<span class="trend-periods">${[3, 7, 14]
    .map((n) => {
      const p = signal.periods?.[n],
        available = p?.available;
      const direction = available
        ? p.change > 0
          ? 'up'
          : p.change < 0
            ? 'down'
            : 'flat'
        : 'unknown';
      const description = available
        ? `${n}${unit}: ${signed(p.change, 1)} · ${p.from_date} to ${p.through}`
        : `${n}${unit}: unavailable`;
      return `<span class="trend-period ${direction}" title="${esc(description)}" aria-label="${esc(description)}">${n}${unit}</span>`;
    })
    .join('')}</span>`;
}
function signalEvidence(signal) {
  return signal.key === 'highs'
    ? trendPeriods(signal)
    : `${esc(signal.title)} · ${esc(signal.value)}`;
}
async function api(path, body) {
  const r = await fetch(
    '/api/' + path,
    body === undefined
      ? {}
      : {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify(body),
        },
  );
  const d = await r.json();
  if (!r.ok) throw Error(d.error || 'Request failed');
  return d;
}
function toast(message, error = false) {
  const el = $('#toast');
  el.textContent = message;
  el.className = 'visible ' + (error ? 'error' : '');
  clearTimeout(toast.timer);
  toast.timer = setTimeout(() => (el.className = ''), 4500);
}
function nav(view) {
  location.hash = view;
}
const navLink = (href, label, ico, count) =>
  `<a href="#${href}" class="nav-link ${state.view === href ? 'active' : ''}">${icon(ico)}<span>${label}</span>${count != null ? `<span class="nav-count">${count}</span>` : ''}</a>`;
function shell() {
  const d = state.data,
    held = d.assets.filter((a) => a.held).length;
  const page =
    state.view === 'asset'
      ? state.detail?.name || 'Asset research'
      : {
          overview: 'Overview',
          candidates: 'Long candidates',
          watchlist: 'Watchlist',
          holdings: 'My holdings',
          journal: 'Research journal',
          settings: 'Data & AI connections',
          nse: 'NSE markets',
          crypto: 'Crypto markets',
          us: 'US overview',
        }[state.view] || 'Overview';
  $('#app').innerHTML =
    `<aside class="sidebar"><a class="brand" href="#overview"><span class="brand-mark">${icon('chart')}</span><span>Swing<span class="brand-light"> Signal</span><small>YOUR MARKET WORKSPACE</small></span></a><div class="workspace-label"><span class="status-dot"></span> Personal workspace ${icon('down')}</div><div class="nav-label">WORKSPACE</div><nav>${navLink('overview', 'Overview', 'grid')}${navLink('candidates', 'Long candidates', 'target')}${navLink('watchlist', 'Watchlist', 'star', d.assets.length)}${navLink('holdings', 'My holdings', 'wallet', held)}${navLink('journal', 'Research journal', 'book')}</nav><div class="nav-label markets-label">MARKETS</div><nav>${navLink('nse', 'Indian equities', 'chart')}${navLink('us', 'US overview', 'globe')}<a href="#crypto" class="nav-link ${state.view === 'crypto' ? 'active' : ''}">${icon('bitcoin')}<span>Crypto</span><span class="pill tiny">24/7</span></a></nav><div class="sidebar-bottom"><div class="process-card"><span class="mini-orbit">${icon('target')}</span><strong>Play the longer game.</strong><p>Your levels. Your conviction.<br>A little more perspective.</p><span>SWING RESEARCH ${icon('arrow')}</span></div>${navLink('settings', 'Data & AI connections', 'settings')}<div class="profile"><div class="profile-avatar">ME</div><div><strong>My trading desk</strong><span>Local · private by default</span></div>${icon('shield')}</div></div></aside><div class="workspace"><header class="topbar"><button class="icon-button mobile-menu" data-action="menu" aria-label="Toggle sidebar">${icon('menu')}</button><div class="breadcrumb">Workspace ${icon('chevron')}<span>${esc(page)}</span></div><div class="top-actions"><button class="search-trigger" data-action="search" aria-label="Find an asset">${icon('search')}<span>Find an asset</span><kbd>⌘ K</kbd></button><span class="local-status"><span class="status-dot"></span> On your Mac</span><button class="icon-button ${d.refresh.running ? 'spinning' : ''}" data-action="refresh" title="Refresh all market data" aria-label="Refresh all market data">${icon('refresh')}</button></div></header><main id="main"></main><footer class="workspace-footer"><span><span class="status-dot"></span> Saved locally. Built for your own perspective.</span><span>Daily + weekly · NSE / US / crypto <span class="footer-separator">/</span> Swing Signal v2.1</span></footer></div>`;
  renderContent();
}
function renderContent() {
  disposeChart();
  if (state.view === 'asset') {
    renderDetail();
    return;
  }
  if (state.view === 'settings') {
    renderSettings();
    return;
  }
  if (state.view === 'journal') {
    renderJournal();
    return;
  }
  if (state.view === 'candidates') {
    renderCandidates();
    return;
  }
  const d = state.data,
    scope = effectiveFilter(),
    held = d.assets.filter((a) => a.held);
  const universe = d.assets.filter(
    (a) => scope === 'all' || (scope === 'held' && a.held) || a.market === scope,
  );
  const title = {
    overview: 'Your swing desk.',
    watchlist: 'Signals across your watchlist.',
    holdings: 'Your holdings. Both timeframes.',
    nse: 'NSE, sector by sector.',
    crypto: 'Crypto swing signals.',
    us: 'US market overview.',
  }[state.view];
  const subtitle = {
    overview: 'NSE, the US and crypto — direction, context, then the stock.',
    watchlist: 'Eight signals, with a separate daily and weekly reading.',
    holdings: 'Review the evidence behind each position.',
    nse: 'Your research groups, company context and the eight signals.',
    crypto: 'Your six original pairs, with daily and weekly structure.',
    us: 'A largest-50 proxy, broad indices, sectors and ten major companies.',
  }[state.view];
  $('#main').innerHTML =
    `<div class="page-heading"><div><div class="eyebrow">DAILY + WEEKLY SWING RESEARCH</div><h1>${title}</h1><p>${subtitle}</p></div><div class="heading-right"><button class="button primary" data-action="add-asset">${icon('plus')} Find / track a stock</button></div></div>${refreshBanner()}
 ${state.view === 'overview' ? marketCompass() + candidatePreview() + `<details class="more-detail"><summary>How the markets move together</summary>${correlationPanel()}</details>` : state.view === 'holdings' ? holdingsSummary(held) : `<div class="market-cards">${scopedBenchmarks(d).map(benchmarkCard).join('')}</div>`}
 ${scope === 'NSE' ? sectorPanel() : scope === 'US' ? usSectorPanel() : ''}
 ${state.view === 'overview' ? `<div class="market-paths"><a href="#nse">NSE · ${d.assets.filter((a) => a.market === 'NSE').length} names, your sectors ${icon('arrow')}</a><a href="#us">US · broad view + 10 leaders ${icon('arrow')}</a><a href="#crypto">Crypto · your original pairs ${icon('arrow')}</a></div>` : ''}
 ${state.view === 'overview' ? '<details class="more-detail"><summary>Open your full watchlist</summary>' : ''}<section class="signal-watch"><div class="section-heading"><div><h2>${state.view === 'holdings' ? 'Holding signals' : scope === 'US' ? 'Ten US leaders' : 'Stock-by-stock signals'} <span class="number-label">${universe.length}</span></h2><p>${scope === 'US' ? 'Curated major-company list; not a live top-ten market-cap ranking.' : 'Buy-side and sell-side are explainable technical leans, not estimated odds.'}</p></div><button class="text-button" data-action="method">How signals work ${icon('info')}</button></div>
 <div class="watch-card"><div class="watch-toolbar"><div class="tabs market-tabs">${[
   ['all', 'All'],
   ['NSE', 'NSE'],
   ['US', 'US'],
   ['CRYPTO', 'Crypto'],
   ['held', 'Holdings'],
 ]
   .map(
     ([v, l]) =>
       `<button data-action="filter" data-value="${v}" class="tab ${scope === v ? 'active' : ''}">${l}</button>`,
   )
   .join('')}</div><div class="signal-toolbar"><div class="segmented">${[
   ['1d', 'Daily'],
   ['1w', 'Weekly'],
 ]
   .map(
     ([v, l]) =>
       `<button data-action="scan-timeframe" data-value="${v}" class="${state.scanTimeframe === v ? 'active' : ''}">${l}</button>`,
   )
   .join(
     '',
   )}</div><select id="setup-filter" aria-label="Filter by swing signal"><option value="all">All signals</option><option value="buy">Buy-side lean</option><option value="sell">Sell-side lean</option><option value="near">Near demand</option><option value="momentum">RSI + Stoch pullback rules</option><option value="confluence">Demand + rising trend or >1% move</option><option value="move">Move above +1%</option><option value="high">3 / 7 / 14 trend rising</option><option value="retest">Confirmed support retest</option></select></div></div>
 <div class="signal-search">${icon('search')}<input id="watch-query" placeholder="Search symbol, company or sector…" value="${esc(state.query)}" aria-label="Search symbol, name or sector"/><select id="signal-sort" aria-label="Sort signals"><option value="default">Watchlist order</option><option value="bias">Buy-side balance first</option><option value="change">Largest period move</option><option value="rsi">Lowest RSI first</option><option value="distance">Nearest demand first</option></select></div><div id="asset-table"></div></div></section>${state.view === 'overview' ? '</details>' : ''}`;
  $('#setup-filter').value = state.setup;
  $('#signal-sort').value = state.sort;
  renderTable();
}

function refreshBanner() {
  const r = state.data.refresh,
    errors = Object.keys(r.errors || {}),
    missing = state.data.assets.filter((a) => !a.available).length;
  if (r.running)
    return `<div class="sync-banner">${icon('refresh', 'spinning')} <span>Refreshing your market view <strong>${r.completed} / ${r.total}</strong></span><span>Last good data stays available.</span></div>`;
  if (!r.running && state.data.assets.some((a) => a.quality_note))
    return `<div class="sync-banner warning">${icon('info')} <span>Some price sources have missing recent candles. Indicators use each asset’s last usable history.</span><a href="#settings">View data health ${icon('arrow')}</a></div>`;
  if (errors.length)
    return `<div class="sync-banner warning">${icon('info')} <span>${errors.length} source${errors.length > 1 ? 's' : ''} could not refresh. ${missing ? `${missing} assets have no cached history.` : 'Showing the last available data.'}</span><a href="#settings">View data health ${icon('arrow')}</a></div>`;
  return '';
}
function scopedBenchmarks(d) {
  const scope = effectiveFilter();
  const fromAsset = (symbol) => {
    const a = d.assets.find((a) => a.symbol === symbol);
    return a?.available
      ? {
          symbol: a.symbol,
          name: a.name + ' · ' + a.currency,
          currency: a.currency,
          price: a.summary.price,
          change: a.summary.change,
          sparkline: a.summary.sparkline,
          as_of: a.as_of,
          source: a.source,
          source_url: a.source_url,
        }
      : { symbol, name: symbol, price: null, change: null, sparkline: [] };
  };
  if (scope === 'CRYPTO')
    return [
      fromAsset('BTCUSDT'),
      fromAsset('ETHUSD'),
      fromAsset('SOLUSD'),
      d.benchmarks.find((b) => b.symbol === 'TOTAL'),
    ].filter(Boolean);
  if (scope === 'US')
    return d.benchmarks.filter((b) => ['SP500', 'NASDAQ', 'US50'].includes(b.symbol));
  if (scope === 'NSE')
    return [
      ...d.benchmarks.filter((b) => ['NIFTY50', 'BANKNIFTY'].includes(b.symbol)),
      fromAsset('GOLDBEES'),
      fromAsset('SILVERBEES'),
    ];
  return d.benchmarks;
}
function benchmarkCard(b) {
  const price =
    b.symbol === 'TOTAL'
      ? '$' + compact(b.price)
      : b.currency === 'USDT' || b.symbol === 'BTC'
        ? '₮' + num(b.price)
        : b.currency === 'INR'
          ? '₹' + num(b.price)
          : b.currency === 'USD'
            ? '$' + num(b.price)
            : num(b.price);
  return `<article class="market-card"><div class="market-card-top"><span class="benchmark-icon ${b.symbol === 'BTC' ? 'orange' : b.symbol === 'TOTAL' ? 'purple' : ''}">${icon(b.symbol === 'TOTAL' ? 'globe' : b.currency === 'USDT' || b.symbol === 'BTC' ? 'bitcoin' : 'chart')}</span><span>${esc(b.name)}</span>${b.source_url ? `<a href="${esc(b.source_url)}" target="_blank" rel="noopener noreferrer" title="View source: ${esc(b.source)}" aria-label="Source for ${esc(b.name)}">${icon('external')}</a>` : ''}</div><div class="market-card-value">${b.price == null ? '—' : price}</div><div class="market-card-bottom">${change(b.change)}${b.sparkline?.length ? spark(b.sparkline, b.change >= 0 ? '#4fc795' : '#e78284') : b.dominance ? `<span class="dominance">BTC ${fmt(b.dominance, 1)}%</span>` : ''}</div><div class="market-card-foot" title="${esc(when(b.as_of, true))}">${b.symbol === 'TOTAL' ? '24h change · ' : b.currency === 'USDT' || b.symbol === 'BTC' ? 'UTC close · ' : 'Session close · '}${b.as_of ? when(b.as_of) : 'Awaiting data'}${b.quality_note ? ' · Gaps' : ''}</div></article>`;
}
function effectiveFilter() {
  return state.view === 'holdings'
    ? 'held'
    : state.view === 'nse'
      ? 'NSE'
      : state.view === 'crypto'
        ? 'CRYPTO'
        : state.view === 'us'
          ? 'US'
          : state.filter;
}
function filteredAssets() {
  const filter = effectiveFilter(),
    q = state.query.toLowerCase();
  let assets = state.data.assets.filter(
    (a) =>
      (filter === 'all' || (filter === 'held' && a.held) || a.market === filter) &&
      (!q ||
        (a.symbol + ' ' + a.name + ' ' + a.sector + ' ' + a.group).toLowerCase().includes(q)) &&
      (!state.sector || a.group === state.sector),
  );
  const swing = (a) => (state.scanTimeframe === '1w' ? a.weekly_swing : a.daily_swing);
  if (state.setup === 'buy') assets = assets.filter((a) => swing(a)?.direction === 'bullish');
  if (state.setup === 'sell') assets = assets.filter((a) => swing(a)?.direction === 'bearish');
  if (state.setup === 'near')
    assets = assets.filter(
      (a) => swing(a)?.demand_distance != null && swing(a).demand_distance <= 3,
    );
  if (state.setup === 'momentum')
    assets = assets.filter(
      (a) =>
        swing(a)
          ?.signals?.filter((s) => ['rsi', 'stoch'].includes(s.key))
          .every((s) => s.score > 0) && swing(a)?.coverage >= 5,
    );
  if (state.setup === 'confluence')
    assets = assets.filter(
      (a) => swing(a)?.near_demand && (swing(a)?.any_period_up || swing(a)?.up_over_one),
    );
  if (state.setup === 'retest')
    assets = assets.filter((a) => swing(a)?.retest?.status === 'confirmed');
  if (state.setup === 'move') assets = assets.filter((a) => swing(a)?.up_over_one);
  if (state.setup === 'high')
    assets = assets.filter((a) => swing(a)?.signals?.some((s) => s.key === 'highs' && s.score > 0));
  if (state.sort === 'change')
    assets.sort((a, b) => (swing(b)?.change ?? -Infinity) - (swing(a)?.change ?? -Infinity));
  if (state.sort === 'bias')
    assets.sort((a, b) => (swing(b)?.score ?? -Infinity) - (swing(a)?.score ?? -Infinity));
  if (state.sort === 'rsi')
    assets.sort((a, b) => {
      const v = (x) => Number.parseFloat(swing(x)?.signals.find((s) => s.key === 'rsi')?.value);
      return (Number.isFinite(v(a)) ? v(a) : Infinity) - (Number.isFinite(v(b)) ? v(b) : Infinity);
    });
  if (state.sort === 'distance')
    assets.sort(
      (a, b) => (swing(a)?.demand_distance ?? Infinity) - (swing(b)?.demand_distance ?? Infinity),
    );
  return assets;
}

function renderTable() {
  const target = $('#asset-table');
  if (!target) return;
  const assets = filteredAssets(),
    show = state.showAll ? assets : assets.slice(0, 8);
  target.innerHTML = `<div class="stock-signal-list">${show.map((a) => assetRow(a, state.view === 'holdings')).join('')}</div>${!assets.length ? `<div class="empty-state"><h3>No matching stocks</h3><p>Change the sector or signal filter, or track another stock.</p><button class="button secondary" data-action="reset-filters">Reset filters</button></div>` : ''}<div class="table-footer"><span>${show.length} of ${assets.length} · ${state.scanTimeframe === '1w' ? 'Weekly' : 'Daily'} signals use completed daily source candles.</span><button class="text-button" data-action="show-all">${state.showAll ? 'Show fewer' : 'View all'} ${icon('arrow')}</button></div>`;
}

function assetRow(a, held) {
  const swing = state.scanTimeframe === '1w' ? a.weekly_swing : a.daily_swing,
    q = a.quote,
    s = a.summary;
  const quote = q?.price ?? s.price;
  return `<article class="stock-signal-card"><div class="stock-signal-top"><a class="asset-cell" href="#asset/${esc(a.symbol)}">${avatar(a)}<div><strong>${esc(a.symbol)}${a.held ? '<i class="held-dot" title="Held"></i>' : ''}</strong><span>${esc(a.name)} · ${esc(a.group || a.sector)}</span></div></a><div class="stock-bias-pair">${biasBadge(a.daily_swing, 'D')}${biasBadge(a.weekly_swing, a.week_partial ? 'W*' : 'W')}</div><div class="stock-quote"><strong>${quote != null ? currency(a) + num(quote) : '—'}</strong>${change(q?.change ?? s.change)}<small title="${esc(q?.delay_note || 'Completed candle close')}">${q ? quoteStamp(q) : a.as_of ? dateOnly(a.as_of.slice(0, 10)) : 'No price'} · ${esc(q?.kind || 'Candle close')}</small></div><a class="icon-button" href="#asset/${esc(a.symbol)}" aria-label="Research ${esc(a.name)}">${icon('chevron')}</a></div>
 ${
   a.available
     ? `<a href="#asset/${esc(a.symbol)}" class="stock-seven compact-signals" aria-label="Open ${esc(a.name)} signal details">${(
         swing?.signals || []
       )
         .filter((item) => ['ma', 'zones', 'retest'].includes(item.key))
         .map(
           (item) =>
             `<div class="mini-signal ${item.direction}" title="${esc(item.reading)}"><span>${esc(item.title)}</span><strong>${esc(item.value)}</strong></div>`,
         )
         .join('')}</a>`
     : `<div class="stock-no-history">History is loading or unavailable. Open the stock to check its data source.</div>`
 }
 <div class="stock-signal-foot"><span>${a.stale || a.quality_note ? '<span class="stale-label">Check stale / incomplete history</span>' : 'Signals through ' + (s.candle_date ? dateOnly(s.candle_date) : '—')}${a.week_partial ? ' · W* = unfinished weekly bar' : ''}</span><span>${swing?.score != null ? 'Evidence balance ' + (swing.score > 0 ? '+' : '') + fmt(swing.score, 1) + ' · ' + swing.coverage + '/8 available' : 'No calculated balance'}${held && a.position?.quantity ? ' · ' + fmt(a.position.quantity, 2) + ' units held' : ''}</span></div></article>`;
}

function holdingsSummary(assets) {
  const sized = assets.filter(
    (a) => a.position?.quantity && a.position?.average && a.available && a.currency === 'INR',
  );
  const total = sized.reduce((t, a) => t + a.position.quantity * a.summary.price, 0),
    cost = sized.reduce((t, a) => t + a.position.quantity * a.position.average, 0);
  return `<div class="holding-summary"><div><span>HELD ASSETS</span><strong>${assets.length}</strong><small>Positions you mark as held</small></div><div><span>TRACKED VALUE · INR</span><strong>${sized.length ? '₹' + num(total) : '—'}</strong><small>${sized.length} of ${assets.filter((a) => a.market === 'NSE').length} INR positions sized</small></div><div><span>UNREALISED P&L · INR</span><strong class="${sized.length ? tone(total - cost) : ''}">${sized.length ? '₹' + num(total - cost) : '—'}</strong><small>${sized.length ? signed((total / cost - 1) * 100) : 'Enter your quantity and average cost'}</small></div><div class="holding-tip">${icon('wallet')}<p>Open a holding to add its position.<br>Enter your own quantity and average cost for portfolio totals.</p></div></div>`;
}

async function openAsset(symbol) {
  const id = ++state.loadId;
  state.view = 'asset';
  state.detail = null;
  state.research = null;
  state.tab = 'brief';
  state.loading = true;
  shell();
  window.scrollTo(0, 0);
  try {
    const d = await api(`assets/${encodeURIComponent(symbol)}?timeframe=${state.timeframe}`);
    if (id !== state.loadId) return;
    state.detail = d;
    state.loading = false;
    shell();
    loadResearch(symbol, id);
  } catch (e) {
    if (id !== state.loadId) return;
    $('#main').innerHTML =
      `<div class="empty-state">${icon('info')}<h2>Could not open this asset</h2><p>${esc(e.message)}</p><a class="button secondary" href="#overview">Back to overview</a></div>`;
  }
}
async function loadResearch(symbol, id = state.loadId) {
  try {
    const r = await api('research/' + encodeURIComponent(symbol));
    if (id !== state.loadId || state.view !== 'asset') return;
    state.research = r;
    renderResearch();
  } catch (e) {
    if (id !== state.loadId) return;
    state.research = { error: e.message };
    renderResearch();
  }
}
function renderDetail() {
  const a = state.detail;
  if (!a) {
    $('#main').innerHTML =
      `<div class="detail-loading"><div class="eyebrow">OPENING YOUR RESEARCH DESK</div><div class="skeleton skeleton-heading"></div><div class="skeleton skeleton-chart"></div></div>`;
    return;
  }
  const s = a.summary;
  $('#main').innerHTML =
    `<a class="back-link" href="#${a.held ? 'holdings' : 'watchlist'}">${icon('back')} Back to ${a.held ? 'holdings' : 'watchlist'}</a><div class="asset-heading"><div class="asset-title">${avatar(a)}<div><div class="asset-title-line"><h1>${esc(a.name)}</h1>${a.held ? '<span class="pill">In your holdings</span>' : ''}</div><p>${esc(a.symbol)} <span>·</span> ${a.market === 'NSE' ? 'NSE · INR' : a.market === 'US' ? 'US · USD' : 'Binance spot · USDT'} <span>·</span> ${esc(a.sector)}</p></div></div><div class="asset-price"><strong>${a.quote?.price != null ? currency(a) + num(a.quote.price) : a.available ? currency(a) + num(s.price) : '—'}</strong>${change(a.quote?.change ?? s.change)}<small>${esc(a.quote?.kind || 'Completed candle close')}${a.quote ? ' · ' + quoteStamp(a.quote) : ''}</small></div></div><div class="asset-subhead"><div class="source-meta">${icon('clock')} Signal candles: ${a.available ? `${esc(a.source)} · As of ${when(a.as_of, true)}${a.stale ? ' <span class="stale-label">STALE</span>' : ''}` : 'Refresh market data to begin.'}</div><div class="asset-actions"><button class="button secondary" data-action="position">${icon('wallet')} ${a.held ? 'Edit position' : 'Track holding'}</button><a class="button secondary" href="${tv(a)}" target="_blank" rel="noopener noreferrer">TradingView ${icon('external')}</a></div></div>
 ${a.quality_note ? `<div class="sync-banner warning">${icon('info')} ${esc(a.quality_note)}</div>` : ''}
 ${a.refresh_error ? `<div class="sync-banner warning">${icon('info')} Refresh failed: ${esc(a.refresh_error)}. Last successful data is shown.</div>` : ''}
 ${renderSignalDesk(a)}<div class="detail-layout"><section class="chart-card"><div class="chart-toolbar"><div class="chart-title">${icon('chart')}<strong>${esc(a.symbol)}</strong><span>${state.timeframe === '1d' ? 'Daily' : 'Weekly'}</span></div><div class="chart-controls"><div class="segmented">${[
   ['1d', 'D'],
   ['1w', 'W'],
 ]
   .map(
     ([v, l]) =>
       `<button data-action="timeframe" data-value="${v}" class="${state.timeframe === v ? 'active' : ''}" aria-label="${v === '1d' ? 'Daily' : 'Weekly'} candles">${l}</button>`,
   )
   .join('')}</div><div class="segmented range-controls">${[
   [90, '3M'],
   [180, '6M'],
   [365, '1Y'],
   [730, '2Y'],
 ]
   .map(
     ([v, l]) =>
       `<button data-action="range" data-value="${v}" class="${state.range === v ? 'active' : ''}">${l}</button>`,
   )
   .join(
     '',
   )}</div><button class="button secondary compact-button" data-action="draw-zone" ${!a.available ? 'disabled' : ''}>${icon('plus')} Draw zone</button></div></div><div class="chart-legend"><span><i style="background:#83bad3"></i>SMA 20${state.timeframe === '1w' ? 'W' : 'D'}</span><span><i style="background:#d8bc7a"></i>SMA 50${state.timeframe === '1w' ? 'W' : 'D'}</span><span><i style="background:#9b99d5"></i>SMA 200${state.timeframe === '1w' ? 'W' : 'D'}</span><button data-action="candidates" class="${state.candidates ? 'selected' : ''}">${icon('layers')} Candidate zones ${state.candidates ? 'on' : 'off'}</button></div><p class="oscillator-key">RSI 15 · yellow SMA 14 &nbsp; / &nbsp; Stoch RSI 14/14 · K 3 / D 3</p><div id="ohlc-readout" class="ohlc-readout">${a.available ? `O ${num(a.bars.at(-1).open)}  H ${num(a.bars.at(-1).high)}  L ${num(a.bars.at(-1).low)}  C ${num(a.bars.at(-1).close)}` : 'No completed candles'}</div><div id="chart-area">${!a.available ? `<div class="empty-state">${icon('chart')}<h3>Bring your chart to life</h3><p>Refresh market data to load completed candles.</p><button class="button secondary" data-action="refresh">${icon('refresh')} Refresh market data</button></div>` : ''}</div><div class="indicator-captions"><span>Volume</span><span class="purple">RSI (15) · ${fmt(s.rsi, 1)}</span><span class="blue">Stoch RSI (14, 14, 3, 3) · K ${fmt(s.k, 1)} / D ${fmt(s.d, 1)}</span></div><div class="chart-footnote"><span>Scroll to zoom · drag to pan ${state.timeframe === '1w' ? '· Current week aggregates completed daily candles' : ''}</span><a href="https://www.tradingview.com/lightweight-charts/" target="_blank" rel="noopener noreferrer">Chart by TradingView ${icon('external')}</a></div></section>
 <aside class="detail-aside"><section class="setup-card"><div class="eyebrow">THE TECHNICAL PICTURE</div><h2>${esc(s.state || 'Awaiting data')}</h2><p>Confluence to investigate, in the context of your own levels.</p><div class="setup-checks">${(s.flags || []).map((f) => `<div><span>${f.label}</span><span class="check-indicator ${f.met ? 'met' : ''}">${icon(f.met ? 'check' : 'close')}</span></div>`).join('')}</div><div class="setup-metric"><span>${state.timeframe === '1w' ? '50-week' : '50-day'} structure</span><strong>${esc(s.trend || '—')}</strong></div><div class="setup-metric"><span>3-${state.timeframe === '1w' ? 'week' : 'session'} move</span><strong class="${tone(s.change_3d)}">${signed(s.change_3d)}</strong></div><div class="setup-metric"><span>20-${state.timeframe === '1w' ? 'week' : 'session'} move</span><strong class="${tone(s.change_20d)}">${signed(s.change_20d)}</strong></div><div class="setup-metric"><span>ATR (14)</span><strong>${num(s.atr)}</strong></div></section><section class="levels-card"><div class="level-card-heading"><h2>Your levels <span class="number-label">${a.zones.length}</span></h2><button class="icon-button" data-action="zone" title="Add a price zone" aria-label="Add a price zone">${icon('plus')}</button></div>${a.zones.length ? a.zones.map((z) => zoneCard(z, true)).join('') : `<div class="levels-empty">${icon('layers')}<p>Mark where buyers or sellers<br>could take over.</p><button class="text-button" data-action="zone">Add your first zone ${icon('plus')}</button></div>`}<div class="auto-zone-heading">ALGORITHMIC CANDIDATES</div>${
   a.candidates.length
     ? a.candidates
         .slice(0, 3)
         .map((z) => zoneCard(z))
         .join('')
     : '<p class="microcopy">No qualifying base/departure or repeated-reaction zones in this history.</p>'
 }<p class="microcopy">Automatic bands use compact bases, strong departures, retests and repeated reactions. Daily/weekly overlap is shown as evidence. Quality ranks the rules; it is not a win rate.</p></section></aside></div>
 <section class="research-card"><div class="research-header"><h2>${icon('book')} Research desk</h2><span class="pill subtle">CONTEXT BEFORE CONVICTION</span></div><div class="tabs research-tabs">${[
   ['brief', 'Research brief'],
   ['ai', 'AI analysis'],
   ['fundamentals', 'Financials'],
   ['news', 'News & attention'],
   ['journal', 'My thesis'],
 ]
   .map(
     ([v, l]) =>
       `<button class="tab ${state.tab === v ? 'active' : ''}" data-action="research-tab" data-value="${v}">${l}</button>`,
   )
   .join('')}</div><div id="research-content"></div></section>`;
  if (a.available) mountChart();
  renderResearch();
}
function mountChart() {
  createAssetChart($('#chart-area'), state.detail, {
    timeframe: state.timeframe,
    range: state.range,
    candidates: state.candidates,
    onZone: ({ low, high }) => {
      zoneModal({ low, high });
    },
  });
  $('#chart-area')?.addEventListener('zonepoint', () =>
    toast('First edge marked. Click the second price edge.'),
  );
}
function zoneCard(z, manual = false) {
  return `<div class="zone-card ${z.kind} ${z.broken ? 'broken' : ''}"><div><span class="zone-kind"><i></i>${esc(z.kind)}${z.broken ? ' · crossed' : ''}</span>${manual ? `<div class="zone-buttons"><button class="icon-button" data-action="edit-zone" data-id="${z.id}" aria-label="Edit ${esc(z.label)}">${icon('edit')}</button><button class="icon-button" data-action="delete-zone" data-id="${z.id}" aria-label="Delete ${esc(z.label)}">${icon('trash')}</button></div>` : `<span class="pill tiny">${z.timeframe === '1w' ? 'Weekly' : 'Daily'} auto</span>`}</div><strong class="tabular">${num(z.low)} <span>–</span> ${num(z.high)}</strong><small>${esc(manual ? z.label : z.label + ' · ' + z.evidence.join(' · '))}${!manual && z.confirmed_at ? ' · Confirmed ' + dateOnly(z.confirmed_at) : ''}</small></div>`;
}
function renderResearch() {
  const el = $('#research-content');
  if (!el || !state.detail) return;
  const a = state.detail,
    s = a.summary,
    r = state.research;
  if (state.tab === 'journal') {
    el.innerHTML = journalForm(a);
    return;
  }
  if (state.tab === 'ai') {
    renderAI(el);
    return;
  }
  if (state.tab === 'fundamentals') {
    el.innerHTML = screenerLink(a) + (r ? financials(r.fundamentals) : researchLoading());
    return;
  }
  if (state.tab === 'news') {
    el.innerHTML = r ? newsPanel(a, r) : researchLoading();
    return;
  }
  el.innerHTML = `<div class="brief-grid"><div><div class="eyebrow">A STRUCTURED READ · RULE-BASED</div><h3>${esc(a.swing?.label || 'Start with current price history.')}</h3><p class="brief-text">${a.available ? `${esc(a.name)} ${state.timeframe === '1w' ? 'has a weekly close through' : 'closed at'} ${state.timeframe === '1w' ? dateOnly(a.as_of.slice(0, 10)) + ' of ' : ''}${currency(a)}${num(s.price)}${state.timeframe === '1w' ? '' : ' on ' + dateOnly(a.bars.at(-1).time)}. ${s.distance != null ? `${s.distance === 0 ? 'It is inside' : `It is ${fmt(s.distance, 1)}% above`} the nearest valid demand zone (${num(s.demand.low)}–${num(s.demand.high)}). ` : 'No valid demand cluster is currently detected. '}${s.rsi != null ? `RSI is ${fmt(s.rsi, 1)}${s.rsi_delta == null ? '' : `, ${s.rsi_delta > 0 ? 'up' : 'down'} ${fmt(Math.abs(s.rsi_delta), 1)} points from the preceding candle`}. ` : ''}${s.volume_ratio != null ? `Volume is ${fmt(s.volume_ratio)}× the prior 20-bar average.` : ''}` : 'A research brief needs completed candle history. Import data or refresh your sources to begin.'}</p><div class="brief-caveat">${icon('eye')}<span>${a.swing?.coverage || 0} of 8 signals available; evidence balance ${fmt(a.swing?.score, 1)}. These are observations to review, with no estimated win rate or forecast.</span></div>${a.journal?.thesis ? `<div class="saved-thesis"><span class="eyebrow">YOUR CURRENT THESIS</span><p>${esc(a.journal.thesis)}</p><button class="text-button" data-action="research-tab" data-value="journal">Review your thesis ${icon('arrow')}</button></div>` : `<button class="button secondary" data-action="research-tab" data-value="journal">${icon('edit')} Write your thesis</button>`}</div><div class="brief-evidence"><h4>Before you build conviction</h4><div>${icon('chart')}<span>Confirm your zone on daily & weekly structure.</span></div><div>${icon('bolt')}<span>Review the 3-session move against your longer holding horizon.</span></div><div>${icon('book')}<span>Check financials, headlines, and the original source.</span></div><div>${icon('shield')}<span>Write what would invalidate your thesis.</span></div><div class="source-note">${r ? `${r.news?.articles?.length || 0} sourced headlines available · ${r.fundamentals?.available ? 'Annual financials available' : 'Company financials unavailable or not applicable'}` : 'Fetching news and financial context…'}</div><p class="microcopy">This rule-based brief explains calculated features. Use AI analysis for optional local or Gemini evidence curation.</p></div></div>`;
}
const researchLoading = () =>
  `<div class="research-loading">${icon('refresh', 'spinning')} Fetching source material…<span>Financials and headlines are cached separately from prices.</span></div>`;
function screenerLink(a) {
  if (a.market !== 'NSE' || /(BEES|ETF)$/.test(a.symbol)) return '';
  return `<div class="financial-intro"><div><h3>More company research</h3><p>Company accounts, ratios and filings on Screener’s free company page.</p></div><a class="button secondary" href="https://www.screener.in/company/${encodeURIComponent(a.symbol)}/consolidated/" target="_blank" rel="noopener noreferrer">Open on Screener ${icon('external')}</a></div>`;
}
function financials(f) {
  if (!f?.available)
    return `<div class="empty-state"><h3>No company financials available</h3><p>${esc(f?.reason || 'This source is currently unavailable.')}</p><p>Company accounts do not apply to ETFs or crypto.</p></div>`;
  const explanations = f.explanations || [];
  return `${f.error ? `<div class="sync-banner warning">Cached financials · ${esc(f.error)}</div>` : ''}<div class="financial-intro"><div><h3>What the business figures mean for your trade.</h3><p>Business strength can support a price thesis. Entry timing still comes from the daily / weekly chart; valuation and expectations can outweigh reported growth.</p></div><a class="text-button" href="${esc(f.source_url)}" target="_blank" rel="noopener noreferrer">Open financial source ${icon('external')}</a></div><div class="financial-grid">${Object.entries(
    f.metrics,
  )
    .map(([key, values]) => {
      const last = values.at(-1),
        e = explanations.find((x) => x.metric === key) || {};
      return `<article class="financial-metric"><span>${esc(e.label || key)}</span><strong>${last.currency === 'INR' ? '₹' : esc(last.currency) + ' '}${key === 'DilutedEPS' ? num(last.value) : compact(last.value)}</strong><div><span class="${e.direction === 'supportive' ? 'positive' : e.direction === 'pressure' ? 'negative' : 'muted'}">${e.yoy != null ? signed(e.yoy, 1) + ' YoY' : 'No comparable annual growth'}</span><small>FY ended ${dateOnly(last.date)}</small></div><div class="financial-history">${values
        .slice(-4)
        .map(
          (v) =>
            `<div><span>${v.date.slice(0, 4)}</span><b>${key === 'DilutedEPS' ? num(v.value) : compact(v.value)}</b></div>`,
        )
        .join(
          '',
        )}</div><div class="financial-meaning"><strong>Meaning</strong><p>${esc(e.meaning || 'Reported annual company metric.')}</p><strong>For the price / buy–sell thesis</strong><p>${esc(e.reading || 'Needs more context.')} ${esc(e.price_implication || '')}</p></div></article>`;
    })
    .join(
      '',
    )}</div><div class="source-note">Annual accounts are a slower context signal, not a daily buy/sell trigger. Figures may already be priced in. ${esc(f.source)} · Retrieved ${when(f.fetched_at, true)}.</div>`;
}

function newsPanel(a, r) {
  const n = r.news;
  return `${attentionPanel(a, r)}<div class="news-layout"><div><div class="financial-intro"><div><h3>What’s making headlines.</h3><p>Matched by company/asset name over the last 14 days.</p></div><span class="pill">${n?.articles?.length || 0} headlines</span></div>${n?.error ? `<div class="sync-banner warning">${esc(n.error)} ${n.cached ? 'Showing cached headlines.' : ''}</div>` : ''}${
    n?.articles?.length
      ? n.articles
          .slice(0, 5)
          .map(
            (article) =>
              `<a class="news-item" href="${esc(article.url)}" target="_blank" rel="noopener noreferrer"><div><span>${esc(article.source)}</span><time>${when(article.published_at)}</time></div><h4>${esc(article.title)} ${icon('external')}</h4><small>${esc(article.tone?.label || 'Unclear wording')} · Open publisher coverage via Google News</small></a>`,
          )
          .join('')
      : '<div class="empty-state"><h3>No matching headlines returned</h3><p>Use the source links to continue your research.</p></div>'
  }${extraHeadlines(n)}<p class="source-note">${n?.fetched_at ? 'Google News RSS · Retrieved ' + when(n.fetched_at, true) + '. ' : ''}Headlines may repeat a story and entity matching can include unrelated coverage. Read the source before drawing conclusions.</p></div><aside class="news-context"><h3>Corporate actions</h3><p class="microcopy">Historical dividends and splits from the price provider. This is not an upcoming earnings calendar.</p>${a.events?.length ? a.events.map((e) => `<div class="event-item"><span>${e.kind === 'dividends' ? 'Dividend' : 'Split'}</span><strong>${e.kind === 'dividends' ? currency(a) + num(e.value) : esc(e.value)}</strong><small>${dateOnly(e.date)}</small></div>`).join('') : '<p class="muted">No actions returned for this history.</p>'}<div class="social-empty">${icon('globe')}<h4>Read the source</h4><p>Wording labels describe short titles. Discussion activity and news volume are attention samples; neither measures every investor’s opinion.</p></div><a class="text-button" href="${a.market === 'NSE' ? 'https://www.nseindia.com/get-quotes/equity?symbol=' + encodeURIComponent(a.symbol) : 'https://www.coingecko.com/'}" target="_blank" rel="noopener noreferrer">${a.market === 'NSE' ? 'Exchange reference' : 'Crypto reference'} ${icon('external')}</a></aside></div>`;
}
function journalForm(a) {
  const j = a.journal || {};
  return `<form id="journal-form" class="journal-form"><div class="journal-intro"><div class="eyebrow">WRITE IT BEFORE THE MOVE</div><h3>What do you see here?</h3><p>Save the reason you’re watching, the level that matters, and what changes your mind.</p></div><div class="form-grid"><label class="span-2">My thesis<textarea name="thesis" rows="4" placeholder="Why this asset? What needs to happen at your level?">${esc(j.thesis || '')}</textarea></label><label class="span-2">What invalidates this idea?<textarea name="invalidation" rows="2" placeholder="Price structure, an event, or a change in the business…">${esc(j.invalidation || '')}</textarea></label><label>Holding horizon<select name="horizon">${['1–3 months', '1 month', '2–6 months', '6+ months'].map((v) => `<option ${j.horizon === v ? 'selected' : ''}>${v}</option>`).join('')}</select></label><label>Next review<input type="date" name="review_date" value="${esc(j.review_date || '')}"/></label></div><div class="form-footer"><span>${j.updated_at ? 'Last saved ' + when(j.updated_at, true) : 'Stored on your laptop, per asset.'}</span><button class="button primary" type="submit">${icon('check')} Save thesis</button></div></form>`;
}
function renderAI(el) {
  const a = state.detail,
    m = state.models,
    saved = a.ai_brief?.rules_version === 5 ? a.ai_brief : null;
  if (!m) {
    el.innerHTML = researchLoading();
    api('models')
      .then((d) => {
        state.models = d;
        if (state.view === 'asset' && state.tab === 'ai') renderResearch();
      })
      .catch((e) => {
        state.models = { available: false, models: [], reason: e.message };
        if (state.tab === 'ai') renderResearch();
      });
    return;
  }
  const provider = state.aiProvider || m.default_provider || 'local',
    connection = m.providers?.[provider],
    cloud = provider !== 'local';
  const options = connection?.models || [],
    remembered = localStorage.getItem('signaldesk-ai-model:' + provider);
  const preferred = options.some((v) => v.id === remembered)
    ? remembered
    : options.some((v) => v.id === connection?.default_model)
      ? connection.default_model
      : options[0]?.id;
  const providerNames = { local: 'Ollama', gemini: 'Gemini', openai: 'OpenAI', groq: 'Groq' };
  const refs = (item) =>
    (item.source_ids || [])
      .map((id) => {
        const source = saved.sources.find((s) => s.id === id);
        return source?.url
          ? `<a class="evidence-ref" href="${esc(source.url)}" target="_blank" rel="noopener noreferrer">${esc(id)} ${icon('external')}</a>`
          : `<span class="evidence-ref">${esc(id)}</span>`;
      })
      .join(' ');
  el.innerHTML = `<div class="ai-intro"><div><div class="eyebrow">DAILY + WEEKLY EVIDENCE, IN CONTEXT</div><h3>Explain the setup and its counterpoints.</h3><p>The signal engine calculates the lean. AI selects source-backed observations and business explanations; it cannot invent prices or override data warnings.</p></div></div><div class="ai-controls"><label>Analysis provider<select id="ai-provider" ${state.aiRunning ? 'disabled' : ''}>${Object.entries(
    providerNames,
  )
    .map(
      ([id, name]) =>
        `<option value="${id}" ${id === provider ? 'selected' : ''}>${name}${id === 'local' ? ' · on this Mac' : ''}</option>`,
    )
    .join(
      '',
    )}</select></label><label>Research model<select id="ai-model" ${state.aiRunning || !options.length ? 'disabled' : ''}>${options.length ? options.map((option) => `<option value="${esc(option.id)}" ${option.id === preferred ? 'selected' : ''}>${esc(option.label)}</option>`).join('') : '<option>No enabled models available</option>'}</select></label><button class="button primary" data-action="generate-ai" ${state.aiRunning || !a.available || !connection?.configured || !options.length ? 'disabled' : ''}>${icon(state.aiRunning ? 'refresh' : 'spark', state.aiRunning ? 'spinning' : '')} ${state.aiRunning ? 'Reviewing evidence…' : saved ? 'Regenerate analysis' : 'Generate analysis'}</button></div><p class="signal-note">${cloud ? `${connection?.configured ? 'API key saved; generation access is checked when requested.' : 'Add your ' + providerNames[provider] + ' key in Data & AI connections.'} ${provider === 'openai' ? 'Uses your OpenAI Platform API billing or credits. ChatGPT subscriptions do not supply API credit.' : `${connection?.tier === 'paid' ? 'Paid account' : 'Free-tier account'} selected. Billing and quota follow your provider account, not this selector.`} Public stock/sector facts, financial figures and matched headlines go to ${providerNames[provider]}. Positions and private journal stay excluded.` : `Runs through Ollama on this Mac. Qwen3 8B is the default; choose other enabled installed chat models in connections. General models explain supplied evidence; they are not validated finance specialists.`} No automatic provider or model fallback. <a href="#settings">Data & AI connections →</a></p>

 ${state.aiRunning ? `<div class="ai-progress">${icon('refresh', 'spinning')} Reading the selected timeframe and both directional summaries. You can continue browsing.</div>` : ''}
 ${
   saved
     ? `${saved.candle_as_of !== a.as_of || saved.rules_version !== 5 || saved.analysis_fingerprint !== a.analysis_fingerprint ? '<div class="sync-banner warning">Saved analysis uses different candles, levels or earlier signal rules. Regenerate for the current evidence.</div>' : ''}<div class="ai-result-meta"><span>${esc(providerNames[saved.provider] || saved.provider)} · ${esc(saved.model)} · ${when(saved.generated_at, true)}</span><span>Price evidence ${when(saved.candle_as_of, true)}</span></div><div class="ai-summary"><span class="eyebrow">SOURCE-GROUNDED READ</span><p>${esc(saved.brief.summary.text)}</p>${refs(saved.brief.summary)}</div><div class="ai-grid"><section><h4>What supports the idea</h4>${saved.brief.observations
         .slice(0, 3)
         .map((item) => `<div class="ai-observation"><p>${esc(item.text)}</p>${refs(item)}</div>`)
         .join('')}</section><section><h4>What argues against it</h4>${saved.brief.counterpoints
         .slice(0, 2)
         .map((item) => `<div class="ai-observation"><p>${esc(item.text)}</p>${refs(item)}</div>`)
         .join(
           '',
         )}</section><section><h4>What to review next</h4><ul>${saved.brief.watch_next.map((x) => `<li>${esc(x)}</li>`).join('')}</ul></section></div><details class="ai-evidence"><summary>Sources & limits · ${saved.sources.length} inputs</summary><section><h4>Still unknown</h4><ul>${saved.brief.unknowns.map((x) => `<li>${esc(x)}</li>`).join('')}</ul></section>${saved.sources.map((source) => `<div><span class="evidence-ref">${esc(source.id)}</span><a href="${esc(source.url || a.source_url)}" target="_blank" rel="noopener noreferrer">${esc(source.title)}</a><small>${when(source.as_of, true)}</small></div>`).join('')}</details><div class="source-note">${esc(saved.notice)} Saved analysis does not update automatically.</div>`
     : `<div class="ai-empty"><h3>Generate an explanation when you need it.</h3><p>Both technical directions, business meaning, contrary evidence and source links. The stock’s chart, eight signals and free attention counts work without AI or an API key.</p></div>`
 }`;
}

async function generateAI() {
  const a = state.detail,
    symbol = a.symbol,
    tf = state.timeframe,
    model = $('#ai-model')?.value,
    provider = state.aiProvider || state.models?.default_provider || 'local';
  state.aiRunning = true;
  localStorage.setItem('signaldesk-ai-model:' + provider, model);
  renderResearch();
  try {
    const result = await api(`assets/${symbol}/ai-brief`, { model, timeframe: tf, provider });
    if (state.detail?.symbol === symbol && state.timeframe === tf) {
      state.detail.ai_brief = result;
      toast('Source-grounded analysis saved.');
    }
  } catch (e) {
    toast(e.message, true);
  } finally {
    state.aiRunning = false;
    if (state.view === 'asset' && state.tab === 'ai') renderResearch();
  }
}
function renderJournal() {
  const notes = state.data.assets.filter((a) => a.journal?.thesis || a.journal?.invalidation);
  $('#main').innerHTML =
    `<div class="page-heading"><div><div class="eyebrow">YOUR THINKING, OVER TIME</div><h1>Keep the thesis close.</h1><p>Your reasons, your invalidations, your next review.</p></div><button class="button secondary" data-action="backup">${icon('download')} Export workspace</button></div>${notes.length ? `<div class="journal-grid">${notes.map((a) => `<a class="journal-note" href="#asset/${esc(a.symbol)}"><div class="asset-cell">${avatar(a)}<div><strong>${esc(a.name)}</strong><span>${esc(a.symbol)} · ${esc(a.journal.horizon)}</span></div>${icon('arrow')}</div><span class="eyebrow">THESIS</span><p>${esc(a.journal.thesis || 'No thesis written yet.')}</p>${a.journal.invalidation ? `<div class="invalidation-note"><strong>Invalidation</strong><p>${esc(a.journal.invalidation)}</p></div>` : ''}<footer>${a.journal.review_date ? 'Review ' + dateOnly(a.journal.review_date) : 'No review date'}<span>Saved ${when(a.journal.updated_at)}</span></footer></a>`).join('')}</div>` : `<div class="empty-state journal-empty">${icon('book')}<h2>A good thesis deserves a place to live.</h2><p>Open any asset, select My thesis, and record what you see.<br>Your notes stay here between sessions.</p><a class="button primary" href="#watchlist">Explore your watchlist ${icon('arrow')}</a></div>`}`;
}
function renderSettings() {
  if (!state.models && !state.modelsLoading) {
    state.modelsLoading = true;
    api('models')
      .then((d) => {
        state.models = d;
        if (state.view === 'settings') renderSettings();
      })
      .catch((e) => {
        state.models = { providers: {}, reason: e.message };
        if (state.view === 'settings') renderSettings();
      })
      .finally(() => {
        state.modelsLoading = false;
      });
  }
  const d = state.data,
    r = d.refresh;
  $('#main').innerHTML =
    `<div class="page-heading"><div><div class="eyebrow">YOUR LOCAL WORKSPACE</div><h1>A clear view of your data.</h1><p>Know the source. Check the timestamp. Keep your work.</p></div><button class="button primary" data-action="backup">${icon('download')} Export workspace</button></div>${connectionsPanel()}<div class="settings-top"><section class="settings-card"><span class="settings-icon">${icon('shield')}</span><h2>At home on your Mac.</h2><p>Positions, notes, zones, and cached research live in a local SQLite database. There is no account or cloud sync.</p><div class="settings-detail"><span>Price refresh</span><strong>History: 15 min · quotes: 1–2 min</strong></div><div class="settings-detail"><span>Indicator basis</span><strong>Completed daily / weekly candles</strong></div><div class="settings-detail"><span>News / financial cache</span><strong>30 minutes / 24 hours</strong></div><div class="settings-detail"><span>Research synthesis</span><strong>Signals + Ollama / Gemini / OpenAI / Groq</strong></div><button class="text-button" data-action="method">Read calculation methodology ${icon('arrow')}</button></section></div><section class="data-health-card"><div class="section-heading"><div><h2>Source health <span class="number-label">${d.assets.length}</span></h2><p>${r.running ? 'Refreshing ' + r.completed + ' / ' + r.total : r.finished_at ? 'Last refresh finished ' + when(r.finished_at, true) : 'Using cached history'}</p></div><button class="button secondary" data-action="refresh">${icon('refresh', r.running ? 'spinning' : '')} Refresh sources</button></div><div class="table-scroll"><table><thead><tr><th>Asset</th><th>Source / pair</th><th>Signal candles through</th><th>Latest quote</th><th>Retrieved</th><th>Status</th></tr></thead><tbody>${d.assets.map((a) => `<tr><td><a href="#asset/${esc(a.symbol)}" class="health-symbol">${esc(a.symbol)} ${icon('external')}</a></td><td>${esc(a.source || 'Awaiting fetch')}<span class="cell-subline muted">${esc(a.provider_symbol || '')}</span></td><td title="${esc(a.quality_note || '')}">${a.as_of ? when(a.as_of, true) : '—'}${a.quality_note ? '<span class="cell-subline stale-label">Missing recent candle(s)</span>' : ''}</td><td>${a.quote ? currency(a) + num(a.quote.price) + '<span class="cell-subline muted">' + quoteStamp(a.quote) + ' · ' + esc(a.quote.source) + '</span>' : 'No quote'}</td><td>${a.fetched_at ? when(a.fetched_at) : '—'}</td><td>${r.errors[a.symbol] ? `<span class="health-error" title="${esc(r.errors[a.symbol])}">${esc(r.errors[a.symbol])}</span>` : `<span class="pill ${a.stale ? 'amber' : ''}">${!a.available ? 'No history' : a.quality_note ? 'History gaps' : a.stale ? 'Stale history' : 'Available'}</span>`}</td></tr>`).join('')}</tbody></table></div></section><div class="source-principles"><div>${icon('info')}<p><strong>Provider data can be delayed.</strong> The page always shows the timestamp of the data used. A successful refresh does not guarantee a current quote.</p></div><div>${icon('bitcoin')}<p><strong>Crypto pair mapping is explicit.</strong> Screenshot labels ETHUSD, SOLUSD and XRPUSD use Binance USDT spot history. TOTAL is CoinGecko market cap in USD, not an asset or candle series.</p></div></div>`;
  const health = $('#main .data-health-card');
  if (health) {
    const disclosure = document.createElement('details');
    disclosure.className = 'more-detail';
    const summary = document.createElement('summary');
    summary.textContent = 'Source health and timestamps';
    health.replaceWith(disclosure);
    disclosure.append(summary, health);
  }
}

function modal(title, content, { wide = false } = {}) {
  $('#modal-root').innerHTML =
    `<div class="modal-backdrop"><section class="modal ${wide ? 'wide' : ''}" role="dialog" aria-modal="true" aria-labelledby="modal-title"><div class="modal-heading"><h2 id="modal-title">${title}</h2><button class="icon-button" data-action="close-modal" aria-label="Close dialog">${icon('close')}</button></div>${content}</section></div>`;
  setTimeout(() => $('#modal-root input')?.focus(), 30);
}
const closeModal = () => ($('#modal-root').innerHTML = '');
function zoneModal(z = {}) {
  modal(
    z.id ? 'Edit your level' : 'Mark your level',
    `<form id="zone-form"><p class="modal-description">A price band where you want to watch the response. Your saved levels stay separate from algorithmic candidates.</p><div class="form-grid"><label class="span-2">Type<select name="kind"><option value="demand" ${z.kind === 'demand' ? 'selected' : ''}>Demand · watch for buyers</option><option value="supply" ${z.kind === 'supply' ? 'selected' : ''}>Supply · watch for sellers</option></select></label><label>Lower price<input type="number" step="any" min="0.000001" name="low" value="${z.low != null ? Number(z.low.toFixed(4)) : ''}" required/></label><label>Upper price<input type="number" step="any" min="0.000001" name="high" value="${z.high != null ? Number(z.high.toFixed(4)) : ''}" required/></label><label class="span-2">Label<input name="label" maxlength="80" placeholder="e.g. Weekly base / prior resistance" value="${esc(z.label || '')}"/></label></div><input type="hidden" name="id" value="${z.id || ''}"/><div class="form-footer"><span>${esc(state.detail.symbol)} · ${esc(state.detail.currency || 'price')}</span><button class="button primary" type="submit">${icon('check')} Save zone</button></div></form>`,
  );
}
function positionModal() {
  const a = state.detail,
    p = a.position || {};
  modal(
    'Your position',
    `<form id="position-form"><p class="modal-description">Choose whether you hold this asset. Add your actual quantity and average cost to calculate position value and unrealised P&L.</p><div class="form-grid"><label class="span-2 checkbox-label"><input type="checkbox" name="held" ${a.held ? 'checked' : ''}/> I hold this asset</label><label>Quantity<input name="quantity" type="number" min="0.00000001" step="any" value="${p.quantity || ''}" placeholder="e.g. 10"/></label><label>Average cost (${esc(a.currency || 'INR')})<input name="average" type="number" min="0.00000001" step="any" value="${p.average || ''}" placeholder="Your entry price"/></label></div><p class="microcopy">Both fields can stay empty. P&L excludes fees, dividends, taxes, and currency conversion.</p><div class="form-footer"><span>${esc(a.name)}</span><button class="button primary" type="submit">Save position</button></div></form>`,
  );
}
function addAssetModal() {
  modal(
    'Find and track another stock.',
    `<form id="add-asset-form"><p class="modal-description">Search the NSE symbol directory, or enter an exact NSE, US or Binance USDT symbol. Your existing levels and holdings stay saved.</p><div class="form-grid"><label class="span-2">Search NSE companies<input id="catalog-search" autocomplete="off" placeholder="e.g. Infosys, petroleum, Tata…"/></label><div class="span-2" id="catalog-results"></div><label>Market<select name="market"><option value="NSE">NSE equity / ETF</option><option value="US">US stock</option><option value="CRYPTO">Crypto · USDT spot</option></select></label><label>Symbol<input name="symbol" required maxlength="24" placeholder="INFY / AAPL / LINKUSDT" style="text-transform:uppercase"/></label><label class="span-2">Display name<input name="name" maxlength="100" placeholder="Company / asset name"/></label><label class="span-2">Research group / sector<select name="sector">${['Custom watchlist', 'Materials & commodity ETFs', 'Healthcare', 'Entertainment & leisure', 'Oil, gas & energy', 'Technology', 'Consumer', 'Banking & finance', 'Other NSE'].map((s) => `<option>${s}</option>`).join('')}</select></label></div><div class="form-footer"><span>Exact symbols work even if directory search is unavailable.</span><button class="button primary" type="submit">${icon('plus')} Track asset</button></div></form>`,
  );
}

function searchModal() {
  modal(
    'Find your next research focus.',
    `<div class="modal-search">${icon('search')}<input id="global-search" placeholder="Search your watchlist…" autocomplete="off"/></div><div id="search-results"></div>`,
  );
  renderSearch('');
}
function renderSearch(query) {
  const q = query.toLowerCase();
  const matches = state.data.assets.filter((a) =>
    (a.name + ' ' + a.symbol).toLowerCase().includes(q),
  );
  $('#search-results').innerHTML =
    matches
      .slice(0, 10)
      .map(
        (a) =>
          `<a href="#asset/${a.symbol}" class="search-result" data-action="close-modal">${avatar(a)}<div><strong>${esc(a.name)}</strong><span>${esc(a.symbol)} · ${a.market}</span></div><span class="tabular">${a.available ? currency(a) + num(a.summary.price) : '—'}</span>${icon('arrow')}</a>`,
      )
      .join('') ||
    '<button class="button secondary" data-action="add-asset">Find and track another stock</button>';
}
function methodModal() {
  modal(
    'Your swing screening rules.',
    `<div class="method-copy"><p><strong>Green means your chosen condition matched.</strong> Several are contrarian pullback watches: they can turn green while price or momentum is still falling. The balance is a count of your rules, not a forecast of a rebound. Daily and weekly are separate; the 200-day reference always uses completed daily closes.</p><ol><li><strong>RSI 15 / SMA 14:</strong> green when RSI dipped strictly below 35 in the previous 30 selected-timeframe bars and is now strictly above 40 and rising versus the preceding bar (+1). Falling RSI below 40 adds −1; other cases zero. The yellow RSI line is its 14-period SMA.</li><li><strong>Stoch RSI 14/14/3/3:</strong> K ≤20 or K below its preceding value turns green (+1). Other cases zero. K/D and new crosses remain visible. Low or falling Stoch RSI does not confirm that a rebound has begun.</li><li><strong>Volume:</strong> at least 1.3× the previous 20-bar average adds +1 on an up-close and −1 on a down-close. Otherwise zero. Partial-week volume remains provisional.</li><li><strong>200-day mean reversion:</strong> the latest completed daily close below its 200-day SMA turns green (+1); at/above adds zero. The percentage to the average is a reference gap, not a target. The chart still shows selected-timeframe SMA 20/50/200.</li><li><strong>Supply & demand:</strong> inside valid demand or ≤3% above it turns green (+1) and qualifies for Long candidates. Nearby supply stays a warning without cancelling this match. Supply within 3% without nearby demand adds −1. Broken demand does not qualify.</li><li><strong>3 / 7 / 14 rising:</strong> any positive net closing-price change turns green (+1), even with red days inside the move. All three negative adds −1; otherwise zero. Missing windows stay unknown. Daily uses the latest close at/before each calendar-day anchor (maximum seven-day anchor gap); weekly uses 3/7/14 weekly bars. Actual window highs remain separate.</li><li><strong>Move above +1%:</strong> strictly more than +1% from the preceding completed close adds +1; below −1% adds −1; otherwise zero. Weekly compares weekly closes. A green demand match plus this move ranks higher.</li><li><strong>Support retest & rebound:</strong> two confirmed troughs near the same floor, a meaningful dip, strong upward response, close above the intervening high and rising SMA 20/50. Fresh confirmation +1; support failure −1; forming/absent zero.</li></ol><p><strong>Candidate order:</strong> demand with both a positive 3/7/14 period and a >1% move, demand with either extra match, then demand alone. Other green rules follow. Setup score /100 gives demand 45 points, a positive period with demand 20, a >1% move with demand 20, the eight-rule balance scaled from −8…+8 to 0…10, and daily/weekly buy-side alignment 5. Candidates sort highest score first. The eight-rule balance itself keeps one point per component; the separate setup score weights your preferred combinations.</p><p><strong>Balance and data:</strong> ≥+2 is a buy-side lean, ≤−2 sell-side, otherwise mixed. Five available components are required for the lean and non-demand candidates. Green demand independently qualifies for the shortlist. Missing, stale or known-incomplete price history excludes candidates. An unfinished weekly view is provisional.</p><details><summary>How automatic bands are drawn</summary><p>A 2–4-bar base followed by a ≥1.4 ATR departure within three bars, including a ≥0.8 ATR body, proposes a band. Repeated confirmed pivots supplement this. Later closes beyond the far edge +0.25 origin ATR invalidate automatic bands. Retests, freshness and daily/weekly overlaps describe the evidence. This detector has no validated win rate.</p></details></div>`,
    { wide: true },
  );
}

async function refreshOverview() {
  state.data = await api('overview');
}
async function refreshDetail() {
  if (!state.detail) return;
  const symbol = state.detail.symbol,
    tf = state.timeframe,
    id = ++state.loadId;
  const next = await api(`assets/${encodeURIComponent(symbol)}?timeframe=${tf}`);
  if (id !== state.loadId || state.view !== 'asset' || state.timeframe !== tf) return;
  state.detail = next;
  await refreshOverview();
  if (id !== state.loadId || state.view !== 'asset') return;
  renderDetail();
  if (!state.research) loadResearch(symbol, id);
}
async function backup() {
  const d = await api('backup');
  const blob = new Blob([JSON.stringify(d, null, 2)], { type: 'application/json' });
  const url = URL.createObjectURL(blob);
  const a = document.createElement('a');
  a.href = url;
  a.download = 'swing-signal-workspace-' + new Date().toISOString().slice(0, 10) + '.json';
  a.click();
  setTimeout(() => URL.revokeObjectURL(url), 1000);
  toast('Workspace exported, including notes, levels, positions and cached history.');
}

document.addEventListener('click', async (event) => {
  const button = event.target.closest('[data-action]');
  if (!button) return;
  const action = button.dataset.action,
    value = button.dataset.value;
  try {
    if (action === 'catalog-pick') {
      const a = state.catalog?.[Number(value)];
      if (!a) return;
      if (a.tracked) {
        closeModal();
        nav('asset/' + a.symbol);
        return;
      }
      const form = $('#add-asset-form');
      form.elements.symbol.value = a.symbol;
      form.elements.name.value = a.name;
      form.elements.market.value = 'NSE';
      $('#catalog-results').innerHTML = '';
      return;
    }
    if (action === 'open-asset') {
      nav('asset/' + button.dataset.symbol);
      return;
    }
    if (action === 'refresh') {
      await api('refresh', {});
      await refreshOverview();
      if (state.view !== 'asset') shell();
      toast('Refreshing market sources…');
      return;
    }
    if (action === 'menu') {
      $('.sidebar').classList.toggle('open');
      return;
    }
    if (action === 'search') {
      searchModal();
      return;
    }
    if (action === 'close-modal') {
      closeModal();
      return;
    }
    if (action === 'add-asset') {
      addAssetModal();
      return;
    }
    if (action === 'scan-timeframe') {
      state.scanTimeframe = value;
      renderContent();
      return;
    }
    if (action === 'sector') {
      state.sector = value;
      state.showAll = true;
      renderContent();
      return;
    }
    if (action === 'filter') {
      state.sector = '';
      state.filter = value;
      state.showAll = false;
      if (['holdings', 'nse', 'crypto', 'us'].includes(state.view)) {
        state.view = 'watchlist';
        history.replaceState(null, '', '#watchlist');
      }
      renderContent();
      return;
    }
    if (action === 'near-filter') {
      state.setup = 'near';
      $('#setup-filter').value = 'near';
      state.showAll = true;
      renderTable();
      $('#asset-table').scrollIntoView({ behavior: 'smooth', block: 'nearest' });
      return;
    }
    if (action === 'sort') {
      state.sort = state.sort === value ? 'default' : value;
      renderTable();
      return;
    }
    if (action === 'table-search') {
      $('#table-search').classList.toggle('hidden');
      $('#watch-query')?.focus();
      return;
    }
    if (action === 'clear-search') {
      state.query = '';
      $('#watch-query').value = '';
      $('#table-search').classList.add('hidden');
      renderTable();
      return;
    }
    if (action === 'reset-filters') {
      state.query = '';
      state.sector = '';
      state.setup = 'all';
      state.filter = 'all';
      renderContent();
      return;
    }
    if (action === 'show-all') {
      state.showAll = !state.showAll;
      renderTable();
      return;
    }
    if (action === 'check-ai-connection') {
      const provider = button.dataset.provider,
        status = document.querySelector(`[data-connection-status="${provider}"]`);
      button.disabled = true;
      status.textContent = 'Checking saved connection…';
      try {
        const result = await api('connections/check', { provider });
        status.textContent = result.message;
        status.className = 'connection-status positive';
      } catch (e) {
        status.textContent = e.message;
        status.className = 'connection-status negative';
      } finally {
        button.disabled = false;
      }
      return;
    }
    if (action === 'refresh-ai-models') {
      button.disabled = true;
      try {
        state.models = await api('models');
        const form = $('#connections-form'),
          draft = {
            ...state.data.connections,
            local_model: form.elements.local_model.value,
            local_models: [...form.querySelectorAll('[name=local_models]:checked')].map(
              (e) => e.value,
            ),
          };
        $('#ollama-model-options').innerHTML = ollamaOptions(draft);
        toast('Installed chat models refreshed.');
      } catch (e) {
        toast(e.message, true);
      } finally {
        button.disabled = false;
      }
      return;
    }
    if (action === 'method') {
      methodModal();
      return;
    }
    if (action === 'zone') {
      zoneModal();
      return;
    }
    if (action === 'edit-zone') {
      zoneModal(state.detail.zones.find((z) => z.id === Number(button.dataset.id)));
      return;
    }
    if (action === 'delete-zone') {
      await api(`assets/${state.detail.symbol}/delete-zone`, { id: Number(button.dataset.id) });
      await refreshDetail();
      toast('Zone removed.');
      return;
    }
    if (action === 'position') {
      positionModal();
      return;
    }
    if (action === 'timeframe') {
      state.timeframe = value;
      await refreshDetail();
      return;
    }
    if (action === 'range') {
      state.range = Number(value);
      document
        .querySelectorAll('.range-controls button')
        .forEach((b) => b.classList.toggle('active', b.dataset.value === value));
      mountChart();
      return;
    }
    if (action === 'candidates') {
      state.candidates = !state.candidates;
      renderDetail();
      return;
    }
    if (action === 'draw-zone') {
      const area = $('#chart-area');
      if (area.dataset.drawing) {
        area.dataset.drawing = '';
        button.classList.remove('drawing');
        toast('Drawing cancelled.');
      } else {
        area.dataset.drawing = '1';
        button.classList.add('drawing');
        toast('Click the two price edges of your zone in the candle pane.');
      }
      return;
    }
    if (action === 'research-tab') {
      state.tab = value;
      document
        .querySelectorAll('.research-tabs button')
        .forEach((b) => b.classList.toggle('active', b.dataset.value === value));
      renderResearch();
      return;
    }
    if (action === 'backup') {
      await backup();
      return;
    }
    if (action === 'generate-ai') {
      await generateAI();
      return;
    }
  } catch (e) {
    toast(e.message, true);
    button.disabled = false;
  }
});
document.addEventListener('submit', async (event) => {
  const form = event.target;
  const formId = form.getAttribute('id');
  if (
    ![
      'zone-form',
      'position-form',
      'journal-form',
      'add-asset-form',
      'connections-form',
      'trends-form',
    ].includes(formId)
  )
    return;
  event.preventDefault();
  const body = Object.fromEntries(new FormData(form)),
    button = form.querySelector('[type=submit]');
  button.disabled = true;
  try {
    if (formId === 'trends-form') {
      const file = form.elements.file.files[0],
        symbol = state.detail.symbol;
      if (file.size > 500_000) throw Error('Choose a Google Trends CSV smaller than 500 KB');
      const result = await api(`assets/${symbol}/trends-import`, { csv: await file.text() });
      if (state.detail?.symbol === symbol && state.research) {
        state.research.search_interest = { ...state.research.search_interest, ...result };
        renderResearch();
      }
      toast('Search interest history saved locally.');
    }
    if (formId === 'connections-form') {
      body.local_models = [...form.querySelectorAll('[name=local_models]:checked')].map(
        (e) => e.value,
      );
      state.data.connections = await api('connections', body);
      for (const provider of ['local', 'gemini', 'openai', 'groq'])
        localStorage.removeItem('signaldesk-ai-model:' + provider);
      state.aiProvider = null;
      state.models = null;
      if (state.view === 'settings') renderSettings();
      toast('Connections saved privately on this Mac.');
    }
    if (formId === 'zone-form') {
      if (body.id) body.id = Number(body.id);
      else delete body.id;
      body.label = body.label || 'My ' + body.kind + ' zone';
      await api(`assets/${state.detail.symbol}/zone`, body);
      closeModal();
      await refreshDetail();
      toast('Your level is saved.');
    }
    if (formId === 'position-form') {
      body.held = form.elements.held.checked;
      await api(`assets/${state.detail.symbol}/position`, body);
      closeModal();
      await refreshDetail();
      toast('Position saved on your Mac.');
    }
    if (formId === 'journal-form') {
      await api(`assets/${state.detail.symbol}/journal`, body);
      await refreshDetail();
      state.tab = 'journal';
      renderResearch();
      toast('Thesis saved.');
    }
    if (formId === 'add-asset-form') {
      if (!body.name) body.name = body.symbol;
      await api('assets', body);
      closeModal();
      await refreshOverview();
      nav('asset/' + body.symbol.trim().toUpperCase().replace(/\.NS$/, ''));
      toast('Tracked. History is refreshing; signals appear when it is available.');
    }
  } catch (e) {
    toast(e.message, true);
  } finally {
    button.disabled = false;
  }
});
document.addEventListener('input', (e) => {
  if (e.target.id === 'catalog-search') {
    clearTimeout(catalogTimer);
    catalogTimer = setTimeout(() => findCatalog(e.target.value), 300);
  }
  if (e.target.id === 'global-search') renderSearch(e.target.value);
  if (e.target.id === 'watch-query') {
    state.query = e.target.value;
    renderTable();
  }
});
document.addEventListener('change', (e) => {
  if (e.target.id === 'candidate-market') {
    state.candidateMarket = e.target.value;
    renderCandidates();
  }
  if (e.target.id === 'candidate-criterion') {
    state.candidateCriterion = e.target.value;
    renderCandidates();
  }
  if (e.target.id === 'candidate-timeframe') {
    state.candidateTimeframe = e.target.value;
    renderCandidates();
  }
  if (e.target.id === 'ai-provider') {
    state.aiProvider = e.target.value;
    renderResearch();
  }
  if (e.target.id === 'ai-model') {
    localStorage.setItem(
      'signaldesk-ai-model:' + (state.aiProvider || state.models?.default_provider || 'local'),
      e.target.value,
    );
  }
  if (e.target.name === 'local_model') {
    const form = e.target.form;
    for (const checkbox of form.querySelectorAll('[name=local_models]'))
      if (checkbox.value === e.target.value) checkbox.checked = true;
  }
  if (e.target.name === 'local_models') {
    const form = e.target.form,
      enabled = [...form.querySelectorAll('[name=local_models]:checked')].map((x) => x.value);
    if (enabled.length && !enabled.includes(form.elements.local_model.value))
      form.elements.local_model.value = enabled[0];
  }
  if (e.target.name === 'gemini_tier') {
    const select = document.querySelector('[name=gemini_model]');
    select.innerHTML = cloudModelOptions('gemini', e.target.value, select.value);
  }
  if (e.target.id === 'setup-filter') {
    state.setup = e.target.value;
    state.showAll = true;
    renderTable();
  }
  if (e.target.id === 'signal-sort') {
    state.sort = e.target.value;
    renderTable();
  }
});
document.addEventListener('keydown', (e) => {
  if ((e.metaKey || e.ctrlKey) && e.key.toLowerCase() === 'k') {
    e.preventDefault();
    searchModal();
  }
  if (e.key === 'Escape') {
    closeModal();
    const area = $('#chart-area');
    if (area) area.dataset.drawing = '';
  }
  if (e.key === 'Enter' && e.target.matches('tr[data-action]'))
    nav('asset/' + e.target.dataset.symbol);
  if (e.key === 'Tab' && $('#modal-root .modal')) {
    const focusable = [
      ...document.querySelectorAll(
        '#modal-root button,#modal-root input,#modal-root select,#modal-root a,#modal-root textarea',
      ),
    ].filter((x) => !x.disabled && x.type !== 'hidden');
    if (!focusable.length) return;
    const first = focusable[0],
      last = focusable.at(-1);
    if (e.shiftKey && document.activeElement === first) {
      e.preventDefault();
      last.focus();
    } else if (!e.shiftKey && document.activeElement === last) {
      e.preventDefault();
      first.focus();
    }
  }
});
document.addEventListener('click', (e) => {
  if (e.target.matches('.modal-backdrop')) closeModal();
});
async function route() {
  if (!state.data) return;
  closeModal();
  disposeChart();
  const hash = location.hash.slice(1) || 'overview';
  if (hash.startsWith('asset/')) {
    await openAsset(decodeURIComponent(hash.slice(6)));
    return;
  }
  ++state.loadId;
  state.view = [
    'overview',
    'candidates',
    'watchlist',
    'holdings',
    'journal',
    'settings',
    'nse',
    'crypto',
    'us',
  ].includes(hash)
    ? hash
    : 'overview';
  state.detail = null;
  state.query = '';
  state.sector = '';
  state.setup = 'all';
  state.showAll = false;
  shell();
  window.scrollTo(0, 0);
}
window.addEventListener('hashchange', route);
async function init() {
  try {
    await refreshOverview();
    await route();
  } catch (e) {
    $('#app').innerHTML =
      `<div class="boot"><h2>Your local service is unavailable.</h2><p>${esc(e.message)}</p><button onclick="location.reload()" class="button primary">Try again</button></div>`;
  }
  setInterval(async () => {
    try {
      const wasRunning = state.data?.refresh.running,
        oldQuotes = state.data?.quote_state?.finished_at;
      await refreshOverview();
      if (oldQuotes !== state.data.quote_state?.finished_at && !$('#modal-root').innerHTML) {
        if (['overview', 'watchlist', 'nse', 'us', 'crypto', 'holdings'].includes(state.view))
          renderTable();
        else if (state.view === 'asset' && state.detail) {
          const current = state.data.assets.find((a) => a.symbol === state.detail.symbol);
          state.detail.quote = current?.quote;
          const q = current?.quote;
          if (q && $('.asset-price'))
            $('.asset-price').innerHTML =
              '<strong>' +
              currency(current) +
              num(q.price) +
              '</strong>' +
              change(q.change) +
              '<small>' +
              esc(q.kind) +
              ' · ' +
              quoteStamp(q) +
              '</small>';
        }
      }
      if (
        (state.data.refresh.running || wasRunning) &&
        !$('#modal-root').innerHTML &&
        !document.activeElement?.matches('input,textarea,select')
      ) {
        if (state.view !== 'asset' && state.view !== 'settings') shell();
        else if (
          wasRunning &&
          !state.data.refresh.running &&
          state.detail &&
          !['journal', 'ai'].includes(state.tab)
        )
          await refreshDetail();
      }
    } catch {
      /* Keep the last view while the local service is restarting. */
    }
  }, 5000);
}
init();

function biasBadge(s, label = '') {
  return `<span class="bias-badge ${s?.direction || 'unavailable'}" title="${esc(s?.basis || 'No price history')}">${label ? `<b>${label}</b> ` : ''}${esc(s?.label || 'No history')}</span>`;
}
function renderSignalDesk(a) {
  const selected = state.timeframe === '1w' ? a.weekly_swing : a.daily_swing;
  return `<section class="swing-desk"><div class="section-heading"><div><h2>The swing reading</h2><p>Daily for the recent turn. Weekly for the broader hold. Green means your screening rule matched. The 200-day reference uses daily candles in both views.</p></div><button class="text-button" data-action="method">Inspect the rules ${icon('info')}</button></div><div class="bias-comparison">${[
    ['Daily', a.daily_swing],
    ['Weekly' + (a.week_partial ? ' · provisional' : ''), a.weekly_swing],
  ]
    .map(
      ([title, s]) =>
        `<article class="bias-summary ${s?.direction || 'unavailable'}"><span>${title}</span><h3>${esc(s?.label || 'No history')}</h3>${s?.near_demand && s?.direction !== 'unavailable' ? '<small class="summary-candidate">Long candidate · demand matched</small>' : ''}<p>Evidence balance ${s?.score == null ? '—' : (s.score > 0 ? '+' : '') + fmt(s.score, 1)} · ${s?.coverage || 0}/8 signals available</p><div>${
          (s?.signals || [])
            .filter((x) => x.score)
            .sort((a, b) => (b.key === 'zones' && b.score > 0) - (a.key === 'zones' && a.score > 0))
            .slice(0, 2)
            .map(
              (x) =>
                `<span class="reason-chip ${x.direction}">${x.key === 'highs' ? trendPeriods(x) : esc(x.title) + ' ' + (x.score > 0 ? '✓' : '↓')}</span>`,
            )
            .join('') || 'No aligned directional evidence.'
        }</div></article>`,
    )
    .join(
      '',
    )}</div><details class="signal-details"><summary>See all 8 signals and their readings</summary><div class="seven-detail-heading"><h3>${state.timeframe === '1w' ? 'Weekly' : 'Daily'} · your eight signals</h3><div class="segmented"><button data-action="timeframe" data-value="1d" aria-label="Show daily signals" class="${state.timeframe === '1d' ? 'active' : ''}">Daily</button><button data-action="timeframe" data-value="1w" aria-label="Show weekly signals" class="${state.timeframe === '1w' ? 'active' : ''}">Weekly</button></div><span>${state.timeframe === '1w' ? '3W / 7W / 14W rising compares weekly closes. Daily high touches remain available as context.' : '3D / 7D / 14D rising compares net closing-price change; red days can occur within an uptrend.'}</span></div><div class="seven-detail">${(selected?.signals || []).map((x, i) => `<article class="signal-tile ${x.direction}"><span class="signal-index">0${i + 1}</span><h4>${esc(x.title)}</h4><strong>${x.key === 'highs' ? trendPeriods(x) : esc(x.value)}</strong><p>${esc(x.reading)}</p>${x.key === 'ma' ? `<small>Chart ${state.timeframe === '1w' ? 'weekly' : 'daily'} averages: ${[20, 50, 200].map((n) => `SMA ${n}: ${num(a.summary['sma' + n])}`).join(' · ')}</small>` : ''}</article>`).join('')}</div>${
    state.timeframe === '1w'
      ? `<p class="signal-note">Daily context: ${[7, 14]
          .map((n) => {
            const h = selected?.daily_highs?.[n];
            return (
              n +
              'D high ' +
              (h?.available
                ? (h.reached ? 'reached' : 'not reached') + ' · ' + num(h.high)
                : 'unavailable')
            );
          })
          .join(' / ')}. This daily context does not enter the weekly balance.</p>`
      : ''
  }${selected?.warnings?.length ? `<div class="signal-counterpoints"><strong>Counterpoints</strong><span>${selected.warnings.map(esc).join(' ')}</span></div>` : ''}<p class="source-note">${esc(a.methodology || '')} ${a.resampled_dates?.length ? 'Recent Yahoo sessions rebuilt from complete hourly data: ' + a.resampled_dates.map(dateOnly).join(', ') : ''}</p></details><p class="signal-note">Eight correlated technical observations, not a success probability. No financial valuation score is mixed into this balance. ${a.week_partial ? 'Weekly numbers can change until the week closes.' : ''}</p></section>`;
}
function marketCompass() {
  return `<div class="market-compass">${[
    ['NSE', 'NIFTY50', 'nse', 'Nifty 50'],
    ['United States', 'SP500', 'us', 'S&P 500'],
    ['Crypto', 'BTC', 'crypto', 'Bitcoin · USDT'],
  ]
    .map(([name, key, path, proxy]) => {
      const b = state.data.benchmarks.find((b) => b.symbol === key);
      return `<a class="compass-card" href="#${path}"><div><span>${name}</span>${icon('arrow')}</div><h2>${b?.change == null ? 'Awaiting data' : b.change > 0 ? 'Moving up' : b.change < 0 ? 'Moving down' : 'Flat'}</h2><strong class="${tone(b?.change)}">${signed(b?.change)}</strong><span>${proxy} · latest completed daily bar</span><span>Latest weekly bar: <b class="${tone(b?.week_change)}">${signed(b?.week_change)}</b> · may be provisional</span>${b?.sparkline?.length ? spark(b.sparkline, b.change >= 0 ? '#4fc795' : '#e78284') : ''}<small>${b?.as_of ? when(b.as_of, true) : 'No history'}${b?.quality_note ? ' · Data gaps' : ''}</small></a>`;
    })
    .join('')}</div>`;
}
function correlationPanel() {
  const values = state.data.correlations || [];
  return `<section class="correlation-panel"><div><h3>Do the markets move together?</h3><p>Historical return correlation. +1 means moving together; −1 means moving opposite.</p></div><div class="correlation-values">${values.map((c) => `<div><span>${esc(c.left)} / ${esc(c.right)}</span><strong>${c.value == null ? 'Insufficient overlap' : fmt(c.value, 2)}</strong><small>${c.samples} matched returns · through ${dateOnly(c.through)}</small></div>`).join('')}</div><p class="signal-note">Up to 60 matching daily return intervals, with at least 20 required. No filled holiday prices. NSE, US and crypto close at different times; this does not establish which market leads.</p></section>`;
}
function sectorPanel() {
  return `<section class="sector-section"><div class="section-heading"><div><h2>Your NSE research groups</h2><p>Coal India, petroleum and power are grouped for your research; these are not formal NSE sector classifications.</p></div><button class="text-button" data-action="sector" data-value="">Show all groups</button></div><div class="sector-grid">${(state.data.sectors || []).map((s) => `<button class="sector-card ${state.sector === s.name ? 'selected' : ''}" data-action="sector" data-value="${esc(s.name)}"><span>${esc(s.name)}</span><strong class="${tone(s.change)}">${signed(s.change)}</strong><small>${s.advancing}/${s.available} advancing · ${s.buy_side} buy-side / ${s.sell_side} sell-side</small><small>${s.count} tracked · ${s.dates.length > 1 ? 'Mixed candle dates' : dateOnly(s.dates[0])}${s.fresh_count < s.available ? ' · Check data' : ''}</small></button>`).join('')}</div><p class="signal-note">Equal-weight latest session moves of the tracked names in each group, not exchange-wide sector returns. METALIETF owns metal-producing companies; it is not a physical metal fund.</p></section>`;
}
function usSectorPanel() {
  return `<section class="sector-section"><div class="section-heading"><div><h2>US sectors at a glance</h2><p>Sector ETF proxies · latest completed session. XLG tracks an index of 50 large S&P 500 companies.</p></div></div><div class="us-sector-grid">${(state.data.us_sectors || []).map((s) => `<a href="${esc(s.source_url || 'https://www.ssga.com/us/en/intermediary/etfs/sector-spdr-etfs')}" target="_blank" rel="noopener noreferrer" class="us-sector"><span>${esc(s.name)} <small>${s.symbol}</small></span><strong class="${tone(s.change)}">${signed(s.change)}</strong><small>${s.as_of ? when(s.as_of) : 'Awaiting data'}${s.stale ? ' · Stale' : ''}</small></a>`).join('')}</div></section>`;
}

function cloudModelOptions(provider, tier, selected) {
  const source = state.models?.providers?.[provider],
    choices = (source?.all_models || source?.models || []).filter(
      (m) => provider !== 'gemini' || tier === 'paid' || m.free_tier,
    );
  if (!choices.length)
    return `<option value="${esc(selected || '')}">${esc(selected || 'Loading models…')}</option>`;
  const preferred = choices.some((m) => m.id === selected) ? selected : choices[0].id;
  return choices
    .map(
      (m) =>
        `<option value="${esc(m.id)}" ${m.id === preferred ? 'selected' : ''}>${esc(m.label)}${provider === 'gemini' && !m.free_tier ? ' · paid only' : ''}</option>`,
    )
    .join('');
}
function ollamaOptions(c) {
  const installed = state.models?.providers?.local?.installed_models || [],
    known = new Map(installed.map((m) => [m.id, m]));
  for (const id of c.local_models || ['qwen3:8b', 'qwen3:14b'])
    if (!known.has(id)) known.set(id, { id, label: id + ' · not currently installed' });
  const enabled = c.local_models || ['qwen3:8b', 'qwen3:14b'];
  return `<label>Default local model<select name="local_model">${[...known.values()].map((m) => `<option value="${esc(m.id)}" ${m.id === (c.local_model || 'qwen3:8b') ? 'selected' : ''}>${esc(m.label)}</option>`).join('')}</select></label><details class="ollama-choices"><summary>Choose which installed chat models appear in the app</summary><p>Enable the models you want to choose per stock. Embedding-only and cloud-hosted models are excluded.</p>${[...known.values()].map((m) => `<label class="checkbox-label"><input type="checkbox" name="local_models" value="${esc(m.id)}" ${enabled.includes(m.id) ? 'checked' : ''}/>${esc(m.label)}</label>`).join('')}</details>`;
}
function connectionsPanel() {
  const c = state.data.connections || {},
    p = state.models?.providers || {};
  const labels = { local: 'Ollama', gemini: 'Gemini', openai: 'OpenAI', groq: 'Groq' };
  const descriptions = {
    local:
      'Local analysis on this Mac. Qwen3 8B is the default. Choose and enable other installed chat models below.',
    gemini:
      'Use a Google AI Studio API key with a free or paid API project. Free-tier quota and data-use terms differ from paid access.',
    openai:
      'Use an OpenAI Platform API key with available API billing or credits. A ChatGPT subscription is separate.',
    groq: 'Choose GPT-OSS 20B, GPT-OSS 120B or Qwen on Groq. The free plan has usage limits; a paid account can use the same connection.',
  };
  return `<section class="connections-card"><div class="section-heading"><div><h2>AI connections</h2><p>Choose a provider and model per stock. Keys are saved privately on this Mac and excluded from workspace exports.</p></div></div><form id="connections-form"><fieldset class="connections-fields" ${!state.models ? 'disabled' : ''}><label class="default-provider">Default analysis provider<select name="default_provider">${Object.entries(
    labels,
  )
    .map(
      ([id, name]) =>
        `<option value="${id}" ${id === (c.default_provider || 'local') ? 'selected' : ''}>${name}</option>`,
    )
    .join('')}</select></label><div class="connection-grid ai-connection-grid">${Object.entries(
    labels,
  )
    .map(
      ([id, name]) =>
        `<section class="provider-card" data-provider="${id}"><div class="provider-card-heading"><h3>${name}</h3><span class="pill">${id === 'local' ? (p.local?.configured ? 'LOCAL AVAILABLE' : state.models ? 'START OLLAMA' : 'CHECKING…') : c[id + '_api_key_configured'] ? 'KEY SAVED' : 'ADD API KEY'}</span></div><p>${descriptions[id]}</p>${id === 'local' ? `<div id="ollama-model-options">${ollamaOptions(c)}</div><p class="microcopy">${esc(p.local?.reason || 'Checking the local Ollama service…')} No model is downloaded automatically.</p><button type="button" class="text-button" data-action="refresh-ai-models">Refresh installed models ${icon('refresh')}</button>` : `<label>${name} API key<input name="${id}_api_key" type="password" autocomplete="new-password" placeholder="${c[id + '_api_key_configured'] ? 'Saved · leave blank to keep' : 'Paste your ' + name + ' API key'}"/></label>${id !== 'openai' ? `<label>Account plan<select name="${id}_tier"><option value="free" ${c[id + '_tier'] !== 'paid' ? 'selected' : ''}>Free tier</option><option value="paid" ${c[id + '_tier'] === 'paid' ? 'selected' : ''}>Paid tier</option></select></label>` : ''}<label>Default model<select name="${id}_model">${cloudModelOptions(id, c[id + '_tier'] || 'free', c[id + '_model'])}</select></label><details><summary>Key settings</summary><label class="checkbox-label"><input type="checkbox" name="clear_${id}_api_key"/>Remove saved ${name} key</label>${c[id + '_api_key_from_environment'] ? '<p>An environment key is active. Remove it from the app’s launch environment to disconnect it.</p>' : ''}</details>`}<div class="provider-actions"><button type="button" class="button secondary" data-action="check-ai-connection" data-provider="${id}" ${id !== 'local' && !c[id + '_api_key_configured'] ? 'disabled' : ''}>Check saved connection</button>${p[id]?.links ? `<a href="${esc(p[id].links.key)}" target="_blank" rel="noopener noreferrer">${id === 'local' ? 'Get Ollama' : 'Get API key'} ↗</a>` : ''}</div><p class="connection-status" data-connection-status="${id}" aria-live="polite"></p>${p[id]?.links && id !== 'local' ? `<div class="connection-links"><a href="${esc(p[id].links.pricing)}" target="_blank" rel="noopener noreferrer">Pricing / limits ↗</a><a href="${esc(p[id].links.usage)}" target="_blank" rel="noopener noreferrer">Usage / account ↗</a></div>` : ''}</section>`,
    )
    .join(
      '',
    )}</div><p class="signal-note">Save changes before checking a connection. Checks only read model information; they do not generate analysis. Free / paid is your account preference: the provider determines actual charges and quotas. Use an unbilled/free provider account for free-only use. No automatic model or provider fallback.</p><div class="form-footer"><span>Blank key fields keep existing keys. Analysis runs only when you request it.</span><button class="button primary" type="submit">Save connections</button></div></fieldset></form><details class="price-connection"><summary>Stock prices · Yahoo Finance · no sign-in needed</summary><p>NSE and US stock prices and daily history use Yahoo Finance. Crypto uses Binance and CoinGecko. Quotes and completed signal candles keep separate timestamps.</p></details></section>`;
}
let catalogTimer = null,
  catalogRequest = 0;
async function findCatalog(query) {
  const id = ++catalogRequest,
    target = $('#catalog-results');
  if (!target) return;
  if (query.trim().length < 2) {
    target.innerHTML = '';
    return;
  }
  target.innerHTML = '<p class="microcopy">Searching NSE companies…</p>';
  try {
    const data = await api('catalog?q=' + encodeURIComponent(query));
    if (id !== catalogRequest || !$('#catalog-results')) return;
    state.catalog = data.results || [];
    $('#catalog-results').innerHTML =
      state.catalog
        .map(
          (a, index) =>
            `<button type="button" class="catalog-result" data-action="catalog-pick" data-value="${index}"><strong>${esc(a.symbol)}</strong><span>${esc(a.name)}</span><small>${a.tracked ? 'Open tracked stock' : 'Select'}</small></button>`,
        )
        .join('') ||
      `<p class="microcopy">${esc(data.error || 'No match. Enter the exact symbol below.')}</p>`;
  } catch (e) {
    if ($('#catalog-results')) $('#catalog-results').textContent = e.message;
  }
}

function mentionBars(points, valueKey = 'count') {
  const values = points.map((p) => p[valueKey]).filter((v) => v != null),
    maximum = Math.max(1, ...values);
  return `<div class="attention-bars" role="img" aria-label="Sample activity over time">${points.map((p) => `<span title="${esc(p.date)}: ${p[valueKey] == null ? 'below 1 or unavailable' : fmt(p[valueKey], 0)}" style="--bar:${p[valueKey] == null ? 0 : Math.max(3, (p[valueKey] / maximum) * 100)}%" class="${p[valueKey] == null ? 'unknown' : ''}"><i></i></span>`).join('')}</div>`;
}
function attentionPanel(a, r) {
  const news = r.news,
    community = r.social_sentiment,
    trends = r.search_interest,
    na = news?.activity,
    ca = community?.activity,
    tc = trends?.comparison;
  const metric = (name, source, data, available, error) =>
    `<article class="attention-card"><span class="eyebrow">${name}</span><h3>${available ? esc(data?.label || 'No recent matches') : 'Unavailable'}</h3>${available ? `<strong>${data?.recent ?? 0} <small>vs ${data?.previous ?? 0}</small></strong><p>Matched ${source}: last 7 days vs preceding 7.</p>${mentionBars(data?.daily || [])}<small>${data?.capped ? 'Feed limit reached; older mentions may be missing.' : 'Limited RSS sample; not a count of people.'}</small>` : `<p>${esc(error || 'No usable sample returned. A missing feed is not zero activity.')}</p>`}</article>`;
  const postTone = ca?.tone || {},
    newsTone = na?.tone || {};
  const wording = (counts) =>
    `${counts.positive || 0} positive · ${counts.negative || 0} negative · ${counts.mixed || 0} mixed · ${counts.unclear || 0} unclear`;
  return `<section class="attention-section"><div class="section-heading"><div><div class="eyebrow">FREE PUBLIC SOURCES</div><h2>News, discussion & search interest</h2><p>Is this stock getting more attention? Check the sampled activity, then read what is driving it.</p></div></div><div class="attention-grid">${metric('NEWS ATTENTION', 'headlines', na, news?.available, news?.error)}${metric('PUBLIC DISCUSSION', 'Reddit posts', ca, community?.available, community?.reason)}<article class="attention-card"><span class="eyebrow">GOOGLE SEARCH INTEREST</span><h3>${esc(tc?.label || 'Open Google Trends')}</h3>${trends?.available ? `<strong>${fmt(tc?.recent, 1)} <small>vs ${fmt(tc?.previous, 1)}</small></strong><p>${esc(tc?.window)} · relative interest, 0–100.</p>${mentionBars((trends.points || []).slice(-30), 'value')}<small>Imported ${when(trends.fetched_at, true)} · through ${esc(trends.as_of)}${tc?.stale ? ' · STALE' : ''}</small><p class="microcopy">${esc(trends.query)}. ${tc?.complete ? '' : 'Missing or below-1 values prevent a full comparison.'}</p>` : '<p>Google’s free Trends website shows relative interest. It does not provide an exact search count for this stock.</p>'}<a class="text-button" href="${esc(trends?.explore_url || 'https://trends.google.com/trends/')}" target="_blank" rel="noopener noreferrer">View search interest ${icon('external')}</a><details class="trends-import"><summary>Import a free Google Trends CSV</summary><p>Open the stock’s Trends link, choose one search term, then download the “Interest over time” CSV. Import daily or weekly points here.</p><form id="trends-form"><label>Google Trends CSV<input name="file" type="file" accept=".csv,text/csv" required/></label><button class="button secondary" type="submit">Import search interest</button></form></details></article></div>${news?.error || community?.error ? `<p class="sync-banner warning">${esc(news?.error || community?.error)} Cached samples, when present, keep their original retrieval time.</p>` : ''}<details class="attention-extra"><summary>Wording, public posts and source limits</summary><div class="attention-reading"><div><strong>News wording · latest 7 days</strong><p>${news?.available ? wording(newsTone) : 'Unavailable'}</p><small>Simple English phrase checks on headlines; not investor sentiment.</small></div><div><strong>Public post wording · latest 7 days</strong><p>${community?.available ? wording(postTone) : 'Unavailable'}</p><small>${(postTone.positive || 0) + (postTone.negative || 0) + (postTone.mixed || 0) < 5 ? 'Too few directional titles to judge the sample.' : 'A small sample of title wording, not investor consensus.'} Questions stay unclear.</small></div></div><p class="signal-note">More discussion can accompany good news, bad news or speculation. Review it alongside traded volume, price structure and your supply/demand levels. These attention measures do not change the eight technical signals or estimate a trading edge.</p><div class="discussion-sources"><div><h3>Recent public discussion</h3>${
    community?.available
      ? (community.posts || [])
          .slice(0, 3)
          .map(
            (p) =>
              `<a class="discussion-item" href="${esc(p.url)}" target="_blank" rel="noopener noreferrer"><strong>${esc(p.title)} ${icon('external')}</strong><small>${esc(p.source)} · ${when(p.published_at)} · ${esc(p.tone?.label || 'Unclear wording')}</small></a>`,
          )
          .join('') ||
        '<p class="muted">No matching recent posts were returned. This does not establish that nobody is discussing the company.</p>'
      : `<p class="muted">${esc(community?.reason || 'Discussion source unavailable.')}</p>`
  }${community?.source_url ? `<a class="text-button" href="${esc(community.source_url)}" target="_blank" rel="noopener noreferrer">Open the public discussion search ${icon('external')}</a>` : ''}<p class="source-note">Reddit public RSS · ${community?.fetched_at ? 'Retrieved ' + when(community.fetched_at, true) : 'No usable retrieval'}. Only matching posts in selected investing communities; comments, votes and unique users are excluded.</p></div><aside><h3>Google trending now</h3>${trends?.trending_now?.available ? (trends.trending_now.matches?.length ? trends.trending_now.matches.map((t) => `<p><strong>${esc(t.title)}</strong> · ${esc(t.traffic)} approximate topic traffic</p>`).join('') : `<p>No matching stock topic in the current ${trends.trending_now.topic_count}-topic feed. This says nothing about its total search interest.</p>`) : '<p>The trending-topic feed is unavailable.</p>'}<p class="source-note">${esc(trends?.trending_now?.note || '')} A topic traffic label is separate from the 0–100 history. ${trends?.trending_now?.fetched_at ? 'Retrieved ' + when(trends.trending_now.fetched_at, true) : ''}</p></aside></div></details></section>`;
}

function candidateCard(c, rank, compact = false) {
  const a = state.data.assets.find((x) => x.symbol === c.symbol);
  if (!a) return '';
  const pattern = c.retest,
    signals = c.matched;
  return `<article class="candidate-card"><div class="candidate-card-top"><span class="candidate-rank" title="Rank in this view">#${rank}</span><a href="#asset/${encodeURIComponent(a.symbol)}" class="asset-cell">${avatar(a)}<span><strong>${esc(a.symbol)}</strong><small>${esc(a.name)}</small></span></a><div>${biasBadge(a.daily_swing, 'D')}${biasBadge(a.weekly_swing, 'W')}</div></div><a class="candidate-chart" href="#asset/${encodeURIComponent(a.symbol)}" aria-label="Open ${esc(a.symbol)} chart">${spark(a.sparkline || a.summary?.sparkline || [], (a.summary?.change || 0) >= 0 ? '#4fc795' : '#e78284')}<span>${a.quote?.price != null ? currency(a) + num(a.quote.price) : currency(a) + num(a.summary?.price)}<small>Recent daily closes</small></span></a><div class="candidate-score"><strong>${fmt(c.overall_score, 1)}<small> / 100</small></strong><span>Setup score</span></div><p class="candidate-setup">${esc(c.setup || c.label)}</p><div class="candidate-reasons">${signals
    .slice(0, compact ? 2 : 3)
    .map((x) => `<span>${icon('check')} ${signalEvidence(x)}</span>`)
    .join(
      '',
    )}</div><p class="candidate-caution">${c.counterpoints?.length ? esc(c.counterpoints[0].title) + ': ' + esc(c.counterpoints[0].reading) : esc(c.warnings?.[0] || 'Check the chart, available volume and the next supply level.')}</p>${
    compact
      ? ''
      : `<details><summary>Score breakdown & signal details</summary><p class="score-breakdown">${Object.entries(
          c.score_breakdown || {},
        )
          .map(
            ([key, value]) =>
              esc(
                {
                  demand: 'Demand',
                  trend_with_demand: 'Trend + demand',
                  move_with_demand: '>1% move + demand',
                  rule_balance: 'Rule balance',
                  daily_weekly_alignment: 'Daily/weekly alignment',
                }[key] || key,
              ) +
              ': ' +
              fmt(value, 1),
          )
          .join(
            ' · ',
          )}</p>${signals.map((x) => `<p><strong>${esc(x.title)}</strong> ${esc(x.reading)}</p>`).join('')}${(c.warnings || []).map((w) => `<p class="negative">${esc(w)}</p>`).join('')}${c.counterpoints.map((x) => `<p class="negative"><strong>${esc(x.title)}</strong> ${esc(x.reading)}</p>`).join('')}${pattern?.first_low ? `<p>First low ${dateOnly(pattern.first_low.time)} · retest ${dateOnly(pattern.second_low.time)} · floor ${num(pattern.support_low)}–${num(pattern.support_high)} · intervening high ${num(pattern.neckline)}.</p>` : ''}<p>Signals through ${dateOnly(a.summary?.candle_date)}. ${a.week_partial ? 'Weekly reading is provisional.' : ''}</p></details>`
  }<a class="text-button" href="#asset/${encodeURIComponent(a.symbol)}">Inspect chart ${icon('arrow')}</a></article>`;
}
function candidatePreview() {
  const items = (state.data.long_candidates?.['1d']?.items || [])
    .filter((c) => state.data.assets.find((a) => a.symbol === c.symbol)?.market === 'NSE')
    .slice(0, 3);
  return `<section class="candidate-preview"><div class="section-heading"><div><h2>Long candidates</h2><p>Demand first. A rising 3 / 7 / 14 period or a >1% move strengthens the setup.</p></div><a class="text-button" href="#candidates">View candidates ${icon('arrow')}</a></div>${items.length ? `<div class="candidate-grid">${items.map((c, i) => candidateCard(c, i + 1, true)).join('')}</div>` : '<div class="empty-state"><h3>No current NSE candidates</h3><p>Fresh, usable history and at least one positive condition are required. Check data health if Yahoo has missing candles.</p></div>'}</section>`;
}
function renderCandidates() {
  const scan = state.data.long_candidates?.[state.candidateTimeframe] || { items: [], excluded: 0 };
  let items = scan.items.filter(
    (c) =>
      state.candidateMarket === 'all' ||
      state.data.assets.find((a) => a.symbol === c.symbol)?.market === state.candidateMarket,
  );
  if (state.candidateCriterion !== 'any')
    items = items.filter((c) => c.matched.some((x) => x.key === state.candidateCriterion));
  $('#main').innerHTML =
    `<div class="page-heading"><div><div class="eyebrow">A SHORTLIST TO INVESTIGATE</div><h1>Long candidates</h1><p>Ranked by your overall setup score, highest first. Demand combinations carry the most weight.</p></div></div>${refreshBanner()}<div class="candidate-controls"><label>Market<select id="candidate-market">${[
      ['NSE', 'NSE'],
      ['US', 'US'],
      ['CRYPTO', 'Crypto'],
      ['all', 'All markets'],
    ]
      .map(
        ([v, l]) =>
          `<option value="${v}" ${state.candidateMarket === v ? 'selected' : ''}>${l}</option>`,
      )
      .join(
        '',
      )}</select></label><label>Timeframe<select id="candidate-timeframe"><option value="1d" ${state.candidateTimeframe === '1d' ? 'selected' : ''}>Daily</option><option value="1w" ${state.candidateTimeframe === '1w' ? 'selected' : ''}>Weekly</option></select></label><label>Condition<select id="candidate-criterion">${[
      ['any', 'Any positive condition'],
      ['retest', 'Confirmed support retest'],
      ['rsi', 'RSI recovery: below 35 → above 40'],
      ['stoch', 'Stoch RSI low or falling'],
      ['volume', 'Upward volume confirmation'],
      ['ma', 'Below 200-day SMA'],
      ['zones', 'Near demand'],
      ['highs', 'Rising over 3 / 7 / 14 periods'],
      ['move', 'Move above +1%'],
    ]
      .map(
        ([v, l]) =>
          `<option value="${v}" ${state.candidateCriterion === v ? 'selected' : ''}>${l}</option>`,
      )
      .join(
        '',
      )}</select></label></div><p class="signal-note">${items.length} names match · ${scan.excluded} assets across all markets excluded for missing, stale or incomplete evidence. <a href="#settings">Data health</a>. Setup score is a custom screening score, not a chance of profit.</p><details class="score-method"><summary>How scoring works</summary><p>${esc(scan.rule || '')}</p></details>${items.length ? `<div class="candidate-grid">${items.map((c, i) => candidateCard(c, i + 1)).join('')}</div>` : '<div class="empty-state"><h3>No matching candidates right now</h3><p>Try another condition or check data health. A forming retest is not shown as confirmed.</p></div>'}`;
}

function extraHeadlines(n) {
  if (!n?.articles || n.articles.length <= 5) return '';
  return `<details class="more-detail"><summary>More matched headlines (${n.articles.length - 5})</summary>${n.articles
    .slice(5)
    .map(
      (article) =>
        `<a class="news-item" href="${esc(article.url)}" target="_blank" rel="noopener noreferrer"><div><span>${esc(article.source)}</span><time>${when(article.published_at)}</time></div><h4>${esc(article.title)} ${icon('external')}</h4><small>${esc(article.tone?.label || 'Unclear wording')}</small></a>`,
    )
    .join('')}</details>`;
}
