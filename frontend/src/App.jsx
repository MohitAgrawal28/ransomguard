import { useState, useEffect, useCallback, useRef } from "react";

// ── CONFIG ────────────────────────────────────────────────────
const API_BASE = "http://127.0.0.1:5000";
const POLL_INTERVAL = 3000;

// ── ICONS (inline SVG) ────────────────────────────────────────
const Icon = {
  Shield: () => (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" className="w-5 h-5">
      <path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z"/>
    </svg>
  ),
  AlertTriangle: () => (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" className="w-5 h-5">
      <path d="m21.73 18-8-14a2 2 0 0 0-3.48 0l-8 14A2 2 0 0 0 4 21h16a2 2 0 0 0 1.73-3Z"/>
      <line x1="12" y1="9" x2="12" y2="13"/><line x1="12" y1="17" x2="12.01" y2="17"/>
    </svg>
  ),
  Activity: () => (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" className="w-5 h-5">
      <polyline points="22 12 18 12 15 21 9 3 6 12 2 12"/>
    </svg>
  ),
  Lock: () => (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" className="w-5 h-5">
      <rect x="3" y="11" width="18" height="11" rx="2" ry="2"/>
      <path d="M7 11V7a5 5 0 0 1 10 0v4"/>
    </svg>
  ),
  Cpu: () => (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" className="w-5 h-5">
      <rect x="4" y="4" width="16" height="16" rx="2"/><rect x="9" y="9" width="6" height="6"/>
      <line x1="9" y1="1" x2="9" y2="4"/><line x1="15" y1="1" x2="15" y2="4"/>
      <line x1="9" y1="20" x2="9" y2="23"/><line x1="15" y1="20" x2="15" y2="23"/>
      <line x1="20" y1="9" x2="23" y2="9"/><line x1="20" y1="14" x2="23" y2="14"/>
      <line x1="1" y1="9" x2="4" y2="9"/><line x1="1" y1="14" x2="4" y2="14"/>
    </svg>
  ),
  XCircle: () => (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" className="w-5 h-5">
      <circle cx="12" cy="12" r="10"/><line x1="15" y1="9" x2="9" y2="15"/>
      <line x1="9" y1="9" x2="15" y2="15"/>
    </svg>
  ),
  CheckCircle: () => (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" className="w-5 h-5">
      <path d="M22 11.08V12a10 10 0 1 1-5.93-9.14"/><polyline points="22 4 12 14.01 9 11.01"/>
    </svg>
  ),
  Database: () => (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" className="w-5 h-5">
      <ellipse cx="12" cy="5" rx="9" ry="3"/><path d="M21 12c0 1.66-4 3-9 3s-9-1.34-9-3"/>
      <path d="M3 5v14c0 1.66 4 3 9 3s9-1.34 9-3V5"/>
    </svg>
  ),
  Zap: () => (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" className="w-5 h-5">
      <polygon points="13 2 3 14 12 14 11 22 21 10 12 10 13 2"/>
    </svg>
  ),
};

// ── COMPONENTS ────────────────────────────────────────────────

function ProbabilityBar({ value, label }) {
  const pct = Math.round((value || 0) * 100);
  const color = pct > 70 ? "#ef4444" : pct > 40 ? "#f59e0b" : "#22c55e";
  return (
    <div className="space-y-1">
      <div style={{ display: "flex", justifyContent: "space-between", fontSize: "12px", color: "#94a3b8" }}>
        <span>{label}</span>
        <span style={{ color, fontWeight: 700 }}>{pct}%</span>
      </div>
      <div style={{ height: "6px", background: "#1e293b", borderRadius: "3px", overflow: "hidden" }}>
        <div style={{
          width: `${pct}%`, height: "100%", background: color,
          borderRadius: "3px", transition: "width 0.6s ease",
          boxShadow: `0 0 8px ${color}80`,
        }} />
      </div>
    </div>
  );
}

