# Copyright (c) Meta Platforms, Inc. and affiliates.
# All rights reserved.
#
# This source code is licensed under the BSD-style license found in the
# LICENSE file in the root directory of this source tree.

"""
Data models for the Customer Support Environment.

The CustomerSupportEnv environment simulates a customer support agent handling
support tickets with different policy complexity levels.
"""

from typing import List
from openenv.core.env_server.types import Action, Observation
from pydantic import BaseModel, Field


class CustomerSupportAction(Action):
    """Action for the Customer Support environment."""

    response: str = Field(
        ..., description="Agent's message to customer"
    )
    action_type: str = Field(
        ..., description="One of: refund, partial_refund, replace, escalate, clarify, deny"
    )
    amount: float = Field(
        ..., description="Refund amount in USD"
    )
    reason: str = Field(
        ..., description="Justification/policy reference for the decision"
    )


class TicketInfo(BaseModel):
    """Information about the support ticket."""

    ticket_id: str = Field(..., description="Unique ticket identifier")
    issue_category: str = Field(..., description="Type: refund, replacement, payment, delivery")
    difficulty: str = Field(..., description="easy, medium, or hard")
    impact: str = Field(default="Low", description="Low, Medium, or High")
    tier: str = Field(default="Free", description="Free, Gold, or Platinum")


class OrderInfo(BaseModel):
    """Information about the customer's order."""

    order_id: str = Field(..., description="Order ID")
    amount: float = Field(..., description="Order total in USD")
    date: str = Field(..., description="Order date ISO format")
    product: str = Field(..., description="Product name")
    status: str = Field(..., description="Order status")


class CustomerInfo(BaseModel):
    """Information about the customer."""

    customer_id: str = Field(..., description="Customer ID")
    name: str = Field(..., description="Customer name")
    email: str = Field(..., description="Customer email")
    satisfaction: float = Field(
        default=0.5, description="Satisfaction score 0.0-1.0"
    )


class ActionHistoryEntry(BaseModel):
    """Entry in the action timeline."""

    step: int = Field(..., description="Step number")
    action_type: str = Field(..., description="Action type")
    description: str = Field(..., description="Rationale/Feedback")
    reward: float = Field(..., description="Reward for this step")


class CustomerSupportObservation(Observation):
    """Observation from the Customer Support environment."""

    customer_message: str = Field(..., description="Current customer message")
    ticket_info: TicketInfo = Field(..., description="Ticket metadata")
    order_info: OrderInfo = Field(..., description="Order details")
    customer_info: CustomerInfo = Field(..., description="Customer details")
    policy_context: str = Field(..., description="Relevant policy text")
    conversation_history: List[str] = Field(
        default_factory=list, description="Prior messages"
    )
    days_since_purchase: int = Field(default=0, description="Days since order")
    item_condition: str = Field(default="unused", description="unused, used, or damaged")
    user_reason: str = Field(default="", description="Customer's reason for request")
    transaction_status: str = Field(default="", description="Payment transaction status")
    transaction_id: str = Field(default="", description="Payment transaction ID")
    delivery_status: str = Field(default="", description="Delivery status")
    delivery_delayed_days: int = Field(default=0, description="Days delivery is delayed")
    sentiment: str = Field(default="Neutral", description="Satisfied, Neutral, or Frustrated")
    phase: str = Field(default="Unassigned", description="Unassigned, In Progress, or Resolved")
    sla_steps_left: int = Field(default=2, description="Steps remaining before SLA breach")
    total_reward: float = Field(default=0.0, description="Cumulative reward in episode")
    cumulative_score: float = Field(default=0.0, description="Percentage score 0-100")
    action_history: List[ActionHistoryEntry] = Field(
        default_factory=list, description="Detailed action timeline"
    )


VALID_ACTION_TYPES = ["refund", "partial_refund", "replace", "escalate", "clarify", "deny"]

VALID_REASONS_REFUND = ["item_damaged", "wrong_item", "changed_mind", "late_delivery", "defective_item"]
VALID_REASONS_REPLACEMENT = ["item_damaged", "wrong_item", "product_defect", "not_working", "missing_parts"]
VALID_TRANSACTION_STATUSES = ["successful", "failed", "pending", "duplicate_charge", "reversed", "bank_delay"]
VALID_DELIVERY_STATUSES = ["on_time", "delayed", "lost", "in_transit", "out_for_delivery", "delivered"]