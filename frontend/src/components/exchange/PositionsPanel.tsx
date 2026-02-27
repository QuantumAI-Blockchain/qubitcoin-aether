// ─── QBC EXCHANGE — Positions / Orders / History / Funding Panel ──────────────
"use client";

import React, { memo, useState, useMemo, useCallback } from "react";
import { usePositions, useOpenOrders, useMyFills, useFunding, useCancelOrder } from "./hooks";
import { useExchangeStore } from "./store";
import {
  X,
  FONT,
  formatPrice,
  formatSize,
  formatUsd,
  formatPct,
  formatFundingRate,
  timeAgo,
  formatUtcTime,
  truncHash,
  SideBadge,
  StatusBadge,
  PnlDisplay,
  panelStyle,
  TabBar,
  CopyButton,
} from "./shared";
import { displayName, FEES } from "./config";
import type { Position, Order, FundingPayment, MarketId } from "./types";

// ─── STYLE CONSTANTS ────────────────────────────────────────────────────────

const thStyle: React.CSSProperties = {
  fontFamily: FONT.display,
  fontSize: 9,
  letterSpacing: "0.1em",
  color: X.textSecondary,
  textTransform: "uppercase",
  padding: "6px 8px",
  textAlign: "left",
  whiteSpace: "nowrap",
  borderBottom: `1px solid ${X.borderSubtle}`,
  position: "sticky",
  top: 0,
  background: X.bgPanel,
  zIndex: 1,
};

const thRightStyle: React.CSSProperties = { ...thStyle, textAlign: "right" };

const tdStyle: React.CSSProperties = {
  padding: "5px 8px",
  fontFamily: FONT.mono,
  fontSize: 12,
  color: X.textPrimary,
  whiteSpace: "nowrap",
  borderBottom: `1px solid ${X.borderSubtle}10`,
};

const tdRightStyle: React.CSSProperties = { ...tdStyle, textAlign: "right" };

const tdSecondaryStyle: React.CSSProperties = { ...tdStyle, color: X.textSecondary };

const emptyStyle: React.CSSProperties = {
  padding: 40,
  textAlign: "center",
  fontFamily: FONT.body,
  fontSize: 13,
  color: X.textSecondary,
};

const microBtnBase: React.CSSProperties = {
  fontFamily: FONT.display,
  fontSize: 9,
  letterSpacing: "0.06em",
  padding: "3px 8px",
  borderRadius: 3,
  border: "none",
  cursor: "pointer",
  textTransform: "uppercase",
};

const roleBadgeStyle = (color: string): React.CSSProperties => ({
  fontFamily: FONT.display,
  fontSize: 9,
  letterSpacing: "0.08em",
  padding: "2px 6px",
  borderRadius: 3,
  background: color + "18",
  color,
  textTransform: "uppercase",
});

// ─── POSITIONS TAB ──────────────────────────────────────────────────────────

