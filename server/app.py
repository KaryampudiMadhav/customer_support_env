# Copyright (c) Meta Platforms, Inc. and affiliates.
# All rights reserved.
#
# This source code is licensed under the BSD-style license found in the
# LICENSE file in the root directory of this source tree.

"""
FastAPI application for the Customersupportenv Environment.

This module creates an HTTP server that exposes the CustomersupportenvEnvironment
over HTTP and WebSocket endpoints, compatible with EnvClient.

Endpoints:
    - POST /reset: Reset the environment
    - POST /step: Execute an action
    - GET /state: Get current environment state
    - GET /schema: Get action/observation schemas
    - WS /ws: WebSocket endpoint for persistent sessions

Usage:
    # Development (with auto-reload):
    uvicorn server.app:app --reload --host 0.0.0.0 --port 8000

    # Production:
    uvicorn server.app:app --host 0.0.0.0 --port 8000 --workers 4

    # Or run directly:
    python -m server.app
"""

import sys
import os

# Add root directory to sys.path to allow importing models and server modules
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from fastapi.responses import HTMLResponse

try:
    from openenv.core.env_server.http_server import create_app
except Exception as e:  # pragma: no cover
    raise ImportError(
        "openenv is required for the web interface. Install dependencies with '\n    uv sync\n'"
    ) from e

try:
    from models import CustomersupportenvAction, CustomersupportenvObservation
    from server.customersupportenv_environment import CustomersupportenvEnvironment
except (ModuleNotFoundError, ImportError):
    from ..models import CustomersupportenvAction, CustomersupportenvObservation
    from .customersupportenv_environment import CustomersupportenvEnvironment


# Create the app with web interface and README integration
app = create_app(
    CustomersupportenvEnvironment,
    CustomersupportenvAction,
    CustomersupportenvObservation,
    env_name="customersupportenv",
    max_concurrent_envs=1,  # increase this number to allow more concurrent WebSocket sessions
)


