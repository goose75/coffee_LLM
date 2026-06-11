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
  const [selectedStoreId, setSelectedStoreId] = useState<string | null>(null);
  const [searchQuery, setSearchQuery] = useState("");
  const [diagnosisStartTimes, setDiagnosisStartTimes] = useState<Map<string, number>>(new Map());
  const [diagnosisErrors, setDiagnosisErrors] = useState<Map<string, string>>(new Map());
  const [currentlyDiagnosingId, setCurrentlyDiagnosingId] = useState<string | null>(null);
  const [autoFixing, setAutoFixing] = useState(false);
  const [autoFixResults, setAutoFixResults] = useState<Map<string, ActionResult[]>>(new Map());

  // Debug: log when diagnosing changes
  useEffect(() => {
    console.log("DEBUG: diagnosing state changed to:", diagnosing);
  }, [diagnosing]);

  // Load stores
  useEffect(() => {
    const loadStores = async () => {
      try {
        if (storeIds.length === 0) {
          // Load stores needing healing (unknown, failing, stale status)
          const data = await getSources({
            health_status: "unknown",
            page_size: 50,
            active_only: true
          });
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

  // Filter stores based on search query
  const filteredStores = stores.filter(s =>
    s.name.toLowerCase().includes(searchQuery.toLowerCase()) ||
    s.domain.toLowerCase().includes(searchQuery.toLowerCase())
  );

  // Get stores to display
  const storesToDisplay = selectedStoreId
    ? filteredStores.filter(s => s.id === selectedStoreId)
    : filteredStores;

  // Diagnose stores
  const handleDiagnose = useCallback(async () => {
    console.log("DEBUG: handleDiagnose called, storesToDisplay:", storesToDisplay);
    if (storesToDisplay.length === 0) {
      console.log("DEBUG: No stores to display, returning early");
      return;
    }
    console.log("DEBUG: Setting diagnosing=true");
    setDiagnosing(true);
    setMessage(null);

    const startTimes = new Map<string, number>();
    const errors = new Map<string, string>();

    try {
      const newDiagnoses = new Map<string, LLMDiagnosis>();

      for (const store of storesToDisplay) {
        try {
          // Mark this store as currently being diagnosed
          setCurrentlyDiagnosingId(store.id);

          // Mark diagnosis start time
          startTimes.set(store.id, Date.now());
          setDiagnosisStartTimes(new Map(startTimes));

          // Get detailed store info
          const detail = await getSource(store.id);

          // Generate LLM diagnosis prompt
          const diagnosis = await generateLLMDiagnosis(store, detail);
          newDiagnoses.set(store.id, diagnosis);

          // Clear error for this store if it was previously errored
          errors.delete(store.id);
        } catch (e: any) {
          console.error(`Failed to diagnose ${store.name}:`, e);
          errors.set(store.id, e.message || "Diagnosis failed");
        }
      }

      setDiagnoses(newDiagnoses);
      setDiagnosisErrors(errors);
      setCurrentlyDiagnosingId(null);
      setMessage(`Diagnosed ${newDiagnoses.size} of ${storesToDisplay.length} store(s)${errors.size > 0 ? ` (${errors.size} failed)` : ""}`);

      // AUTO-FIX: Apply high-priority recommendations automatically
      console.log("DEBUG: Starting auto-fix of high-priority recommendations...");
      await applyAutoFixes(newDiagnoses);
    } catch (e: any) {
      setMessage(`Error: ${e.message}`);
      setCurrentlyDiagnosingId(null);
    } finally {
      setDiagnosing(false);
    }
  }, [storesToDisplay]);

  // AUTO-FIX: Apply high-priority recommendations automatically
  const applyAutoFixes = useCallback(async (diagnoses: Map<string, LLMDiagnosis>) => {
    console.log("DEBUG: applyAutoFixes called with", diagnoses.size, "diagnoses");
    setAutoFixing(true);
    setMessage(null);

    const autoFixResults = new Map<string, ActionResult[]>();

    try {
      for (const [storeId, diagnosis] of diagnoses) {
        const storeResults: ActionResult[] = [];

        // Find high-priority actions (confidence > 0.8)
        const highPriorityActions = diagnosis.recommended_actions.filter(
          a => a.priority === "high" && diagnosis.confidence > 0.8
        );

        console.log(`DEBUG: Store ${storeId} has ${highPriorityActions.length} high-priority actions`);

        if (highPriorityActions.length > 0) {
          for (const action of highPriorityActions) {
            try {
              console.log(`DEBUG: Auto-applying action: ${action.action}`);
              const result = await applyLLMAction(storeId, action.action);
              storeResults.push({
                action: action.action,
                success: result.success,
                message: result.message,
              });
            } catch (e: any) {
              storeResults.push({
                action: action.action,
                success: false,
                message: e.message,
              });
            }
          }
        }

        if (storeResults.length > 0) {
          autoFixResults.set(storeId, storeResults);
        }
      }

      setAutoFixResults(autoFixResults);

      // Update message with auto-fix summary
      const totalFixed = Array.from(autoFixResults.values()).reduce(
        (sum, results) => sum + results.filter(r => r.success).length,
        0
      );
      const totalAttempted = Array.from(autoFixResults.values()).reduce(
        (sum, results) => sum + results.length,
        0
      );

      if (totalAttempted > 0) {
        setMessage(
          `✓ Auto-fixed ${totalFixed}/${totalAttempted} high-priority issue(s)${totalFixed < totalAttempted ? ` (${totalAttempted - totalFixed} failed)` : ""}`
        );
      }

      console.log("DEBUG: Auto-fix complete");
    } catch (e: any) {
      console.error("DEBUG: Auto-fix error:", e);
      setMessage(`Auto-fix error: ${e.message}`);
    } finally {
      setAutoFixing(false);
    }
  }, []);

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
          <div className="text-slate-500 text-sm">No stores needing assistance found. All stores may be healthy. You can still select specific stores from the Sources page.</div>
        </div>
      ) : (
        <>
          {/* STORE SELECTOR */}
          <div className="mb-8 grid grid-cols-1 md:grid-cols-3 gap-4">
            <div>
              <label className="block text-xs uppercase tracking-widest text-slate-400 mb-2">Search Stores</label>
              <input
                type="text"
                placeholder="Search by name or domain..."
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
                className="w-full px-3 py-2 border border-slate-600 rounded bg-slate-900 text-slate-100 text-sm focus:outline-none focus:border-cyan-500"
              />
            </div>
            <div>
              <label className="block text-xs uppercase tracking-widest text-slate-400 mb-2">Select Store</label>
              <select
                value={selectedStoreId || ""}
                onChange={(e) => setSelectedStoreId(e.target.value || null)}
                className="w-full px-3 py-2 border border-slate-600 rounded bg-slate-900 text-slate-100 text-sm focus:outline-none focus:border-cyan-500"
              >
                <option value="">All Stores ({filteredStores.length})</option>
                {filteredStores.map(store => (
                  <option key={store.id} value={store.id}>
                    {store.name} ({store.domain})
                  </option>
                ))}
              </select>
            </div>
            <div className="flex items-end">
              <button
                onClick={() => {
                  setSearchQuery("");
                  setSelectedStoreId(null);
                }}
                className="w-full px-3 py-2 border border-slate-600 rounded bg-slate-900 hover:bg-slate-800 text-slate-400 hover:text-slate-300 text-sm uppercase tracking-widest transition"
              >
                Clear Filters
              </button>
            </div>
          </div>

          {/* STATS */}
          <div className="grid grid-cols-4 gap-4 mb-8">
            <div className="border border-cyan-500/30 rounded bg-cyan-500/5 p-4">
              <div className="text-sm font-black text-cyan-400">{storesToDisplay.length}</div>
              <div className="text-xs text-slate-500 uppercase tracking-widest mt-1">Showing</div>
              {storesToDisplay.length !== stores.length && (
                <div className="text-xs text-slate-600 mt-1">of {stores.length} total</div>
              )}
            </div>
            <div className="border border-amber-500/30 rounded bg-amber-500/5 p-4">
              <div className="text-sm font-black text-amber-400">
                {storesToDisplay.filter(s => diagnoses.has(s.id)).length}
              </div>
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
              disabled={diagnosing || autoFixing || diagnoses.size > 0}
              className="px-6 py-3 border border-green-500/50 rounded bg-green-500/10 hover:bg-green-500/20 text-sm uppercase tracking-widest text-green-400 font-mono disabled:opacity-50 transition"
            >
              {autoFixing ? "Auto-fixing..." : diagnosing ? "Diagnosing..." : diagnoses.size > 0 ? "Diagnosed ✓" : "🔍 Diagnose All"}
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

          {/* DEBUG INFO */}
          <div className="mb-6 p-4 border border-slate-600/30 rounded bg-slate-900/30 text-xs text-slate-500 font-mono">
            <div>stores.length: {stores.length}</div>
            <div>storesToDisplay.length: {storesToDisplay.length}</div>
            <div>diagnosing: {String(diagnosing)}</div>
            <div>currentlyDiagnosingId: {currentlyDiagnosingId || "null"}</div>
            <div>diagnoses.size: {diagnoses.size}</div>
            <div>selectedStoreId: {selectedStoreId || "null"}</div>
          </div>

          {/* QUEUE STATUS */}
          {diagnosing && (
            <div className="border border-cyan-500/30 rounded bg-cyan-500/5 p-6 mb-8">
              <div className="text-sm font-black uppercase tracking-widest text-cyan-400 mb-4">
                📋 Diagnosis Queue Status
              </div>

              <div className="grid grid-cols-4 gap-4 mb-6">
                <div className="border border-cyan-500/30 rounded p-3 bg-cyan-500/10">
                  <div className="text-2xl font-black text-cyan-400">{storesToDisplay.length}</div>
                  <div className="text-xs text-cyan-600 uppercase tracking-widest mt-1">Total Queued</div>
                </div>
                <div className="border border-blue-500/30 rounded p-3 bg-blue-500/10">
                  <div className="text-2xl font-black text-blue-400">
                    {storesToDisplay.filter(s => diagnoses.has(s.id)).length}
                  </div>
                  <div className="text-xs text-blue-600 uppercase tracking-widest mt-1">Completed</div>
                </div>
                <div className="border border-amber-500/30 rounded p-3 bg-amber-500/10">
                  <div className="text-2xl font-black text-amber-400">
                    {currentlyDiagnosingId ? 1 : 0}
                  </div>
                  <div className="text-xs text-amber-600 uppercase tracking-widest mt-1">In Progress</div>
                </div>
                <div className="border border-green-500/30 rounded p-3 bg-green-500/10">
                  <div className="text-2xl font-black text-green-400">
                    {storesToDisplay.filter(s => !diagnoses.has(s.id) && s.id !== currentlyDiagnosingId).length}
                  </div>
                  <div className="text-xs text-green-600 uppercase tracking-widest mt-1">Pending</div>
                </div>
              </div>

              {/* Currently Diagnosing */}
              {currentlyDiagnosingId && (
                <div className="mb-4">
                  <div className="text-xs uppercase tracking-widest text-slate-400 mb-2">Currently Diagnosing</div>
                  {storesToDisplay.find(s => s.id === currentlyDiagnosingId) && (
                    <div className="border border-amber-500/50 rounded p-4 bg-amber-500/10">
                      <div className="flex items-center gap-3">
                        <div className="inline-flex gap-1">
                          <span className="inline-block w-2 h-2 rounded-full bg-amber-400 animate-bounce" style={{ animationDelay: "0s" }} />
                          <span className="inline-block w-2 h-2 rounded-full bg-amber-400 animate-bounce" style={{ animationDelay: "0.2s" }} />
                          <span className="inline-block w-2 h-2 rounded-full bg-amber-400 animate-bounce" style={{ animationDelay: "0.4s" }} />
                        </div>
                        <div className="flex-1">
                          <div className="font-black text-amber-400">
                            {storesToDisplay.find(s => s.id === currentlyDiagnosingId)?.name}
                          </div>
                          <div className="text-xs text-amber-300 mt-1">
                            {storesToDisplay.find(s => s.id === currentlyDiagnosingId)?.domain}
                          </div>
                        </div>
                      </div>
                    </div>
                  )}
                </div>
              )}

              {/* Next in Queue */}
              {storesToDisplay.filter(s => !diagnoses.has(s.id) && s.id !== currentlyDiagnosingId).length > 0 && (
                <div>
                  <div className="text-xs uppercase tracking-widest text-slate-400 mb-2">
                    Next in Queue (Up to 3)
                  </div>
                  <div className="space-y-2">
                    {storesToDisplay
                      .filter(s => !diagnoses.has(s.id) && s.id !== currentlyDiagnosingId)
                      .slice(0, 3)
                      .map((store, index) => (
                        <div key={store.id} className="border border-slate-600 rounded p-3 bg-slate-900/50">
                          <div className="flex items-center gap-3">
                            <div className="text-xs font-black text-slate-500 bg-slate-700 rounded-full w-6 h-6 flex items-center justify-center">
                              {index + 1}
                            </div>
                            <div className="flex-1 min-w-0">
                              <div className="text-sm font-mono text-slate-300 truncate">{store.name}</div>
                              <div className="text-xs text-slate-600 truncate">{store.domain}</div>
                            </div>
                          </div>
                        </div>
                      ))}
                  </div>
                </div>
              )}
            </div>
          )}

          {/* DIAGNOSES */}
          <div className="space-y-6">
            {storesToDisplay.length === 0 && searchQuery ? (
              <div className="border border-slate-500/30 rounded bg-slate-500/5 p-6 text-center">
                <div className="text-slate-500 text-sm">No stores match your search: "{searchQuery}"</div>
              </div>
            ) : (
              storesToDisplay.map((store) => {
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

                  <>
                    <div className="px-6 pt-6">
                      <DiagnosisStatus
                        storeId={store.id}
                        storeName={store.name}
                        diagnosis={diagnosis}
                        diagnosing={diagnosing}
                        error={diagnosisErrors.get(store.id)}
                        startTime={diagnosisStartTimes.get(store.id)}
                      />
                    </div>

                    {diagnosis && (
                    <div className="p-6 space-y-6 border-t border-slate-700/50">
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
                            const wasAutoApplied = autoFixResults.get(store.id)?.some(r => r.action === action.action) ?? false;
                            const autoApplyResult = autoFixResults.get(store.id)?.find(r => r.action === action.action);

                            const priorityColor = wasAutoApplied
                              ? "border-green-500/50 bg-green-500/10"
                              : {
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
                                onClick={() => !wasAutoApplied && toggleAction(store.id, action.action)}
                                className={`border rounded p-3 ${wasAutoApplied ? "" : "cursor-pointer"} transition ${priorityColor} ${isSelected && !wasAutoApplied ? "ring-2 ring-green-500" : ""}`}
                              >
                                <div className="flex items-start gap-3">
                                  <input
                                    type="checkbox"
                                    checked={isSelected || wasAutoApplied}
                                    disabled={wasAutoApplied}
                                    onChange={() => {}}
                                    className="mt-1"
                                  />
                                  <div className="flex-1">
                                    <div className="flex items-center gap-2 mb-1">
                                      <span className="text-sm font-mono font-black text-slate-100">
                                        {wasAutoApplied && "✓ "}{action.action}
                                      </span>
                                      <span className={`text-[10px] font-mono px-2 py-0.5 rounded border ${wasAutoApplied ? "border-green-500 text-green-400" : action.priority === "high" ? "border-red-500 text-red-400" : action.priority === "medium" ? "border-amber-500 text-amber-400" : "border-blue-500 text-blue-400"}`}>
                                        {wasAutoApplied ? "AUTO-APPLIED" : priorityLabel}
                                      </span>
                                      {wasAutoApplied && autoApplyResult && (
                                        <span className={`text-[10px] font-mono px-2 py-0.5 rounded border ${autoApplyResult.success ? "border-green-500 text-green-400" : "border-red-500 text-red-400"}`}>
                                          {autoApplyResult.success ? "SUCCESS" : "FAILED"}
                                        </span>
                                      )}
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
                      {(storeResults.length > 0 || autoFixResults.has(store.id)) && (
                        <div>
                          <h4 className="text-sm font-black text-slate-400 uppercase tracking-widest mb-3">📋 Action Results</h4>
                          <div className="space-y-2">
                            {/* Auto-applied results */}
                            {autoFixResults.get(store.id)?.map((result, i) => (
                              <div
                                key={`auto-${i}`}
                                className={`p-2 rounded text-xs border ${result.success ? "border-green-500/50 bg-green-500/5 text-green-400" : "border-red-500/50 bg-red-500/5 text-red-400"}`}
                              >
                                <span>{result.success ? "✓" : "✕"}</span> [AUTO] {result.action}: {result.message}
                              </div>
                            ))}
                            {/* Manual results */}
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
                  </>
                </div>
              );
              })
            )}
          </div>
        </>
      )}
    </div>
  );
}

// ============================================================================
// Helper Components
// ============================================================================

function DiagnosisStatus({
  storeId,
  storeName,
  diagnosis,
  diagnosing,
  error,
  startTime,
}: {
  storeId: string;
  storeName: string;
  diagnosis: LLMDiagnosis | undefined;
  diagnosing: boolean;
  error?: string;
  startTime?: number;
}) {
  const [elapsed, setElapsed] = useState(0);

  useEffect(() => {
    if (!diagnosing || !startTime) return;

    const interval = setInterval(() => {
      setElapsed(Math.floor((Date.now() - startTime) / 1000));
    }, 100);

    return () => clearInterval(interval);
  }, [diagnosing, startTime]);

  if (error) {
    return (
      <div className="p-6 border-l-4 border-red-500 bg-red-500/10 rounded">
        <div className="flex items-start gap-3">
          <span className="text-red-400 text-xl mt-0.5">✗</span>
          <div className="flex-1">
            <div className="text-sm font-black text-red-400 uppercase tracking-widest">Diagnosis Failed</div>
            <div className="text-xs text-red-300 mt-2">{error}</div>
          </div>
        </div>
      </div>
    );
  }

  if (diagnosing && startTime) {
    return (
      <div className="p-6 border-l-4 border-cyan-500 bg-cyan-500/10 rounded">
        <div className="flex items-start gap-3">
          <div className="inline-flex gap-1 mt-0.5">
            <span className="inline-block w-1.5 h-1.5 rounded-full bg-cyan-400 animate-bounce" style={{ animationDelay: "0s" }} />
            <span className="inline-block w-1.5 h-1.5 rounded-full bg-cyan-400 animate-bounce" style={{ animationDelay: "0.2s" }} />
            <span className="inline-block w-1.5 h-1.5 rounded-full bg-cyan-400 animate-bounce" style={{ animationDelay: "0.4s" }} />
          </div>
          <div className="flex-1">
            <div className="text-sm font-black text-cyan-400 uppercase tracking-widest">
              Diagnosing... {elapsed}s
            </div>
            <div className="text-xs text-cyan-300 mt-1">
              Analyzing store configuration with Ollama LLM
            </div>
          </div>
        </div>
      </div>
    );
  }

  if (diagnosis) {
    return (
      <div className="p-6 border-l-4 border-green-500 bg-green-500/10 rounded">
        <div className="flex items-start gap-3">
          <span className="text-green-400 text-xl mt-0.5">✓</span>
          <div className="flex-1">
            <div className="text-sm font-black text-green-400 uppercase tracking-widest">
              Diagnosis Complete ({elapsed}s)
            </div>
            <div className="text-xs text-green-300 mt-1">
              Confidence: {(diagnosis.confidence * 100).toFixed(0)}% • Found {diagnosis.recommended_actions.length} recommended action(s)
            </div>
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className="p-6 border-l-4 border-amber-500 bg-amber-500/10 rounded">
      <div className="flex items-start gap-3">
        <span className="text-amber-400 text-xl mt-0.5">⏱</span>
        <div className="flex-1">
          <div className="text-sm font-black text-amber-400 uppercase tracking-widest">
            Ready to Diagnose
          </div>
          <div className="text-xs text-amber-300 mt-1">
            Click "🔍 Diagnose All" button above to start LLM analysis
          </div>
        </div>
      </div>
    </div>
  );
}

// ============================================================================
// Parser Testing & Selection
// ============================================================================

interface ParserScore {
  parser: string;
  score: number;
  confidence: number;
  status: string;
  reason: string;
}

async function testParsersOnStore(store: Store, detail: StoreDetail): Promise<ParserScore[]> {
  // Test each parser (html, schema_org, llm) and rank by extraction quality

  const scores: ParserScore[] = [];

  // Skip testing if no source pages
  if (!detail.source_pages || detail.source_pages.length === 0) {
    return [];
  }

  // Use first source page for testing
  const testPage = detail.source_pages[0];
  const apiUrl = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

  try {
    // Test each parser
    for (const parser of ["html", "schema_org", "llm"]) {
      try {
        // Call extraction API with specific parser
        const response = await fetch(
          `${apiUrl}/api/v1/admin/test-parser?store_id=${store.id}&parser=${parser}&url=${encodeURIComponent(testPage.url)}`,
          { method: "POST" }
        );

        if (response.ok) {
          const result = await response.json();

          // Score based on: status (40%) + confidence (40%) + field count (20%)
          const statusScore = result.status === "valid" ? 1.0 : result.status === "partial" ? 0.5 : 0.0;
          const confidenceScore = result.confidence || 0;
          const fieldScore = (result.fields_extracted || 0) / 7; // Max 7 fields for coffee

          const totalScore = (statusScore * 0.4) + (confidenceScore * 0.4) + Math.min(fieldScore, 1.0) * 0.2;

          scores.push({
            parser,
            score: totalScore,
            confidence: result.confidence || 0,
            status: result.status || "unknown",
            reason: result.extraction_summary || "No data extracted",
          });
        }
      } catch (e: any) {
        // Parser test failed, assign low score
        console.log(`DEBUG: Parser ${parser} test failed:`, e.message);
        scores.push({
          parser,
          score: 0,
          confidence: 0,
          status: "error",
          reason: `Test failed: ${e.message}`,
        });
      }
    }
  } catch (e) {
    console.error("Parser testing error:", e);
  }

  // Sort by score descending
  return scores.sort((a, b) => b.score - a.score);
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

    // Fallback heuristic diagnosis with PARSER TESTING
    const diagnosis = generateHeuristicDiagnosis(store, detail);

    // Test parsers and add recommendation if extraction is failing
    if (diagnosis.current_issues.length > 0) {
      try {
        console.log(`DEBUG: Testing parsers for ${store.name}...`);
        const parserScores = await testParsersOnStore(store, detail);

        if (parserScores.length > 0 && parserScores[0].score > 0) {
          const bestParser = parserScores[0];
          const others = parserScores.slice(1);

          console.log(`DEBUG: Best parser for ${store.name}: ${bestParser.parser} (score: ${bestParser.score.toFixed(2)})`);

          // Add parser switch recommendation if current parser isn't the best
          if (bestParser.parser !== store.parser_strategy) {
            diagnosis.recommended_actions.unshift({
              action: `switch_to_${bestParser.parser}`,
              description: `Switch to ${bestParser.parser} parser (scored ${(bestParser.score * 100).toFixed(0)}% vs current ${store.parser_strategy})`,
              priority: "high",
              expected_improvement: `${bestParser.parser} extraction will work better for this site's structure`,
            });
          }
        }
      } catch (e) {
        console.error("Parser testing error:", e);
        // Continue with normal diagnosis if testing fails
      }
    }

    return diagnosis;
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
  if (store.health_status === "failing" || store.health_status === "unknown") {
    issues.push("Store extraction needs improvement");

    if (!store.last_successful_crawl_at) {
      issues.push("No successful extraction history");
      causes.push("Current parser strategy may not be optimized for this site");
      actions.push({
        action: "rescan_parser",
        description: "Test multiple parsers and select best performing one for this site",
        priority: "high",
        expected_improvement: "Identifies optimal extraction method (LLM, schema.org, or HTML rules)",
      });
    }

    if (detail.source_pages.length === 0) {
      issues.push("No source pages configured");
      causes.push("Cannot find product pages to extract from");
      actions.push({
        action: "reingest_now",
        description: "Trigger re-ingestion to discover and extract from pages",
        priority: "high",
        expected_improvement: "Will attempt to extract from any available pages",
      });
    }

    if (store.parser_strategy === "html") {
      issues.push("HTML extraction may be blocked");
      causes.push("Website detecting and blocking bot requests");
      actions.push({
        action: "reingest_now",
        description: "Re-attempt ingestion with current configuration",
        priority: "high",
        expected_improvement: "Will retry extraction from configured pages",
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
      action: "rescan_parser",
      description: "Re-run parser detection to find correct extraction method",
      priority: "high",
      expected_improvement: "May identify alternative parser that works better",
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
      // Handle dynamic parser switching (switch_to_html, switch_to_schema_org, switch_to_llm)
      if (action.startsWith("switch_to_")) {
        try {
          const newParser = action.replace("switch_to_", "");
          console.log(`DEBUG: Switching ${storeId} to ${newParser} parser`);

          // Update parser strategy
          const patchRes = await fetch(`${apiUrl}/api/v1/admin/sources/${storeId}?parser_strategy=${newParser}`, {
            method: "PATCH",
          });
          if (!patchRes.ok) throw new Error(await patchRes.text());

          // Trigger re-ingestion with new parser
          const reingestRes = await fetch(`${apiUrl}/api/v1/admin/sources/${storeId}/reingest`, {
            method: "POST",
          });
          if (!reingestRes.ok) throw new Error(await reingestRes.text());

          return {
            success: true,
            message: `Switched to ${newParser} parser and queued re-ingestion`,
          };
        } catch (e: any) {
          return { success: false, message: e.message };
        }
      }
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
