import json
import os
import re
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional
from uuid import uuid4

from openenv.core.env_server.interfaces import Environment
from openenv.core.env_server.types import State

try:
    from ..models import CustomersupportenvAction, CustomersupportenvObservation
except (ImportError, ModuleNotFoundError):
    from models import CustomersupportenvAction, CustomersupportenvObservation


class CustomersupportenvEnvironment(Environment):
    """
    Customer Support Environment that evaluates agent actions against company policies.
    """

    SUPPORTS_CONCURRENT_SESSIONS: bool = True

    # Class-level state to persist across stateless HTTP requests in simulation mode
    _shared_state: Optional[State] = None
    _shared_ticket: Optional[Dict[str, Any]] = None
    _shared_history: List[Dict[str, str]] = []
    _shared_start_time: Optional[datetime] = None
    _shared_reward: float = 0.01

    def __init__(self):
        """Initialize the environment and load policies."""
        if CustomersupportenvEnvironment._shared_state is None:
            CustomersupportenvEnvironment._shared_state = State(episode_id=str(uuid4()), step_count=0)
        self._policies = self._load_policies()

    def _load_policies(self) -> Dict[str, Dict[str, Any]]:
        """Load policy JSON files from the policies directory."""
        policies = {}
        # Try relative to this file or current working directory
        policy_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), "policies")
        if not os.path.exists(policy_dir):
            policy_dir = "policies"

        if os.path.exists(policy_dir):
            for filename in os.listdir(policy_dir):
                if filename.endswith(".json"):
                    try:
                        with open(os.path.join(policy_dir, filename), "r") as f:
                            policy = json.load(f)
                            category = policy.get("category")
                            if category:
                                policies[category] = policy
                    except Exception:
                        pass
        return policies

    def reset(self, task: Optional[Dict[str, Any]] = None) -> CustomersupportenvObservation:
        """
        Reset the environment with a specific task or a default one.
        """
        CustomersupportenvEnvironment._shared_state = State(episode_id=str(uuid4()), step_count=0)
        CustomersupportenvEnvironment._shared_history = []
        CustomersupportenvEnvironment._shared_start_time = datetime.now()
        CustomersupportenvEnvironment._shared_reward = 0.01

        if task:
            CustomersupportenvEnvironment._shared_ticket = task
        else:
            # Default mock ticket if no task provided
            CustomersupportenvEnvironment._shared_ticket = {
                "ticket_id": f"TKT-{uuid4().hex[:8].upper()}",
                "customer_message": "I'd like a refund for my recent order. It's within 7 days and I haven't opened it.",
                "order_info": {
                    "id": "ORD-123456",
                    "amount": 99.99,
                    "date": (datetime.now() - timedelta(days=5)).isoformat(),
                    "product": "Premium Headphones",
                    "item_condition": "unused",
                    "days_since_purchase": 5
                },
                "issue_type": "refund"
            }

        # Select relevant policy context
        issue_type = CustomersupportenvEnvironment._shared_ticket.get("issue_type", "refund")
        policy = self._policies.get(issue_type, {})
        policy_context = json.dumps(policy, indent=2) if policy else "No specific policy found for this issue type."

        return CustomersupportenvObservation(
            customer_message=CustomersupportenvEnvironment._shared_ticket["customer_message"],
            order_info=CustomersupportenvEnvironment._shared_ticket["order_info"],
            policy_context=policy_context,
            conversation_history=CustomersupportenvEnvironment._shared_history,
            ticket_id=CustomersupportenvEnvironment._shared_ticket["ticket_id"],
            issue_type=issue_type,
            done=False,
            reward=0.01
        )

    def step(self, action: CustomersupportenvAction) -> CustomersupportenvObservation:
        """
        Execute an agent action and evaluate it against the policy.
        """
        if CustomersupportenvEnvironment._shared_state:
            CustomersupportenvEnvironment._shared_state.step_count += 1

        if not CustomersupportenvEnvironment._shared_ticket:
            raise ValueError("Environment must be reset before step.")

        # Evaluate action against policy
        score, reward, done = self._evaluate_action(action)
        # Update cumulative reward and clamp to strict range (0, 1)
        # as required for Phase 2 deep validation.
        new_total = CustomersupportenvEnvironment._shared_reward + reward
        CustomersupportenvEnvironment._shared_reward = max(0.01, min(0.99, new_total))

        # Update conversation history with action details and reward
        CustomersupportenvEnvironment._shared_history.append({
            "role": "agent",
            "message": action.response,
            "action_type": action.action_type,
            "reward": reward
        })

        # If not done, we might add a customer response (optional, but good for multi-turn)
        current_customer_msg = CustomersupportenvEnvironment._shared_ticket["customer_message"]
        if not done and action.action_type == "request_clarification":
            # Simulate customer responding to clarification
            follow_up = "I've checked and I have the original packaging. Does that help?"
            CustomersupportenvEnvironment._shared_history.append({
                "role": "customer",
                "message": follow_up
            })
            current_customer_msg = follow_up

        # Return next observation
        return CustomersupportenvObservation(
            customer_message=current_customer_msg,
            order_info=CustomersupportenvEnvironment._shared_ticket["order_info"],
            policy_context="",  # Clear context on completion if done, otherwise keep?
                               # Usually keep for multi-turn, but OpenEnv might expect it to stay.
            conversation_history=CustomersupportenvEnvironment._shared_history,
            ticket_id=CustomersupportenvEnvironment._shared_ticket["ticket_id"],
            customer_satisfaction=score,
            issue_type=CustomersupportenvEnvironment._shared_ticket.get("issue_type", ""),
            elapsed_time=int((datetime.now() - (CustomersupportenvEnvironment._shared_start_time or datetime.now())).total_seconds()),
            done=done,
            reward=reward,
            metadata={"score": score, "reason": action.reason, "total_reward": CustomersupportenvEnvironment._shared_reward}
        )

    def _evaluate_action(self, action: CustomersupportenvAction) -> tuple[float, float, bool]:
        """
        Evaluate the agent's action against the loaded policies.
        Returns (score, reward, done)
        """
        issue_type = CustomersupportenvEnvironment._shared_ticket.get("issue_type", "refund")
        policy = self._policies.get(issue_type)

        if not policy:
            return 0.5, 0.5, True

        ticket_data = {**CustomersupportenvEnvironment._shared_ticket.get("order_info", {}), **CustomersupportenvEnvironment._shared_ticket}

        # Check rules in priority order
        rule_priority = policy.get("rule_priority", ["normal_rules", "default_rule"])

        matched_action = None
        matched_reason = "Default application"

        for group_name in rule_priority:
            rules = policy.get(group_name, [])
            if isinstance(rules, dict): # default_rule is a dict
                matched_action = rules.get("action")
                matched_reason = rules.get("reason", "Default rule")
                break

            for rule in rules:
                if self._check_condition(rule.get("condition"), ticket_data):
                    matched_action = rule.get("action") or rule.get("override_action")
                    matched_reason = rule.get("policy_reason")
                    break
            if matched_action:
                break

        # Scoring Logic
        score = 0.01  # Initialize with a small positive value

        # Define terminal vs non-terminal
        # In this env, anything other than 'request_clarification' is terminal
        is_clarification = action.action_type == "request_clarification"
        done = not is_clarification

        # 1. Action matched (0.6 points)
        if action.action_type == matched_action:
            score += 0.6
        elif is_clarification and matched_action == "request_clarification":
            score += 0.6

        # 2. Amount matched (0.2 points)
        if action.amount is not None and "amount" in ticket_data:
            expected_amount = ticket_data["amount"]
            if abs(action.amount - expected_amount) < 0.01:
                score += 0.2
        elif action.action_type in ["request_clarification", "escalate"]:
            score += 0.2 # No amount expected

        # 3. Tone/Length (0.2 points)
        if len(action.response) > 20:
            score += 0.2

        # 4. Hallucination check
        order_id = ticket_data.get("id")
        if order_id:
            mentioned_ids = re.findall(r"[A-Z]{3}-\d{6}", action.response)
            for mid in mentioned_ids:
                if mid != order_id:
                    score -= 0.5 # Heavier penalty for wrong IDs

        # Ensure score is strictly between 0 and 1 (not 0.0 and not 1.0)
        # as required for Phase 2 deep validation.
        score = max(0.01, min(0.99, score))
        reward = score

        return score, reward, done

    def _check_condition(self, condition: Any, data: Dict[str, Any]) -> bool:
        """Check if a condition from the JSON matches the ticket data."""
        if not condition:
            return False

        try:
            if isinstance(condition, str):
                # Handle conditions like "missing_required_fields"
                if condition == "missing_required_fields":
                    issue_type = data.get("issue_type", "refund")
                    policy = self._policies.get(issue_type, {})
                    required = policy.get("required_fields", [])
                    return any(field not in data or data[field] is None or data[field] == "" for field in required)

                # Handle "user_reason is null" or "user_reason == unknown"
                if "is null" in condition or "== unknown" in condition:
                    field = condition.split()[0]
                    val = data.get(field)
                    return val is None or val == "unknown" or val == ""

                # Handle " > " comparison like "amount > 500"
                if " > " in condition:
                    try:
                        field, val_str = condition.split(" > ")
                        val = data.get(field.strip())
                        if val is not None and float(val) > float(val_str.strip()):
                            return True
                    except Exception:
                        pass

                # Handle " == " comparison like "suspicious_activity == true"
                if " == " in condition:
                    try:
                        field, val_str = condition.split(" == ")
                        field = field.strip()
                        val_str = val_str.strip()
                        val = data.get(field)
                        if val_str == "true" and (val is True or str(val).lower() == "true"):
                            return True
                        if str(val).lower() == val_str:
                            return True
                    except Exception:
                        pass

                return False

            if isinstance(condition, dict):
                for key, value in condition.items():
                    # Support both top-level and potential nested checks if data was flattened
                    ticket_val = data.get(key)

                    if ticket_val is None:
                        return False

                    if isinstance(value, str):
                        # Handle comparisons like "<=7"
                        match = re.match(r"([<=|>=|<|>]+)(\d+)", value)
                        if match:
                            op, val_str = match.groups()
                            val = int(val_str)
                            try:
                                t_val = int(ticket_val)
                                if op == "<=":
                                    if not (t_val <= val): return False
                                elif op == ">=":
                                    if not (t_val >= val): return False
                                elif op == "<":
                                    if not (t_val < val): return False
                                elif op == ">":
                                    if not (t_val > val): return False
                            except (ValueError, TypeError):
                                return False
                        else:
                            if str(ticket_val).lower() != str(value).lower():
                                return False
                    else:
                        if ticket_val != value:
                            return False
                return True
        except Exception as e:
            print(f"[DEBUG] Condition matching error: {e}")
            return False

        return False

    @property
    def state(self) -> State:
        """Get the current environment state."""
        return CustomersupportenvEnvironment._shared_state or State(episode_id=str(uuid4()), step_count=0)