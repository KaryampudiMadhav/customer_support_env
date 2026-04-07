# Copyright (c) Meta Platforms, Inc. and affiliates.
# All rights reserved.
#
# This source code is licensed under the BSD-style license found in the
# LICENSE file in the root directory of this source tree.

"""
Scenario generator and policy loader for Customer Support Environment.

Generates test tickets based on policy complexity levels.
"""

import json
import random
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional

try:
    from .models import (
        VALID_REASONS_REFUND,
        VALID_REASONS_REPLACEMENT,
        VALID_TRANSACTION_STATUSES,
        VALID_DELIVERY_STATUSES,
    )
except ImportError:
    from models import (
        VALID_REASONS_REFUND,
        VALID_REASONS_REPLACEMENT,
        VALID_TRANSACTION_STATUSES,
        VALID_DELIVERY_STATUSES,
    )
    VALID_REASONS_REFUND = ["item_damaged", "wrong_item", "changed_mind", "late_delivery", "defective_item"]
    VALID_REASONS_REPLACEMENT = ["item_damaged", "wrong_item", "product_defect", "not_working", "missing_parts"]
    VALID_TRANSACTION_STATUSES = ["successful", "failed", "pending", "duplicate_charge", "reversed", "bank_delay"]
    VALID_DELIVERY_STATUSES = ["on_time", "delayed", "lost", "in_transit", "out_for_delivery", "delivered"]


class PolicyLoader:
    """Loads and manages company policies."""

    def __init__(self, policies_dir: str = "policies"):
        self.policies_dir = Path(policies_dir)
        self.policies: Dict[str, Dict] = {}
        self._load_all_policies()

    def _load_all_policies(self):
        """Load all JSON policy files."""
        for i in range(1, 5):
            policy_file = self.policies_dir / f"{i}.json"
            if policy_file.exists():
                with open(policy_file) as f:
                    policy = json.load(f)
                    category = policy.get("category", f"policy_{i}")
                    self.policies[category] = policy

    def get_policy(self, category: str) -> Optional[Dict]:
        """Get policy by category name."""
        return self.policies.get(category)

    def get_all_categories(self) -> List[str]:
        """Get all policy category names."""
        return list(self.policies.keys())


