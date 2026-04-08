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
    from customerSupportEnv.client import CustomerSupportEnv
    from customerSupportEnv.models import CustomerSupportAction
except ImportError:
    from client import CustomerSupportEnv
    from models import CustomerSupportAction

# Environment configuration
API_KEY = os.getenv("HF_TOKEN") or os.getenv("API_KEY")
API_BASE_URL = os.getenv("API_BASE_URL") or "https://router.huggingface.co/v1"
MODEL_NAME = os.getenv("MODEL_NAME") or "Qwen/Qwen2.5-72B-Instruct"

# Task configuration
TASK_NAME = os.getenv("CUSTOMER_SUPPORT_TASK", "support_ticket")
BENCHMARK = os.getenv("CUSTOMER_SUPPORT_BENCHMARK", "customerSupportEnv")
TICKET_CATEGORY = os.getenv("TICKET_CATEGORY", None)

# Inference configuration
MAX_STEPS = int(os.getenv("MAX_STEPS", "8"))
TEMPERATURE = float(os.getenv("TEMPERATURE", "0.7"))
MAX_TOKENS = int(os.getenv("MAX_TOKENS", "500"))
SUCCESS_SCORE_THRESHOLD = float(os.getenv("SUCCESS_SCORE_THRESHOLD", "0.5"))

# Valid action types
VALID_ACTION_TYPES = [
    "refund",
    "partial_refund",
    "replace",
    "escalate",
    "clarify",
    "deny",
]


def log_start(task: str, env: str, model: str) -> None:
    print(f"[START] task={task} env={env} model={model}", flush=True)


def log_step(
    step: int, action: str, reward: float, done: bool, error: Optional[str]
) -> None:
    error_val = error if error else "null"
    done_val = str(done).lower()
    print(
        f"[STEP] step={step} action={action} reward={reward:.2f} done={done_val} error={error_val}",
        flush=True,
    )


def log_end(success: bool, steps: int, score: float, rewards: List[float]) -> None:
    rewards_str = ",".join(f"{r:.2f}" for r in rewards)
    print(
        f"[END] success={str(success).lower()} steps={steps} score={score:.3f} rewards={rewards_str}",
        flush=True,
    )


def build_system_prompt() -> str:
    return textwrap.dedent("""
        You are a professional customer support agent handling support tickets.

        Your goal is to resolve customer issues while following company policies.

        Available action types:
        - refund: Issue a full refund to the customer
        - partial_refund: Issue a partial refund (specify amount)
        - replace: Initiate a product replacement
        - escalate: Escalate to a supervisor/specialist
        - clarify: Ask the customer for more information
        - deny: Deny the customer's request

        For each action, you must provide:
        - action_type: The type of action you're taking
        - response: Your message to the customer explaining your decision
        - amount: The refund amount (for refund/partial_refund actions)
        - reason: The justification for your decision based on policy

        Always be polite, professional, and empathetic in your responses.
        Follow the policy guidelines provided in each ticket to make fair decisions.

        IMPORTANT: Output your response as a valid JSON object with exactly these fields:
        {
            "action_type": "<action_type>",
            "response": "<your message to the customer>",
            "amount": <refund_amount_or_0>,
            "reason": "<your policy-based justification>"
        }

        Do not include any text outside the JSON object.
    """).strip()


def build_user_prompt(obs_dict: Dict[str, Any]) -> str:
    ticket_info = obs_dict.get("ticket_info", {})
    order_info = obs_dict.get("order_info", {})
    customer_info = obs_dict.get("customer_info", {})

    category = (
        ticket_info.get("issue_category", "unknown")
        if isinstance(ticket_info, dict)
        else "unknown"
    )
    difficulty = (
        ticket_info.get("difficulty", "medium")
        if isinstance(ticket_info, dict)
        else "medium"
    )

    customer_message = obs_dict.get("customer_message", "No message")
    policy_context = obs_dict.get("policy_context", "")
    conversation_history = obs_dict.get("conversation_history", [])

    days_since_purchase = obs_dict.get("days_since_purchase", 0)
    item_condition = obs_dict.get("item_condition", "unused")
    user_reason = obs_dict.get("user_reason", "")
    transaction_status = obs_dict.get("transaction_status", "")
    delivery_status = obs_dict.get("delivery_status", "")
    delivery_delayed_days = obs_dict.get("delivery_delayed_days", 0)

    order_amount = 0.0
    if isinstance(order_info, dict):
        order_amount = order_info.get("amount", 0.0)

    prompt = f"""You are handling a {category} support ticket.

Customer Message:
{customer_message}

Ticket Category: {category}
Difficulty: {difficulty}

Order Information:
- Order ID: {order_info.get("order_id", "N/A") if isinstance(order_info, dict) else "N/A"}
- Amount: ${order_amount:.2f}
- Date: {order_info.get("date", "N/A") if isinstance(order_info, dict) else "N/A"}
- Product: {order_info.get("product", "N/A") if isinstance(order_info, dict) else "N/A"}
- Status: {order_info.get("status", "N/A") if isinstance(order_info, dict) else "N/A"}

Customer Information:
- Name: {customer_info.get("name", "N/A") if isinstance(customer_info, dict) else "N/A"}
- Email: {customer_info.get("email", "N/A") if isinstance(customer_info, dict) else "N/A"}
- Satisfaction: {customer_info.get("satisfaction", 0.5) * 100:.0f}%"""

    if category == "refund":
        prompt += f"""
Refund Details:
- Days since purchase: {days_since_purchase}
- Item condition: {item_condition}
- Customer reason: {user_reason}"""
    elif category == "payment":
        prompt += f"""
Payment Details:
- Transaction status: {transaction_status}"""
    elif category == "delivery":
        prompt += f"""
Delivery Details:
- Status: {delivery_status}
- Delayed by: {delivery_delayed_days} days"""

    prompt += f"""

Policy Context:
{policy_context}"""

    if conversation_history:
        prompt += """

Conversation History:
"""
        for entry in conversation_history[-5:]:
            prompt += entry + "\n"

    prompt += """

What is your response to this customer? Output only the JSON object."""

    return prompt


def parse_llm_response(response_text: str) -> CustomerSupportAction:
    try:
        json_start = response_text.find("{")
        json_end = response_text.rfind("}") + 1

        if json_start != -1 and json_end != 0:
            json_str = response_text[json_start:json_end]
            data = json.loads(json_str)
        else:
            data = json.loads(response_text)

        action_type = data.get("action_type", "clarify")
        if action_type not in VALID_ACTION_TYPES:
            action_type = "clarify"

        return CustomerSupportAction(
            response=data.get("response", "I need some more information to help you."),
            action_type=action_type,
            amount=float(data.get("amount", 0.0)),
            reason=data.get("reason", "Following standard procedure."),
        )
    except (json.JSONDecodeError, KeyError, TypeError, ValueError):
        return CustomerSupportAction(
            response="Could you please provide more details about your issue?",
            action_type="clarify",
            amount=0.0,
            reason="Default clarification needed.",
        )


def get_model_action(client: OpenAI, obs: Dict[str, Any]) -> CustomerSupportAction:
    system_prompt = build_system_prompt()
    user_prompt = build_user_prompt(obs)

    try:
        completion = client.chat.completions.create(
            model=MODEL_NAME,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            temperature=TEMPERATURE,
            max_tokens=MAX_TOKENS,
            stream=False,
        )
        response_text = (completion.choices[0].message.content or "").strip()
        return parse_llm_response(response_text)
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
