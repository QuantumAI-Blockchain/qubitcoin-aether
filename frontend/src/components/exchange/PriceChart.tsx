"use client";
// ─── QBC EXCHANGE — TradingView Lightweight Charts v5 Candlestick Chart ──────
// Full implementation: candlestick + volume + moving averages, auto-resize,
// timeframe selector, indicator toggles, current price line.

import React, { useRef, useEffect, useCallback } from "react";
import {
  createChart,
  CandlestickSeries,
  HistogramSeries,
  LineSeries,
  LineStyle,
  type IChartApi,
  type ISeriesApi,
  type IPriceLine,
  type UTCTimestamp,
} from "lightweight-charts";
import type { OHLCBar, MarketId, Timeframe } from "./types";
import { useOHLC } from "./hooks";
import { useExchangeStore } from "./store";
import { X, FONT } from "./shared";

// ─── CONSTANTS ───────────────────────────────────────────────────────────────

const TIMEFRAMES: Timeframe[] = ["1m", "5m", "15m", "1h", "4h", "1D", "1W"];

interface IndicatorDef {
  key: string;
  label: string;
}

const INDICATORS: IndicatorDef[] = [
  { key: "volume", label: "Volume" },
  { key: "ma20", label: "MA(20)" },
  { key: "ma50", label: "MA(50)" },
];

const MA20_COLOR = "#f5c842";
const MA50_COLOR = "#7c3aed";

// ─── MA CALCULATION ──────────────────────────────────────────────────────────

function computeMA(
  bars: OHLCBar[],
  period: number,
): { time: UTCTimestamp; value: number }[] {
  const result: { time: UTCTimestamp; value: number }[] = [];
  if (bars.length < period) return result;

  let sum = 0;
  for (let i = 0; i < period; i++) {
    sum += bars[i].close;
  }
  result.push({
    time: bars[period - 1].time as UTCTimestamp,
    value: sum / period,
  });

  for (let i = period; i < bars.length; i++) {
    sum += bars[i].close - bars[i - period].close;
    result.push({
      time: bars[i].time as UTCTimestamp,
      value: sum / period,
    });
  }
  return result;
}

// ─── TOOLBAR BUTTON STYLES ──────────────────────────────────────────────────

const toolbarBase: React.CSSProperties = {
  fontFamily: FONT.display,
  fontSize: 10,
  letterSpacing: "0.08em",
  border: "none",
  cursor: "pointer",
  padding: "4px 10px",
  borderRadius: 4,
  textTransform: "uppercase",
  transition: "background 0.15s, color 0.15s",
};

// ─── COMPONENT ───────────────────────────────────────────────────────────────

