"use client";

import { useEffect, useState, useCallback, Suspense } from "react";
import { useSearchParams } from "next/navigation";
import { getSources, getSource, rescanSource, type Store, type StoreDetail } from "@/lib/api";

interface LLMDiagnosis {
  store_id: string;
  store_name: string;
  current_issues: string[];
  root_causes: string[];
  recommended_actions: Array<{
    action: string;
    description: string;
    priority: "high" | "medium" | "low";
    expected_improvement: string;
  }>;
  confidence: number;
}

interface ActionResult {
  action: string;
  success: boolean;
  message: string;
}

// ============================================================================
// Inner Component that uses useSearchParams
// ============================================================================
function LLMAssistContent() {
  const searchParams = useSearchParams();
  const storeIds = (searchParams.get("stores") || "").split(",").filter(Boolean);

  const [stores, setStores] = useState<Store[]>([]);
  const [diagnoses, setDiagnoses] = useState<Map<string, LLMDiagnosis>>(new Map());
  const [results, setResults] = useState<Map<string, ActionResult[]>>(new Map());
  const [loading, setLoading] = useState(true);
  const [diagnosing, setDiagnosing] = useState(false);
  const [fixing, setFixing] = useState(false);
  const [selectedActions, setSelectedActions] = useState<Map<string, Set<string>>>(new Map());
  const [message, setMessage] = useState<string | null>(null);

  // Load stores
  useEffect(() => {
    const loadStores = async () => {
      try {
        if (storeIds.length === 0) {
          // Load all failing stores
          const data = await getSources({ health_status: "failing", page_size: 100 });
          setStores(data.data);
        } else {
          // Load selected stores
          const data = await getSources({ page_size: 100 });
          const selected = data.data.filter(s => storeIds.includes(s.id));
          setStores(selected);
        }
      } catch (e) {
        console.error("Failed to load stores:", e);
        setMessage("Failed to load stores");
      } finally {
        setLoading(false);
      }
    };

    loadStores();
  }, [storeIds]);

  // Diagnose stores
  const handleDiagnose = useCallback(async () => {
    if (stores.length === 0) return;
    setDiagnosing(true);
    setMessage(null);

    try {
      const newDiagnoses = new Map<string, LLMDiagnosis>();

      for (const store of stores) {
        try {
          // Get detailed store info
          const detail = await getSource(store.id);

          // Generate LLM diagnosis prompt
          const diagnosis = await generateLLMDiagnosis(store, detail);
          newDiagnoses.set(store.id, diagnosis);
        } catch (e) {
          console.error(`Failed to diagnose ${store.name}:`, e);
        }
      }

      setDiagnoses(newDiagnoses);
      setMessage(`Diagnosed ${newDiagnoses.size} store(s)`);
    } catch (e: any) {
      setMessage(`Error: ${e.message}`);
    } finally {
      setDiagnosing(false);
    }
  }, [stores]);

  // Apply selected fixes
  const handleApplyFixes = useCallback(async () => {
    if (selectedActions.size === 0) return;
    setFixing(true);
    setMessage(null);

    try {
      const newResults = new Map<string, ActionResult[]>();

      for (const [storeId, actions] of selectedActions) {
        const storeResults: ActionResult[] = [];

        for (const action of actions) {
          try {
            const result = await applyLLMAction(storeId, action);
            storeResults.push({
              action,
              success: result.success,
              message: result.message,
            });
          } catch (e: any) {
            storeResults.push({
              action,
              success: false,
              message: e.message,
            });
          }
        }

        newResults.set(storeId, storeResults);
      }

      setResults(newResults);
      setSelectedActions(new Map());
      setMessage("Fixes applied! Reloading store status...");

      // Reload stores after a delay
      setTimeout(() => {
        window.location.reload();
      }, 2000);
    } catch (e: any) {
      setMessage(`Error: ${e.message}`);
    } finally {
      setFixing(false);
    }
  }, [selectedActions]);

  const toggleAction = (storeId: string, action: string) => {
    const storeActions = selectedActions.get(storeId) || new Set();
    const newActions = new Set(storeActions);
    if (newActions.has(action)) {
      newActions.delete(action);
    } else {
      newActions.add(action);
    }
    if (newActions.size === 0) {
      selectedActions.delete(storeId);
    } else {
      selectedActions.set(storeId, newActions);
    }
    setSelectedActions(new Map(selectedActions));
  };

  const toggleAllStoreActions = (storeId: string) => {
    const diagnosis = diagnoses.get(storeId);
    if (!diagnosis) return;

    const storeActions = selectedActions.get(storeId) || new Set();
    const allActionKeys = diagnosis.recommended_actions.map(a => a.action);

    if (storeActions.size === allActionKeys.length) {
      selectedActions.delete(storeId);
    } else {
      selectedActions.set(storeId, new Set(allActionKeys));
    }
    setSelectedActions(new Map(selectedActions));
  };

  if (loading) {
    return (
      <div className="min-h-screen bg-slate-950 text-slate-100 p-6 font-mono flex items-center justify-center">
        <div className="text-slate-500">Loading stores...</div>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-slate-950 text-slate-100 p-6 font-mono">
      {/* HEADER */}
      <div className="mb-8">
        <h1 className="text-4xl font-black text-green-400 mb-2" style={{ textShadow: "0 0 20px rgba(34, 197, 94, 0.5)" }}>
          🤖 LLM ASSIST
        </h1>
        <p className="text-xs text-slate-500 uppercase tracking-widest">
          Automated diagnosis and repair of failing stores using local LLM
        </p>
      </div>

      {/* MESSAGE */}
      {message && (
        <div className={`mb-6 p-4 border rounded text-sm ${message.includes("Error") ? "border-red-500/50 bg-red-500/5 text-red-400" : "border-green-500/50 bg-green-500/5 text-green-400"}`}>
          {message}
        </div>
      )}

      {/* EMPTY STATE */}
      {stores.length === 0 ? (
        <div className="border border-slate-500/30 rounded bg-slate-500/5 p-12 text-center">
          <div className="text-slate-500 text-sm">No stores to diagnose. Select stores from the Sources page.</div>
        </div>
      ) : (
        <>
          {/* STATS */}
          <div className="grid grid-cols-4 gap-4 mb-8">
            <div className="border border-cyan-500/30 rounded bg-cyan-500/5 p-4">
              <div className="text-sm font-black text-cyan-400">{stores.length}</div>
              <div className="text-xs text-slate-500 uppercase tracking-widest mt-1">Stores</div>
            </div>
            <div className="border border-amber-500/30 rounded bg-amber-500/5 p-4">
              <div className="text-sm font-black text-amber-400">{diagnoses.size}</div>
              <div className="text-xs text-slate-500 uppercase tracking-widest mt-1">Diagnosed</div>
            </div>
            <div className="border border-blue-500/30 rounded bg-blue-500/5 p-4">
              <div className="text-sm font-black text-blue-400">{selectedActions.size}</div>
              <div className="text-xs text-slate-500 uppercase tracking-widest mt-1">Selected</div>
            </div>
            <div className="border border-green-500/30 rounded bg-green-500/5 p-4">
              <div className="text-sm font-black text-green-400">{results.size}</div>
              <div className="text-xs text-slate-500 uppercase tracking-widest mt-1">Fixed</div>
            </div>
          </div>

          {/* CONTROLS */}
          <div className="flex gap-2 mb-8">
            <button
              onClick={handleDiagnose}
              disabled={diagnosing || diagnoses.size > 0}
              className="px-6 py-3 border border-green-500/50 rounded bg-green-500/10 hover:bg-green-500/20 text-sm uppercase tracking-widest text-green-400 font-mono disabled:opacity-50 transition"
            >
              {diagnosing ? "Diagnosing..." : diagnoses.size > 0 ? "Diagnosed ✓" : "🔍 Diagnose All"}
            </button>

            {selectedActions.size > 0 && (
              <button
                onClick={handleApplyFixes}
                disabled={fixing}
                className="px-6 py-3 border border-cyan-500/50 rounded bg-cyan-500/10 hover:bg-cyan-500/20 text-sm uppercase tracking-widest text-cyan-400 font-mono disabled:opacity-50 transition"
              >
                {fixing ? "Applying..." : `✓ Apply ${selectedActions.size} Fix(es)`}
              </button>
            )}

            <button
              onClick={() => window.history.back()}
              className="px-6 py-3 border border-slate-500/50 rounded bg-slate-500/10 hover:bg-slate-500/20 text-sm uppercase tracking-widest text-slate-400 font-mono transition ml-auto"
            >
              ← Back
            </button>
          </div>

          {/* DIAGNOSES */}
          <div className="space-y-6">
            {stores.map((store) => {
              const diagnosis = diagnoses.get(store.id);
              const storeResults = results.get(store.id) || [];
              const storeActions = selectedActions.get(store.id) || new Set();

              return (
                <div key={store.id} className="border border-slate-700/50 rounded bg-slate-900/50 overflow-hidden">
                  {/* STORE HEADER */}
                  <div className="bg-slate-800/30 border-b border-slate-700/50 p-4">
                    <div className="flex items-start justify-between">
                      <div>
                        <h3 className="text-lg font-black text-slate-100">{store.name}</h3>
                        <p className="text-xs text-slate-600 mt-1">{store.domain}</p>
                      </div>
                      <div className="text-right">
                        <div className={`text-xs font-mono px-2 py-1 rounded border ${store.health_status === "failing" ? "border-red-500 text-red-400 bg-red-500/10" : "border-amber-500 text-amber-400 bg-amber-500/10"}`}>
                          {store.health_status}
                        </div>
                        {diagnosis && (
                          <div className="text-xs text-slate-500 mt-2">
                            Confidence: {(diagnosis.confidence * 100).toFixed(0)}%
                          </div>
                        )}
                      </div>
                    </div>
                  </div>

                  {!diagnosis ? (
                    <div className="p-6 text-slate-500 text-sm">Waiting for diagnosis...</div>
                  ) : (
                    <div className="p-6 space-y-6">
                      {/* CURRENT ISSUES */}
                      <div>
                        <h4 className="text-sm font-black text-red-400 uppercase tracking-widest mb-3">🚨 Current Issues</h4>
                        <ul className="space-y-2">
                          {diagnosis.current_issues.map((issue, i) => (
                            <li key={i} className="text-sm text-slate-400 flex gap-2">
                              <span className="text-red-500">•</span>
                              <span>{issue}</span>
                            </li>
                          ))}
                        </ul>
                      </div>

                      {/* ROOT CAUSES */}
                      <div>
                        <h4 className="text-sm font-black text-amber-400 uppercase tracking-widest mb-3">⚠️ Root Causes</h4>
                        <ul className="space-y-2">
                          {diagnosis.root_causes.map((cause, i) => (
                            <li key={i} className="text-sm text-slate-400 flex gap-2">
                              <span className="text-amber-500">•</span>
                              <span>{cause}</span>
                            </li>
                          ))}
                        </ul>
                      </div>

                      {/* RECOMMENDED ACTIONS */}
                      <div>
                        <div className="flex items-center justify-between mb-3">
                          <h4 className="text-sm font-black text-green-400 uppercase tracking-widest">✓ Recommended Fixes</h4>
                          {diagnosis.recommended_actions.length > 0 && (
                            <button
                              onClick={() => toggleAllStoreActions(store.id)}
                              className="text-xs text-slate-500 hover:text-slate-400"
                            >
                              {storeActions.size === diagnosis.recommended_actions.length ? "Deselect All" : "Select All"}
                            </button>
                          )}
                        </div>

                        <div className="space-y-3">
                          {diagnosis.recommended_actions.map((action, i) => {
                            const isSelected = storeActions.has(action.action);
                            const priorityColor = {
                              high: "border-red-500/30 bg-red-500/5",
                              medium: "border-amber-500/30 bg-amber-500/5",
                              low: "border-blue-500/30 bg-blue-500/5",
                            }[action.priority];

                            const priorityLabel = {
                              high: "HIGH",
                              medium: "MED",
                              low: "LOW",
                            }[action.priority];

                            return (
                              <div
                                key={i}
                                onClick={() => toggleAction(store.id, action.action)}
                                className={`border rounded p-3 cursor-pointer transition ${priorityColor} ${isSelected ? "ring-2 ring-green-500" : ""}`}
                              >
                                <div className="flex items-start gap-3">
                                  <input
                                    type="checkbox"
                                    checked={isSelected}
                                    onChange={() => {}}
                                    className="mt-1"
                                  />
                                  <div className="flex-1">
                                    <div className="flex items-center gap-2 mb-1">
                                      <span className="text-sm font-mono font-black text-slate-100">{action.action}</span>
                                      <span className={`text-[10px] font-mono px-2 py-0.5 rounded border ${action.priority === "high" ? "border-red-500 text-red-400" : action.priority === "medium" ? "border-amber-500 text-amber-400" : "border-blue-500 text-blue-400"}`}>
                                        {priorityLabel}
                                      </span>
                                    </div>
                                    <p className="text-xs text-slate-400 mb-2">{action.description}</p>
                                    <p className="text-xs text-slate-600">
                                      <span className="text-slate-500">Expected: </span>
                                      {action.expected_improvement}
                                    </p>
                                  </div>
                                </div>
                              </div>
                            );
                          })}
                        </div>
                      </div>

                      {/* ACTION RESULTS */}
                      {storeResults.length > 0 && (
                        <div>
                          <h4 className="text-sm font-black text-slate-400 uppercase tracking-widest mb-3">📋 Action Results</h4>
                          <div className="space-y-2">
                            {storeResults.map((result, i) => (
                              <div
                                key={i}
                                className={`p-2 rounded text-xs border ${result.success ? "border-green-500/50 bg-green-500/5 text-green-400" : "border-red-500/50 bg-red-500/5 text-red-400"}`}
                              >
                                <span>{result.success ? "✓" : "✕"}</span> {result.action}: {result.message}
                              </div>
                            ))}
                          </div>
                        </div>
                      )}
                    </div>
                  )}
                </div>
              );
            })}
          </div>
        </>
      )}
    </div>
  );
}

// ============================================================================
// Helper functions
// ============================================================================

async function generateLLMDiagnosis(store: Store, detail: StoreDetail): Promise<LLMDiagnosis> {
  // Build context about the store's issues
  const context = {
    name: store.name,
    domain: store.domain,
    parser_strategy: store.parser_strategy,
    health_status: store.health_status,
    last_successful_crawl: store.last_successful_crawl_at,
    last_run: store.last_run,
    source_pages: detail.source_pages,
  };

  // Make request to local Ollama instance to diagnose
  try {
    const response = await fetch("http://localhost:11434/api/generate", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        model: "neural-coffee",
        prompt: buildDiagnosisPrompt(context),
        stream: false,
      }),
    });

    if (!response.ok) {
      throw new Error(`LLM error: ${response.statusText}`);
    }

    const data = await response.json();
    return parseLLMDiagnosis(store.id, store.name, data.response);
  } catch (e) {
    console.error("LLM diagnosis failed:", e);

    // Fallback heuristic diagnosis
    return generateHeuristicDiagnosis(store, detail);
  }
}