const PositionRow = memo(function PositionRow({
  pos,
  onClose,
}: {
  pos: Position;
  onClose: (marketId: MarketId) => void;
}) {
  const [expanded, setExpanded] = useState(false);

  const marginUsed = pos.marginRatio;
  const isWarning = marginUsed > 0.8;
  const isDanger = marginUsed > 0.9;

  const liqStyle: React.CSSProperties = {
    ...tdRightStyle,
    color: isDanger ? X.glowCrimson : isWarning ? X.glowAmber : X.textPrimary,
    ...(isDanger ? { animation: "pulseCrimson 1.5s ease-in-out infinite" } : {}),
  };

  const marginBarWidth = Math.min(marginUsed * 100, 100);
  const marginBarColor = isDanger
    ? X.glowCrimson
    : isWarning
      ? X.glowAmber
      : X.glowEmerald;

  return (
    <>
      <tr
        style={{ cursor: "pointer" }}
        onClick={() => setExpanded((p) => !p)}
      >
        <td style={tdStyle}>
          <span style={{ fontFamily: FONT.display, fontSize: 11, letterSpacing: "0.04em" }}>
            {displayName(pos.marketId)}
          </span>
        </td>
        <td style={tdStyle}>
          <SideBadge side={pos.side} />
        </td>
        <td style={tdRightStyle}>{formatSize(pos.size)}</td>
        <td style={tdRightStyle}>{formatPrice(pos.entryPrice)}</td>
        <td style={tdRightStyle}>{formatPrice(pos.markPrice)}</td>
        <td style={liqStyle}>{formatPrice(pos.liquidationPrice)}</td>
        <td style={tdRightStyle}>
          <div style={{ display: "flex", flexDirection: "column", alignItems: "flex-end", gap: 2 }}>
            <span>{formatUsd(pos.initialMargin)}</span>
            <div
              style={{
                width: 48,
                height: 3,
                borderRadius: 2,
                background: X.borderSubtle,
                overflow: "hidden",
              }}
            >
              <div
                style={{
                  width: `${marginBarWidth}%`,
                  height: "100%",
                  borderRadius: 2,
                  background: marginBarColor,
                  transition: "width 0.3s, background 0.3s",
                }}
              />
            </div>
          </div>
        </td>
        <td style={tdRightStyle}>
          <PnlDisplay pnl={pos.unrealisedPnl} />
        </td>
        <td style={tdRightStyle}>
          <PnlDisplay pnl={pos.unrealisedPnl} pct={pos.unrealisedPnlPct} showPct={false} />
          <span
            style={{
              fontFamily: FONT.mono,
              fontSize: 11,
              marginLeft: 4,
              color: pos.unrealisedPnlPct >= 0 ? X.glowEmerald : X.glowCrimson,
            }}
          >
            {formatPct(pos.unrealisedPnlPct)}
          </span>
        </td>
        <td style={{ ...tdStyle, textAlign: "right" }}>
          <div style={{ display: "flex", gap: 4, justifyContent: "flex-end" }} onClick={(e) => e.stopPropagation()}>
            <button
              style={{
                ...microBtnBase,
                background: X.glowEmerald + "18",
                color: X.glowEmerald,
              }}
              title="Set Take Profit"
            >
              TP
            </button>
            <button
              style={{
                ...microBtnBase,
                background: X.glowAmber + "18",
                color: X.glowAmber,
              }}
              title="Set Stop Loss"
            >
              SL
            </button>
            <button
              style={{
                ...microBtnBase,
                background: X.glowCrimson + "18",
                color: X.glowCrimson,
              }}
              onClick={() => onClose(pos.marketId)}
              title="Close Position"
            >
              Close
            </button>
          </div>
        </td>
      </tr>
      {expanded && (
        <tr>
          <td colSpan={10} style={{ padding: 0 }}>
            <div
              style={{
                background: X.bgElevated,
                padding: "10px 16px",
                display: "grid",
                gridTemplateColumns: "repeat(3, 1fr)",
                gap: "8px 24px",
                borderBottom: `1px solid ${X.borderSubtle}`,
                fontSize: 11,
                fontFamily: FONT.body,
              }}
            >
              <div>
                <span style={{ color: X.textSecondary }}>Opened: </span>
                <span style={{ color: X.textPrimary, fontFamily: FONT.mono }}>
                  {formatUtcTime(pos.openedAt)}
                </span>
              </div>
              <div>
                <span style={{ color: X.textSecondary }}>Block Height: </span>
                <span style={{ color: X.textPrimary, fontFamily: FONT.mono }}>
                  #{pos.openBlockHeight.toLocaleString()}
                </span>
              </div>
              <div>
                <span style={{ color: X.textSecondary }}>Leverage: </span>
                <span style={{ color: X.glowCyan, fontFamily: FONT.mono }}>
                  {pos.leverage}x
                </span>
              </div>
              <div>
                <span style={{ color: X.textSecondary }}>Funding Paid: </span>
                <span
                  style={{
                    color: pos.fundingPaid >= 0 ? X.glowCrimson : X.glowEmerald,
                    fontFamily: FONT.mono,
                  }}
                >
                  {pos.fundingPaid >= 0 ? "-" : "+"}
                  {formatUsd(Math.abs(pos.fundingPaid))}
                </span>
              </div>
              <div>
                <span style={{ color: X.textSecondary }}>Notional: </span>
                <span style={{ color: X.textPrimary, fontFamily: FONT.mono }}>
                  {formatUsd(pos.notionalValue)}
                </span>
              </div>
              <div>
                <span style={{ color: X.textSecondary }}>Maint. Margin: </span>
                <span style={{ color: X.textPrimary, fontFamily: FONT.mono }}>
                  {formatUsd(pos.maintenanceMargin)}
                </span>
              </div>
              <div style={{ gridColumn: "1 / -1", display: "flex", alignItems: "center", gap: 8 }}>
                <span style={{ color: X.textSecondary }}>Tx: </span>
                <span style={{ color: X.glowCyan, fontFamily: FONT.mono, fontSize: 10 }}>
                  {truncHash(pos.openTxHash, 10)}
                </span>
                <CopyButton text={pos.openTxHash} />
              </div>
              {pos.takeProfitPrice !== null && (
                <div>
                  <span style={{ color: X.textSecondary }}>TP: </span>
                  <span style={{ color: X.glowEmerald, fontFamily: FONT.mono }}>
                    {formatPrice(pos.takeProfitPrice)}
                  </span>
                </div>
              )}
              {pos.stopLossPrice !== null && (
                <div>
                  <span style={{ color: X.textSecondary }}>SL: </span>
                  <span style={{ color: X.glowAmber, fontFamily: FONT.mono }}>
                    {formatPrice(pos.stopLossPrice)}
                  </span>
                </div>
              )}
            </div>
          </td>
        </tr>
      )}
    </>
  );
});

