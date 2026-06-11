"use client";

import { useEffect, useState } from "react";
import { getIngestionRuns, type IngestionRun } from "@/lib/api";

interface HealingStatus {
  total_roasters: number;
  roasters_needing_healing: number;
  healed_this_hour: number;
  healed_this_day: number;
  success_rate_percent: number;
  unknown_status_count: number;
  never_crawled_count: number;
  extraction_success_rate_percent: number;
  status: string;
}

// ============================================================================
// GAUGE COMPONENT - Animated dial for metrics
// ============================================================================
function Gauge({ label, value, max, unit = "", color = "text-cyan-400" }: { label: string; value: number; max: number; unit?: string; color?: string }) {
  const safeMax = Math.max(1, max); // Prevent division by zero
  const percentage = Math.min(100, (value / safeMax) * 100);
  const rotation = isNaN(percentage) ? -135 : (percentage / 100) * 270 - 135; // -135 to +135 degrees

  return (
    <div className="flex flex-col items-center gap-3">
      <div className="relative w-32 h-32">
        {/* Outer ring */}
        <svg className="absolute inset-0 w-full h-full" viewBox="0 0 100 100">
          {/* Background track */}
          <circle cx="50" cy="50" r="40" fill="none" stroke="#1e293b" strokeWidth="3" opacity="0.3" />

          {/* Colored fill track */}
          <circle
            cx="50"
            cy="50"
            r="40"
            fill="none"
            stroke={color === "text-green-400" ? "#22c55e" : color === "text-amber-400" ? "#f59e0b" : color === "text-red-500" ? "#ef4444" : "#06b6d4"}
            strokeWidth="4"
            strokeDasharray={`${isNaN(percentage) ? 0 : (percentage / 100) * 251.3} 251.3`}
            strokeLinecap="round"
            opacity="0.8"
            style={{ transition: "stroke-dasharray 0.5s ease-out" }}
          />

          {/* Needle */}
          <g style={{ transform: `rotate(${rotation}deg)`, transformOrigin: "50% 50%", transition: "transform 0.5s ease-out" }}>
            <line x1="50" y1="20" x2="50" y2="10" stroke={color === "text-green-400" ? "#22c55e" : color === "text-amber-400" ? "#f59e0b" : color === "text-red-500" ? "#ef4444" : "#06b6d4"} strokeWidth="2" />
            <circle cx="50" cy="50" r="3" fill={color === "text-green-400" ? "#22c55e" : color === "text-amber-400" ? "#f59e0b" : color === "text-red-500" ? "#ef4444" : "#06b6d4"} />
          </g>

          {/* Label marks */}
          {[0, 25, 50, 75, 100].map((mark) => {
            const markRotation = (mark / 100) * 270 - 135;
            const rad = (markRotation * Math.PI) / 180;
            const x1 = 50 + 38 * Math.cos(rad);
            const y1 = 50 + 38 * Math.sin(rad);
            const x2 = 50 + 35 * Math.cos(rad);
            const y2 = 50 + 35 * Math.sin(rad);
            return (
              <line key={mark} x1={x1} y1={y1} x2={x2} y2={y2} stroke="#475569" strokeWidth="1.5" />
            );
          })}
        </svg>

        {/* Center value */}
        <div className="absolute inset-0 flex flex-col items-center justify-center">
          <div className={`text-3xl font-black ${color}`} style={{ fontFamily: "Courier New, monospace" }}>
            {value}
          </div>
          <div className="text-[10px] text-slate-500 font-mono uppercase tracking-widest">{unit}</div>
        </div>
      </div>

      <div className="text-xs font-mono uppercase tracking-widest text-slate-400 text-center">{label}</div>
    </div>
  );
}

// ============================================================================
// STATUS INDICATOR - Real-time pulsing status
// ============================================================================
function StatusDot({ status }: { status: string }) {
  const dotColor = status === "healthy" ? "bg-green-500" : status === "critical" ? "bg-red-500" : status === "degraded" ? "bg-amber-500" : "bg-slate-500";
  const pulseColor = status === "healthy" ? "bg-green-500/30" : status === "critical" ? "bg-red-500/30" : status === "degraded" ? "bg-amber-500/30" : "bg-slate-500/30";

  return (
    <div className="relative inline-flex items-center justify-center">
      <div className={`absolute w-3 h-3 rounded-full ${pulseColor} animate-pulse`} />
      <div className={`w-2 h-2 rounded-full ${dotColor}`} />
    </div>
  );
}