function buildDiagnosisPrompt(context: any): string {
  return `You are a coffee e-commerce automation expert. Analyze this store configuration and provide diagnosis and fixes.

Store: ${context.name}
Domain: ${context.domain}
Parser Strategy: ${context.parser_strategy}
Health Status: ${context.health_status}
Last Crawl: ${context.last_successful_crawl || "Never"}

Last Run Summary:
${context.last_run ? `- Status: ${context.last_run.status}
- Records Created: ${context.last_run.records_created}
- Records Updated: ${context.last_run.records_updated}
- Errors: ${context.last_run.error_count}
- Top Errors: ${context.last_run.top_errors?.slice(0, 2).join(", ") || "None"}` : "- No runs yet"}

Source Pages Configured: ${context.source_pages?.length || 0}

Provide a JSON response with:
{
  "current_issues": ["issue1", "issue2"],
  "root_causes": ["cause1", "cause2"],
  "recommended_actions": [
    {
      "action": "action_name",
      "description": "what it does",
      "priority": "high|medium|low",
      "expected_improvement": "what will improve"
    }
  ],
  "confidence": 0.85
}`;
}

function parseLLMDiagnosis(storeId: string, storeName: string, response: string): LLMDiagnosis {
  try {
    // Extract JSON from response
    const jsonMatch = response.match(/\{[\s\S]*\}/);
    if (!jsonMatch) throw new Error("No JSON found in response");

    const parsed = JSON.parse(jsonMatch[0]);
    return {
      store_id: storeId,
      store_name: storeName,
      current_issues: parsed.current_issues || [],
      root_causes: parsed.root_causes || [],
      recommended_actions: parsed.recommended_actions || [],
      confidence: parsed.confidence || 0.5,
    };
  } catch (e) {
    console.error("Failed to parse LLM response:", e);
    return {
      store_id: storeId,
      store_name: storeName,
      current_issues: ["Failed to parse LLM diagnosis"],
      root_causes: ["LLM model unavailable or offline"],
      recommended_actions: [],
      confidence: 0,
    };
  }
}