function StatCard({ icon: IconComp, label, value, sub, color = "#38bdf8", pulse = false }) {
  return (
    <div style={{
      background: "linear-gradient(135deg, #0f172a 0%, #1e293b 100%)",
      border: `1px solid ${color}30`,
      borderRadius: "12px",
      padding: "20px",
      position: "relative",
      overflow: "hidden",
    }}>
      <div style={{
        position: "absolute", top: 0, right: 0, width: "80px", height: "80px",
        background: `radial-gradient(circle, ${color}15 0%, transparent 70%)`,
      }} />
      <div style={{ display: "flex", alignItems: "center", gap: "10px", marginBottom: "12px" }}>
        <div style={{
          color, background: `${color}15`, padding: "8px", borderRadius: "8px",
          display: "flex", alignItems: "center",
          ...(pulse ? { animation: "pulse 2s infinite" } : {}),
        }}>
          <IconComp />
        </div>
        <span style={{ color: "#64748b", fontSize: "13px", fontWeight: 500 }}>{label}</span>
      </div>
      <div style={{ color: "#f1f5f9", fontSize: "28px", fontWeight: 800, letterSpacing: "-1px" }}>
        {value ?? "—"}
      </div>
      {sub && <div style={{ color: "#64748b", fontSize: "12px", marginTop: "4px" }}>{sub}</div>}
    </div>
  );
}

function AlertBadge({ level }) {
  const cfg = {
    ransomware: { bg: "#7f1d1d", border: "#ef4444", color: "#fca5a5", text: "RANSOMWARE" },
    suspicious: { bg: "#78350f", border: "#f59e0b", color: "#fcd34d", text: "SUSPICIOUS" },
    info:       { bg: "#1e3a5f", border: "#38bdf8", color: "#7dd3fc", text: "INFO" },
  }[level] || { bg: "#1e293b", border: "#475569", color: "#94a3b8", text: level?.toUpperCase() };
  return (
    <span style={{
      background: cfg.bg, border: `1px solid ${cfg.border}`, color: cfg.color,
      padding: "2px 8px", borderRadius: "4px", fontSize: "10px",
      fontWeight: 800, letterSpacing: "0.05em", fontFamily: "monospace",
    }}>{cfg.text}</span>
  );
}

function AlertRow({ alert, index }) {
  const isRansom = alert.type === "process_killed" || alert.ransomware_prob > 0.7;
  const level = isRansom ? "ransomware" : alert.ransomware_prob > 0.4 ? "suspicious" : "info";
  const ts = alert.timestamp ? new Date(alert.timestamp).toLocaleTimeString() : "—";
  return (
    <div style={{
      background: isRansom ? "linear-gradient(90deg, #7f1d1d20, transparent)" : "#0f172a",
      border: `1px solid ${isRansom ? "#ef444430" : "#1e293b"}`,
      borderRadius: "8px", padding: "12px 16px",
      display: "flex", alignItems: "center", gap: "12px",
      animation: index === 0 ? "fadeIn 0.4s ease" : "none",
    }}>
      <AlertBadge level={level} />
      <div style={{ flex: 1, minWidth: 0 }}>
        <div style={{ color: "#f1f5f9", fontSize: "13px", fontWeight: 600 }}>
          {alert.process_name || "Unknown Process"}
          <span style={{ color: "#64748b", fontWeight: 400, marginLeft: "8px" }}>
            PID {alert.pid || "—"}
          </span>
        </div>
        {alert.action_taken && (
          <div style={{ color: "#94a3b8", fontSize: "11px", marginTop: "2px" }}>
            Action: <span style={{ color: "#fca5a5" }}>{alert.action_taken}</span>
          </div>
        )}
      </div>
      {alert.ransomware_prob != null && (
        <div style={{ color: "#ef4444", fontWeight: 800, fontSize: "14px", fontFamily: "monospace" }}>
          {Math.round(alert.ransomware_prob * 100)}%
        </div>
      )}
      <div style={{ color: "#475569", fontSize: "11px", whiteSpace: "nowrap" }}>{ts}</div>
    </div>
  );
}