const PriceChart = React.memo(function PriceChart() {
  const activeMarket = useExchangeStore((s) => s.activeMarket);
  const timeframe = useExchangeStore((s) => s.timeframe);
  const setTimeframe = useExchangeStore((s) => s.setTimeframe);
  const indicators = useExchangeStore((s) => s.indicators);
  const toggleIndicator = useExchangeStore((s) => s.toggleIndicator);

  const containerRef = useRef<HTMLDivElement>(null);
  const chartRef = useRef<IChartApi | null>(null);
  const candleSeriesRef = useRef<ISeriesApi<"Candlestick"> | null>(null);
  const volumeSeriesRef = useRef<ISeriesApi<"Histogram"> | null>(null);
  const ma20SeriesRef = useRef<ISeriesApi<"Line"> | null>(null);
  const ma50SeriesRef = useRef<ISeriesApi<"Line"> | null>(null);
  const priceLineRef = useRef<IPriceLine | null>(null);

  const { data: ohlcData } = useOHLC(activeMarket, timeframe);

  // ── Memoized indicator flags ────────────────────────────────────────────
  const showVolume = indicators.includes("volume");
  const showMA20 = indicators.includes("ma20");
  const showMA50 = indicators.includes("ma50");

  // ── Create chart on mount ───────────────────────────────────────────────
  useEffect(() => {
    const container = containerRef.current;
    if (!container) return;

    const chart = createChart(container, {
      layout: {
        background: { color: X.bgBase },
        textColor: X.textSecondary,
        fontFamily: FONT.mono,
        fontSize: 11,
      },
      grid: {
        vertLines: { color: "#0d1a2a" },
        horzLines: { color: "#0d1a2a" },
      },
      crosshair: {
        vertLine: {
          color: X.glowCyan + "40",
          labelBackgroundColor: X.bgElevated,
        },
        horzLine: {
          color: X.glowCyan + "40",
          labelBackgroundColor: X.bgElevated,
        },
      },
      rightPriceScale: {
        borderColor: X.borderSubtle,
        scaleMargins: { top: 0.05, bottom: 0.2 },
      },
      timeScale: {
        borderColor: X.borderSubtle,
        timeVisible: true,
        secondsVisible: false,
      },
      handleScroll: { vertTouchDrag: false },
    });

    chartRef.current = chart;

    // Candlestick series
    const candleSeries = chart.addSeries(CandlestickSeries, {
      upColor: X.bid,
      downColor: X.ask,
      borderUpColor: X.bid,
      borderDownColor: X.ask,
      wickUpColor: X.bid,
      wickDownColor: X.ask,
    });
    candleSeriesRef.current = candleSeries;

    // Volume histogram series (in a separate price scale below)
    const volumeSeries = chart.addSeries(HistogramSeries, {
      priceFormat: { type: "volume" },
      priceScaleId: "volume",
    });
    volumeSeries.priceScale().applyOptions({
      scaleMargins: { top: 0.85, bottom: 0 },
    });
    volumeSeriesRef.current = volumeSeries;

    // ResizeObserver for auto-resize
    const ro = new ResizeObserver((entries) => {
      for (const entry of entries) {
        const { width, height } = entry.contentRect;
        if (width > 0 && height > 0) {
          chart.resize(width, height);
        }
      }
    });
    ro.observe(container);

    return () => {
      ro.disconnect();
      chart.remove();
      chartRef.current = null;
      candleSeriesRef.current = null;
      volumeSeriesRef.current = null;
      ma20SeriesRef.current = null;
      ma50SeriesRef.current = null;
      priceLineRef.current = null;
    };
  }, []);

  // ── Update candlestick + volume data ────────────────────────────────────
  useEffect(() => {
    const chart = chartRef.current;
    const candleSeries = candleSeriesRef.current;
    const volumeSeries = volumeSeriesRef.current;
    if (!chart || !candleSeries || !volumeSeries || !ohlcData || ohlcData.length === 0) return;

    // Sort by time ascending (lightweight-charts requires sorted data)
    const sorted = [...ohlcData].sort((a, b) => a.time - b.time);

    // Candlestick data
    const candleData = sorted.map((bar) => ({
      time: bar.time as UTCTimestamp,
      open: bar.open,
      high: bar.high,
      low: bar.low,
      close: bar.close,
    }));
    candleSeries.setData(candleData);

    // Volume data with color per bar
    const volData = sorted.map((bar) => ({
      time: bar.time as UTCTimestamp,
      value: bar.volume,
      color: bar.close >= bar.open
        ? X.bid + "33"  // ~20% opacity green
        : X.ask + "33", // ~20% opacity red
    }));
    volumeSeries.setData(volData);

    // Current price line
    if (priceLineRef.current) {
      candleSeries.removePriceLine(priceLineRef.current);
      priceLineRef.current = null;
    }
    const lastBar = sorted[sorted.length - 1];
    if (lastBar) {
      priceLineRef.current = candleSeries.createPriceLine({
        price: lastBar.close,
        color: lastBar.close >= lastBar.open ? X.bid : X.ask,
        lineWidth: 1,
        lineStyle: LineStyle.Dashed,
        axisLabelVisible: true,
        title: "",
      });
    }

    // Fit content on data change
    chart.timeScale().fitContent();
  }, [ohlcData]);

  // ── Volume visibility ───────────────────────────────────────────────────
  useEffect(() => {
    const volumeSeries = volumeSeriesRef.current;
    if (!volumeSeries) return;
    volumeSeries.applyOptions({
      visible: showVolume,
    });
  }, [showVolume]);

  // ── MA(20) series ───────────────────────────────────────────────────────
  useEffect(() => {
    const chart = chartRef.current;
    if (!chart) return;

    if (showMA20) {
      if (!ma20SeriesRef.current) {
        const series = chart.addSeries(LineSeries, {
          color: MA20_COLOR,
          lineWidth: 1,
          priceLineVisible: false,
          lastValueVisible: false,
          crosshairMarkerVisible: false,
        });
        ma20SeriesRef.current = series;
      }
      if (ohlcData && ohlcData.length > 0) {
        const sorted = [...ohlcData].sort((a, b) => a.time - b.time);
        const maData = computeMA(sorted, 20);
        ma20SeriesRef.current.setData(maData);
      }
    } else {
      if (ma20SeriesRef.current) {
        chart.removeSeries(ma20SeriesRef.current);
        ma20SeriesRef.current = null;
      }
    }
  }, [showMA20, ohlcData]);

  // ── MA(50) series ───────────────────────────────────────────────────────
  useEffect(() => {
    const chart = chartRef.current;
    if (!chart) return;

    if (showMA50) {
      if (!ma50SeriesRef.current) {
        const series = chart.addSeries(LineSeries, {
          color: MA50_COLOR,
          lineWidth: 1,
          priceLineVisible: false,
          lastValueVisible: false,
          crosshairMarkerVisible: false,
        });
        ma50SeriesRef.current = series;
      }
      if (ohlcData && ohlcData.length > 0) {
        const sorted = [...ohlcData].sort((a, b) => a.time - b.time);
        const maData = computeMA(sorted, 50);
        ma50SeriesRef.current.setData(maData);
      }
    } else {
      if (ma50SeriesRef.current) {
        chart.removeSeries(ma50SeriesRef.current);
        ma50SeriesRef.current = null;
      }
    }
  }, [showMA50, ohlcData]);

  // ── Timeframe click handler ─────────────────────────────────────────────
  const handleTimeframeClick = useCallback(
    (tf: Timeframe) => {
      setTimeframe(tf);
    },
    [setTimeframe],
  );

  // ── Indicator toggle handler ────────────────────────────────────────────
  const handleIndicatorToggle = useCallback(
    (key: string) => {
      toggleIndicator(key);
    },
    [toggleIndicator],
  );

  return (
    <div style={{ display: "flex", flexDirection: "column", width: "100%", height: "100%" }}>
      {/* ── Toolbar: Timeframes + Indicators ────────────────────────────── */}
      <div
        style={{
          display: "flex",
          alignItems: "center",
          justifyContent: "space-between",
          padding: "6px 10px",
          borderBottom: `1px solid ${X.borderSubtle}`,
          flexShrink: 0,
          fontFamily: FONT.display,
          fontSize: 10,
          letterSpacing: "0.08em",
        }}
      >
        {/* Timeframe buttons */}
        <div style={{ display: "flex", gap: 2 }}>
          {TIMEFRAMES.map((tf) => {
            const isActive = tf === timeframe;
            return (
              <button
                key={tf}
                onClick={() => handleTimeframeClick(tf)}
                style={{
                  ...toolbarBase,
                  background: isActive ? X.glowCyan + "20" : "transparent",
                  color: isActive ? X.glowCyan : X.textSecondary,
                  border: isActive ? `1px solid ${X.glowCyan}40` : "1px solid transparent",
                }}
              >
                {tf}
              </button>
            );
          })}
        </div>

        {/* Indicator toggles */}
        <div style={{ display: "flex", gap: 2 }}>
          {INDICATORS.map((ind) => {
            const isActive = indicators.includes(ind.key);
            const dotColor =
              ind.key === "ma20"
                ? MA20_COLOR
                : ind.key === "ma50"
                  ? MA50_COLOR
                  : X.glowCyan;
            return (
              <button
                key={ind.key}
                onClick={() => handleIndicatorToggle(ind.key)}
                style={{
                  ...toolbarBase,
                  background: isActive ? dotColor + "18" : "transparent",
                  color: isActive ? dotColor : X.textSecondary,
                  border: isActive ? `1px solid ${dotColor}40` : "1px solid transparent",
                  display: "flex",
                  alignItems: "center",
                  gap: 4,
                }}
              >
                <span
                  style={{
                    width: 6,
                    height: 6,
                    borderRadius: "50%",
                    background: isActive ? dotColor : X.textSecondary + "40",
                    display: "inline-block",
                    flexShrink: 0,
                  }}
                />
                {ind.label}
              </button>
            );
          })}
        </div>
      </div>

      {/* ── Chart container ─────────────────────────────────────────────── */}
      <div
        ref={containerRef}
        style={{
          width: "100%",
          height: "100%",
          minHeight: 350,
          flexGrow: 1,
        }}
      />
    </div>
  );
});

export default PriceChart;
