let activeChart = null;
let activeObserver = null;
export function disposeChart() {
  activeObserver?.disconnect();
  activeObserver = null;
  if (activeChart) {
    activeChart.remove();
    activeChart = null;
  }
}
export function createAssetChart(
  element,
  asset,
  { timeframe = '1d', range = 180, candidates = true, onZone } = {},
) {
  disposeChart();
  const L = window.LightweightCharts;
  if (!L || !asset.bars?.length) return;
  const bars = asset.bars;
  const chart = L.createChart(element, {
    width: element.clientWidth,
    height: 650,
    layout: {
      background: { type: L.ColorType.Solid, color: '#0b0b0b' },
      textColor: '#b0b8c5',
      fontFamily: '-apple-system, BlinkMacSystemFont, sans-serif',
      fontSize: 12,
      panes: { separatorColor: '#303540', separatorHoverColor: '#566171', enableResize: true },
    },
    grid: { vertLines: { color: '#202020' }, horzLines: { color: '#202020' } },
    rightPriceScale: { borderColor: '#303540', minimumWidth: 76 },
    timeScale: { borderColor: '#303540', timeVisible: false, rightOffset: 5 },
    crosshair: {
      mode: L.CrosshairMode.Normal,
      vertLine: { color: '#8894a7' },
      horzLine: { color: '#8894a7' },
    },
    localization: {
      priceFormatter: (v) => v.toLocaleString('en-IN', { maximumFractionDigits: v < 1 ? 5 : 2 }),
    },
    handleScroll: {
      mouseWheel: true,
      pressedMouseMove: true,
      horzTouchDrag: true,
      vertTouchDrag: false,
    },
  });
  activeChart = chart;
  const candles = chart.addSeries(L.CandlestickSeries, {
    upColor: '#4fc795',
    downColor: '#e78284',
    borderVisible: false,
    wickUpColor: '#4fc795',
    wickDownColor: '#e78284',
    priceLineColor: '#4fc795',
  });
  candles.setData(
    bars.map(({ time, open, high, low, close }) => ({ time, open, high, low, close })),
  );
  for (const [period, color] of [
    [20, '#83bad3'],
    [50, '#d8bc7a'],
    [200, '#9b99d5'],
  ]) {
    const ma = chart.addSeries(L.LineSeries, {
      color,
      lineWidth: 1,
      lastValueVisible: false,
      priceLineVisible: false,
      crosshairMarkerVisible: false,
    });
    ma.setData(
      bars
        .filter((b) => b['sma' + period] != null)
        .map((b) => ({ time: b.time, value: b['sma' + period] })),
    );
  }
  const zones = [
    ...asset.zones,
    ...(candidates
      ? [
          ...asset.candidates.filter((z) => z.kind === 'demand').slice(0, 2),
          ...asset.candidates.filter((z) => z.kind === 'supply').slice(0, 2),
        ]
      : []),
  ];
  for (const z of zones) {
    const demand = z.kind === 'demand',
      color = z.broken ? '#867a6b' : demand ? '#4fc795' : '#e78284';
    const zone = chart.addSeries(L.BaselineSeries, {
      baseValue: { type: 'price', price: z.low },
      topFillColor1: demand ? 'rgba(79,199,149,.08)' : 'rgba(231,130,132,.08)',
      topFillColor2: demand ? 'rgba(79,199,149,.08)' : 'rgba(231,130,132,.08)',
      topLineColor: 'transparent',
      bottomLineColor: 'transparent',
      bottomFillColor1: 'transparent',
      bottomFillColor2: 'transparent',
      lastValueVisible: false,
      priceLineVisible: false,
      crosshairMarkerVisible: false,
      autoscaleInfoProvider: () => null,
    });
    zone.setData([
      {
        time: (bars.find((b) => b.time >= (z.origin || bars[0].time)) || bars[0]).time,
        value: z.high,
      },
      { time: bars.at(-1).time, value: z.high },
    ]);
    for (const [p, title] of [
      [z.high, `${z.source === 'manual' ? 'My' : 'Auto'} ${z.kind}`],
      [z.low, ''],
    ])
      candles.createPriceLine({
        price: p,
        color,
        lineWidth: 1,
        lineStyle: z.source === 'manual' ? L.LineStyle.Solid : L.LineStyle.Dashed,
        axisLabelVisible: false,
        title,
      });
  }
  const retest = asset.swing?.retest;
  if (retest?.first_low) {
    const markers = [
      {
        time: retest.first_low.time,
        position: 'belowBar',
        color: '#b8ccef',
        shape: 'circle',
        text: 'First low',
      },
      {
        time: retest.second_low.time,
        position: 'belowBar',
        color: '#b8ccef',
        shape: 'circle',
        text: 'Retest',
      },
    ];
    if (retest.confirmed_at)
      markers.push({
        time: retest.confirmed_at,
        position: 'aboveBar',
        color: '#4fc795',
        shape: 'arrowUp',
        text: 'Breakout',
      });
    markers.sort((a, b) => a.time.localeCompare(b.time));
    if (L.createSeriesMarkers) L.createSeriesMarkers(candles, markers);
    for (const [price, title] of [
      [retest.support_low, 'Retest floor'],
      [retest.neckline, 'Intervening high'],
    ])
      candles.createPriceLine({
        price,
        color: '#9bb3d5',
        lineWidth: 1,
        lineStyle: L.LineStyle.Dotted,
        axisLabelVisible: false,
        title,
      });
  }
  const vol = chart.addSeries(
    L.HistogramSeries,
    { priceFormat: { type: 'volume' }, priceLineVisible: false, lastValueVisible: false },
    1,
  );
  vol.setData(
    bars.map((b) => ({
      time: b.time,
      value: b.volume,
      color: b.close >= b.open ? '#428b70' : '#b4666a',
    })),
  );
  const rs = chart.addSeries(
    L.LineSeries,
    { color: '#c1a8e2', lineWidth: 1.5, priceLineVisible: false, lastValueVisible: false },
    2,
  );
  rs.setData(bars.filter((b) => b.rsi != null).map((b) => ({ time: b.time, value: b.rsi })));
  const rsiMean = chart.addSeries(
    L.LineSeries,
    { color: '#ddc96a', lineWidth: 1.5, priceLineVisible: false, lastValueVisible: false },
    2,
  );
  rsiMean.setData(
    bars.filter((b) => b.rsi_average != null).map((b) => ({ time: b.time, value: b.rsi_average })),
  );
  for (const level of [30, 50, 70])
    rs.createPriceLine({
      price: level,
      color: '#4d435d',
      lineStyle: 2,
      lineWidth: 1,
      axisLabelVisible: true,
    });
  const k = chart.addSeries(
    L.LineSeries,
    { color: '#83b8d1', lineWidth: 1.5, priceLineVisible: false, lastValueVisible: false },
    3,
  );
  const d = chart.addSeries(
    L.LineSeries,
    { color: '#cba67c', lineWidth: 1.5, priceLineVisible: false, lastValueVisible: false },
    3,
  );
  k.setData(bars.filter((b) => b.k != null).map((b) => ({ time: b.time, value: b.k })));
  d.setData(bars.filter((b) => b.d != null).map((b) => ({ time: b.time, value: b.d })));
  for (const level of [20, 80])
    k.createPriceLine({
      price: level,
      color: '#384c55',
      lineStyle: 2,
      lineWidth: 1,
      axisLabelVisible: true,
    });
  chart.panes().forEach((p, i) => p.setStretchFactor([3.6, 0.8, 1.2, 1.2][i]));
  const count =
    timeframe === '1w'
      ? Math.ceil(range / 7)
      : Math.ceil(range * (asset.market === 'CRYPTO' ? 1 : 5 / 7));
  chart
    .timeScale()
    .setVisibleLogicalRange({ from: Math.max(0, bars.length - count), to: bars.length + 4 });
  activeObserver = new ResizeObserver(() => chart.applyOptions({ width: element.clientWidth }));
  activeObserver.observe(element);
  let first = null;
  chart.subscribeClick((param) => {
    if (!element.dataset.drawing || !param.point || param.paneIndex !== 0) return;
    const price = candles.coordinateToPrice(param.point.y);
    if (price == null) return;
    if (first == null) {
      first = price;
      element.dispatchEvent(new CustomEvent('zonepoint', { detail: price }));
    } else {
      const low = Math.min(first, price),
        high = Math.max(first, price);
      first = null;
      element.dataset.drawing = '';
      if (high > low) onZone?.({ low, high });
    }
  });
  const readout = document.querySelector('#ohlc-readout');
  chart.subscribeCrosshairMove((p) => {
    const b = p.seriesData.get(candles);
    if (readout && b?.close != null) {
      const f = (n) => n.toLocaleString('en-IN', { maximumFractionDigits: n < 1 ? 5 : 2 });
      readout.textContent = `${p.time}   O ${f(b.open)}  H ${f(b.high)}  L ${f(b.low)}  C ${f(b.close)}`;
    }
  });
  return chart;
}