const PositionsTable = memo(function PositionsTable() {
  const { data: positions } = usePositions();
  const addToast = useExchangeStore((s) => s.addToast);

  const handleClose = useCallback(
    (marketId: MarketId) => {
      addToast(`Position closed — ${displayName(marketId)}`, "success");
    },
    [addToast],
  );

  if (!positions || positions.length === 0) {
    return <div style={emptyStyle}>No open positions</div>;
  }

  return (
    <div className="exchange-scroll" style={{ overflowX: "auto", overflowY: "auto", maxHeight: 340 }}>
      <table style={{ width: "100%", borderCollapse: "collapse" }}>
        <thead>
          <tr>
            <th style={thStyle}>Market</th>
            <th style={thStyle}>Side</th>
            <th style={thRightStyle}>Size</th>
            <th style={thRightStyle}>Entry</th>
            <th style={thRightStyle}>Mark</th>
            <th style={thRightStyle}>Liq Price</th>
            <th style={thRightStyle}>Margin</th>
            <th style={thRightStyle}>PnL</th>
            <th style={thRightStyle}>PnL%</th>
            <th style={thRightStyle}>Actions</th>
          </tr>
        </thead>
        <tbody>
          {positions.map((pos) => (
            <PositionRow key={pos.marketId} pos={pos} onClose={handleClose} />
          ))}
        </tbody>
      </table>
    </div>
  );
});

// ─── ORDERS TAB ─────────────────────────────────────────────────────────────

