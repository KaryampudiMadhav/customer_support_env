# Copyright (c) Meta Platforms, Inc. and affiliates.
# All rights reserved.
#
# This source code is licensed under the BSD-style license found in the
# LICENSE file in the root directory of this source tree.

"""
Customer Support Environment Implementation.

Simulates a customer support agent handling support tickets
with policy evaluation across different difficulty levels.
"""

import random
from datetime import datetime, timedelta
from typing import Any, Dict , Optional

from openenv.core.env_server.interfaces import Environment
from openenv.core.env_server.types import State

try:
    from ..models import (
        CustomerSupportAction,
        CustomerSupportObservation,
        OrderInfo,
        TicketInfo,
        CustomerInfo,
        VALID_ACTION_TYPES,
        ActionHistoryEntry,
    )
    from ..grading import final_grade
except ImportError:
    from models import (
        CustomerSupportAction,
        CustomerSupportObservation,
        OrderInfo,
        TicketInfo,
        CustomerInfo,
        VALID_ACTION_TYPES,
        ActionHistoryEntry,
    )
    from grading import final_grade


DEFAULT_POLICIES = {
    "refund": {
        "category": "refund",
        "valid_user_reasons": ["item_damaged", "wrong_item", "changed_mind", "late_delivery", "defective_item"],
        "normal_rules": [
            {"id": "R1", "condition": {"days_since_purchase": "<=7", "item_condition": "unused"}, "action": "approve_refund"},
            {"id": "R2", "condition": {"days_since_purchase": ">7"}, "action": "deny_refund"},
            {"id": "R3", "condition": {"item_condition": "used"}, "action": "deny_refund"},
        ],
        "exceptions": [
            {"condition": {"user_reason": "item_damaged"}, "override_action": "offer_resolution_options"},
            {"condition": {"user_reason": "wrong_item"}, "override_action": "offer_resolution_options"},
        ],
    },
    "replacement": {
        "category": "replacement",
        "valid_user_reasons": ["item_damaged", "wrong_item", "product_defect", "not_working", "missing_parts"],
        "normal_rules": [
            {"id": "R1", "condition": {"days_since_purchase": "<=10"}, "action": "initiate_replacement"},
            {"id": "R2", "condition": {"days_since_purchase": ">10"}, "action": "deny_replacement"},
        ],
        "exceptions": [
            {"condition": {"user_reason": "product_defect"}, "override_action": "initiate_replacement"},
            {"condition": {"user_reason": "missing_parts"}, "override_action": "initiate_replacement"},
        ],
    },
    "payment": {
        "category": "payment",
        "valid_transaction_statuses": ["successful", "failed", "pending", "duplicate_charge", "reversed", "bank_delay"],
        "normal_rules": [
            {"condition": {"duplicate_charge": True}, "action": "issue_refund"},
            {"condition": {"payment_failed": True}, "action": "investigate_payment"},
        ],
        "edge_cases": [
            {"condition": "suspicious_activity", "action": "escalate"},
        ],
    },
    "delivery": {
        "category": "delivery",
        "valid_delivery_statuses": ["on_time", "delayed", "lost", "in_transit", "out_for_delivery", "delivered"],
        "normal_rules": [
            {"condition": {"delivery_delayed_days": "<3"}, "action": "apologize_and_inform"},
            {"condition": {"delivery_delayed_days": ">=3"}, "action": "provide_tracking_info"},
        ],
    },
}


