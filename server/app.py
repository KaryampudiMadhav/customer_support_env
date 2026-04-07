# Copyright (c) Meta Platforms, Inc. and affiliates.
# All rights reserved.
#
# This source code is licensed under the BSD-style license found in the
# LICENSE file in the root directory of this source tree.

"""
FastAPI application for the Customer Support Environment.

This module creates an HTTP server that exposes the CustomerSupportEnvironment
over HTTP and WebSocket endpoints.

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
    python -m server.app --port 8000
"""

from typing import Any, Dict, Optional
import uuid

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.responses import HTMLResponse
from pydantic import BaseModel
import uvicorn

try:
    from models import CustomerSupportAction, CustomerSupportObservation
except ImportError:
    from ..models import CustomerSupportAction, CustomerSupportObservation

try:
    from server.customerSupportEnv_environment import CustomerSupportEnvironment
except ImportError:
    from .customerSupportEnv_environment import CustomerSupportEnvironment


app = FastAPI(
    title="Customer Support Environment",
    description="A realistic simulation of a customer support agent handling support tickets",
    version="0.1.0",
)

_env: Optional[CustomerSupportEnvironment] = None
_websocket_sessions: Dict[str, WebSocket] = {}


def get_env() -> CustomerSupportEnvironment:
    """Get or create the environment instance."""
    global _env
    if _env is None:
        _env = CustomerSupportEnvironment()
    return _env


@app.post("/reset", response_model=CustomerSupportObservation)
async def reset_env():
    """Reset the environment."""
    return get_env().reset()


@app.post("/step")
async def step_env(action: CustomerSupportAction):
    """Execute a step in the environment."""
    obs = get_env().step(action)
    return {
        "customer_message": obs.customer_message,
        "ticket_id": obs.ticket_info.ticket_id,
        "phase": obs.phase,
        "done": obs.done,
        "reward": obs.reward,
        "total_reward": obs.total_reward,
        "action_type": action.action_type,
    }


@app.get("/state")
async def get_state():
    """Get current environment state."""
    return get_env().state


@app.get("/health")
async def health():
    """Health check."""
    return {"status": "ok", "episode_id": get_env().state.episode_id}


@app.get("/grade")
async def get_grade():
    """Get the final grade of the current episode."""
    return {"score": get_env().grade}


@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    """
    WebSocket endpoint for persistent sessions.

    Protocol:
    1. Client connects
    2. Server sends {"type": "connected", "episode_id": "..."}
    3. Client sends {"type": "reset"} or {"type": "step", "action": {...}}
    4. Server responds with observation
    5. Repeat until disconnect
    """
    session_id = str(uuid.uuid4())
    await websocket.accept()
    _websocket_sessions[session_id] = websocket

    env = get_env()

    try:
        # Send connection confirmation
        await websocket.send_json({
            "type": "connected",
            "episode_id": env.state.episode_id,
            "session_id": session_id,
        })

        while True:
            # Receive message from client
            data = await websocket.receive_json()
            msg_type = data.get("type")

            if msg_type == "reset":
                category = data.get("category")
                observation = env.reset(category=category)
                await websocket.send_json({
                    "type": "observation",
                    "data": _observation_to_dict(observation),
                    "reward": 0.0,
                    "done": False,
                })

            elif msg_type == "step":
                action_data = data.get("action", {})
                action = CustomerSupportAction(
                    response=action_data.get("response", ""),
                    action_type=action_data.get("action_type", "clarify"),
                    amount=action_data.get("amount", 0.0),
                    reason=action_data.get("reason", ""),
                )
                observation = env.step(action)
                await websocket.send_json({
                    "type": "observation",
                    "data": _observation_to_dict(observation),
                    "reward": observation.reward,
                    "done": observation.done,
                })

            elif msg_type == "state":
                await websocket.send_json({
                    "type": "state",
                    "episode_id": env.state.episode_id,
                    "step_count": env.state.step_count,
                })


            else:
                await websocket.send_json({
                    "type": "error",
                    "message": f"Unknown message type: {msg_type}",
                })

    except WebSocketDisconnect:
        pass
    finally:
        _websocket_sessions.pop(session_id, None)