function PredictForm({ onResult }) {
  const [vals, setVals] = useState({
    file_write_count: 500, file_rename_count: 450,
    entropy_before: 4.2, entropy_after: 7.8, entropy_change: 3.6,
    process_execution_time: 12.0, api_call_frequency: 8000,
    file_access_rate: 35.0, extension_change_count: 400, encryption_indicator: 0.9,
  });
  const [loading, setLoading] = useState(false);

  const fields = [
    ["file_write_count", "File Write Count", 0, 10000],
    ["file_rename_count", "File Rename Count", 0, 5000],
    ["entropy_before", "Entropy Before", 0, 8],
    ["entropy_after", "Entropy After", 0, 8],
    ["entropy_change", "Entropy Change", 0, 8],
    ["process_execution_time", "Execution Time (s)", 0, 600],
    ["api_call_frequency", "API Call Frequency", 0, 100000],
    ["file_access_rate", "File Access Rate", 0, 200],
    ["extension_change_count", "Extension Changes", 0, 5000],
    ["encryption_indicator", "Encryption Indicator", 0, 1],
  ];

  const handleSubmit = async () => {
    setLoading(true);
    try {
      const r = await fetch(`${API_BASE}/predict`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(vals),
      });
      const data = await r.json();
      onResult(data.data);
    } catch {
      onResult({ error: "Cannot connect to backend. Start the Flask server." });
    }
    setLoading(false);
  };

  const loadPreset = (preset) => {
    if (preset === "ransomware") {
      setVals({ file_write_count: 2500, file_rename_count: 2400, entropy_before: 4.2,
        entropy_after: 7.9, entropy_change: 3.7, process_execution_time: 15.0,
        api_call_frequency: 25000, file_access_rate: 80.0, extension_change_count: 2000,
        encryption_indicator: 0.95 });
    } else {
      setVals({ file_write_count: 5, file_rename_count: 0, entropy_before: 4.2,
        entropy_after: 4.3, entropy_change: 0.1, process_execution_time: 120.0,
        api_call_frequency: 250, file_access_rate: 0.1, extension_change_count: 0,
        encryption_indicator: 0.02 });
    }
  };

  return (
    <div>
      <div style={{ display: "flex", gap: "8px", marginBottom: "16px" }}>
        <button onClick={() => loadPreset("ransomware")} style={{
          background: "#7f1d1d", border: "1px solid #ef4444", color: "#fca5a5",
          padding: "6px 14px", borderRadius: "6px", cursor: "pointer", fontSize: "12px", fontWeight: 700,
        }}>Load Ransomware Sample</button>
        <button onClick={() => loadPreset("benign")} style={{
          background: "#14532d", border: "1px solid #22c55e", color: "#86efac",
          padding: "6px 14px", borderRadius: "6px", cursor: "pointer", fontSize: "12px", fontWeight: 700,
        }}>Load Benign Sample</button>
      </div>
      <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "10px", marginBottom: "16px" }}>
        {fields.map(([key, label, min, max]) => (
          <div key={key}>
            <label style={{ color: "#94a3b8", fontSize: "11px", display: "block", marginBottom: "4px" }}>
              {label}
            </label>
            <input
              type="number" min={min} max={max} step="any"
              value={vals[key]}
              onChange={e => setVals(v => ({ ...v, [key]: parseFloat(e.target.value) || 0 }))}
              style={{
                width: "100%", background: "#0f172a", border: "1px solid #1e293b",
                borderRadius: "6px", padding: "6px 10px", color: "#f1f5f9",
                fontSize: "13px", outline: "none", boxSizing: "border-box",
              }}
            />
          </div>
        ))}
      </div>
      <button onClick={handleSubmit} disabled={loading} style={{
        width: "100%", background: loading ? "#1e293b" : "linear-gradient(135deg, #1d4ed8, #7c3aed)",
        color: "#fff", border: "none", borderRadius: "8px", padding: "12px",
        cursor: loading ? "not-allowed" : "pointer", fontWeight: 700, fontSize: "14px",
        letterSpacing: "0.05em",
      }}>
        {loading ? "Analyzing..." : "🔍 ANALYZE BEHAVIOR"}
      </button>
    </div>
  );
}