const OrderRow = memo(function OrderRow({
  order,
  onCancel,
}: {
  order: Order;
  onCancel: (id: string, marketId: MarketId) => void;
}) {
  const filledPct = order.size > 0 ? (order.filledSize / order.size) * 100 : 0;

  return (
    <tr>
      <td style={tdSecondaryStyle}>
        <span style={{ fontSize: 11 }}>{timeAgo(order.createdAt)}</span>
      </td>
      <td style={tdStyle}>
        <span style={{ fontFamily: FONT.display, fontSize: 11, letterSpacing: "0.04em" }}>
          {displayName(order.marketId)}
        </span>
      </td>
      <td style={tdStyle}>
        <StatusBadge status={order.type.replace("_", " ")} />
      </td>
      <td style={tdStyle}>
        <SideBadge side={order.side} />
      </td>
      <td style={tdRightStyle}>
        {order.price !== null ? formatPrice(order.price) : "Market"}
      </td>
      <td style={tdRightStyle}>{formatSize(order.size)}</td>
      <td style={tdRightStyle}>
        <div style={{ display: "flex", flexDirection: "column", alignItems: "flex-end", gap: 2 }}>
          <span>{formatSize(order.filledSize)}</span>
          <div
            style={{
              width: 40,
              height: 2,
              borderRadius: 1,
              background: X.borderSubtle,
              overflow: "hidden",
            }}
          >
            <div
              style={{
                width: `${filledPct}%`,
                height: "100%",
                background: X.glowCyan,
                borderRadius: 1,
              }}
            />
          </div>
        </div>
      </td>
      <td style={tdRightStyle}>{formatSize(order.remainingSize)}</td>
      <td style={tdStyle}>
        <span
          style={{
            fontFamily: FONT.display,
            fontSize: 9,
            letterSpacing: "0.08em",
            color: X.textSecondary,
            textTransform: "uppercase",
          }}
        >
          {order.tif}
        </span>
      </td>
      <td style={{ ...tdStyle, textAlign: "right" }}>
        <button
          style={{
            ...microBtnBase,
            background: X.glowCrimson + "18",
            color: X.glowCrimson,
          }}
          onClick={() => onCancel(order.id, order.marketId)}
          title="Cancel Order"
        >
          Cancel
        </button>
      </td>
    </tr>
  );
});

