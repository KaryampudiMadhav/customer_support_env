"""
Inference Script for Customer Support Environment
=================================================

MANDATORY:
- Before submitting, ensure the following variables are defined in your environment:
    API_BASE_URL   The API endpoint for the LLM
    MODEL_NAME     The model identifier to use for inference
    HF_TOKEN       Your Hugging Face / API key

- The inference script must be named `inference.py` and placed in the root directory
- Participants must use OpenAI Client for all LLM calls using above variables

STDOUT FORMAT:
- The script must emit exactly three line types to stdout, in this order:
    [START] task=<task_name> env=<benchmark> model=<model_name>
    [STEP]  step=<n> action=<action_str> reward=<0.00> done=<true|false> error=<msg|null>
    [END]   success=<true|false> steps=<n> score=<score> rewards=<r1,r2,...,rn>

  Rules:
    - One [START] line at episode begin
    - One [STEP] line per step, immediately after env.step() returns
    - One [END] line after env.close(), always emitted (even on exception)
    - reward and rewards are formatted to 2 decimal places
    - done and success are lowercase booleans: true or false
    - error is the raw last_action_error string, or null if none
    - All fields on a single line with no newlines within a line
    - Each task should return score in [0, 1]

  Example:
    [START] task=refund-test env=customerSupport model=Qwen3-VL-30B
    [STEP] step=1 action=refund(amount=99.99) reward=0.80 done=false error=null
    [STEP] step=2 action=close_ticket() reward=0.20 done=true error=null
    [END] success=true steps=2 score=1.00 rewards=0.80,0.20
"""

import asyncio
import json
import os
import textwrap
from typing import Any, Dict, List, Optional

from openai import OpenAI

# Import from customerSupportEnv package
try:
    from models import CustomerSupportAction, VALID_ACTION_TYPES
    from grading import final_grade, partial_reward, strict_score
except ImportError:
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
        if OpenAI is not None and api_base_url and api_key and model_name
        else None
    )

    # Verify the environment server is reachable before starting tasks
    import requests as _req
    try:
        _req.get(f"{env_url}/health", timeout=5)
    except Exception as exc:
        print(f"[DEBUG] Model request failed: {exc}", flush=True)
        return CustomerSupportAction(
            response="I'm experiencing technical difficulties. Please hold.",
            action_type="clarify",
            amount=0.0,
            reason="Technical error fallback.",
        )


def action_to_string(action: CustomerSupportAction) -> str:
    if action.action_type in ["refund", "partial_refund"]:
        return f"{action.action_type}(amount={action.amount:.2f})"
    return f"{action.action_type}()"


def get_observation_dict(obs) -> Dict[str, Any]:
    if hasattr(obs, "model_dump"):
        return obs.model_dump()
    return obs


async def run_episode(client: OpenAI, category: Optional[str] = None) -> Dict[str, Any]:
    async with CustomerSupportEnv(base_url="http://localhost:8000") as env:
        result = await env.reset(category=category)
        obs = get_observation_dict(result.observation)

        rewards: List[float] = []
        steps_taken = 0

        for step in range(1, MAX_STEPS + 1):
            if result.done:
                break

            action = get_model_action(client, obs)
            result = await env.step(action)
            obs = get_observation_dict(result.observation)

            reward = result.reward or 0.0
            done = result.done

            rewards.append(reward)
            steps_taken = step

            action_str = action_to_string(action)
            log_step(step=step, action=action_str, reward=reward, done=done, error=None)

            if done:
                break

        total_reward = sum(rewards)
        max_possible = MAX_STEPS
        score = min(max(total_reward / max_possible, 0.0), 1.0)
        success = score >= SUCCESS_SCORE_THRESHOLD

        return {
            "rewards": rewards,
            "steps": steps_taken,
            "score": score,
            "success": success,
        }


async def main() -> None:
    client = OpenAI(base_url=API_BASE_URL, api_key=API_KEY)

    log_start(task=TASK_NAME, env=BENCHMARK, model=MODEL_NAME)

    try:
        result = await run_episode(client, category=TICKET_CATEGORY)
        log_end(
            success=result["success"],
            steps=result["steps"],
            score=result["score"],
            rewards=result["rewards"],
        )
    except Exception as e:
        print(f"[DEBUG] Episode failed with error: {e}", flush=True)
        log_end(success=False, steps=0, score=0.0, rewards=[])


if __name__ == "__main__":
    asyncio.run(main())
