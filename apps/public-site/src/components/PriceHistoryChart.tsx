"use client";

import { useEffect, useState } from "react";
import { getPriceHistory } from "@/lib/api";
import type { BeanPriceHistory } from "@/lib/api";

interface PriceHistoryChartProps {
  coffeeId: string;
  days?: number;
}

export function PriceHistoryChart({ coffeeId, days = 30 }: PriceHistoryChartProps) {
  const [data, setData] = useState<BeanPriceHistory | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let mounted = true;

    (async () => {
      try {
        const result = await getPriceHistory(coffeeId, { days });
        if (mounted) {
          setData(result);
          setError(null);
        }
      } catch (err) {
        if (mounted) {
          setError(err instanceof Error ? err.message : "Failed to load price history");
          setData(null);
        }
      } finally {
        if (mounted) setLoading(false);
      }
    })();

    return () => {
      mounted = false;
    };
  }, [coffeeId, days]);

  if (loading) {
    return (
      <div className="price-history-chart-skeleton">
        <div style={{ height: "200px", background: "var(--surface)", borderRadius: "8px" }} />
      </div>
    );
  }

  if (error || !data) {
    return null; // Graceful degradation
  }

  if (!data.variants || data.variants.length === 0) {
    return null;
  }

  // Find the cheapest variant for display
  const cheapestVariant = data.variants.reduce((prev, curr) => {
    const prevMin = Math.min(...prev.history.map(h => h.price_gbp));
    const currMin = Math.min(...curr.history.map(h => h.price_gbp));
    return currMin < prevMin ? curr : prev;
  });

  // Get price statistics
  const prices = cheapestVariant.history.map(h => h.price_gbp);
  const minPrice = Math.min(...prices);
  const maxPrice = Math.max(...prices);
  const currentPrice = cheapestVariant.history[cheapestVariant.history.length - 1].price_gbp;
  const change = currentPrice - minPrice;
  const changePercent = ((change / minPrice) * 100).toFixed(1);

  // Create simple ASCII chart
  const chartPoints = cheapestVariant.history.map(h => ({
    date: new Date(h.recorded_at).toLocaleDateString('en-US', { month: 'short', day: 'numeric' }),
    price: h.price_gbp,
  }));

  return (
    <div className="price-history-chart">
      <h3 className="price-history-title">Price History ({days} days)</h3>

      <div className="price-history-stats">
        <div className="stat">
          <span className="label">Current</span>
          <span className="value">£{currentPrice.toFixed(2)}</span>
        </div>
        <div className="stat">
          <span className="label">Low</span>
          <span className="value">£{minPrice.toFixed(2)}</span>
        </div>
        <div className="stat">
          <span className="label">High</span>
          <span className="value">£{maxPrice.toFixed(2)}</span>
        </div>
      </div>

      <div className="price-history-chart-area">
        {/* Simple sparkline-style visualization */}
        <svg viewBox="0 0 100 50" className="price-history-sparkline">
          {/* Normalize prices to 0-50 range */}
          {prices.map((price, i) => {
            const x = (i / (prices.length - 1)) * 100;
            const normalized = ((maxPrice - price) / (maxPrice - minPrice)) * 50;
            return (
              <circle
                key={i}
                cx={x}
                cy={normalized}
                r="1"
                fill="var(--accent)"
                opacity="0.8"
              />
            );
          })}
        </svg>
      </div>

      <div className="price-history-change">
        {change < 0 ? (
          <>
            <span className="badge badge-positive">↓ {Math.abs(changePercent)}% from high</span>
            <span className="amount">Save £{Math.abs(change).toFixed(2)}</span>
          </>
        ) : change > 0 ? (
          <span className="badge badge-negative">↑ {changePercent}% from low</span>
        ) : (
          <span className="badge">Stable price</span>
        )}
      </div>

      <style jsx>{`
        .price-history-chart {
          padding: 16px;
          border: 1px solid var(--border-light);
          border-radius: 8px;
          background: var(--surface);
          font-family: var(--font-body);
        }

        .price-history-title {
          margin: 0 0 12px 0;
          font-size: 14px;
          font-weight: 600;
          color: var(--text);
          text-transform: uppercase;
          letter-spacing: 0.5px;
        }

        .price-history-stats {
          display: grid;
          grid-template-columns: repeat(3, 1fr);
          gap: 12px;
          margin-bottom: 16px;
        }

        .stat {
          display: flex;
          flex-direction: column;
          gap: 4px;
        }

        .stat .label {
          font-size: 12px;
          color: var(--text-faint);
          text-transform: uppercase;
          letter-spacing: 0.3px;
        }

        .stat .value {
          font-size: 16px;
          font-weight: 600;
          color: var(--text);
        }

        .price-history-chart-area {
          margin: 16px 0;
          height: 60px;
        }

        .price-history-sparkline {
          width: 100%;
          height: 100%;
        }

        .price-history-change {
          display: flex;
          align-items: center;
          gap: 8px;
          font-size: 13px;
        }

        .badge {
          display: inline-block;
          padding: 4px 8px;
          border-radius: 4px;
          background: var(--bg);
          color: var(--text-faint);
          font-size: 12px;
          font-weight: 500;
        }

        .badge-positive {
          background: rgba(76, 175, 80, 0.1);
          color: #4caf50;
        }

        .badge-negative {
          background: rgba(244, 67, 54, 0.1);
          color: #f44336;
        }

        .amount {
          font-weight: 600;
          color: #4caf50;
        }
      `}</style>
    </div>
  );
}