class CustomerSupportEnvironment(Environment):
    """
    Customer support environment for evaluating agent policy compliance.

    The environment presents support tickets to agents and evaluates
    their responses based on company policy adherence and resolution quality.
    """

    SUPPORTS_CONCURRENT_SESSIONS: bool = True

    def __init__(self, policies_dir: str = "policies"):
        self._state = State(episode_id="", step_count=0)
        self._current_ticket: Dict[str, Any] = {}
        self._conversation_history = []
        self._rng = random.Random()
        self._policies = DEFAULT_POLICIES
        self._total_reward = 0.0
        self._max_possible_reward = 0.0
        self._action_history = []
        self._baseline_satisfaction = 0.5

    @property
    def state(self) -> State:
        return self._state

    @property
    def grade(self) -> float:
        """Compute the final grade using the grading module."""
        if not self._action_history:
            return 0.0

        last_action = self._action_history[-1]
        action_type = last_action.get("action_type", "")

        final_obs = self.get_observation().model_dump()
        final_obs["done"] = True  # Grade only computed after episode ends

        baseline_satisfaction = self._baseline_satisfaction
        steps_used = self._state.step_count
        requires_decisive = self._current_ticket.get("difficulty") == "hard"

        return final_grade(
            action_type=action_type,
            final_obs=final_obs,
            baseline_satisfaction=baseline_satisfaction,
            steps_used=steps_used,
            requires_decisive=requires_decisive,
        )

    def reset(
        self,
        seed: Optional[int] = None,
        episode_id: Optional[str] = None,
        **kwargs: Any
    ) -> CustomerSupportObservation:
        """Reset the environment with a new random ticket."""
        import uuid

        self._state = State(episode_id=episode_id or str(uuid.uuid4()), step_count=0)
        self._conversation_history = []
        self._total_reward = 0.0
        self._max_possible_reward = 0.0
        self._action_history = []
        self._current_ticket = self._generate_random_ticket(category=kwargs.get("category"))
        self._rng = random.Random(self._state.episode_id)
        self._baseline_satisfaction = self._current_ticket.get("customer_info", {}).get("satisfaction", 0.5)

        return self.get_observation()

    def _generate_random_ticket(self, category: Optional[str] = None) -> Dict[str, Any]:
        """Generate a random ticket or one from a specific category."""
        if not category:
            categories = ["refund", "replacement", "payment", "delivery"]
            category = self._rng.choice(categories)

        if category == "refund":
            return self._generate_refund_ticket()
        elif category == "replacement":
            return self._generate_replacement_ticket()
        elif category == "payment":
            return self._generate_payment_ticket()
        else:
            return self._generate_delivery_ticket()

    def _generate_refund_ticket(self) -> Dict[str, Any]:
        """Generate a refund ticket."""
        policy = self._policies.get("refund", {})
        valid_reasons = policy.get("valid_user_reasons", [
            "item_damaged", "wrong_item", "changed_mind", "late_delivery", "defective_item"
        ])
        user_reason = self._rng.choice(valid_reasons)

        days_since_purchase = self._rng.randint(1, 35)
        if user_reason in ["item_damaged", "wrong_item", "defective_item"]:
            item_condition = "damaged"
        else:
            item_condition = self._rng.choice(["unused", "used"])

        order_amount = round(self._rng.uniform(20, 500), 2)
        order_date = datetime.now() - timedelta(days=days_since_purchase)

        return {
            "ticket_id": f"TKT-{self._rng.randint(1000, 9999)}",
            "issue_category": "refund",
            "difficulty": self._rng.choice(["easy", "medium", "hard"]),
            "customer_message": f"I want a refund because: {user_reason}",
            "order_info": {
                "order_id": f"ORD-{self._rng.randint(10000, 999999)}",
                "amount": order_amount,
                "date": order_date.strftime("%Y-%m-%d"),
                "product": self._rng.choice(["Laptop", "Headphones", "Watch", "Camera", "Phone"]),
                "status": "delivered",
            },
            "customer_info": {
                "customer_id": f"CUST-{self._rng.randint(100, 999)}",
                "name": self._rng.choice(["Alice Johnson", "Bob Smith", "Carol White", "David Brown"]),
                "email": f"customer{self._rng.randint(1, 100)}@example.com",
                "satisfaction": round(self._rng.uniform(0.3, 0.9), 2),
            },
            "days_since_purchase": days_since_purchase,
            "item_condition": item_condition,
            "user_reason": user_reason,
            "policy": policy,
            "impact": self._rng.choice(["Low", "Medium", "High"]),
            "tier": self._rng.choice(["Free", "Gold", "Platinum"]),
            "sentiment": self._rng.choice(["Satisfied", "Neutral", "Frustrated"]),
            "phase": "Unassigned",
            "sla_steps_left": self._rng.randint(2, 5),
        }

    def _generate_replacement_ticket(self) -> Dict[str, Any]:
        """Generate a replacement ticket."""
        policy = self._policies.get("replacement", {})
        valid_reasons = policy.get("valid_user_reasons", [
            "item_damaged", "wrong_item", "product_defect", "not_working", "missing_parts"
        ])
        user_reason = self._rng.choice(valid_reasons)

        days_since_purchase = self._rng.randint(1, 15)
        order_date = datetime.now() - timedelta(days=days_since_purchase)

        return {
            "ticket_id": f"TKT-{self._rng.randint(1000, 9999)}",
            "issue_category": "replacement",
            "difficulty": self._rng.choice(["easy", "medium", "hard"]),
            "customer_message": f"I need a replacement because: {user_reason}",
            "order_info": {
                "order_id": f"ORD-{self._rng.randint(10000, 999999)}",
                "amount": round(self._rng.uniform(50, 800), 2),
                "date": order_date.strftime("%Y-%m-%d"),
                "product": self._rng.choice(["Laptop", "Phone", "Tablet", "Watch", "Speaker"]),
                "status": "delivered",
            },
            "customer_info": {
                "customer_id": f"CUST-{self._rng.randint(100, 999)}",
                "name": self._rng.choice(["Alice Johnson", "Bob Smith", "Carol White", "David Brown"]),
                "email": f"customer{self._rng.randint(1, 100)}@example.com",
                "satisfaction": round(self._rng.uniform(0.3, 0.9), 2),
            },
            "days_since_purchase": days_since_purchase,
            "user_reason": user_reason,
            "policy": policy,
            "impact": self._rng.choice(["Low", "Medium", "High"]),
            "tier": self._rng.choice(["Free", "Gold", "Platinum"]),
            "sentiment": self._rng.choice(["Satisfied", "Neutral", "Frustrated"]),
            "phase": "Unassigned",
            "sla_steps_left": self._rng.randint(2, 5),
        }

    def _generate_payment_ticket(self) -> Dict[str, Any]:
        """Generate a payment ticket."""
        policy = self._policies.get("payment", {})
        valid_statuses = policy.get("valid_transaction_statuses", [
            "successful", "failed", "pending", "duplicate_charge", "reversed", "bank_delay"
        ])
        transaction_status = self._rng.choice(valid_statuses)

        return {
            "ticket_id": f"TKT-{self._rng.randint(1000, 9999)}",
            "issue_category": "payment",
            "difficulty": self._rng.choice(["easy", "medium", "hard"]),
            "customer_message": f"Payment issue: {transaction_status}",
            "order_info": {
                "order_id": f"ORD-{self._rng.randint(10000, 99999)}",
                "amount": round(self._rng.uniform(20, 300), 2),
                "date": datetime.now().strftime("%Y-%m-%d"),
                "product": self._rng.choice(["Subscription", "Digital Goods", "Service"]),
                "status": "paid",
            },
            "customer_info": {
                "customer_id": f"CUST-{self._rng.randint(100, 999)}",
                "name": self._rng.choice(["Alice Johnson", "Bob Smith", "Carol White", "David Brown"]),
                "email": f"customer{self._rng.randint(1, 100)}@example.com",
                "satisfaction": round(self._rng.uniform(0.3, 0.9), 2),
            },
            "transaction_status": transaction_status,
            "transaction_id": f"TXN-{self._rng.randint(100000, 999999)}",
            "policy": policy,
            "impact": self._rng.choice(["Low", "Medium", "High"]),
            "tier": self._rng.choice(["Free", "Gold", "Platinum"]),
            "sentiment": self._rng.choice(["Satisfied", "Neutral", "Frustrated"]),
            "phase": "Unassigned",
            "sla_steps_left": self._rng.randint(2, 5),
        }

    def _generate_delivery_ticket(self) -> Dict[str, Any]:
        """Generate a delivery ticket."""
        policy = self._policies.get("delivery", {})
        valid_statuses = policy.get("valid_delivery_statuses", [
            "on_time", "delayed", "lost", "in_transit", "out_for_delivery", "delivered"
        ])
        delivery_status = self._rng.choice(valid_statuses)

        delayed_days = self._rng.randint(0, 10)

        return {
            "ticket_id": f"TKT-{self._rng.randint(1000, 9999)}",
            "issue_category": "delivery",
            "difficulty": "easy",
            "customer_message": f"Delivery status: {delivery_status}, delayed {delayed_days} days",
            "order_info": {
                "order_id": f"ORD-{self._rng.randint(10000, 99999)}",
                "amount": round(self._rng.uniform(20, 300), 2),
                "date": datetime.now().strftime("%Y-%m-%d"),
                "product": self._rng.choice(["Electronics", "Clothing", "Books"]),
                "status": delivery_status,
            },
            "customer_info": {
                "customer_id": f"CUST-{self._rng.randint(100, 999)}",
                "name": self._rng.choice(["Alice Johnson", "Bob Smith", "Carol White", "David Brown"]),
                "email": f"customer{self._rng.randint(1, 100)}@example.com",
                "satisfaction": round(self._rng.uniform(0.3, 0.9), 2),
            },
            "delivery_delayed_days": delayed_days,
            "delivery_status": delivery_status,
            "policy": policy,
            "impact": self._rng.choice(["Low", "Medium", "High"]),
            "tier": self._rng.choice(["Free", "Gold", "Platinum"]),
            "sentiment": "Frustrated" if delayed_days > 5 else "Neutral",
            "phase": "Unassigned",
            "sla_steps_left": self._rng.randint(2, 5),
        }

    def get_observation(self) -> CustomerSupportObservation:
        """Build observation from current ticket."""
        ticket = self._current_ticket
        order = ticket.get("order_info", {})
        customer = ticket.get("customer_info", {})

        policy = ticket.get("policy", {})
        policy_text = ""
        if policy:
            rules = policy.get("normal_rules", [])
            if rules:
                policy_text = " | ".join([r.get("action", "") for r in rules[:3]])
            policy_text += f" [Category: {ticket.get('issue_category', 'general')}]"

        return CustomerSupportObservation(
            customer_message=ticket.get("customer_message", ""),
            ticket_info=TicketInfo(
                ticket_id=ticket.get("ticket_id", ""),
                issue_category=ticket.get("issue_category", "general"),
                difficulty=ticket.get("difficulty", "medium"),
                impact=ticket.get("impact", "Low"),
                tier=ticket.get("tier", "Free"),
            ),
            order_info=OrderInfo(
                order_id=order.get("order_id", ""),
                amount=order.get("amount", 0.0),
                date=order.get("date", ""),
                product=order.get("product", ""),
                status=order.get("status", ""),
            ),
            customer_info=CustomerInfo(
                customer_id=customer.get("customer_id", ""),
                name=customer.get("name", ""),
                email=customer.get("email", ""),
                satisfaction=customer.get("satisfaction", 0.5),
            ),
            policy_context=policy_text,
            conversation_history=self._conversation_history.copy(),
            days_since_purchase=ticket.get("days_since_purchase", 0),
            item_condition=ticket.get("item_condition", "unused"),
            user_reason=ticket.get("user_reason", ""),
            transaction_status=ticket.get("transaction_status", ""),
            transaction_id=ticket.get("transaction_id", ""),
            delivery_status=ticket.get("delivery_status", ""),
            delivery_delayed_days=ticket.get("delivery_delayed_days", 0),
            sentiment=ticket.get("sentiment", "Neutral"),
            phase=ticket.get("phase", "Unassigned"),
            sla_steps_left=ticket.get("sla_steps_left", 2),
            total_reward=round(self._total_reward, 2),
            cumulative_score=round((self._total_reward / self._max_possible_reward * 100) if self._max_possible_reward > 0 else 0, 2),
            action_history=[ActionHistoryEntry(**entry) for entry in self._action_history],
            done=False,
            reward=0.0,
        )

    def step(
        self,
        action: CustomerSupportAction,
        timeout_s: Optional[float] = None,
        **kwargs: Any
    ) -> CustomerSupportObservation:
        """Execute a step and evaluate the agent's response."""
        self._state.step_count += 1
        self._conversation_history.append(action.response)

        # Track max possible reward for score calculation
        self._max_possible_reward += 1.0

        reward, rationale = self._evaluate_action(action)
        self._total_reward += reward

        # Record in action history
        self._action_history.append({
            "step": self._state.step_count,
            "action_type": action.action_type,
            "description": rationale,
            "reward": round(reward, 2)
        })

        # Update SLA steps left
        current_sla = self._current_ticket.get("sla_steps_left", 2)
        self._current_ticket["sla_steps_left"] = max(0, current_sla - 1)

        # Determine if episode should end
        decisive_actions = {"refund", "partial_refund", "replace", "escalate", "deny"}
        is_decisive = action.action_type in decisive_actions
        is_sla_exhausted = self._current_ticket.get("sla_steps_left", 0) <= 0

        # Set phase based on action
        if is_decisive:
            self._current_ticket["phase"] = "resolved"

        obs = self.get_observation()
        obs.reward = reward
        # Episode ends on decisive action OR SLA exhaustion
        obs.done = is_decisive or is_sla_exhausted

        return obs

    def _evaluate_action(self, action: CustomerSupportAction) -> tuple[float, str]:
        """Evaluate the agent's action against policy."""
        ticket = self._current_ticket
        category = ticket.get("issue_category", "general")
        policy = ticket.get("policy", {})

        score = 0.0
        rationale = "Evaluated against general policy."

        if action.action_type not in VALID_ACTION_TYPES:
            return -0.5, f"Invalid action type: {action.action_type}"

        if category == "refund":
            score, rationale = self._evaluate_refund_action(action, ticket, policy)
        elif category == "replacement":
            score, rationale = self._evaluate_replacement_action(action, ticket, policy)
        elif category == "payment":
            score, rationale = self._evaluate_payment_action(action, ticket, policy)
        elif category == "delivery":
            score, rationale = self._evaluate_delivery_action(action, ticket, policy)

        if action.response and len(action.response) < 10:
            score -= 0.2
            rationale += " (Response too short)"

        if self._detect_hallucination(action, ticket):
            score -= 0.3
            rationale += " (Potential hallucination detected)"

        return max(-1.0, min(1.0, score)), rationale

    def _evaluate_refund_action(
        self,
        action: CustomerSupportAction,
        ticket: Dict,
        policy: Dict
    ) -> tuple[float, str]:
        """Evaluate refund action against policy."""
        days = ticket.get("days_since_purchase", 0)
        item_condition = ticket.get("item_condition", "unused")
        order_amount = ticket.get("order_info", {}).get("amount", 0.0)

        can_refund = days <= 7 and item_condition == "unused"
        cannot_refund = days > 7 or item_condition == "used"

        if action.action_type == "clarify":
            return 0.5, "Clarification is a safe starting point."
        elif action.action_type == "escalate":
            return 0.3, "Escalation before policy check is premature."
        elif action.action_type == "deny" and cannot_refund:
            return 0.8, f"Correctly denied: {days} days since purchase or used condition."
        elif action.action_type == "deny" and not can_refund:
            return 0.6, "Denied refund based on suboptimal conditions."
        elif action.action_type in ["refund", "partial_refund"] and can_refund:
            score = 0.8
            rationale = "Approved refund within 7-day unused policy."
            if action.amount and action.amount > order_amount:
                score -= 0.4
                rationale += f" (Warning: Amount {action.amount} exceeds order value {order_amount})"
            return score, rationale
        else:
            return 0.1, f"Action '{action.action_type}' does not align with refund policy."

    def _evaluate_replacement_action(
        self,
        action: CustomerSupportAction,
        ticket: Dict,
        policy: Dict
    ) -> tuple[float, str]:
        """Evaluate replacement action against policy."""
        days = ticket.get("days_since_purchase", 0)
        user_reason = ticket.get("user_reason", "")

        can_replace = days <= 10 or user_reason in ["product_defect", "missing_parts"]

        if action.action_type == "clarify":
            return 0.5, "Clarification for replacement criteria."
        elif action.action_type == "escalate":
            return 0.3, "Escalation for replacement."
        elif action.action_type == "replace" and can_replace:
            return 0.8, "Approved replacement per 10-day defect policy."
        elif action.action_type == "deny" and not can_replace:
            return 0.7, "Denied replacement (outside 10-day window/no defect)."
        else:
            return 0.1, "Action does not match replacement policy."

    def _evaluate_payment_action(
        self,
        action: CustomerSupportAction,
        ticket: Dict,
        policy: Dict
    ) -> tuple[float, str]:
        """Evaluate payment action against policy."""
        transaction_status = ticket.get("transaction_status", "")
        normal_rules = policy.get("normal_rules", [])
        expected_action = "investigate_payment"

        for rule in normal_rules:
            conditions = rule.get("condition", {})
            if "duplicate_charge" in conditions and transaction_status == "duplicate_charge":
                expected_action = rule.get("action", "issue_refund")
                break
            if "payment_failed" in conditions and transaction_status == "failed":
                expected_action = rule.get("action", "investigate_payment")
                break

        if action.action_type == "clarify":
            return 0.5, "Clarification for payment issues."
        elif action.action_type == "escalate":
            return 0.3, "Escalation for payment issues."

        return 0.1, "Payment policy check completed."

    def _evaluate_delivery_action(
        self,
        action: CustomerSupportAction,
        ticket: Dict,
        policy: Dict
    ) -> tuple[float, str]:
        """Evaluate delivery action against policy."""
        delayed_days = ticket.get("delivery_delayed_days", 0)

        if action.action_type == "clarify":
            return 0.5, f"Clarifying delivery timeline for {delayed_days} day delay."
        elif action.action_type == "escalate":
            return 0.3, "Escalating delivery delay."

        return 0.2, "Delivery policy evaluation completed."

    def _check_days(self, condition: str, days: int) -> bool:
        """Check if days condition matches."""
        if "<=7" in condition:
            return days <= 7
        elif ">7" in condition:
            return days > 7
        elif "<=10" in condition:
            return days <= 10
        elif ">10" in condition:
            return days > 10
        elif "<3" in condition:
            return days < 3
        elif ">=" in condition:
            return days >= int(condition.replace(">=", ""))
        return True

    def _detect_hallucination(self, action: CustomerSupportAction, ticket: Dict) -> bool:
        """Detect potential hallucinations in the response."""
        response_lower = action.response.lower()
        order = ticket.get("order_info", {})

        hallucination_patterns = [
            "lifetime warranty",
            "100% satisfaction guarantee",
            "free for life",
            "VIP customer",
            "exclusive deal",
        ]

        for pattern in hallucination_patterns:
            if pattern in response_lower:
                return True

        if action.amount and order.get("amount", 0) > 0:
            if action.amount > order.get("amount", 0) * 2:
                return True

        return False