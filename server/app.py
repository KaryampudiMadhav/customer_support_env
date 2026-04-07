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


# ============================================================================
# Main
# ============================================================================

def main(host: str = "0.0.0.0", port: int = 8000):
    """Run the server."""
    uvicorn.run(app, host=host, port=port)


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--port", type=int, default=8000)
    parser.add_argument("--host", type=str, default="0.0.0.0")
    args = parser.parse_args()
    main(host=args.host, port=args.port)