UI_HTML = """<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>Customer Support Command Center</title>
  <style>
    :root {
      --bg: #0f172a;
      --surface: #1e293b;
      --border: #334155;
      --text: #f8fafc;
      --muted: #94a3b8;
      --accent: #3b82f6;
      --exec: #f59e0b;
      --exec-hover: #d97706;
      --hint-bg: #8b5cf61a;
      --hint-border: #8b5cf680;
      --card-blue: #2563eb;
      --card-orange: #ea580c;
      --card-green: #16a34a;
      --card-grey: #475569;
      --danger: #ef4444;
      --mono: ui-monospace, "Cascadia Code", "SF Mono", Menlo, monospace;
    }
    * { box-sizing: border-box; }
    html { color-scheme: dark; }
    body {
      margin: 0;
      min-height: 100vh;
      font-family: system-ui, -apple-system, Segoe UI, Roboto, sans-serif;
      background: var(--bg);
      color: var(--text);
      line-height: 1.45;
    }
    .wrap { max-width: 1600px; margin: 0 auto; padding: 1.5rem 2rem 3rem; display: flex; flex-direction: column; gap: 1.5rem; }
    .page-head { display: flex; align-items: center; justify-content: space-between; border-bottom: 1px solid var(--border); padding-bottom: 1rem; }
    h1 { font-size: 1.5rem; font-weight: 700; margin: 0; letter-spacing: -0.02em; }
    .page-head-text p { color: var(--muted); font-size: 0.9rem; margin: 0.5rem 0 0; }
    .metrics { display: grid; grid-template-columns: repeat(4, 1fr); gap: 1rem; width: 100%; }
    .metric { background: var(--surface); border: 1px solid var(--border); border-radius: 12px; padding: 1.25rem; display: flex; flex-direction: column; gap: 0.5rem; }
    .metric .m-label { font-size: 0.75rem; text-transform: uppercase; color: var(--muted); letter-spacing: 0.05em; font-weight: 600; }
    .metric .m-val { font-size: 1.75rem; font-weight: 700; font-variant-numeric: tabular-nums; }
    .metric.blue .m-val { color: #60a5fa; }
    .metric.orange .m-val { color: #fb923c; }
    .metric.green .m-val { color: #4ade80; }
    .metric.grey .m-val { color: #cbd5e1; }

    .main-grid { display: grid; grid-template-columns: 350px 1fr 350px; gap: 1.5rem; align-items: start; }

    .panel { background: var(--surface); border: 1px solid var(--border); border-radius: 12px; display: flex; flex-direction: column; overflow: hidden; }
    .panel-header { background: #0f172ab3; padding: 1rem; border-bottom: 1px solid var(--border); font-weight: 600; font-size: 0.95rem; }
    .panel-body { padding: 1rem; }

    label { font-size: 0.8rem; color: var(--muted); display: block; margin-bottom: 0.4rem; font-weight: 500; }
    select, input[type="text"], input[type="number"], textarea { width: 100%; padding: 0.6rem 0.75rem; border-radius: 8px; border: 1px solid var(--border); background: #0f172a; color: var(--text); font-size: 0.9rem; transition: border-color 0.2s; }
    select:focus, input:focus, textarea:focus { outline: none; border-color: var(--accent); }
    textarea { font-family: var(--mono); font-size: 0.85rem; min-height: 80px; resize: vertical; }
    .form-grid { display: grid; gap: 1rem; margin-top: 1rem; }
    .form-row { display: grid; grid-template-columns: 1fr 1fr; gap: 1rem; }

    button { border: none; padding: 0.75rem 1.25rem; border-radius: 8px; font-size: 0.85rem; font-weight: 600; cursor: pointer; text-transform: uppercase; letter-spacing: 0.05em; transition: all 0.2s; }
    button.exec { background: var(--exec); color: #fff; width: 100%; margin-top: 1rem; }
    button.exec:hover:not(:disabled) { background: var(--exec-hover); transform: translateY(-1px); }
    button.exec:disabled { background: var(--border); color: var(--muted); cursor: not-allowed; transform: none; }
    button.secondary { background: var(--border); color: var(--text); }
    button.secondary:hover { background: #475569; }
    .action-bar { display: flex; gap: 0.5rem; margin-top: 1rem; }
    .action-bar button { flex: 1; padding: 0.6rem 0.5rem; font-size: 0.75rem; }

    .timeline-scroll { max-height: calc(100vh - 250px); overflow-y: auto; padding-right: 0.5rem; }
    .timeline-list { display: flex; flex-direction: column; gap: 0.75rem; }
    .timeline-item { background: #0f172a; border: 1px solid var(--border); border-radius: 8px; padding: 0.75rem; }
    .tl-header { display: flex; justify-content: space-between; margin-bottom: 0.5rem; align-items: center; }
    .tl-step-num { font-size: 0.75rem; font-weight: 600; color: var(--muted); padding: 0.2rem 0.5rem; background: var(--surface); border-radius: 12px; }
    .tl-action-name { font-size: 0.85rem; color: var(--accent); font-weight: 600; text-transform: uppercase; }
    .tl-reward { font-weight: 700; font-variant-numeric: tabular-nums; font-size: 0.9rem; }
    .tl-reward.pos { color: var(--card-green); }
    .tl-reward.neg { color: var(--danger); }
    .tl-feedback { color: #cbd5e1; font-size: 0.8rem; line-height: 1.5; border-top: 1px dashed var(--border); padding-top: 0.5rem; margin-top: 0.5rem; }

    .ticket-pills { display: flex; flex-wrap: wrap; gap: 0.5rem; margin-bottom: 1.5rem; }
    .pill { display: flex; align-items: center; gap: 0.5rem; padding: 0.4rem 0.75rem; background: #0f172a; border: 1px solid var(--border); border-radius: 6px; font-size: 0.8rem; }
    .pill kbd { color: var(--muted); font-size: 0.7rem; text-transform: uppercase; font-family: inherit; font-weight: 600; }
    .pill span { color: #f8fafc; font-weight: 600; }

    .ticket-msg { background: #0f172a; border-left: 4px solid var(--accent); padding: 1.25rem; border-radius: 0 8px 8px 0; margin-bottom: 1.5rem; }
    .ticket-msg-label { font-size: 0.75rem; color: var(--muted); text-transform: uppercase; font-weight: 600; margin-bottom: 0.75rem; letter-spacing: 0.05em; }
    .ticket-msg-body { font-size: 1.05rem; line-height: 1.6; color: #f8fafc; white-space: pre-wrap; font-style: italic; }

    pre { margin: 0; background: #0f172a; color: #a5b4fc; font-family: var(--mono); font-size: 0.75rem; padding: 1rem; overflow-x: auto; max-height: calc(100vh - 250px); border-radius: 8px; }

    #status { font-size: 0.85rem; padding: 0.75rem; background: var(--surface); border: 1px solid var(--border); border-radius: 8px; margin-top: 1rem; min-height: 2.8rem; display: flex; align-items: center; }
    #status.err { border-color: var(--danger); color: #fca5a5; background: #450a0a80; }

    ::-webkit-scrollbar { width: 8px; height: 8px; }
    ::-webkit-scrollbar-track { background: transparent; }
    ::-webkit-scrollbar-thumb { background: #475569; border-radius: 4px; }
    ::-webkit-scrollbar-thumb:hover { background: #64748b; }

    .hint-bar { background: var(--hint-bg); border: 1px solid var(--hint-border); color: #c4b5fd; padding: 1rem; border-radius: 8px; font-size: 0.85rem; margin-bottom: 1.5rem; line-height: 1.5; }
  </style>
</head>
<body>
  <div class="wrap">
    <header class="page-head">
      <div class="page-head-text">
        <h1>Customer Support Command Center</h1>
        <p>Handle support tickets · <a href="/health" style="color:var(--accent)">/health</a></p>
      </div>
      <div class="action-bar" style="margin:0;">
        <select id="resetCategory" style="width: auto; padding: 0.5rem;">
          <option value="">Random Category</option>
          <option value="refund">Refund</option>
          <option value="replacement">Replacement</option>
          <option value="payment">Payment</option>
          <option value="delivery">Delivery</option>
        </select>
        <button type="button" class="secondary" id="btnReset">Reset Env</button>
      </div>
    </header>

    <div class="metrics">
      <div class="metric blue"><div class="m-label">Last Reward</div><div class="m-val" id="mLastReward">—</div></div>
      <div class="metric orange"><div class="m-label">Total Reward</div><div class="m-val" id="mTotalReward">—</div></div>
      <div class="metric green"><div class="m-label">Grade / Score</div><div class="m-val" id="mScore">—</div></div>
      <div class="metric grey"><div class="m-label">Episode Status</div><div class="m-val" id="mStatus" style="font-size:1.25rem; align-items:center; display:flex; height:100%;">—</div></div>
    </div>

    <div class="main-grid">
      <!-- Left Column: Timeline -->
      <div class="panel">
        <div class="panel-header">Action Timeline</div>
        <div class="panel-body">
          <div class="timeline-scroll">
            <div class="timeline-list" id="timelineList">
              <div style="color: var(--muted); text-align: center; padding: 2rem 0; font-size: 0.9rem;">No actions yet.<br/>Start an episode.</div>
            </div>
          </div>
        </div>
      </div>

      <!-- Center Column: Ticket & Execution -->
      <div class="panel">
        <div class="panel-header">Current Ticket & Execution</div>
        <div class="panel-body">
          <div class="ticket-pills" id="ticketPills"></div>

          <div class="ticket-msg">
            <div class="ticket-msg-label">Customer Message</div>
            <div class="ticket-msg-body" id="ticketBody">Click "Reset Env" to generate a support ticket.</div>
          </div>

          <div class="form-grid">
            <div>
              <label for="actionType">Action Type</label>
              <select id="actionType">
                <option value="clarify">clarify</option>
                <option value="refund">refund</option>
                <option value="partial_refund">partial_refund</option>
                <option value="replace">replace</option>
                <option value="escalate">escalate</option>
                <option value="deny">deny</option>
              </select>
            </div>
            <div>
              <label for="actionResponse">Response to Customer</label>
              <textarea id="actionResponse" spellcheck="false">I understand your concern and will help resolve this.</textarea>
            </div>
            <div class="form-row">
              <div>
                <label for="actionAmount">Refund Amount ($)</label>
                <input type="number" id="actionAmount" step="any" placeholder="e.g. 50.00" />
              </div>
              <div>
                <label for="actionReason">Internal Reason</label>
                <input type="text" id="actionReason" placeholder="Policy justification" />
              </div>
            </div>
          </div>

          <button type="button" class="exec" id="btnStep">Execute Action</button>

          <div class="action-bar">
            <button type="button" class="secondary" id="btnState">Get State</button>
            <button type="button" class="secondary" id="btnGrade">Get Final Grade</button>
          </div>
          <div id="status">Ready</div>
        </div>
      </div>

      <!-- Right Column: Observations -->
      <div class="panel">
        <div class="panel-header">Raw Observation</div>
        <div class="panel-body" style="padding: 0;">
          <pre id="outObs" style="border-radius: 0;">—</pre>
        </div>
      </div>
    </div>
  </div>

  <script>
(function () {
  const $ = (id) => document.getElementById(id);
  const status = $("status");
  const outObs = $("outObs");
  const mLast = $("mLastReward");
  const mTotal = $("mTotalReward");
  const mScore = $("mScore");
  const mStat = $("mStatus");
  let totalReward = 0;
  let episodeActive = false;

  function syncStepButton() { $("btnStep").disabled = !episodeActive; }
  function pretty(obj) { return JSON.stringify(obj, null, 2); }

  function buildAction() {
    return {
      action_type: $("actionType").value,
      response: $("actionResponse").value.trim() || " ",
      amount: parseFloat($("actionAmount").value) || 0,
      reason: $("actionReason").value.trim() || "Per policy"
    };
  }

  function renderTicket(obs) {
    const body = $("ticketBody");
    const pills = $("ticketPills");
    pills.innerHTML = "";
    if (!obs) { body.textContent = "No active ticket."; return; }
    body.textContent = '"' + (obs.customer_message || "") + '"';

    function addPill(label, value) {
      if (value === undefined || value === null || value === "") return;
      const p = document.createElement("div"); p.className = "pill";
      const k = document.createElement("kbd"); k.textContent = label;
      const v = document.createElement("span"); v.textContent = String(value);
      p.appendChild(k); p.appendChild(v); pills.appendChild(p);
    }

    addPill("ID", obs.ticket_id);
    if (obs.issue_type) addPill("Category", obs.issue_type);
    if (obs.order_info) addPill("Order", "$" + (obs.order_info.amount || 0).toFixed(2));
    if (obs.order_info && obs.order_info.days_since_purchase !== undefined) {
      addPill("Days Ago", obs.order_info.days_since_purchase);
    }
  }

  function renderTimeline(obs) {
    const list = $("timelineList");
    list.innerHTML = "";
    if (!obs || !obs.conversation_history || obs.conversation_history.length === 0) {
      list.innerHTML = '<div style="color: var(--muted); text-align: center; padding: 2rem 0; font-size: 0.9rem;">No actions yet.<br/>Start an episode.</div>';
      return;
    }
    obs.conversation_history.forEach((h, idx) => {
      const item = document.createElement("div"); item.className = "timeline-item";
      const header = document.createElement("div"); header.className = "tl-header";

      const left = document.createElement("div");
      let roleLabel = h.role === "agent" ? (h.action_type || "agent") : h.role;
      left.innerHTML = '<span class="tl-step-num">#' + (idx + 1) + '</span> <span class="tl-action-name">' + roleLabel + '</span>';

      if (h.reward !== undefined) {
          const rw = document.createElement("span");
          rw.className = "tl-reward";
          const rVal = parseFloat(h.reward);
          rw.textContent = (rVal >= 0 ? "+" : "") + rVal.toFixed(2);
          rw.style.background = rVal > 0 ? "#16a34a33" : (rVal < 0 ? "#ef444433" : "transparent");
          rw.style.color = rVal > 0 ? "#4ade80" : (rVal < 0 ? "#f87171" : "var(--muted)");
          rw.style.padding = "2px 6px";
          rw.style.borderRadius = "4px";
          rw.style.fontSize = "0.75rem";
          rw.style.marginLeft = "8px";
          left.appendChild(rw);
      }

      header.appendChild(left);
      item.appendChild(header);

      const fb = document.createElement("div"); fb.className = "tl-feedback";
      fb.textContent = h.message;
      item.appendChild(fb);

      list.appendChild(item);
    });
  }

  function showPayload(data) {
    outObs.textContent = pretty(data);

    // openenv responses can be the observation itself (reset)
    // or a wrapped object (step) { observation: ..., reward: ..., done: ... }
    const obsObj = data.observation || data;

    const reward = parseFloat(data.reward !== undefined ? data.reward : (obsObj.reward || 0));
    mLast.textContent = reward.toFixed(2);

    let currentTotal = (obsObj.metadata && obsObj.metadata.total_reward !== undefined) ?
                       obsObj.metadata.total_reward :
                       (data.total_reward !== undefined ? data.total_reward : obsObj.total_reward);
    totalReward = currentTotal !== undefined ? currentTotal : (totalReward + reward);
    mTotal.textContent = totalReward.toFixed(2);

    const isDone = data.done !== undefined ? data.done : (obsObj.done || false);
    mStat.textContent = isDone ? "DONE" : "ACTIVE";
    mStat.style.color = isDone ? "var(--card-green)" : "var(--accent)";

    renderTicket(obsObj);
    renderTimeline(obsObj);
  }

  function setStatus(msg, isErr) {
    if (typeof msg === "object") {
        try { msg = JSON.stringify(msg, null, 1); } catch(e) {}
    }
    status.textContent = msg || "";
    status.className = isErr ? "err" : "";
  }

  async function parseJsonResponse(res) {
    const text = await res.text();
    try { return { ok: res.ok, data: JSON.parse(text), raw: text }; }
    catch { return { ok: res.ok, data: null, raw: text }; }
  }

  async function doReset() {
    setStatus("Resetting environment...");
    const cat = $("resetCategory").value;
    const res = await fetch("/reset", { method: "POST", headers: {"Content-Type":"application/json"}, body: JSON.stringify(cat ? {category:cat} : {}) });
    const { ok, data, raw } = await parseJsonResponse(res);
    if (!ok || !data) { setStatus(data ? (data.detail || data.message || data) : (raw || res.statusText), true); return; }
    totalReward = 0; episodeActive = true; syncStepButton();
    showPayload(data);
    mScore.textContent = "—";
    setStatus("Environment reset successfully.");
  }

  async function doState() {
    setStatus("Fetching state...");
    const res = await fetch("/state", { method: "GET" });
    const { ok, data, raw } = await parseJsonResponse(res);
    if (!ok || !data) { setStatus(data ? (data.detail || data.message || data) : (raw || res.statusText), true); return; }
    episodeActive = !data.done; syncStepButton();
    outObs.textContent = pretty(data);
    setStatus("State fetched.");
  }

  async function doStep() {
    if (!episodeActive) { setStatus("Cannot step: Episode is not active. Please reset first.", true); return; }
    setStatus("Executing action...");
    const payload = { action: buildAction() };
    const res = await fetch("/step", { method: "POST", headers: {"Content-Type":"application/json"}, body: JSON.stringify(payload) });
    const { ok, data, raw } = await parseJsonResponse(res);
    if (!ok || !data) { setStatus(data ? (data.detail || data.message || data) : (raw || res.statusText), true); return; }
    if (data.done) { episodeActive = false; syncStepButton(); }
    showPayload(data);
    setStatus("Action executed.");
  }

  async function doGrade() {
    setStatus("Fetching grade...");
    const res = await fetch("/grade", { method: "GET" });
    const { ok, data, raw } = await parseJsonResponse(res);
    if (!ok || !data) { setStatus(data ? (data.detail || data.message || data) : (raw || res.statusText), true); return; }
    mScore.textContent = data.score !== undefined ? data.score.toFixed(2) : "—";
    setStatus("Grade fetched.");
  }

  $("btnReset").addEventListener("click", () => doReset().catch(e => setStatus(String(e), true)));
  $("btnState").addEventListener("click", () => doState().catch(e => setStatus(String(e), true)));
  $("btnStep").addEventListener("click", () => doStep().catch(e => setStatus(String(e), true)));
  $("btnGrade").addEventListener("click", () => doGrade().catch(e => setStatus(String(e), true)));
  syncStepButton();
})();
  </script>
</body>
</html>
"""


@app.get("/", response_class=HTMLResponse, tags=["Interface"], summary="Start Page")
@app.get("/dashboard", response_class=HTMLResponse, tags=["Interface"], summary="Custom UI")
def ui() -> HTMLResponse:
    """Browser debug UI."""
    return HTMLResponse(content=UI_HTML)


@app.get("/grade", tags=["Simulation"])
def get_grade():
    """Get the final grade for the current session."""
    from server.customersupportenv_environment import CustomersupportenvEnvironment
    # Retrieve the score from shared state if available
    reward = getattr(CustomersupportenvEnvironment, "_shared_reward", 0.01)
    # Ensure score is strictly between 0 and 1
    clamped_reward = max(0.01, min(0.99, reward))
    return {"score": clamped_reward}


def main():
    """
    Entry point for direct execution.
    """
    import uvicorn
    import argparse

    parser = argparse.ArgumentParser()
    parser.add_argument("--host", type=str, default="0.0.0.0")
    parser.add_argument("--port", type=int, default=8000)
    args = parser.parse_args()

    uvicorn.run(app, host=args.host, port=args.port)


if __name__ == "__main__":
    main()
