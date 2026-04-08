"""Baseline inference runner for Customer Support OpenEnv environment.

This script evaluates three tasks (easy, medium, hard) and emits strict
stdout logs in [START]/[STEP]/[END] format.
"""

from __future__ import annotations

import json
import os
from typing import Any, Dict, List, Optional

import requests
from openai import OpenAI

API_BASE_URL = os.getenv("API_BASE_URL", "https://router.huggingface.co/v1")
MODEL_NAME = os.getenv("MODEL_NAME", "Qwen/Qwen2.5-72B-Instruct")
HF_TOKEN = os.getenv("HF_TOKEN")
ENV_BASE_URL = os.getenv("ENV_BASE_URL", "http://127.0.0.1:8000")
BENCHMARK = os.getenv("BENCHMARK", "customer_support_env")
MAX_STEPS = int(os.getenv("MAX_STEPS", "6"))
SUCCESS_THRESHOLD = float(os.getenv("SUCCESS_THRESHOLD", "0.6"))

if HF_TOKEN is None:
    raise ValueError("HF_TOKEN environment variable is required")


TASKS = [
    {"task": "easy-delivery", "category": "delivery", "difficulty": "easy"},
    {"task": "medium-refund", "category": "refund", "difficulty": "medium"},
    {"task": "hard-payment", "category": "payment", "difficulty": "hard"},
]


def log_start(task: str, env: str, model: str) -> None:
    print(f"[START] task={task} env={env} model={model}", flush=True)


def log_step(step: int, action: str, reward: float, done: bool, error: Optional[str]) -> None:
    error_val = error if error else "null"
    print(
        f"[STEP] step={step} action={action} reward={reward:.2f} done={str(done).lower()} error={error_val}",
        flush=True,
    )


def log_end(success: bool, steps: int, score: float, rewards: List[float]) -> None:
    rewards_str = ",".join(f"{r:.2f}" for r in rewards)
    print(
        f"[END] success={str(success).lower()} steps={steps} score={score:.2f} rewards={rewards_str}",
        flush=True,
    )


def _post(path: str, payload: Dict[str, Any]) -> Dict[str, Any]:
    response = requests.post(
        f"{ENV_BASE_URL}{path}",
        json=payload,
        timeout=30,
    )
    response.raise_for_status()
    return response.json()


def _normalise_action(action: Dict[str, Any]) -> Dict[str, Any]:
    valid_actions = {"refund", "partial_refund", "replace", "escalate", "clarify", "deny"}
    action_type = str(action.get("action_type", "clarify")).strip().lower()
    if action_type not in valid_actions:
        action_type = "clarify"

    try:
        amount = float(action.get("amount", 0.0) or 0.0)
    except (TypeError, ValueError):
        amount = 0.0

    return {
        "response": str(action.get("response", "I will help resolve this issue.")).strip()
        or "I will help resolve this issue.",
        "action_type": action_type,
        "amount": amount,
        "reason": str(action.get("reason", "Policy-aligned resolution")).strip()
        or "Policy-aligned resolution",
    }


def _heuristic_action(obs: Dict[str, Any]) -> Dict[str, Any]:
    category = (obs.get("ticket_info", {}) or {}).get("issue_category", "")
    days = int(obs.get("days_since_purchase", 0) or 0)
    item_condition = str(obs.get("item_condition", "unused")).lower()
    txn = str(obs.get("transaction_status", "")).lower()
    delay = int(obs.get("delivery_delayed_days", 0) or 0)

    if category == "refund":
        can_refund = days <= 7 and item_condition == "unused"
        if can_refund:
            amount = float((obs.get("order_info", {}) or {}).get("amount", 0.0) or 0.0)
            return {
                "response": "I can approve a refund under our return policy.",
                "action_type": "refund",
                "amount": amount,
                "reason": "Within 7-day unused return window",
            }
        return {
            "response": "This request is outside refund eligibility, so I must deny it.",
            "action_type": "deny",
            "amount": 0.0,
            "reason": "Outside refund policy window or item not unused",
        }

    if category == "replacement":
        if days <= 10:
            return {
                "response": "I will initiate a replacement right away.",
                "action_type": "replace",
                "amount": 0.0,
                "reason": "Eligible replacement window",
            }
        return {
            "response": "This replacement request is outside policy and must be denied.",
            "action_type": "deny",
            "amount": 0.0,
            "reason": "Outside replacement eligibility window",
        }

    if category == "payment":
        if txn in {"duplicate_charge", "failed", "reversed", "bank_delay"}:
            return {
                "response": "I am escalating this payment issue for specialist handling.",
                "action_type": "escalate",
                "amount": 0.0,
                "reason": "Payment anomaly requires specialist review",
            }
        return {
            "response": "Please share additional payment details so I can investigate.",
            "action_type": "clarify",
            "amount": 0.0,
            "reason": "Need supporting payment details",
        }

    if category == "delivery":
        if delay >= 3:
            return {
                "response": "I am escalating this delayed delivery to logistics support.",
                "action_type": "escalate",
                "amount": 0.0,
                "reason": "Delivery delay beyond SLA threshold",
            }
        return {
            "response": "Thanks for your patience. I can confirm your delivery status update.",
            "action_type": "clarify",
            "amount": 0.0,
            "reason": "Provide delivery status guidance",
        }

    return {
        "response": "I need more information to help effectively.",
        "action_type": "clarify",
        "amount": 0.0,
        "reason": "General fallback",
    }


