"""
Inference script for the Customer Support Environment.

Run environment server first:
    uvicorn server.app:app --host 0.0.0.0 --port 8000

Then run this script:
    API_KEY=<key> MODEL_NAME=<model> python inference.py
"""

from __future__ import annotations

import json
import os
import re
from typing import Any

from openai import OpenAI

try:
    from client import CustomerSupportEnv
    from models import CustomerSupportAction, VALID_ACTION_TYPES
    from grading import final_grade, partial_reward, strict_score
except ImportError:
    from client import CustomerSupportEnv  # type: ignore[no-redef]
    from models import CustomerSupportAction, VALID_ACTION_TYPES  # type: ignore[no-redef]
    from grading import final_grade, partial_reward, strict_score  # type: ignore[no-redef]

# Four ticket categories the environment supports
TASKS = ["refund", "replacement", "payment", "delivery"]
TASK_MAX_STEPS = {
    "refund": 5,
    "replacement": 5,
    "payment": 5,
    "delivery": 5,
}


# ---------------------------------------------------------------------------
# LLM response parsing
# ---------------------------------------------------------------------------

def parse_llm_response(text: str) -> dict[str, Any]:
    """Parse LLM output into a CustomerSupportAction-compatible dict."""
    raw = (text or "").strip()
    if not raw:
        return _default_action()

    # Strip markdown code fences
    if raw.startswith("```"):
        raw = re.sub(r"^```(?:json)?", "", raw).strip()
        raw = re.sub(r"```$", "", raw).strip()

    # Try full JSON parse
    try:
        parsed = json.loads(raw)
        if isinstance(parsed, dict):
            return _normalise_action(parsed)
    except Exception:
        pass

    # Try extracting first JSON object
    start = raw.find("{")
    end = raw.rfind("}")
    if start >= 0 and end > start:
        try:
            parsed = json.loads(raw[start : end + 1])
            if isinstance(parsed, dict):
                return _normalise_action(parsed)
        except Exception:
            pass

    return _default_action()


def _normalise_action(d: dict[str, Any]) -> dict[str, Any]:
    """Ensure required fields exist and action_type is valid."""
    action_type = str(d.get("action_type", "clarify")).strip().lower()
    if action_type not in VALID_ACTION_TYPES:
        action_type = "clarify"

    try:
        amount = float(d.get("amount", 0.0) or 0.0)
    except (TypeError, ValueError):
        amount = 0.0

    return {
        "response": str(d.get("response", "")).strip(),
        "action_type": action_type,
        "amount": amount,
        "reason": str(d.get("reason", "")).strip(),
    }


def _default_action() -> dict[str, Any]:
    return {
        "response": "Could you please provide more details about your issue?",
        "action_type": "clarify",
        "amount": 0.0,
        "reason": "Need more information to proceed.",
    }


# ---------------------------------------------------------------------------
# Prompt builder
# ---------------------------------------------------------------------------

def _prompt(obs: dict[str, Any]) -> str:
    ticket = obs.get("ticket_info", {}) or {}
    order = obs.get("order_info", {}) or {}
    customer = obs.get("customer_info", {}) or {}
    history = obs.get("conversation_history", []) or []

    history_text = "\n".join(f"  - {msg}" for msg in history) if history else "  (none)"

    return (
        "You are a customer support agent. Reply with JSON only.\n"
        "Format: {\n"
        '  "response": "<message to customer>",\n'
        '  "action_type": "<one of: refund, partial_refund, replace, escalate, clarify, deny>",\n'
        '  "amount": <refund amount as float, 0 if not applicable>,\n'
        '  "reason": "<policy justification>"\n'
        "}\n\n"
        "=== TICKET ===\n"
        f"Category   : {ticket.get('issue_category', 'unknown')}\n"
        f"Difficulty : {ticket.get('difficulty', 'medium')}\n"
        f"Ticket ID  : {ticket.get('ticket_id', '')}\n"
        f"Impact     : {ticket.get('impact', 'Low')}\n"
        f"Tier       : {ticket.get('tier', 'Free')}\n\n"
        "=== CUSTOMER MESSAGE ===\n"
        f"{obs.get('customer_message', '')}\n\n"
        "=== ORDER INFO ===\n"
        f"Order ID   : {order.get('order_id', '')}\n"
        f"Product    : {order.get('product', '')}\n"
        f"Amount     : ${order.get('amount', 0):.2f}\n"
        f"Date       : {order.get('date', '')}\n"
        f"Status     : {order.get('status', '')}\n\n"
        "=== CUSTOMER INFO ===\n"
        f"Name       : {customer.get('name', '')}\n"
        f"Satisfaction: {customer.get('satisfaction', 0.5)}\n\n"
        "=== CONTEXT ===\n"
        f"Days since purchase : {obs.get('days_since_purchase', 0)}\n"
        f"Item condition      : {obs.get('item_condition', 'unused')}\n"
        f"User reason         : {obs.get('user_reason', '')}\n"
        f"Transaction status  : {obs.get('transaction_status', '')}\n"
        f"Delivery status     : {obs.get('delivery_status', '')}\n"
        f"Delivery delayed by : {obs.get('delivery_delayed_days', 0)} days\n"
        f"Customer sentiment  : {obs.get('sentiment', 'Neutral')}\n"
        f"SLA steps left      : {obs.get('sla_steps_left', 2)}\n\n"
        "=== POLICY ===\n"
        f"{obs.get('policy_context', '(none)')}\n\n"
        "=== CONVERSATION HISTORY ===\n"
        f"{history_text}\n\n"
        "=== SCORING ===\n"
        f"Cumulative score: {obs.get('cumulative_score', 0.0):.1f}%\n"
        f"Total reward    : {obs.get('total_reward', 0.0):.2f}\n\n"
        "Choose the action that best aligns with policy. "
        "Prefer the most specific action (refund/replace/deny) over 'clarify' when policy is clear."
    )