function PredictResult({ result }) {
  if (!result) return null;
  if (result.error) {
    return (
      <div style={{ background: "#1e293b", borderRadius: "8px", padding: "16px", marginTop: "16px",
        border: "1px solid #f59e0b30", color: "#fcd34d", fontSize: "13px" }}>
        ⚠️ {result.error}
      </div>
    );
  }
  const isRansom = result.label === "ransomware";
  const pct = Math.round((result.probability || 0) * 100);
  return (
    <div style={{
      marginTop: "16px", borderRadius: "10px", padding: "20px",
      background: isRansom
        ? "linear-gradient(135deg, #7f1d1d40, #0f172a)"
        : "linear-gradient(135deg, #14532d40, #0f172a)",
      border: `1px solid ${isRansom ? "#ef4444" : "#22c55e"}50`,
    }}>
      <div style={{ display: "flex", alignItems: "center", gap: "12px", marginBottom: "16px" }}>
        <div style={{
          fontSize: "36px", fontWeight: 900, color: isRansom ? "#ef4444" : "#22c55e",
          fontFamily: "monospace",
        }}>{pct}%</div>
        <div>
          <div style={{ color: isRansom ? "#fca5a5" : "#86efac", fontWeight: 800, fontSize: "16px" }}>
            {isRansom ? "🚨 RANSOMWARE DETECTED" : "✅ BENIGN BEHAVIOR"}
          </div>
          <div style={{ color: "#64748b", fontSize: "12px", marginTop: "4px" }}>
            Confidence: {Math.round((result.confidence || 0) * 100)}% | Threshold: {(result.threshold || 0.5) * 100}%
          </div>
        </div>
      </div>
      <ProbabilityBar value={result.probability} label="Ransomware Probability" />
    </div>
  );
}

// ── MAIN APP ──────────────────────────────────────────────────

