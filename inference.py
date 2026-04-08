```python
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
import requests

# Safe imports (no crash)
try:
    from openai import OpenAI
except Exception:
    OpenAI = None

try:
    from models import CustomerSupportAction, VALID_ACTION_TYPES
    from grading import final_grade, partial_reward, strict_score
except Exception:
    # fallback defaults (prevents crash if missing)
    VALID_ACTION_TYPES = ["refund", "partial_refund", "replace", "escalate", "clarify", "deny"]

    def final_grade(**kwargs): return 0.0
    def partial_reward(*args, **kwargs): return 0.0
    def strict_score(x): return float(x)


# ---------------------------------------------------------------------------
# CONSTANTS
# ---------------------------------------------------------------------------

TASKS = ["refund", "replacement", "payment", "delivery"]
TASK_MAX_STEPS = {task: 5 for task in TASKS}


# ---------------------------------------------------------------------------
# SAFE ACTION HANDLING
# ---------------------------------------------------------------------------

def _default_action():
    return {
        "response": "Could you please provide more details?",
        "action_type": "clarify",
        "amount": 0.0,
        "reason": "Need more information"
    }


def _normalise_action(d: dict[str, Any]) -> dict[str, Any]:
    action_type = str(d.get("action_type", "clarify")).lower()
    if action_type not in VALID_ACTION_TYPES:
        action_type = "clarify"

    try:
        amount = float(d.get("amount", 0.0))
    except:
        amount = 0.0

    return {
        "response": str(d.get("response", "")),
        "action_type": action_type,
        "amount": amount,
        "reason": str(d.get("reason", "")),
    }


def parse_llm_response(text: str) -> dict[str, Any]:
    if not text:
        return _default_action()

    try:
        data = json.loads(text)
        if isinstance(data, dict):
            return _normalise_action(data)
    except:
        pass

    return _default_action()


# ---------------------------------------------------------------------------
# PROMPT
# ---------------------------------------------------------------------------

def build_prompt(obs: dict[str, Any]) -> str:
    return f"""
You are a customer support agent. Reply ONLY in JSON.

Customer message:
{obs.get("customer_message", "")}

Return:
{{
  "response": "...",
  "action_type": "refund/partial_refund/replace/escalate/clarify/deny",
  "amount": 0.0,
  "reason": "..."
}}
"""


# ---------------------------------------------------------------------------
# MAIN
# ---------------------------------------------------------------------------

def run():
    base_url = os.getenv("ENV_BASE_URL", "http://localhost:8000")
    api_key = os.getenv("API_KEY", "")
    model_name = os.getenv("MODEL_NAME", "")

    # Setup LLM (optional)
    llm = None
    if OpenAI and api_key:
        try:
            llm = OpenAI(api_key=api_key)
        except:
            llm = None

    session = requests.Session()

    for task in TASKS:
        print(f"[START] task={task}")

        try:
            res = session.post(f"{base_url}/reset", json={"category": task}, timeout=10)
            obs = res.json()
        except Exception as e:
            print(f"[ERROR] reset failed: {e}")
            continue

        done = False

        for step in range(1, TASK_MAX_STEPS[task] + 1):

            action = _default_action()

            # LLM call (safe)
            if llm:
                try:
                    completion = llm.chat.completions.create(
                        model=model_name,
                        messages=[
                            {"role": "user", "content": build_prompt(obs)}
                        ],
                        max_tokens=200
                    )
                    text = completion.choices[0].message.content
                    action = parse_llm_response(text)
                except Exception:
                    pass

            try:
                res = session.post(f"{base_url}/step", json=action, timeout=10)
                data = res.json()
            except Exception as e:
                print(f"[STEP] step={step} error={e}")
                break

            reward = float(data.get("reward", 0.0))
            done = bool(data.get("done", False))

            print(f"[STEP] step={step} action={action['action_type']} reward={reward:.2f} done={done}")

            obs = data

            if done:
                break

        print(f"[END] task={task}")

    return 0


if __name__ == "__main__":
    raise SystemExit(run())
```