# ---------------------------------------------------------------------------
# Score normalisation
# ---------------------------------------------------------------------------

# strict_score is imported from grading.py (re-exported here for compat)
_strict_score = strict_score


# ---------------------------------------------------------------------------
# Main loop
# ---------------------------------------------------------------------------

def run() -> int:
    api_base_url = os.getenv("API_BASE_URL", "https://router.huggingface.co/v1")
    api_key = os.getenv("API_KEY")
    model_name = os.getenv("MODEL_NAME", "Qwen/Qwen2.5-72B-Instruct")
    env_url = os.getenv("ENV_BASE_URL", "http://127.0.0.1:8000")
    max_tokens = 512

    llm_client = (
        OpenAI(base_url=api_base_url, api_key=api_key)
        if api_base_url and api_key and model_name
        else None
    )

    # One persistent WebSocket connection for all tasks (use sync wrapper)
    try:
        env = CustomerSupportEnv(base_url=env_url)
        sync_env = env.sync()
    except Exception as exc:
        connect_error = str(exc).replace("\n", " ")
        for task in TASKS:
            print(f"[START] task={task} env=customer_support model={model_name}")
            print(f"[STEP] step=1 action=clarify reward=-0.10 done=true error={connect_error}")
            print("[END] success=false steps=1 score=0.01 rewards=-0.10")
        return 0

    # Use plain HTTP requests to interact with the environment server (avoids
    # websocket transport quirks in the upstream openenv client).
    import requests

    base = env_url.rstrip("/")
    with requests.Session() as session:
        for task in TASKS:
            rewards: list[float] = []
            success = False
            steps_used = 0
            baseline_satisfaction: float = 0.5
            requires_decisive: bool = False
            prev_obs_obj: dict[str, Any] | None = None
            print(f"[START] task={task} env=customer_support model={model_name}")

            try:
                # Reset via HTTP
                resp = session.post(f"{base}/reset", json={"category": task}, timeout=10)
                data = resp.json()
                obs_obj = data.get("data", {}).get("observation", {}) or {}

                # Capture baseline values for grading
                customer_info = obs_obj.get("customer_info", {}) or {}
                baseline_satisfaction = float(customer_info.get("satisfaction", 0.5))
                ticket_info = obs_obj.get("ticket_info", {}) or {}
                requires_decisive = ticket_info.get("difficulty", "medium") == "hard"

                for step in range(1, TASK_MAX_STEPS[task] + 1):
                    action_dict: dict[str, Any] = _default_action()
                    action_error: str | None = None

                    if llm_client is None:
                        action_error = "llm_unavailable"
                    else:
                        try:
                            completion = llm_client.chat.completions.create(
                                model=model_name,
                                temperature=0.2,
                                max_tokens=max_tokens,
                                messages=[  # type: ignore[arg-type]
                                    {"role": "system", "content": "Return strict JSON only. No markdown, no prose."},
                                    {"role": "user", "content": _prompt(obs_obj)},
                                ],
                            )
                            response_text = completion.choices[0].message.content or ""
                            action_dict = parse_llm_response(response_text)
                        except Exception as exc:
                            action_error = str(exc).replace("\n", " ")

                    action_type = action_dict["action_type"]
                    action_payload = {
                        "response": action_dict["response"],
                        "action_type": action_type,
                        "amount": float(action_dict.get("amount", 0.0) or 0.0),
                        "reason": action_dict.get("reason", ""),
                    }

                    try:
                        step_resp = session.post(f"{base}/step", json=action_payload, timeout=10)
                        step_data = step_resp.json()
                        obs_obj = step_data.get("data", {}).get("observation", {}) or {}
                        env_reward = float(step_data.get("reward", 0.0) or 0.0)
                        shaping = partial_reward(prev_obs_obj, obs_obj, action_type)
                        reward = env_reward + shaping
                        done = bool(step_data.get("done", False))
                        err = action_error
                    except Exception as exc:
                        reward = -0.1
                        done = False
                        err = action_error or str(exc).replace("\n", " ")

                    prev_obs_obj = obs_obj
                    steps_used = step
                    rewards.append(reward)
                    done_str = "true" if done else "false"
                    err_str = "null" if err is None else err
                    print(f"[STEP] step={step} action={action_type} reward={reward:.2f} done={done_str} error={err_str}")

                    if done:
                        success = reward > 0
                        break

            except Exception as exc:
                steps_used = 1
                rewards.append(-0.1)
                error_text = str(exc).replace("\n", " ")
                print("[STEP] step=1 action=clarify reward=-0.10 done=true error=" + error_text)
                action_dict = _default_action()
                obs_obj = {}
            finally:
                try:
                    last_action = action_dict.get("action_type", "clarify")
                    score = final_grade(
                        action_type=last_action,
                        final_obs=obs_obj,
                        baseline_satisfaction=baseline_satisfaction,
                        steps_used=steps_used,
                        requires_decisive=requires_decisive,
                    )
                except Exception:
                    try:
                        raw_score = float(obs_obj.get("cumulative_score", 0.0) or 0.0)
                        score = _strict_score(raw_score / 100.0)
                    except Exception:
                        score = _strict_score(sum(rewards))

                rewards_str = ",".join(f"{r:.2f}" for r in rewards)
                print(f"[END] success={'true' if success else 'false'} steps={steps_used} score={score:.2f} rewards={rewards_str}")

    return 0


if __name__ == "__main__":
    raise SystemExit(run())
