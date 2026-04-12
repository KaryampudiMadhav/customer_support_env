import asyncio
import os
import json
import re
import textwrap
from datetime import datetime, timedelta
from typing import List, Optional, Dict, Any

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

from openai import OpenAI
from client import CustomersupportenvEnv
from models import CustomersupportenvAction

# Configuration from Environment Variables
# Changed default to 'customersupportenv:latest' to match 'openenv build --tag'
IMAGE_NAME = os.getenv("LOCAL_IMAGE_NAME", "customersupportenv:latest")
API_KEY = os.getenv("HF_TOKEN") or os.getenv("API_KEY")
API_BASE_URL = os.getenv("API_BASE_URL", "https://router.huggingface.co/v1")
MODEL_NAME = os.getenv("MODEL_NAME", "Qwen/Qwen2.5-72B-Instruct")

# Task settings
MAX_STEPS = 5

# Define diverse test scenarios with enriched data for policy matching
TEST_TASKS = [
    {
        "issue_type": "refund",
        "ticket_id": "TKT-REF-001",
        "customer_message": "I want a refund for my order ORD-111111. It arrived today, I haven't opened it, but I changed my mind.",
        "order_info": {
            "id": "ORD-111111",
            "amount": 49.99,
            "days_since_purchase": 2,
            "item_condition": "unused",
            "user_reason": "changed_mind", # Added required field
            "product": "Wireless Mouse"
        }
    },
    {
        "issue_type": "replacement",
        "ticket_id": "TKT-REP-002",
        "customer_message": "My order ORD-222222 arrived shattered. I'd like a replacement sent out immediately.",
        "order_info": {
            "id": "ORD-222222",
            "amount": 120.00,
            "days_since_purchase": 1,
            "item_condition": "damaged",
            "user_reason": "item_damaged", # Matches policy exception
            "product": "Glass Vase"
        }
    },
    {
        "issue_type": "delivery",
        "ticket_id": "TKT-DEL-003",
        "customer_message": "My package ORD-333333 says delivered but I don't see it anywhere.",
        "order_info": {
            "id": "ORD-333333",
            "amount": 25.00,
            "days_since_purchase": 10,
            "status": "delivered",
            "delivery_date": (datetime.now() - timedelta(days=2)).isoformat(),
            "product": "Book"
        }
    },
    {
        "issue_type": "payment",
        "ticket_id": "TKT-PAY-004",
        "customer_message": "I was charged twice for order ORD-444444. Please fix this.",
        "order_info": {
            "id": "ORD-444444",
            "amount": 5.00,
            "days_since_purchase": 3,
            "duplicate_charge": True, # Matches policy criteria
            "transaction_id": "TXN-888999", # Added required field
            "transaction_status": "duplicate_charge", # Added required field
            "product": "Cloud Subscription"
        }
    },
    {
        "issue_type": "refund",
        "ticket_id": "TKT-REF-901",
        "customer_message": "I'm a VIP! I want to return this, it's been 10 days and I used it.",
        "order_info": {
            "id": "ORD-REF-901",
            "amount": 150.00,
            "days_since_purchase": 10,
            "item_condition": "used",
            "loyalty_status": "VIP",
            "user_reason": "changed_mind"
        }
    },
    {
        "issue_type": "delivery",
        "ticket_id": "TKT-DEL-902",
        "customer_message": "My order ORD-FAKE-999 hasn't arrived!",
        "order_info": {
            "id": "ORD-REAL-123",
            "amount": 50.00,
            "delivery_delayed_days": 2,
            "delivery_status": "delayed"
        }
    },
    {
        "issue_type": "refund",
        "ticket_id": "TKT-REF-903",
        "customer_message": "I want a refund.",
        "order_info": {
            "id": "ORD-REF-903",
            "amount": 25.00,
            "days_since_purchase": 2
        }
    },
    {
        "issue_type": "payment",
        "ticket_id": "TKT-PAY-904",
        "customer_message": "I was charged twice for a $600 order. Fix this!",
        "order_info": {
            "id": "ORD-PAY-904",
            "transaction_id": "TXN_999_B",
            "amount": 600.00,
            "transaction_status": "duplicate_charge",
            "duplicate_charge": True
        }
    }
]