// ============================================================================
// MAIN CONTROL TOWER DASHBOARD
// ============================================================================
export default function ControlTowerPage() {
  const [healingStatus, setHealingStatus] = useState<HealingStatus | null>(null);
  const [runs, setRuns] = useState<IngestionRun[]>([]);
  const [loading, setLoading] = useState(true);
  const [autoRefresh, setAutoRefresh] = useState(true);

  // Load data
  useEffect(() => {
    const fetchData = async () => {
      try {
        const API_BASE = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";
        const statusRes = await fetch(`${API_BASE}/api/v1/admin/healing/status`);
        const runsRes = await getIngestionRuns({ page_size: 50 });

        if (statusRes.ok) {
          const status = (await statusRes.json()) as HealingStatus;
          setHealingStatus(status);
        }
        setRuns(runsRes.data);
      } catch (e) {
        console.error("Failed to load control tower data:", e);
      } finally {
        setLoading(false);
      }
    };

    fetchData();

    // Auto-refresh every 5 seconds
    if (autoRefresh) {
      const interval = setInterval(fetchData, 5000);
      return () => clearInterval(interval);
    }
  }, [autoRefresh]);

  // Use healing status data (with safe defaults)
  const total = healingStatus?.total_roasters ?? 0;
  const needsHealing = healingStatus?.roasters_needing_healing ?? 0;
  const successRate = Math.round(healingStatus?.extraction_success_rate_percent ?? 0);
  const neverCrawled = healingStatus?.never_crawled_count ?? 0;
  const systemStatus = healingStatus?.status ?? "unknown";

  // Don't render until data is loaded
  if (loading) {
    return (
      <div className="min-h-screen bg-slate-950 text-slate-100 p-6 font-mono flex items-center justify-center">
        <div className="text-center">
          <div className="text-4xl font-black text-cyan-400 mb-4" style={{ textShadow: "0 0 20px rgba(34, 211, 238, 0.5)" }}>
            ⚡ CONTROL TOWER
          </div>
          <div className="text-sm text-slate-400">Loading healing system data...</div>
        </div>
      </div>
    );
  }

  const runningRuns = runs.filter(r => r.status === "running").length;
  const failedRuns = runs.filter(r => r.status === "failed").length;
  const completedRuns = runs.filter(r => r.status === "completed").length;

  return (
    <div className="min-h-screen bg-slate-950 text-slate-100 p-6 font-mono">
      {/* HEADER */}
      <div className="mb-8">
        <div className="flex items-center justify-between mb-4">
          <div>
            <h1 className="text-4xl font-black text-cyan-400" style={{ textShadow: "0 0 20px rgba(34, 211, 238, 0.5)" }}>
              ⚡ CONTROL TOWER
            </h1>
            <p className="text-xs text-slate-500 mt-2 uppercase tracking-widest">Coffee Platform Master Control</p>
          </div>

          {/* Controls */}
          <div className="flex items-center gap-4">
            <div className="flex items-center gap-2 px-4 py-2 border border-cyan-500/30 rounded bg-cyan-500/5">
              <div className="w-2 h-2 rounded-full bg-green-500 animate-pulse" />
              <span className="text-xs uppercase tracking-widest text-green-400">ONLINE</span>
            </div>

            <button
              onClick={() => setAutoRefresh(!autoRefresh)}
              className="px-4 py-2 border border-amber-500/30 rounded bg-amber-500/5 hover:bg-amber-500/10 text-xs uppercase tracking-widest text-amber-400 transition"
            >
              {autoRefresh ? "⏸ PAUSE" : "▶ LIVE"}
            </button>
          </div>
        </div>

        <div className="border-t border-b border-cyan-500/20 py-2 mb-6">
          <div className="text-[10px] text-slate-600 uppercase tracking-widest font-mono">
            ▸ Autonomous Healing System: {systemStatus.toUpperCase()} | Roasters: {total} | Extraction Rate: {successRate}%
          </div>
        </div>
      </div>

      {/* MAIN GAUGE CLUSTER */}
      <div className="grid grid-cols-6 gap-6 mb-12">
        <div className="col-span-1">
          <Gauge
            label="Extraction Success"
            value={successRate}
            max={100}
            unit="%"
            color={successRate >= 80 ? "text-green-400" : successRate >= 50 ? "text-amber-400" : "text-red-500"}
          />
        </div>

        <div className="col-span-1">
          <Gauge
            label="Total Roasters"
            value={total}
            max={Math.max(1000, total)}
            unit={""}
            color="text-cyan-400"
          />
        </div>

        <div className="col-span-1">
          <Gauge
            label="Needing Healing"
            value={needsHealing}
            max={total}
            unit={`/ ${total}`}
            color={needsHealing === 0 ? "text-green-400" : needsHealing <= total * 0.1 ? "text-amber-400" : "text-red-500"}
          />
        </div>

        <div className="col-span-1">
          <Gauge
            label="Never Crawled"
            value={neverCrawled}
            max={total}
            unit={`/ ${total}`}
            color={neverCrawled === 0 ? "text-green-400" : neverCrawled <= total * 0.1 ? "text-amber-400" : "text-red-500"}
          />
        </div>

        <div className="col-span-1">
          <Gauge
            label="Healed Today"
            value={healingStatus?.healed_this_day ?? 0}
            max={Math.max(10, healingStatus?.healed_this_day ?? 0)}
            unit="✓"
            color={healingStatus?.healed_this_day ?? 0 > 0 ? "text-green-400" : "text-slate-600"}
          />
        </div>

        <div className="col-span-1">
          <Gauge
            label="Queue Depth"
            value={runningRuns}
            max={Math.max(5, runningRuns)}
            unit="⏳"
            color={runningRuns <= 2 ? "text-green-400" : runningRuns <= 5 ? "text-amber-400" : "text-red-500"}
          />
        </div>
      </div>

      {/* INGESTION QUEUE PANEL */}
      <div className="grid grid-cols-3 gap-6 mb-12">
        {/* Queue Monitor */}
        <div className="col-span-2 border border-cyan-500/30 rounded bg-cyan-500/5 p-6">
          <div className="text-sm font-black uppercase tracking-widest text-cyan-400 mb-6" style={{ textShadow: "0 0 10px rgba(34, 211, 238, 0.3)" }}>
            📊 INGESTION QUEUE
          </div>

          {/* Queue Stats */}
          <div className="grid grid-cols-4 gap-4 mb-6">
            <div className="border border-green-500/30 rounded p-3 bg-green-500/5">
              <div className="text-2xl font-black text-green-400">{completedRuns}</div>
              <div className="text-[10px] text-green-600 uppercase tracking-widest mt-1">Completed</div>
            </div>
            <div className="border border-blue-500/30 rounded p-3 bg-blue-500/5">
              <div className="text-2xl font-black text-blue-400">{runningRuns}</div>
              <div className="text-[10px] text-blue-600 uppercase tracking-widest mt-1">Running</div>
            </div>
            <div className="border border-amber-500/30 rounded p-3 bg-amber-500/5">
              <div className="text-2xl font-black text-amber-400">
                {runs.filter(r => r.status === "partial").length}
              </div>
              <div className="text-[10px] text-amber-600 uppercase tracking-widest mt-1">Partial</div>
            </div>
            <div className="border border-red-500/30 rounded p-3 bg-red-500/5">
              <div className="text-2xl font-black text-red-400">{failedRuns}</div>
              <div className="text-[10px] text-red-600 uppercase tracking-widest mt-1">Failed</div>
            </div>
          </div>

          {/* Recent Runs */}
          <div className="space-y-2 max-h-48 overflow-y-auto">
            {runs.slice(0, 8).map((run) => (
              <div key={run.id} className="border border-slate-700 rounded p-3 hover:border-cyan-500/50 transition">
                <div className="flex items-center justify-between gap-4">
                  <div className="flex items-center gap-3 flex-1 min-w-0">
                    <StatusDot status={run.status === "running" ? "running" : run.status === "completed" ? "healthy" : run.status === "failed" ? "failing" : "stale"} />
                    <div className="min-w-0">
                      <div className="text-xs font-mono text-slate-300 truncate">{run.store_name || "System"}</div>
                      <div className="text-[10px] text-slate-600">{new Date(run.started_at).toLocaleTimeString()}</div>
                    </div>
                  </div>

                  <div className="flex items-center gap-6 text-xs font-mono">
                    <div className="text-green-400">{run.records_created || 0}✓</div>
                    <div className="text-blue-400">{run.records_updated || 0}↑</div>
                    <div className={run.error_count > 0 ? "text-red-400" : "text-slate-600"}>{run.error_count || 0}✕</div>
                  </div>
                </div>

                {run.status === "running" && (
                  <div className="mt-2 w-full h-1 bg-slate-800 rounded-full overflow-hidden">
                    <div className="h-full bg-cyan-500 rounded-full animate-pulse" style={{ width: "45%" }} />
                  </div>
                )}
              </div>
            ))}
          </div>
        </div>

        {/* Quick Actions */}
        <div className="border border-amber-500/30 rounded bg-amber-500/5 p-6">
          <div className="text-sm font-black uppercase tracking-widest text-amber-400 mb-6">⚙️ QUICK ACTIONS</div>

          <div className="space-y-3">
            <a href="/sources" className="block w-full px-4 py-3 border border-cyan-500/50 rounded bg-cyan-500/10 hover:bg-cyan-500/20 text-xs uppercase tracking-widest text-cyan-400 font-mono transition text-center">
              🔍 View Queue
            </a>
            <a href="/sources" className="block w-full px-4 py-3 border border-green-500/50 rounded bg-green-500/10 hover:bg-green-500/20 text-xs uppercase tracking-widest text-green-400 font-mono transition text-center">
              ✓ Healthy Only
            </a>
            <a href="/ingestion-runs" className="block w-full px-4 py-3 border border-amber-500/50 rounded bg-amber-500/10 hover:bg-amber-500/20 text-xs uppercase tracking-widest text-amber-400 font-mono transition text-center">
              📊 Ingestion Logs
            </a>
            <a href="/sources" className="block w-full px-4 py-3 border border-red-500/50 rounded bg-red-500/10 hover:bg-red-500/20 text-xs uppercase tracking-widest text-red-400 font-mono transition text-center">
              🚨 Needs Healing
            </a>
          </div>

          <div className="mt-6 pt-6 border-t border-slate-700 space-y-2 text-[10px] text-slate-600">
            <div>▸ System: {systemStatus.toUpperCase()}</div>
            <div>▸ Queue depth: {runningRuns}</div>
            <div>▸ Healing rate: {successRate}%</div>
          </div>
        </div>
      </div>

      {/* HEALING SYSTEM STATUS */}
      <div className="border border-purple-500/30 rounded bg-purple-500/5 p-6">
        <div className="text-sm font-black uppercase tracking-widest text-purple-400 mb-6" style={{ textShadow: "0 0 10px rgba(168, 85, 247, 0.3)" }}>
          🏥 AUTONOMOUS HEALING STATUS
        </div>

        <div className="grid grid-cols-4 gap-4">
          {[
            { label: "Total Roasters", count: total, color: "border-cyan-500 bg-cyan-500/5", textColor: "text-cyan-400" },
            { label: "Needing Healing", count: needsHealing, color: "border-red-500 bg-red-500/5", textColor: "text-red-400" },
            { label: "Never Crawled", count: neverCrawled, color: "border-amber-500 bg-amber-500/5", textColor: "text-amber-400" },
            { label: "Healed Today", count: healingStatus?.healed_this_day ?? 0, color: "border-green-500 bg-green-500/5", textColor: "text-green-400" },
          ].map((item) => (
            <div key={item.label} className={`border ${item.color} rounded-lg p-6 cursor-pointer hover:border-opacity-100 transition`}>
              <div className={`text-4xl font-black ${item.textColor}`}>{item.count}</div>
              <div className="text-xs uppercase tracking-widest text-slate-500 mt-2">{item.label}</div>
              <div className={`mt-3 h-1 bg-slate-800 rounded-full overflow-hidden`}>
                <div className={`h-full ${item.textColor.replace("text-", "bg-")}`} style={{ width: `${total > 0 ? (item.count / total) * 100 : 0}%` }} />
              </div>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}