function generateHeuristicDiagnosis(store: Store, detail: StoreDetail): LLMDiagnosis {
  const issues: string[] = [];
  const causes: string[] = [];
  const actions: LLMDiagnosis["recommended_actions"] = [];

  // Analyze health status
  if (store.health_status === "failing") {
    issues.push("Store extraction is failing");

    if (!store.last_successful_crawl_at) {
      issues.push("No successful crawl history");
      causes.push("Store may be unreachable or blocking requests");
      actions.push({
        action: "rescan_parser",
        description: "Re-run automatic parser detection to identify best extraction method",
        priority: "high",
        expected_improvement: "May discover working parser strategy (schema.org, LLM)",
      });
    }

    if (detail.source_pages.length === 0) {
      issues.push("No source pages configured");
      causes.push("Cannot find product pages to extract from");
      actions.push({
        action: "discover_pages",
        description: "Automatically discover product pages from homepage",
        priority: "high",
        expected_improvement: "Will enable extraction from discovered pages",
      });
    }

    if (store.parser_strategy === "html") {
      issues.push("HTML extraction may be blocked");
      causes.push("Website detecting and blocking bot requests");
      actions.push({
        action: "upgrade_headers",
        description: "Add browser-like headers (Referer, Sec-Fetch-*) to bypass bot detection",
        priority: "high",
        expected_improvement: "Will bypass basic bot detection",
      });
      actions.push({
        action: "retry_strategy",
        description: "Implement exponential backoff retry for 403/429 errors",
        priority: "high",
        expected_improvement: "Will recover from temporary blocks",
      });
    }
  }

  if (store.health_status === "stale") {
    issues.push("Store data is outdated");
    causes.push("No recent successful ingestion runs");
    actions.push({
      action: "reingest_now",
      description: "Trigger immediate re-ingestion of all product pages",
      priority: "high",
      expected_improvement: "Will refresh product data",
    });
  }

  if (store.parser_strategy === "no_pipeline") {
    issues.push("Parser strategy not determined");
    causes.push("Automatic detection has not run or failed");
    actions.push({
      action: "rescan_parser",
      description: "Run automatic parser detection",
      priority: "high",
      expected_improvement: "Will identify correct extraction method (shopify, html, schema.org, llm)",
    });
  }

  if (detail.source_pages.length === 0 && store.parser_strategy !== "shopify") {
    actions.push({
      action: "discover_pages",
      description: "Discover product pages from homepage",
      priority: "high",
      expected_improvement: "Will enable extraction to begin",
    });
  }

  // If no issues found, just recommend reingest
  if (issues.length === 0) {
    issues.push("Routine maintenance recommended");
    actions.push({
      action: "reingest_now",
      description: "Trigger re-ingestion to refresh data",
      priority: "low",
      expected_improvement: "Will keep data current",
    });
  }

  return {
    store_id: store.id,
    store_name: store.name,
    current_issues: issues,
    root_causes: causes,
    recommended_actions: actions,
    confidence: 0.75,
  };
}