class ScenarioGenerator:
    """Generates test scenarios across difficulty levels."""

    DIFFICULTY_MAP = {
        "refund": "medium",
        "replacement": "medium",
        "payment": "medium",
        "delivery": "easy",
    }

    def __init__(self, policies_dir: str = "policies"):
        self.policy_loader = PolicyLoader(policies_dir)
        self.rng = random.Random(42)

    def generate_ticket(
        self,
        category: str,
        difficulty: Optional[str] = None
    ) -> Dict[str, Any]:
        """Generate a single ticket for the given category."""
        if difficulty is None:
            difficulty = self.DIFFICULTY_MAP.get(category, "medium")

        if category == "refund":
            return self._generate_refund_ticket(difficulty)
        elif category == "replacement":
            return self._generate_replacement_ticket(difficulty)
        elif category == "payment":
            return self._generate_payment_ticket(difficulty)
        elif category == "delivery":
            return self._generate_delivery_ticket(difficulty)
        else:
            raise ValueError(f"Unknown category: {category}")

    def _generate_refund_ticket(self, difficulty: str) -> Dict[str, Any]:
        """Generate a refund ticket."""
        policy = self.policy_loader.get_policy("refund")
        valid_reasons = policy.get("valid_user_reasons", VALID_REASONS_REFUND)
        user_reason = self.rng.choice(valid_reasons)

        days_since_purchase = self.rng.randint(1, 35)
        if difficulty == "easy":
            days_since_purchase = self.rng.randint(1, 7)
        elif difficulty == "medium":
            days_since_purchase = self.rng.randint(1, 14)

        if user_reason in ["item_damaged", "wrong_item", "defective_item"]:
            item_condition = "damaged"
        else:
            item_condition = self.rng.choice(["unused", "used"])

        order_amount = round(self.rng.uniform(20, 500), 2)
        order_date = datetime.now() - timedelta(days=days_since_purchase)

        return {
            "ticket_id": f"TKT-{self.rng.randint(1000, 9999)}",
            "issue_category": "refund",
            "difficulty": difficulty,
            "customer_message": self._create_refund_message(user_reason, days_since_purchase),
            "order_info": {
                "order_id": f"ORD-{self.rng.randint(10000, 99999)}",
                "amount": order_amount,
                "date": order_date.strftime("%Y-%m-%d"),
                "product": self.rng.choice(["Laptop", "Headphones", "Watch", "Camera", "Phone"]),
                "status": "delivered",
            },
            "customer_info": {
                "customer_id": f"CUST-{self.rng.randint(100, 999)}",
                "name": self.rng.choice(["Alice Johnson", "Bob Smith", "Carol White", "David Brown"]),
                "email": f"customer{self.rng.randint(1, 100)}@example.com",
                "satisfaction": round(self.rng.uniform(0.3, 0.9), 2),
            },
            "days_since_purchase": days_since_purchase,
            "item_condition": item_condition,
            "user_reason": user_reason,
            "policy": policy,
        }

    def _create_refund_message(self, reason: str, days: int) -> str:
        """Create a customer message for refund scenarios."""
        messages = {
            "item_damaged": "I received my order and it's damaged. I want a refund.",
            "wrong_item": "Wrong item delivered. I ordered something else. Please refund.",
            "changed_mind": "I changed my mind about this purchase. I'd like a refund.",
            "late_delivery": "My order arrived way too late. I want a refund.",
            "defective_item": "The product doesn't work properly. It's defective.",
        }
        return messages.get(reason, f"I want a refund: {reason}")

    def _generate_replacement_ticket(self, difficulty: str) -> Dict[str, Any]:
        """Generate a replacement ticket."""
        policy = self.policy_loader.get_policy("replacement")
        valid_reasons = policy.get("valid_user_reasons", VALID_REASONS_REPLACEMENT)
        user_reason = self.rng.choice(valid_reasons)

        days_since_purchase = self.rng.randint(1, 15)
        order_date = datetime.now() - timedelta(days=days_since_purchase)

        return {
            "ticket_id": f"TKT-{self.rng.randint(1000, 9999)}",
            "issue_category": "replacement",
            "difficulty": difficulty,
            "customer_message": self._create_replacement_message(user_reason),
            "order_info": {
                "order_id": f"ORD-{self.rng.randint(10000, 99999)}",
                "amount": round(self.rng.uniform(50, 800), 2),
                "date": order_date.strftime("%Y-%m-%d"),
                "product": self.rng.choice(["Laptop", "Phone", "Tablet", "Watch", "Speaker"]),
                "status": "delivered",
            },
            "customer_info": {
                "customer_id": f"CUST-{self.rng.randint(100, 999)}",
                "name": self.rng.choice(["Alice Johnson", "Bob Smith", "Carol White", "David Brown"]),
                "email": f"customer{self.rng.randint(1, 100)}@example.com",
                "satisfaction": round(self.rng.uniform(0.3, 0.9), 2),
            },
            "days_since_purchase": days_since_purchase,
            "user_reason": user_reason,
            "policy": policy,
        }

    def _create_replacement_message(self, reason: str) -> str:
        """Create a customer message for replacement scenarios."""
        messages = {
            "item_damaged": "My item arrived damaged. I need a replacement.",
            "wrong_item": "I received the wrong item. Please send a replacement.",
            "product_defect": "This product has a defect. I need a replacement.",
            "not_working": "The product doesn't work at all. I need a replacement.",
            "missing_parts": "My order is missing parts. I need a replacement.",
        }
        return messages.get(reason, f"I need a replacement: {reason}")

    def _generate_payment_ticket(self, difficulty: str) -> Dict[str, Any]:
        """Generate a payment ticket."""
        policy = self.policy_loader.get_policy("payment")
        valid_statuses = policy.get("valid_transaction_statuses", VALID_TRANSACTION_STATUSES)
        transaction_status = self.rng.choice(valid_statuses)

        return {
            "ticket_id": f"TKT-{self.rng.randint(1000, 9999)}",
            "issue_category": "payment",
            "difficulty": difficulty,
            "customer_message": self._create_payment_message(transaction_status),
            "order_info": {
                "order_id": f"ORD-{self.rng.randint(10000, 99999)}",
                "amount": round(self.rng.uniform(20, 300), 2),
                "date": (datetime.now() - timedelta(days=self.rng.randint(0, 30))).strftime("%Y-%m-%d"),
                "product": self.rng.choice(["Subscription", "Digital Goods", "Service"]),
                "status": "paid",
            },
            "customer_info": {
                "customer_id": f"CUST-{self.rng.randint(100, 999)}",
                "name": self.rng.choice(["Alice Johnson", "Bob Smith", "Carol White", "David Brown"]),
                "email": f"customer{self.rng.randint(1, 100)}@example.com",
                "satisfaction": round(self.rng.uniform(0.3, 0.9), 2),
            },
            "transaction_status": transaction_status,
            "transaction_id": f"TXN-{self.rng.randint(100000, 999999)}",
            "policy": policy,
        }

    def _create_payment_message(self, status: str) -> str:
        """Create a customer message for payment scenarios."""
        messages = {
            "duplicate_charge": "I was charged twice for my order. Please refund the duplicate.",
            "failed": "My payment failed but I was charged. I need help.",
            "pending": "My payment has been pending for days. What's happening?",
            "reversed": "My payment was reversed. I need to complete this purchase.",
            "bank_delay": "My bank says the payment is delayed. What should I do?",
        }
        return messages.get(status, f"Payment issue: {status}")

    def _generate_delivery_ticket(self, difficulty: str) -> Dict[str, Any]:
        """Generate a delivery ticket."""
        policy = self.policy_loader.get_policy("delivery")
        valid_statuses = policy.get("valid_delivery_statuses", VALID_DELIVERY_STATUSES)
        delivery_status = self.rng.choice(valid_statuses)

        delayed_days = self.rng.randint(0, 10)
        if difficulty == "easy":
            delayed_days = self.rng.randint(0, 2)

        return {
            "ticket_id": f"TKT-{self.rng.randint(1000, 9999)}",
            "issue_category": "delivery",
            "difficulty": difficulty,
            "customer_message": self._create_delivery_message(delayed_days),
            "order_info": {
                "order_id": f"ORD-{self.rng.randint(10000, 99999)}",
                "amount": round(self.rng.uniform(20, 300), 2),
                "date": (datetime.now() - timedelta(days=self.rng.randint(3, 14))).strftime("%Y-%m-%d"),
                "product": self.rng.choice(["Electronics", "Clothing", "Books"]),
                "status": delivery_status,
            },
            "customer_info": {
                "customer_id": f"CUST-{self.rng.randint(100, 999)}",
                "name": self.rng.choice(["Alice Johnson", "Bob Smith", "Carol White", "David Brown"]),
                "email": f"customer{self.rng.randint(1, 100)}@example.com",
                "satisfaction": round(self.rng.uniform(0.3, 0.9), 2),
            },
            "delivery_delayed_days": delayed_days,
            "delivery_status": delivery_status,
            "policy": policy,
        }

    def _create_delivery_message(self, delayed_days: int) -> str:
        """Create a customer message for delivery scenarios."""
        if delayed_days <= 2:
            return "My package is taking longer than expected. When will it arrive?"
        elif delayed_days < 7:
            return f"My order is now {delayed_days} days late. This is unacceptable!"
        else:
            return f"My package is {delayed_days} days late! I want a refund and to cancel my order!"

    def get_policy_text(self, category: str) -> str:
        """Extract human-readable policy text for the category."""
        policy = self.policy_loader.get_policy(category)
        if not policy:
            return ""

        lines = []
        lines.append(f"Category: {policy.get('category', category)}")
        lines.append("")

        normal_rules = policy.get("normal_rules", [])
        if normal_rules:
            lines.append("Normal Rules:")
            for rule in normal_rules:
                lines.append(f"  - {rule.get('policy_reason', '')}")

        exceptions = policy.get("exceptions", [])
        if exceptions:
            lines.append("Exceptions:")
            for exc in exceptions:
                lines.append(f"  - {exc.get('policy_reason', '')}")

        return "\n".join(lines)


def get_scenario_pool(policies_dir: str = "policies") -> Dict[str, List[Dict]]:
    """Get a pre-generated pool of scenarios by difficulty."""
    generator = ScenarioGenerator(policies_dir)

    pool = {
        "easy": [],
        "medium": [],
        "hard": [],
    }

    categories = generator.policy_loader.get_all_categories()
    for category in categories:
        difficulty = ScenarioGenerator.DIFFICULTY_MAP.get(category, "medium")
        for _ in range(5):
            ticket = generator.generate_ticket(category, difficulty)
            pool[difficulty].append(ticket)

    return pool