def log_start(task_id: str, env: str, model: str) -> None:
    print(f"\n[START] task={task_id} env={env} model={model}", flush=True)

def log_step(step: int, action: str, reward: float, done: bool, error: Optional[str]) -> None:
    error_val = error if error else "null"
    done_val = str(done).lower()
    print(
        f"[STEP] step={step} action={action} reward={reward:.2f} done={done_val} error={error_val}",
        flush=True,
    )

def log_end(success: bool, steps: int, score: float, rewards: List[float]) -> None:
    rewards_str = ",".join(f"{r:.2f}" for r in rewards)
    print(f"[END] success={str(success).lower()} steps={steps} score={score:.3f} rewards={rewards_str}", flush=True)

def build_system_prompt() -> str:
    return textwrap.dedent(
        """
        You are an expert Customer Support Agent. Your goal is to resolve customer issues while following company policies.
        
        Available Actions:
        - approve_refund: Use when a refund is justified. Requires an 'amount'.
        - deny_refund: Use when a refund is not justified.
        - request_clarification: Use when you need more information to make a decision.
        - escalate: Use for complex cases that require supervisor intervention.
        - initiate_replacement: Choose this if the item is damaged or defective.
        - initiate_return: Start a return process for items that don't need immediate refund.
        - update_payment_method: Use for billing issues.
        - investigate_payment: Use for payment disputes.

        MANDATORY POLICY CHECK:
        Check the 'Required Fields' for the specific issue type. If any are missing, you MUST use 'request_clarification' first.
        
        Mandatory Response Format:
        You must reply with a JSON object containing EXACTLY these fields:
        {
            "action_type": "one of the available actions",
            "response": "the message you will send to the customer",
            "reason": "internal justification based on policy",
            "amount": number or null
        }
        """
    ).strip()

def build_user_prompt(obs) -> str:
    history = "\n".join([f"{h['role'].upper()}: {h['message']}" for h in obs.conversation_history])
    return textwrap.dedent(
        f"""
        [TICKET INFO]
        ID: {obs.ticket_id}
        Customer Message: {obs.customer_message}
        Issue Type: {obs.issue_type}
        Order Info: {json.dumps(obs.order_info, indent=2)}
        
        [POLICY CONTEXT]
        {obs.policy_context}
        
        [CONVERSATION HISTORY]
        {history if history else "No prior history."}
        
        Provide your next action in JSON format.
        """
    ).strip()

def get_model_action(client: OpenAI, obs) -> CustomersupportenvAction:
    if not API_KEY:
        return CustomersupportenvAction(
            action_type="request_clarification",
            response="I am missing the API authorization to help you.",
            reason="Missing API_KEY.",
            amount=None
        )

    system_prompt = build_system_prompt()
    user_prompt = build_user_prompt(obs)
    
    try:
        completion = client.chat.completions.create(
            model=MODEL_NAME,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            temperature=0.01,
            response_format={"type": "json_object"}
        )
        content = completion.choices[0].message.content
        data = json.loads(content)
        
        return CustomersupportenvAction(
            action_type=data.get("action_type", "request_clarification"),
            response=data.get("response", "I'm looking into this for you."),
            reason=data.get("reason", "Defaulting to clarification."),
            amount=data.get("amount")
        )
    except Exception as exc:
        print(f"[DEBUG] LLM Failure: {exc}", flush=True)
        return CustomersupportenvAction(
            action_type="request_clarification",
            response="I need a moment to review the policy.",
            reason=f"LLM parsing failed: {str(exc)[:50]}",
            amount=None
        )