const OrdersTable = memo(function OrdersTable() {
  const { data: orders } = useOpenOrders();
  const cancelOrderMutation = useCancelOrder();

  const handleCancel = useCallback(
    (id: string, marketId: MarketId) => {
      cancelOrderMutation.mutate({ orderId: id, pair: marketId });
    },
    [cancelOrderMutation],
  );

  const handleCancelAll = useCallback(() => {
    if (orders && orders.length > 0) {
      for (const order of orders) {
        cancelOrderMutation.mutate({ orderId: order.id, pair: order.marketId });
      }
    }
  }, [cancelOrderMutation, orders]);

  return (
    <div style={{ display: "flex", flexDirection: "column", height: "100%" }}>
      {orders && orders.length > 0 && (
        <div
          style={{
            display: "flex",
            justifyContent: "flex-end",
            padding: "6px 12px",
            borderBottom: `1px solid ${X.borderSubtle}`,
          }}
        >
          <button
            style={{
              ...microBtnBase,
              background: X.glowCrimson + "18",
              color: X.glowCrimson,
              fontSize: 10,
              padding: "4px 12px",
            }}
            onClick={handleCancelAll}
          >
            Cancel All ({orders.length})
          </button>
        </div>
      )}
      {!orders || orders.length === 0 ? (
        <div style={emptyStyle}>No open orders</div>
      ) : (
        <div className="exchange-scroll" style={{ overflowX: "auto", overflowY: "auto", maxHeight: 340 }}>
          <table style={{ width: "100%", borderCollapse: "collapse" }}>
            <thead>
              <tr>
                <th style={thStyle}>Time</th>
                <th style={thStyle}>Market</th>
                <th style={thStyle}>Type</th>
                <th style={thStyle}>Side</th>
                <th style={thRightStyle}>Price</th>
                <th style={thRightStyle}>Size</th>
                <th style={thRightStyle}>Filled</th>
                <th style={thRightStyle}>Remaining</th>
                <th style={thStyle}>TIF</th>
                <th style={thRightStyle}>Actions</th>
              </tr>
            </thead>
            <tbody>
              {orders.map((order) => (
                <OrderRow key={order.id} order={order} onCancel={handleCancel} />
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
});

// ─── HISTORY TAB ────────────────────────────────────────────────────────────

const FillRow = memo(function FillRow({ fill }: { fill: Order }) {
  // Determine maker/taker role by comparing fee to expected maker/taker rates
  const notional = (fill.avgFillPrice ?? fill.price ?? 0) * fill.filledSize;
  const makerFeeExpected = notional * FEES.maker;
  const takerFeeExpected = notional * FEES.taker;

  // If fee is closer to maker rate, classify as maker
  const makerDiff = Math.abs(fill.fee - makerFeeExpected);
  const takerDiff = Math.abs(fill.fee - takerFeeExpected);
  const isMaker = makerDiff <= takerDiff;

  return (
    <tr>
      <td style={tdSecondaryStyle}>
        <span style={{ fontSize: 11 }}>{timeAgo(fill.createdAt)}</span>
      </td>
      <td style={tdStyle}>
        <span style={{ fontFamily: FONT.display, fontSize: 11, letterSpacing: "0.04em" }}>
          {displayName(fill.marketId)}
        </span>
      </td>
      <td style={tdStyle}>
        <SideBadge side={fill.side} />
      </td>
      <td style={tdStyle}>
        <StatusBadge status={fill.type.replace("_", " ")} />
      </td>
      <td style={tdRightStyle}>
        {fill.avgFillPrice !== null ? formatPrice(fill.avgFillPrice) : fill.price !== null ? formatPrice(fill.price) : "---"}
      </td>
      <td style={tdRightStyle}>{formatSize(fill.filledSize)}</td>
      <td style={tdRightStyle}>
        <span style={{ color: X.textSecondary }}>{formatUsd(fill.fee)}</span>
      </td>
      <td style={tdStyle}>
        <span style={roleBadgeStyle(isMaker ? X.glowCyan : X.glowGold)}>
          {isMaker ? "Maker" : "Taker"}
        </span>
      </td>
      <td style={tdStyle}>
        <div style={{ display: "flex", alignItems: "center", gap: 4 }}>
          <span
            style={{
              fontFamily: FONT.mono,
              fontSize: 11,
              color: X.glowCyan,
              cursor: "pointer",
            }}
            title={fill.txHash}
          >
            {truncHash(fill.txHash)}
          </span>
          <CopyButton text={fill.txHash} />
        </div>
      </td>
    </tr>
  );
});

const HistoryTable = memo(function HistoryTable() {
  const { data: fills } = useMyFills();

  if (!fills || fills.length === 0) {
    return <div style={emptyStyle}>No trade history</div>;
  }

  return (
    <div className="exchange-scroll" style={{ overflowX: "auto", overflowY: "auto", maxHeight: 340 }}>
      <table style={{ width: "100%", borderCollapse: "collapse" }}>
        <thead>
          <tr>
            <th style={thStyle}>Time</th>
            <th style={thStyle}>Market</th>
            <th style={thStyle}>Side</th>
            <th style={thStyle}>Type</th>
            <th style={thRightStyle}>Price</th>
            <th style={thRightStyle}>Size</th>
            <th style={thRightStyle}>Fee</th>
            <th style={thStyle}>Role</th>
            <th style={thStyle}>Tx</th>
          </tr>
        </thead>
        <tbody>
          {fills.map((fill) => (
            <FillRow key={fill.id} fill={fill} />
          ))}
        </tbody>
      </table>
    </div>
  );
});

// ─── FUNDING TAB ────────────────────────────────────────────────────────────

const FundingRow = memo(function FundingRow({ fp }: { fp: FundingPayment }) {
  const paymentColor = fp.payment < 0 ? X.glowCrimson : fp.payment > 0 ? X.glowEmerald : X.textSecondary;
  const cumColor = fp.cumulative < 0 ? X.glowCrimson : fp.cumulative > 0 ? X.glowEmerald : X.textSecondary;

  return (
    <tr>
      <td style={tdSecondaryStyle}>
        <span style={{ fontSize: 11 }}>{timeAgo(fp.timestamp)}</span>
      </td>
      <td style={tdStyle}>
        <span style={{ fontFamily: FONT.display, fontSize: 11, letterSpacing: "0.04em" }}>
          {displayName(fp.marketId)}
        </span>
      </td>
      <td style={tdRightStyle}>{formatSize(fp.positionSize)}</td>
      <td style={tdRightStyle}>
        <span style={{ color: fp.fundingRate >= 0 ? X.glowEmerald : X.glowCrimson }}>
          {formatFundingRate(fp.fundingRate)}
        </span>
      </td>
      <td style={tdRightStyle}>
        <span style={{ color: paymentColor }}>
          {fp.payment >= 0 ? "+" : ""}
          {formatUsd(fp.payment)}
        </span>
      </td>
      <td style={tdRightStyle}>
        <span style={{ color: cumColor }}>
          {fp.cumulative >= 0 ? "+" : ""}
          {formatUsd(fp.cumulative)}
        </span>
      </td>
    </tr>
  );
});

const FundingTable = memo(function FundingTable() {
  const activeMarket = useExchangeStore((s) => s.activeMarket);
  const { data: payments } = useFunding(activeMarket);

  if (!payments || payments.length === 0) {
    return <div style={emptyStyle}>No funding payments</div>;
  }

  return (
    <div className="exchange-scroll" style={{ overflowX: "auto", overflowY: "auto", maxHeight: 340 }}>
      <table style={{ width: "100%", borderCollapse: "collapse" }}>
        <thead>
          <tr>
            <th style={thStyle}>Time</th>
            <th style={thStyle}>Market</th>
            <th style={thRightStyle}>Pos Size</th>
            <th style={thRightStyle}>Rate</th>
            <th style={thRightStyle}>Payment</th>
            <th style={thRightStyle}>Cumulative</th>
          </tr>
        </thead>
        <tbody>
          {payments.map((fp, i) => (
            <FundingRow key={`${fp.marketId}-${fp.timestamp}-${i}`} fp={fp} />
          ))}
        </tbody>
      </table>
    </div>
  );
});

// ─── MAIN PANEL ─────────────────────────────────────────────────────────────

const PositionsPanel = memo(function PositionsPanel() {
  const positionsTab = useExchangeStore((s) => s.positionsTab);
  const setPositionsTab = useExchangeStore((s) => s.setPositionsTab);

  const { data: positions } = usePositions();
  const { data: orders } = useOpenOrders();
  const { data: fills } = useMyFills();
  const activeMarket = useExchangeStore((s) => s.activeMarket);
  const { data: funding } = useFunding(activeMarket);

  const tabs = useMemo(
    () => [
      { key: "positions", label: "Positions", count: positions?.length ?? 0 },
      { key: "orders", label: "Orders", count: orders?.length ?? 0 },
      { key: "history", label: "History", count: fills?.length ?? 0 },
      { key: "funding", label: "Funding", count: funding?.length ?? 0 },
    ],
    [positions?.length, orders?.length, fills?.length, funding?.length],
  );

  const handleTabChange = useCallback(
    (key: string) => {
      setPositionsTab(key);
    },
    [setPositionsTab],
  );

  return (
    <div style={{ ...panelStyle, display: "flex", flexDirection: "column", width: "100%", overflow: "hidden" }}>
      <TabBar tabs={tabs} active={positionsTab} onChange={handleTabChange} />
      <div style={{ flex: 1, minHeight: 0 }}>
        {positionsTab === "positions" && <PositionsTable />}
        {positionsTab === "orders" && <OrdersTable />}
        {positionsTab === "history" && <HistoryTable />}
        {positionsTab === "funding" && <FundingTable />}
      </div>
    </div>
  );
});

export default PositionsPanel;