# ============================================================================
# Helpers
# ============================================================================

def _observation_to_dict(obs: CustomerSupportObservation) -> Dict[str, Any]:
    """Convert observation to dictionary."""
    return {
        "customer_message": obs.customer_message,
        "ticket_info": {
            "ticket_id": obs.ticket_info.ticket_id,
            "issue_category": obs.ticket_info.issue_category,
            "difficulty": obs.ticket_info.difficulty,
            "impact": obs.ticket_info.impact,
            "tier": obs.ticket_info.tier,
        },
        "order_info": {
            "order_id": obs.order_info.order_id,
            "amount": obs.order_info.amount,
            "date": obs.order_info.date,
            "product": obs.order_info.product,
            "status": obs.order_info.status,
        },
        "customer_info": {
            "customer_id": obs.customer_info.customer_id,
            "name": obs.customer_info.name,
            "email": obs.customer_info.email,
            "satisfaction": obs.customer_info.satisfaction,
        },
        "policy_context": obs.policy_context,
        "conversation_history": obs.conversation_history,
        "days_since_purchase": obs.days_since_purchase,
        "item_condition": obs.item_condition,
        "user_reason": obs.user_reason,
        "transaction_status": obs.transaction_status,
        "transaction_id": obs.transaction_id,
        "delivery_status": obs.delivery_status,
        "delivery_delayed_days": obs.delivery_delayed_days,
        "sentiment": obs.sentiment,
        "phase": obs.phase,
        "sla_steps_left": obs.sla_steps_left,
        "total_reward": obs.total_reward,
        "cumulative_score": obs.cumulative_score,
        "action_history": [
            {
                "step": entry.step,
                "action_type": entry.action_type,
                "description": entry.description,
                "reward": entry.reward
            }
            for entry in obs.action_history
        ]
    }


