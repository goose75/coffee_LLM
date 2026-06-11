"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { getTrendingCoffees } from "@/lib/api";
import type { Coffee, Paginated } from "@/lib/api";
import CoffeeCard from "./CoffeeCard";

export function TrendingSection() {
  const [trending, setTrending] = useState<Coffee[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    let mounted = true;

    (async () => {
      try {
        const result: Paginated<Coffee> = await getTrendingCoffees({ days: 14, page: 1, page_size: 6 });
        if (mounted) {
          setTrending(result.data);
        }
      } catch (err) {
        console.error("Failed to load trending:", err);
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
      <section className="trending-section">
        <div className="container">
          <div style={{ paddingTop: "48px", paddingBottom: "48px", textAlign: "center" }}>
            <p style={{ color: "var(--text-faint)" }}>Loading trending...</p>
          </div>
        </div>
      </section>
    );
  }

  if (!trending.length) {
    return null;
  }

  return (
    <section className="trending-section">
      <div className="container">
        <div className="section-header">
          <span className="section-eyebrow">⚡ Fresh</span>
          <h2 className="section-title">Just Added</h2>
          <p className="section-description">
            New coffees from roasters this week
          </p>
        </div>

        <div className="trending-grid">
          {trending.map((coffee) => (
            <CoffeeCard key={coffee.id} coffee={coffee} />
          ))}
        </div>

        <div className="section-footer">
          <Link href="/coffees/trending" className="link-button">
            See all new releases →
          </Link>
        </div>
      </div>

      <style jsx>{`
        .trending-section {
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

        .trending-grid {
          display: grid;
          grid-template-columns: repeat(auto-fill, minmax(280px, 1fr));
          gap: 24px;
          margin-bottom: 32px;
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
          .trending-grid {
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