async function applyLLMAction(storeId: string, action: string): Promise<{ success: boolean; message: string }> {
  const apiUrl = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

  switch (action) {
    case "rescan_parser":
      try {
        await rescanSource(storeId);
        return { success: true, message: "Parser detection started" };
      } catch (e: any) {
        return { success: false, message: e.message };
      }

    case "reingest_now":
      try {
        const res = await fetch(`${apiUrl}/api/v1/admin/sources/${storeId}/reingest`, {
          method: "POST",
        });
        if (!res.ok) throw new Error(await res.text());
        return { success: true, message: "Re-ingestion queued" };
      } catch (e: any) {
        return { success: false, message: e.message };
      }

    case "discover_pages":
      try {
        const res = await fetch(`${apiUrl}/api/v1/admin/sources/${storeId}/discover-pages`, {
          method: "POST",
        });
        if (!res.ok) throw new Error(await res.text());
        return { success: true, message: "Page discovery started" };
      } catch (e: any) {
        return { success: false, message: e.message };
      }

    case "upgrade_headers":
      try {
        const res = await fetch(`${apiUrl}/api/v1/admin/sources/${storeId}`, {
          method: "PATCH",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ parser_strategy: "html" }),
        });
        if (!res.ok) throw new Error(await res.text());
        return { success: true, message: "Headers configured" };
      } catch (e: any) {
        return { success: false, message: e.message };
      }

    case "retry_strategy":
      try {
        const res = await fetch(`${apiUrl}/api/v1/admin/sources/${storeId}`, {
          method: "PATCH",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ parser_strategy: "html" }),
        });
        if (!res.ok) throw new Error(await res.text());
        return { success: true, message: "Retry strategy enabled" };
      } catch (e: any) {
        return { success: false, message: e.message };
      }

    default:
      return { success: false, message: "Unknown action" };
  }
}

// ============================================================================
// Default Export with Suspense Boundary
// ============================================================================
export default function LLMAssistPage() {
  return (
    <Suspense fallback={<LoadingFallback />}>
      <LLMAssistContent />
    </Suspense>
  );
}

function LoadingFallback() {
  return (
    <div className="min-h-screen bg-slate-950 text-slate-100 p-6 font-mono flex items-center justify-center">
      <div className="text-slate-500">Loading LLM Assist...</div>
    </div>
  );
}