export default function App() {
  const [tab, setTab] = useState("dashboard");
  const [status, setStatus] = useState(null);
  const [alerts, setAlerts] = useState([]);
  const [logs, setLogs] = useState([]);
  const [predictResult, setPredictResult] = useState(null);
  const [backendOk, setBackendOk] = useState(null);
  const [lastUpdate, setLastUpdate] = useState(null);
  const intervalRef = useRef(null);

  const fetchData = useCallback(async () => {
    try {
      const [monRes, alertRes] = await Promise.all([
        fetch(`${API_BASE}/monitor`).then(r => r.json()),
        fetch(`${API_BASE}/alerts?limit=20`).then(r => r.json()),
      ]);
      if (monRes.success)   setStatus(monRes.data);
      if (alertRes.success) setAlerts(alertRes.data.alerts || []);
      setBackendOk(true);
      setLastUpdate(new Date().toLocaleTimeString());
    } catch {
      setBackendOk(false);
    }
  }, []);

  const fetchLogs = useCallback(async () => {
    try {
      const r = await fetch(`${API_BASE}/logs?limit=30`).then(r => r.json());
      if (r.success) setLogs(r.data.logs || []);
    } catch {}
  }, []);

  useEffect(() => {
    fetchData();
    intervalRef.current = setInterval(fetchData, POLL_INTERVAL);
    return () => clearInterval(intervalRef.current);
  }, [fetchData]);

  useEffect(() => {
    if (tab === "logs") fetchLogs();
  }, [tab, fetchLogs]);

  const TABS = [
    { id: "dashboard", label: "Dashboard", icon: Icon.Shield },
    { id: "alerts",    label: "Alerts",    icon: Icon.AlertTriangle },
    { id: "predict",   label: "Predict",   icon: Icon.Zap },
    { id: "logs",      label: "Logs",      icon: Icon.Database },
  ];

  return (
    <div style={{
      minHeight: "100vh",
      background: "linear-gradient(160deg, #020617 0%, #0a1628 50%, #020617 100%)",
      fontFamily: "'IBM Plex Mono', 'Fira Code', 'Courier New', monospace",
      color: "#e2e8f0",
    }}>
      <style>{`
        @import url('https://fonts.googleapis.com/css2?family=IBM+Plex+Mono:wght@400;500;700&display=swap');
        * { box-sizing: border-box; }
        ::-webkit-scrollbar { width: 6px; }
        ::-webkit-scrollbar-track { background: #0f172a; }
        ::-webkit-scrollbar-thumb { background: #1e293b; border-radius: 3px; }
        @keyframes pulse { 0%,100%{opacity:1} 50%{opacity:0.5} }
        @keyframes fadeIn { from{opacity:0;transform:translateY(-8px)} to{opacity:1;transform:translateY(0)} }
        @keyframes scanline {
          0%{background-position:0 0} 100%{background-position:0 100px}
        }
        input:focus { border-color: #38bdf8 !important; }
      `}</style>

      {/* ── HEADER ── */}
      <div style={{
        borderBottom: "1px solid #0f172a",
        background: "rgba(2,6,23,0.9)", backdropFilter: "blur(10px)",
        position: "sticky", top: 0, zIndex: 100,
      }}>
        <div style={{ maxWidth: "1200px", margin: "0 auto", padding: "0 24px",
          display: "flex", alignItems: "center", height: "60px", gap: "16px" }}>
          <div style={{ display: "flex", alignItems: "center", gap: "10px" }}>
            <div style={{
              background: "linear-gradient(135deg, #ef4444, #7c3aed)",
              padding: "8px", borderRadius: "8px", color: "#fff", display: "flex",
            }}><Icon.Shield /></div>
            <div>
              <div style={{ fontWeight: 800, fontSize: "14px", letterSpacing: "0.1em", color: "#f1f5f9" }}>
                RАНСOMGUARD
              </div>
              <div style={{ fontSize: "10px", color: "#475569", letterSpacing: "0.05em" }}>
                BEHAVIORAL DETECTION ENGINE
              </div>
            </div>
          </div>

          <div style={{ flex: 1 }} />

          {/* Nav tabs */}
          {TABS.map(t => (
            <button key={t.id} onClick={() => setTab(t.id)} style={{
              background: tab === t.id ? "#1e293b" : "transparent",
              border: tab === t.id ? "1px solid #334155" : "1px solid transparent",
              color: tab === t.id ? "#f1f5f9" : "#475569",
              padding: "6px 14px", borderRadius: "6px", cursor: "pointer",
              fontSize: "12px", fontWeight: 600, display: "flex", alignItems: "center", gap: "6px",
              transition: "all 0.2s",
            }}>
              <t.icon /> {t.label}
            </button>
          ))}

          {/* Status indicator */}
          <div style={{ display: "flex", alignItems: "center", gap: "6px" }}>
            <div style={{
              width: "8px", height: "8px", borderRadius: "50%",
              background: backendOk === null ? "#f59e0b" : backendOk ? "#22c55e" : "#ef4444",
              boxShadow: `0 0 6px ${backendOk === null ? "#f59e0b" : backendOk ? "#22c55e" : "#ef4444"}`,
              animation: backendOk ? "pulse 2s infinite" : "none",
            }} />
            <span style={{ fontSize: "10px", color: "#64748b" }}>
              {backendOk === null ? "connecting" : backendOk ? "live" : "offline"}
            </span>
          </div>
        </div>
      </div>

      <div style={{ maxWidth: "1200px", margin: "0 auto", padding: "28px 24px" }}>

        {/* ── OFFLINE BANNER ── */}
        {backendOk === false && (
          <div style={{
            background: "#78350f30", border: "1px solid #f59e0b50",
            borderRadius: "10px", padding: "14px 18px", marginBottom: "20px",
            color: "#fcd34d", fontSize: "13px",
          }}>
            ⚠️ Backend offline. Start the Flask server: <code style={{ background: "#0f172a",
              padding: "2px 8px", borderRadius: "4px" }}>python backend/app.py</code>
          </div>
        )}

        {/* ── DASHBOARD TAB ── */}
        {tab === "dashboard" && (
          <div>
            <div style={{ marginBottom: "24px" }}>
              <h1 style={{ fontSize: "24px", fontWeight: 800, color: "#f1f5f9", margin: 0 }}>
                System Dashboard
              </h1>
              <p style={{ color: "#475569", fontSize: "13px", margin: "4px 0 0" }}>
                Real-time behavioral ransomware monitoring
                {lastUpdate && <span style={{ marginLeft: "12px" }}>· Updated {lastUpdate}</span>}
              </p>
            </div>

            {/* Stat cards */}
            <div style={{ display: "grid", gridTemplateColumns: "repeat(4, 1fr)", gap: "16px", marginBottom: "24px" }}>
              <StatCard icon={Icon.AlertTriangle} label="Detections"
                value={status?.ransomware_detections ?? "—"} color="#ef4444"
                pulse={status?.ransomware_detections > 0} />
              <StatCard icon={Icon.Activity} label="Total Predictions"
                value={status?.total_predictions ?? "—"} color="#38bdf8" />
              <StatCard icon={Icon.XCircle} label="Processes Killed"
                value={status?.processes_killed ?? "—"} color="#f59e0b" />
              <StatCard icon={Icon.Lock} label="Alerts Logged"
                value={status?.alert_count ?? "—"} color="#a855f7" />
            </div>

            {/* Status + Recent Alerts 2-col */}
            <div style={{ display: "grid", gridTemplateColumns: "1fr 1.5fr", gap: "20px" }}>
              {/* Engine status */}
              <div style={{
                background: "#0f172a", border: "1px solid #1e293b",
                borderRadius: "12px", padding: "20px",
              }}>
                <h3 style={{ color: "#94a3b8", fontSize: "12px", letterSpacing: "0.1em",
                  margin: "0 0 16px", textTransform: "uppercase" }}>Engine Status</h3>
                {[
                  ["Status",    status?.engine_status ?? "unknown"],
                  ["Watch Dir", status?.watch_directory?.replace(/^.*\//, "~/") ?? "—"],
                  ["Active PIDs", status?.active_pids ?? 0],
                  ["Model",     status?.model_meta ? "loaded" : "—"],
                  ["Threshold", status?.model_meta ? "—" : "—"],
                ].map(([k, v]) => (
                  <div key={k} style={{
                    display: "flex", justifyContent: "space-between",
                    padding: "8px 0", borderBottom: "1px solid #0f172a",
                    fontSize: "13px",
                  }}>
                    <span style={{ color: "#475569" }}>{k}</span>
                    <span style={{ color: "#94a3b8", fontFamily: "monospace" }}>{String(v)}</span>
                  </div>
                ))}
              </div>

              {/* Recent alerts */}
              <div style={{
                background: "#0f172a", border: "1px solid #1e293b",
                borderRadius: "12px", padding: "20px",
              }}>
                <h3 style={{ color: "#94a3b8", fontSize: "12px", letterSpacing: "0.1em",
                  margin: "0 0 16px", textTransform: "uppercase" }}>Recent Alerts</h3>
                {alerts.length === 0 ? (
                  <div style={{ color: "#22c55e", textAlign: "center", padding: "30px 0", fontSize: "13px" }}>
                    ✅ No ransomware activity detected
                  </div>
                ) : (
                  <div style={{ display: "flex", flexDirection: "column", gap: "8px", maxHeight: "280px", overflowY: "auto" }}>
                    {alerts.slice(-5).reverse().map((a, i) => <AlertRow key={i} alert={a} index={i} />)}
                  </div>
                )}
              </div>
            </div>
          </div>
        )}

        {/* ── ALERTS TAB ── */}
        {tab === "alerts" && (
          <div>
            <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "20px" }}>
              <h1 style={{ fontSize: "22px", fontWeight: 800, color: "#f1f5f9", margin: 0 }}>
                Alert Log
              </h1>
              <button onClick={async () => {
                await fetch(`${API_BASE}/alerts/clear`, { method: "DELETE" });
                setAlerts([]);
              }} style={{
                background: "#1e293b", border: "1px solid #334155", color: "#94a3b8",
                padding: "6px 14px", borderRadius: "6px", cursor: "pointer", fontSize: "12px",
              }}>Clear All</button>
            </div>
            {alerts.length === 0 ? (
              <div style={{ color: "#22c55e", textAlign: "center", padding: "60px", fontSize: "14px",
                background: "#0f172a", borderRadius: "12px", border: "1px solid #14532d40" }}>
                ✅ No ransomware alerts. System is clean.
              </div>
            ) : (
              <div style={{ display: "flex", flexDirection: "column", gap: "8px" }}>
                {[...alerts].reverse().map((a, i) => <AlertRow key={i} alert={a} index={i} />)}
              </div>
            )}
          </div>
        )}

        {/* ── PREDICT TAB ── */}
        {tab === "predict" && (
          <div>
            <div style={{ marginBottom: "20px" }}>
              <h1 style={{ fontSize: "22px", fontWeight: 800, color: "#f1f5f9", margin: 0 }}>
                Behavioral Analysis
              </h1>
              <p style={{ color: "#475569", fontSize: "13px", margin: "4px 0 0" }}>
                Submit behavioral features to the LSTM model for analysis
              </p>
            </div>
            <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "24px" }}>
              <div style={{ background: "#0f172a", border: "1px solid #1e293b",
                borderRadius: "12px", padding: "24px" }}>
                <h3 style={{ color: "#94a3b8", fontSize: "12px", letterSpacing: "0.1em",
                  margin: "0 0 16px", textTransform: "uppercase" }}>Input Features</h3>
                <PredictForm onResult={setPredictResult} />
              </div>
              <div style={{ background: "#0f172a", border: "1px solid #1e293b",
                borderRadius: "12px", padding: "24px" }}>
                <h3 style={{ color: "#94a3b8", fontSize: "12px", letterSpacing: "0.1em",
                  margin: "0 0 16px", textTransform: "uppercase" }}>Model Output</h3>
                {!predictResult ? (
                  <div style={{ color: "#334155", textAlign: "center", padding: "60px 0", fontSize: "13px" }}>
                    Submit features to see prediction
                  </div>
                ) : (
                  <PredictResult result={predictResult} />
                )}
              </div>
            </div>
          </div>
        )}

        {/* ── LOGS TAB ── */}
        {tab === "logs" && (
          <div>
            <h1 style={{ fontSize: "22px", fontWeight: 800, color: "#f1f5f9", marginBottom: "20px" }}>
              Attack Logs
            </h1>
            {logs.length === 0 ? (
              <div style={{ color: "#475569", textAlign: "center", padding: "60px",
                background: "#0f172a", borderRadius: "12px", border: "1px solid #1e293b",
                fontSize: "13px" }}>
                No attack logs found. Logs are written to <code>logs/attacks.jsonl</code>
              </div>
            ) : (
              <div style={{ display: "flex", flexDirection: "column", gap: "8px" }}>
                {[...logs].reverse().map((log, i) => (
                  <div key={i} style={{
                    background: "#0f172a", border: "1px solid #1e293b",
                    borderRadius: "8px", padding: "14px 16px", fontSize: "12px",
                    fontFamily: "monospace",
                  }}>
                    <div style={{ display: "flex", gap: "12px", marginBottom: "8px", flexWrap: "wrap" }}>
                      <AlertBadge level="ransomware" />
                      <span style={{ color: "#f1f5f9", fontWeight: 700 }}>{log.process_name}</span>
                      <span style={{ color: "#64748b" }}>PID {log.pid}</span>
                      <span style={{ color: "#ef4444" }}>
                        {Math.round((log.ransomware_prob || 0) * 100)}%
                      </span>
                      <span style={{ color: "#64748b", marginLeft: "auto" }}>
                        {log.timestamp ? new Date(log.timestamp).toLocaleString() : "—"}
                      </span>
                    </div>
                    <div style={{ color: "#475569" }}>
                      Action: <span style={{ color: "#fca5a5" }}>{log.action_taken}</span>
                      {log.snapshot && (
                        <span style={{ marginLeft: "16px" }}>
                          Writes: <span style={{ color: "#94a3b8" }}>{log.snapshot.file_write_count}</span>
                          {" "} Renames: <span style={{ color: "#94a3b8" }}>{log.snapshot.file_rename_count}</span>
                          {" "} Entropy Δ: <span style={{ color: "#94a3b8" }}>
                            {log.snapshot.entropy_change?.toFixed(2)}
                          </span>
                        </span>
                      )}
                    </div>
                  </div>
                ))}
              </div>
            )}
          </div>
        )}

      </div>
    </div>
  );
}