async def run_episode(env: CustomersupportenvEnv, task: Dict[str, Any], client_llm: OpenAI) -> Dict[str, Any]:
    task_id = task.get("ticket_id", "TKT-UNKNOWN")
    log_start(task_id=task_id, env="customersupportenv", model=MODEL_NAME)
    
    rewards = []
    steps_taken = 0
    success = False
    score = 0.0
    
    try:
        result = await env.reset(task=task)
        
        for step in range(1, MAX_STEPS + 1):
            if result.done:
                break
            
            action = get_model_action(client_llm, result.observation)
            
            try:
                # Add a smaller timeout to avoid infinite hangs
                result = await asyncio.wait_for(env.step(action), timeout=30.0)
                reward = result.reward if result.reward is not None else 0.0
                done = result.done
                error_msg = None
            except asyncio.TimeoutError:
                reward = 0.0
                done = True
                error_msg = "Step timed out"
            except Exception as e:
                print(f"[DEBUG] Step failed for {task_id}: {e}")
                reward = 0.0
                done = True
                error_msg = str(e)
            
            rewards.append(reward)
            steps_taken = step
            
            log_step(
                step=step, 
                action=f"{action.action_type}({action.reason[:20]}...)", 
                reward=reward, 
                done=done, 
                error=error_msg
            )
            
            if done:
                break
        
        if rewards:
            score = rewards[-1]
            success = score >= 0.6
            
        log_end(success=success, steps=steps_taken, score=score, rewards=rewards)
        
        return {
            "task_id": task_id,
            "success": success,
            "steps": steps_taken,
            "score": score,
            "rewards": rewards
        }
        
    except Exception as e:
        print(f"[DEBUG] Episode {task_id} failed: {e}")
        log_end(success=False, steps=0, score=0.0, rewards=[])
        return {"task_id": task_id, "success": False, "steps": 0, "score": 0.0, "rewards": []}

async def main() -> None:
    if not API_KEY:
        print("[WARNING] No API key found. Please export HF_TOKEN or API_KEY.")

    client_llm = OpenAI(base_url=API_BASE_URL, api_key=API_KEY or "missing")
    
    try:
        # Prefer Docker if available, use exact tag 'customersupportenv:latest'
        env = await CustomersupportenvEnv.from_docker_image(IMAGE_NAME)
    except Exception as e:
        print(f"[DEBUG] Docker image {IMAGE_NAME} failed to start: {e}. Trying local server.")
        env = CustomersupportenvEnv(base_url="http://localhost:8000")

    results = []
    
    print("\n" + "="*50)
    print("CUSTOMER SUPPORT MULTI-TASK SIMULATION (REFINED)")
    print("="*50)

    try:
        async with env:
            for task in TEST_TASKS:
                res = await run_episode(env, task, client_llm)
                results.append(res)
        
        # Aggregated Summary
        if results:
            total_tasks = len(results)
            successful_tasks = sum(1 for r in results if r["success"])
            avg_score = sum(r["score"] for r in results) / total_tasks
            avg_steps = sum(r["steps"] for r in results) / total_tasks
            # Added Total Cumulative Rewards as requested
            total_rewards = sum(sum(r["rewards"]) for r in results)
            
            print("\n" + "="*50)
            print("SIMULATION SUMMARY")
            print("-" * 50)
            print(f"Total Tasks:           {total_tasks}")
            print(f"Success Rate:          {(successful_tasks/total_tasks)*100:.1f}% ({successful_tasks}/{total_tasks})")
            print(f"Average Final Score:   {avg_score:.3f}")
            print(f"Average Steps:         {avg_steps:.1f}")
            print(f"Total Cumulative Rewards: {total_rewards:.2f}")
            print("="*50 + "\n")

    except Exception as e:
        print(f"Simulation failed: {e}")

if __name__ == "__main__":
    asyncio.run(main())