UI_HTML = """<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>Customer Support Command Center</title>
  <style>
    :root {
      --bg: #141517;
      --surface: #25262b;
      --border: #373a40;
      --text: #e9ecef;
      --muted: #868e96;
      --accent: #4c6ef5;
      --exec: #e8590c;
      --exec-hover: #fd7e14;
      --hint-bg: #1b4332;
      --hint-border: #2b8a3e;
      --card-blue: #1864ab;
      --card-orange: #d9480f;
      --card-green: #2b8a3e;
      --card-grey: #495057;
      --danger: #fa5252;
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
    .wrap { max-width: 56rem; margin: 0 auto; padding: 1.5rem 1rem 3rem; }
    h1 { font-size: 1.35rem; font-weight: 700; margin: 0 0 0.25rem; letter-spacing: -0.02em; }
    .sub { color: var(--muted); font-size: 0.875rem; margin: 0 0 1.25rem; }
    .hint-bar {
      background: var(--hint-bg);
      border: 1px solid var(--hint-border);
      color: #b2f2bb;
      font-size: 0.8rem;
      padding: 0.5rem 0.75rem;
      border-radius: 6px;
      margin-bottom: 1rem;
    }
    .panel {
      background: var(--surface);
      border: 1px solid var(--border);
      border-radius: 10px;
      padding: 1rem 1.15rem;
      margin-bottom: 1rem;
    }
    .panel h2 {
      margin: 0 0 0.75rem;
      font-size: 0.95rem;
      font-weight: 600;
      color: var(--text);
    }
    label { font-size: 0.75rem; color: var(--muted); display: block; margin-bottom: 0.3rem; }
    label .hint { font-weight: 400; color: #5c636a; }
    select, input[type="text"], input[type="number"], textarea {
      width: 100%;
      padding: 0.5rem 0.55rem;
      border-radius: 6px;
      border: 1px solid var(--border);
      background: #1a1b1e;
      color: var(--text);
      font-size: 0.85rem;
    }
    select {
      cursor: pointer;
      appearance: auto;
      min-height: 2.25rem;
    }
    textarea { font-family: var(--mono); font-size: 0.8rem; min-height: 4.5rem; resize: vertical; }
    textarea, pre { scrollbar-width: thin; scrollbar-color: #5c636a #141517; }
    textarea::-webkit-scrollbar, pre::-webkit-scrollbar { width: 8px; height: 8px; }
    textarea::-webkit-scrollbar-corner, pre::-webkit-scrollbar-corner { background: #141517; }
    textarea::-webkit-scrollbar-track, pre::-webkit-scrollbar-track { background: #141517; border-radius: 4px; }
    textarea::-webkit-scrollbar-thumb, pre::-webkit-scrollbar-thumb { background: #5c636a; border-radius: 4px; border: 2px solid #141517; }
    textarea::-webkit-scrollbar-thumb:hover, pre::-webkit-scrollbar-thumb:hover { background: #868e96; }
    input[type="number"] { -moz-appearance: textfield; appearance: textfield; }
    input[type="number"]::-webkit-outer-spin-button, input[type="number"]::-webkit-inner-spin-button { -webkit-appearance: none; margin: 0; }
    .form-grid { display: grid; gap: 0.75rem; margin-top: 0.75rem; }
    @media (min-width: 560px) { .form-grid.cols-2 { grid-template-columns: 1fr 1fr; } }
    .field-group { display: none; }
    .field-group.active { display: block; }
    .btn-row { display: flex; flex-wrap: wrap; gap: 0.5rem; margin-top: 1rem; }
    button {
      border: none;
      padding: 0.55rem 1rem;
      border-radius: 8px;
      font-size: 0.8rem;
      font-weight: 600;
      cursor: pointer;
      text-transform: uppercase;
      letter-spacing: 0.03em;
    }
    button.exec { background: var(--exec); color: #fff; }
    button.exec:hover:not(:disabled) { background: var(--exec-hover); }
    button.exec:disabled { background: #495057; color: #868e96; cursor: not-allowed; opacity: 0.65; }
    button.secondary { background: #495057; color: #fff; }
    button.secondary:hover { background: #5c636a; }
    .metrics { display: grid; grid-template-columns: repeat(2, 1fr); gap: 0.65rem; }
    @media (min-width: 720px) { .metrics { grid-template-columns: repeat(4, 1fr); } }
    .metric { border-radius: 8px; padding: 0.75rem 0.85rem; color: #fff; }
    .metric .m-label { font-size: 0.65rem; text-transform: uppercase; opacity: 0.9; letter-spacing: 0.06em; }
    .metric .m-val { font-size: 1.35rem; font-weight: 700; margin-top: 0.2rem; font-variant-numeric: tabular-nums; }
    .metric.blue { background: linear-gradient(135deg, var(--card-blue), #1c7ed6); }
    .metric.orange { background: linear-gradient(135deg, var(--card-orange), #e8590c); }
    .metric.green { background: linear-gradient(135deg, var(--card-green), #37b24d); }
    .metric.grey { background: linear-gradient(135deg, #495057, #6c757d); }
    pre { margin: 0; padding: 0.65rem 0.75rem; background: #1a1b1e; border: 1px solid var(--border); border-radius: 6px; font-family: var(--mono); font-size: 0.72rem; overflow-x: auto; white-space: pre-wrap; word-break: break-word; }
    .tag { font-size: 0.72rem; color: var(--muted); margin-bottom: 0.25rem; }
    #status { font-size: 0.8rem; min-height: 1.25rem; margin: 0.5rem 0; }
    #status.err { color: var(--danger); }
    #toast-root { position: fixed; top: 0.75rem; left: 50%; transform: translateX(-50%); z-index: 10000; display: flex; flex-direction: column; align-items: stretch; gap: 0.45rem; max-width: min(38rem, calc(100vw - 1.5rem)); pointer-events: none; }
    .toast { pointer-events: auto; margin: 0; padding: 0.65rem 1rem; border-radius: 8px; font-size: 0.82rem; line-height: 1.45; box-shadow: 0 10px 28px rgba(0, 0, 0, 0.5); border: 1px solid rgba(250, 82, 82, 0.45); background: #3b1219; color: #ffc9c9; opacity: 0; transform: translateY(-0.4rem); transition: opacity 0.22s ease, transform 0.22s ease; cursor: pointer; word-break: break-word; }
    .toast.toast-visible { opacity: 1; transform: translateY(0); }
    .toast:focus { outline: 2px solid var(--accent); outline-offset: 2px; }
    footer { margin-top: 1.25rem; font-size: 0.72rem; color: var(--muted); }
    footer a { color: var(--accent); }
    h2.section-title { font-size: 1rem; font-weight: 700; color: #f8f9fa; margin: 0 0 0.5rem; letter-spacing: -0.01em; }
    .ticket-panel { background: #1e1f23 !important; border-color: #2c2e33 !important; padding: 1rem 1.1rem 1.1rem !important; }
    .ticket-pills { display: flex; flex-wrap: wrap; gap: 0.45rem; margin-bottom: 0.85rem; }
    .pill { display: inline-flex; align-items: center; gap: 0.35rem; padding: 0.28rem 0.65rem; border-radius: 5px; background: #2f3138; border: 1px solid #3d4049; font-size: 0.72rem; color: #dee2e6; }
    .pill kbd { font-family: inherit; font-weight: 600; color: #adb5bd; font-size: 0.68rem; text-transform: uppercase; letter-spacing: 0.04em; }
    .pill span.val { font-weight: 600; color: #fff; }
    .ticket-msg-wrap { background: #121214; border: 1px solid #2c2e33; border-radius: 6px; padding: 0.75rem 0.9rem 1rem; }
    .ticket-msg-label { font-size: 0.68rem; font-weight: 600; text-transform: uppercase; letter-spacing: 0.06em; color: #868e96; margin-bottom: 0.5rem; }
    .ticket-msg-body { font-size: 0.95rem; line-height: 1.55; color: #f1f3f5; white-space: pre-wrap; word-break: break-word; }
    .ticket-msg-body.empty { color: #5c636a; font-style: italic; }
    .timeline-panel { background: #252830 !important; border-color: #3d4150 !important; }
    .timeline-scroll { max-height: 18rem; overflow-y: auto; overflow-x: hidden; scrollbar-gutter: stable; scrollbar-width: thin; scrollbar-color: #5c636a #141517; }
    .timeline-scroll::-webkit-scrollbar { width: 8px; }
    .timeline-scroll::-webkit-scrollbar-track { background: #141517; border-radius: 4px; }
    .timeline-scroll::-webkit-scrollbar-thumb { background: #5c636a; border-radius: 4px; border: 2px solid #141517; }
    .timeline-scroll::-webkit-scrollbar-thumb:hover { background: #868e96; }
    .timeline-list { display: flex; flex-direction: column; gap: 0.5rem; }
    .timeline-item { background: #121214; border: 1px solid #2c2e33; border-radius: 6px; padding: 0.65rem 0.85rem; overflow: hidden; }
    .timeline-row { display: flex; align-items: flex-start; justify-content: space-between; gap: 1rem; }
    .tl-main { min-width: 0; flex: 1; }
    .tl-step-num { font-weight: 700; color: #e9ecef; font-size: 0.82rem; }
    .tl-action-name { font-size: 0.82rem; color: #ced4da; font-weight: 500; }
    .tl-reward { font-size: 0.85rem; font-weight: 700; font-variant-numeric: tabular-nums; color: #fff; flex-shrink: 0; }
    .tl-reward.neg { color: #ff8787; }
    .tl-reward.pos { color: #8ce99a; }
    .tl-feedback { margin-top: 0.45rem; padding-top: 0.45rem; border-top: 1px solid #2c2e33; font-size: 0.72rem; line-height: 1.4; color: #868e96; }
    .timeline-empty { text-align: center; padding: 1.25rem 0.75rem; color: #868e96; font-size: 0.82rem; background: #121214; border-radius: 6px; border: 1px dashed #3d4049; }
    .page-head { display: flex; flex-wrap: wrap; align-items: flex-start; justify-content: space-between; gap: 0.75rem; margin-bottom: 0.25rem; }
    .page-head-text { flex: 1; min-width: 12rem; }
    .page-head-text h1 { margin-bottom: 0.25rem; }
    .page-head-actions { display: flex; flex-wrap: wrap; gap: 0.45rem; align-items: center; }
    a.btn-mini { display: inline-block; padding: 0.35rem 0.65rem; border-radius: 6px; font-size: 0.72rem; font-weight: 600; text-decoration: none; text-transform: uppercase; letter-spacing: 0.04em; background: #fdfd96; color: #111; border: none; cursor: pointer; font-family: inherit; line-height: 1.2; }
    a.btn-mini:hover { filter: brightness(1.06); }
    a.btn-mini:focus-visible { outline: 2px solid var(--accent); outline-offset: 2px; }
    .ticket-section { margin-bottom: 1rem; }
    .ticket-grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(120px, 1fr)); gap: 0.5rem; }
    .ticket-info-item { background: #2f3138; padding: 0.5rem 0.75rem; border-radius: 5px; font-size: 0.75rem; }
    .ticket-info-item kbd { color: #adb5bd; font-size: 0.68rem; text-transform: uppercase; }
    .ticket-info-item span { color: #fff; font-weight: 600; }
  </style>
</head>
<body>
  <div id="toast-root" aria-live="assertive" aria-relevant="additions"></div>
  <div class="wrap">
    <header class="page-head">
      <div class="page-head-text">
        <h1>Customer Support Command Center</h1>
        <p class="sub">Handle support tickets · <a href="/health" style="color:var(--accent)">/health</a> · <a href="/docs" style="color:var(--accent)">/docs</a></p>
      </div>
    </header>
    <div class="metrics panel" style="padding:0.85rem;margin-bottom:1rem;background:#1a1b1e;border-style:dashed">
      <div class="metric blue"><div class="m-label">Last reward</div><div class="m-val" id="mLastReward">—</div></div>
      <div class="metric orange"><div class="m-label">Total reward</div><div class="m-val" id="mTotalReward">—</div></div>
      <div class="metric green"><div class="m-label">Grade</div><div class="m-val" id="mScore">—</div></div>
      <div class="metric grey"><div class="m-label">Status</div><div class="m-val" id="mStatus" style="font-size:1rem">—</div></div>
    </div>
    <h2 class="section-title">Current Ticket</h2>
    <div class="panel ticket-panel">
      <div class="ticket-pills" id="ticketPills"></div>
      <div class="ticket-msg-wrap">
        <div class="ticket-msg-label">Customer Message</div>
        <div class="ticket-msg-body empty" id="ticketBody">Reset or load state to show the active ticket.</div>
      </div>
    </div>
    <div class="panel">
      <div class="hint-bar">
        <strong>Action types:</strong> refund, partial_refund, replace, escalate, clarify, deny<br>
        Use <strong>Reset</strong> to start a new ticket, then <strong>Execute step</strong> to take an action.
      </div>
      <h2>Execute Action</h2>
      <label for="actionType">Action type</label>
      <select id="actionType">
        <option value="clarify">clarify</option>
        <option value="refund">refund</option>
        <option value="partial_refund">partial_refund</option>
        <option value="replace">replace</option>
        <option value="escalate">escalate</option>
        <option value="deny">deny</option>
      </select>
      <div class="form-grid" style="margin-top:0.75rem">
        <div style="grid-column:1/-1">
          <label for="actionResponse">Response message</label>
          <textarea id="actionResponse" spellcheck="false">I understand your concern and will help resolve this.</textarea>
        </div>
        <div>
          <label for="actionAmount">Amount (for refund)</label>
          <input type="number" id="actionAmount" step="any" placeholder="0.00" />
        </div>
        <div>
          <label for="actionReason">Reason</label>
          <input type="text" id="actionReason" placeholder="Policy justification" />
        </div>
      </div>
      <div class="form-grid cols-2" style="margin-top:0.85rem">
        <div>
          <label for="resetCategory">Reset · category</label>
          <select id="resetCategory">
            <option value="">Random</option>
            <option value="refund">refund</option>
            <option value="replacement">replacement</option>
            <option value="payment">payment</option>
            <option value="delivery">delivery</option>
          </select>
        </div>
      </div>
      <div class="btn-row">
        <button type="button" class="exec" id="btnStep">Execute step</button>
        <button type="button" class="secondary" id="btnReset">Reset</button>
        <button type="button" class="secondary" id="btnState">Get state</button>
        <button type="button" class="secondary" id="btnGrade">Get grade</button>
      </div>
    </div>
    <h2 class="section-title">Action Timeline</h2>
    <div class="panel timeline-panel">
      <div class="timeline-scroll">
        <div class="timeline-list" id="timelineList">
          <div class="timeline-empty">No actions yet. Run <strong>Reset</strong>, then <strong>Execute step</strong>.</div>
        </div>
      </div>
    </div>
    <p id="status"></p>
    <div class="panel">
      <div class="tag">observation</div>
      <pre id="outObs">—</pre>
    </div>
    <footer>Built for Customer Support Environment · POST /step takes action_type, response, amount, reason</footer>
  </div>
  <script>
(function () {
  const $ = (id) => document.getElementById(id);
  const toastRoot = $("toast-root");
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
    if (!obs) { body.textContent = "No observation loaded."; body.classList.add("empty"); return; }
    body.classList.remove("empty");
    body.textContent = obs.customer_message || "";
    function addPill(label, value) {
      if (value === undefined || value === null || value === "") return;
      const p = document.createElement("div");
      p.className = "pill";
      const k = document.createElement("kbd");
      k.textContent = label;
      const v = document.createElement("span");
      v.className = "val";
      v.textContent = String(value);
      p.appendChild(k); p.appendChild(v);
      pills.appendChild(p);
    }
    if (obs.ticket_info) {
      addPill("ID", obs.ticket_info.ticket_id);
      addPill("Category", obs.ticket_info.issue_category);
      addPill("Difficulty", obs.ticket_info.difficulty);
    }
    if (obs.order_info) addPill("Order", "$" + (obs.order_info.amount || 0).toFixed(2));
    if (obs.customer_info) addPill("Satisfaction", (obs.customer_info.satisfaction || 0).toFixed(2));
    addPill("Phase", obs.phase);
  }
  function renderTimeline(obs) {
    const list = $("timelineList");
    list.innerHTML = "";
    if (!obs || !obs.action_history || obs.action_history.length === 0) {
      list.innerHTML = '<div class="timeline-empty">No actions yet. Run <strong>Reset</strong>, then <strong>Execute step</strong>.</div>';
      return;
    }
    obs.action_history.forEach(function (h) {
      const item = document.createElement("div");
      item.className = "timeline-item";
      const row = document.createElement("div");
      row.className = "timeline-row";
      const main = document.createElement("div");
      main.className = "tl-main";
      main.innerHTML = '<span class="tl-step-num">Step ' + h.step + ':</span> <span class="tl-action-name">' + h.action_type + '</span>';
      const rw = document.createElement("div");
      rw.className = "tl-reward";
      const r = Number(h.reward || 0);
      rw.textContent = (r >= 0 ? "+" : "") + r.toFixed(2);
      if (r < 0) rw.classList.add("neg"); else if (r > 0) rw.classList.add("pos");
      row.appendChild(main); row.appendChild(rw);
      item.appendChild(row);
      if (h.description) {
        const fb = document.createElement("div");
        fb.className = "tl-feedback";
        fb.textContent = h.description;
        item.appendChild(fb);
      }
      list.appendChild(item);
    });
  }
  function showPayload(data) {
    const obs = data;
    outObs.textContent = pretty(obs);
    const reward = parseFloat(obs.reward || 0);
    mLast.textContent = reward.toFixed(2);
    totalReward += reward;
    mTotal.textContent = totalReward.toFixed(2);
    mStat.textContent = obs.done ? "DONE" : "RUNNING";
    renderTicket(obs);
    renderTimeline(obs);
  }
  function showErrorToast(msg) {
    if (!msg || !toastRoot) return;
    const el = document.createElement("div");
    el.className = "toast";
    el.textContent = msg;
    el.setAttribute("role", "alert");
    el.tabIndex = 0;
    toastRoot.appendChild(el);
    requestAnimationFrame(function () { el.classList.add("toast-visible"); });
    function dismiss() { el.classList.remove("toast-visible"); setTimeout(function () { el.remove(); }, 280); }
    setTimeout(dismiss, 8500);
    el.addEventListener("click", dismiss);
  }
  function setStatus(msg, isErr) {
    status.textContent = msg || "";
    status.className = isErr ? "err" : "";
    if (isErr && msg) showErrorToast(msg);
  }
  async function parseJsonResponse(res) {
    const text = await res.text();
    try { return { ok: res.ok, data: JSON.parse(text), raw: text }; }
    catch { return { ok: res.ok, data: null, raw: text }; }
  }
  async function doReset() {
    setStatus("POST /reset …");
    const cat = $("resetCategory").value;
    const payload = cat ? { category: cat } : {};
    const res = await fetch("/reset", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(payload) });
    const { ok, data, raw } = await parseJsonResponse(res);
    if (!ok || !data) { setStatus((data && data.detail) || raw || res.statusText, true); return; }
    totalReward = 0; episodeActive = true; syncStepButton();
    showPayload(data);
    mScore.textContent = "—";
    setStatus("POST /reset → " + res.status);
  }
  async function doState() {
    setStatus("GET /state …");
    const res = await fetch("/state", { method: "GET" });
    const { ok, data, raw } = await parseJsonResponse(res);
    if (!ok || !data) { setStatus((data && data.detail) || raw || res.statusText, true); return; }
    episodeActive = !data.done; syncStepButton();
    showPayload(data);
    setStatus("GET /state → " + res.status);
  }
  async function doStep() {
    if (!episodeActive) { setStatus("Call Reset before executing a step.", true); return; }
    const action = buildAction();
    setStatus("POST /step …");
    const res = await fetch("/step", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(action) });
    const { ok, data, raw } = await parseJsonResponse(res);
    if (!ok || !data) { const detail = data && (data.detail || data.message); setStatus(String(detail || raw || res.statusText), true); return; }
    if (data.done) { episodeActive = false; syncStepButton(); }
    showPayload(data);
    setStatus("POST /step → " + res.status);
  }
  async function doGrade() {
    setStatus("GET /grade …");
    const res = await fetch("/grade", { method: "GET" });
    const { ok, data, raw } = await parseJsonResponse(res);
    if (!ok || !data) { setStatus((data && data.detail) || raw || res.statusText, true); return; }
    mScore.textContent = data.score ? data.score.toFixed(2) : "—";
    setStatus("GET /grade → " + res.status);
  }
  $("btnReset").addEventListener("click", function () { doReset().catch(function (e) { setStatus(String(e), true); }); });
  $("btnState").addEventListener("click", function () { doState().catch(function (e) { setStatus(String(e), true); }); });
  $("btnStep").addEventListener("click", function () { doStep().catch(function (e) { setStatus(String(e), true); }); });
  $("btnGrade").addEventListener("click", function () { doGrade().catch(function (e) { setStatus(String(e), true); }); });
  syncStepButton();
})();
  </script>
</body>
</html>
"""


@app.get("/web", response_class=HTMLResponse, tags=["Interface"], summary="Web UI")
def ui() -> HTMLResponse:
    """Browser debug UI."""
    return HTMLResponse(content=UI_HTML)


# ============================================================================
# Main
# ============================================================================

def main():
    """Run the server. Entry point for openenv multi-mode deployment."""
    uvicorn.run(app, host="0.0.0.0", port=8000)


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--port", type=int, default=8000)
    parser.add_argument("--host", type=str, default="0.0.0.0")
    args = parser.parse_args()
    uvicorn.run(app, host=args.host, port=args.port)
