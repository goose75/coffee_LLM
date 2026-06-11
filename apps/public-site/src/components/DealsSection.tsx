"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { getDeals } from "@/lib/api";
import type { Coffee } from "@/lib/api";
import CoffeeCard from "./CoffeeCard";

export function DealsSection() {
  const [deals, setDeals] = useState<Coffee[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    let mounted = true;

    (async () => {
      try {
        const result = await getDeals({ days: 7, min_discount_percent: 10, limit: 6 });
        if (mounted) {
          setDeals(result);
        }
      } catch (err) {
        console.error("Failed to load deals:", err);
      } finally {
        if (mounted) setLoading(false);
      }
    })();

    return () => {
      mounted = false;
    };
  }, []);

  if (loading) {
    return (
      <section className="deals-section">
        <div className="container">
          <div style={{ paddingTop: "48px", paddingBottom: "48px", textAlign: "center" }}>
            <p style={{ color: "var(--text-faint)" }}>Loading deals...</p>
          </div>
        </div>
      </section>
    );
  }

  if (!deals.length) {
    return null;
  }

  return (
    <section className="deals-section">
      <div className="container">
        <div className="section-header">
          <span className="section-eyebrow">🎉 Price Drops</span>
          <h2 className="section-title">Deals This Week</h2>
          <p className="section-description">
            Biggest price drops in the last 7 days
          </p>
        </div>

        <div className="deals-grid">
          {deals.map((coffee) => (
            <div key={coffee.id} className="deals-card-wrapper">
              <CoffeeCard coffee={coffee} />
              {coffee.discount_percent && (
                <div className="deal-badge">
                  <span className="deal-badge-percent">
                    {coffee.discount_percent.toFixed(0)}%
                  </span>
                  <span className="deal-badge-label">OFF</span>
                </div>
              )}
            </div>
          ))}
        </div>

        <div className="section-footer">
          <Link href="/coffees/deals" className="link-button">
            See all deals →
          </Link>
        </div>
      </div>

      <style jsx>{`
        .deals-section {
          padding: 64px 0;
          border-bottom: 1px solid var(--border-light);
        }

        .container {
          max-width: 1200px;
          margin: 0 auto;
          padding: 0 20px;
        }

        .section-header {
          text-align: center;
          margin-bottom: 48px;
        }

        .section-eyebrow {
          display: block;
          font-size: 12px;
          color: var(--text-faint);
          text-transform: uppercase;
          letter-spacing: 1px;
          margin-bottom: 8px;
        }

        .section-title {
          font-size: 36px;
          font-weight: 300;
          margin: 0 0 12px 0;
          font-family: var(--font-display);
          color: var(--text);
        }

        .section-description {
          font-size: 16px;
          color: var(--text-muted);
          margin: 0;
        }

        .deals-grid {
          display: grid;
          grid-template-columns: repeat(auto-fill, minmax(280px, 1fr));
          gap: 24px;
          margin-bottom: 32px;
        }

        .deals-card-wrapper {
          position: relative;
        }

        .deal-badge {
          position: absolute;
          top: 12px;
          left: 12px;
          background: #4caf50;
          color: white;
          border-radius: 8px;
          padding: 6px 10px;
          font-size: 11px;
          font-weight: 700;
          display: flex;
          flex-direction: column;
          align-items: center;
          gap: 2px;
          line-height: 1;
        }

        .deal-badge-percent {
          font-size: 14px;
        }

        .deal-badge-label {
          font-size: 9px;
          opacity: 0.9;
        }

        .section-footer {
          text-align: center;
        }

        .link-button {
          display: inline-block;
          padding: 12px 24px;
          border: 1px solid var(--border-light);
          border-radius: 8px;
          color: var(--accent);
          text-decoration: none;
          font-size: 14px;
          font-weight: 500;
          transition: all 0.2s;
        }

        .link-button:hover {
          border-color: var(--accent);
          background: rgba(181, 136, 42, 0.05);
        }

        @media (max-width: 768px) {
          .deals-grid {
            grid-template-columns: repeat(auto-fill, minmax(160px, 1fr));
            gap: 16px;
          }

          .section-title {
            font-size: 28px;
          }
        }
      `}</style>
    </section>
  );
}