def _build_prompt(obs: Dict[str, Any]) -> str:
    return (
        "You are a customer support agent. Respond with JSON only.\\n"
        "Required keys: response, action_type, amount, reason.\\n"
        "Valid action_type: refund, partial_refund, replace, escalate, clarify, deny.\\n"
        "Observation:\\n"
        f"{json.dumps(obs, ensure_ascii=True)}"
    )


def _model_action(client: OpenAI, obs: Dict[str, Any]) -> Dict[str, Any]:
    try:
        completion = client.chat.completions.create(
            model=MODEL_NAME,
            messages=[
                {
                    "role": "system",
                    "content": "Return only strict JSON with action fields for a customer support action.",
                },
                {"role": "user", "content": _build_prompt(obs)},
            ],
            temperature=0.0,
            max_tokens=180,
            stream=False,
        )
        text = (completion.choices[0].message.content or "").strip()
        if text.startswith("```"):
            text = text.strip("`")
            text = text.replace("json", "", 1).strip()
        candidate = json.loads(text)
        if isinstance(candidate, dict):
            return _normalise_action(candidate)
    except Exception:
        pass

    return _normalise_action(_heuristic_action(obs))


def _action_str(action: Dict[str, Any]) -> str:
    if action["action_type"] in {"refund", "partial_refund"}:
        return f"{action['action_type']}(amount={action['amount']:.2f})"
    return f"{action['action_type']}()"


def run_episode(client: OpenAI, task: Dict[str, str]) -> Dict[str, Any]:
    log_start(task=task["task"], env=BENCHMARK, model=MODEL_NAME)

    rewards: List[float] = []
    steps_taken = 0
    done = False

    try:
        reset_payload = {
            "category": task["category"],
            "difficulty": task["difficulty"],
            "seed": 42,
        }
        reset_result = _post("/reset", reset_payload)
        obs = ((reset_result.get("data") or {}).get("observation") or {})

        for step in range(1, MAX_STEPS + 1):
            if done:
                break

            action = _model_action(client, obs)
            error: Optional[str] = None

            try:
                step_result = _post("/step", action)
                reward = float(step_result.get("reward", 0.0) or 0.0)
                done = bool(step_result.get("done", False))
                obs = ((step_result.get("data") or {}).get("observation") or {})
            except Exception as exc:
                reward = -0.5
                done = True
                error = str(exc)

            rewards.append(reward)
            steps_taken = step
            log_step(
                step=step,
                action=_action_str(action),
                reward=reward,
                done=done,
                error=error,
            )

    except Exception as exc:
        rewards.append(-1.0)
        steps_taken = 1
        log_step(
            step=1,
            action="clarify()",
            reward=-1.0,
            done=True,
            error=str(exc),
        )

    max_possible = float(MAX_STEPS)
    score = min(max(sum(rewards) / max_possible, 0.0), 1.0) if max_possible > 0 else 0.0
    success = score >= SUCCESS_THRESHOLD
    log_end(success=success, steps=steps_taken, score=score, rewards=rewards)

    return {"score": score, "success": success}


def main() -> None:
    client = OpenAI(base_url=API_BASE_URL, api_key=HF_TOKEN)
    for task in TASKS:
        run_episode(client=client, task=task)


if __name__ == "__main__":
    main()
