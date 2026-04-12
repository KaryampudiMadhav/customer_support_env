# Copyright (c) Meta Platforms, Inc. and affiliates.
# All rights reserved.
#
# This source code is licensed under the BSD-style license found in the
# LICENSE file in the root directory of this source tree.

"""
Data models for the Customersupportenv Environment.

The customersupportenv environment is a simple test environment that echoes back messages.
"""

from typing import Optional, List, Dict, Any
from openenv.core.env_server.types import Action, Observation
from pydantic import Field


class CustomersupportenvAction(Action):
    """Action for the Customersupportenv environment."""

    response: str = Field(..., description="Agent's message to customer (required)")
    action_type: str = Field(..., description="Decision made. Valid values include: approve_refund, deny_refund, request_clarification, escalate, initiate_replacement, initiate_return, update_payment_method")
    amount: Optional[float] = Field(None, description="Refund/credit amount in USD (if applicable)")
    reason: str = Field(..., description="Justification for the decision (from policy context)")


class CustomersupportenvObservation(Observation):
    """Observation from the Customersupportenv environment."""

    customer_message: str = Field(default="", description="Current customer message")
    order_info: Dict[str, Any] = Field(default_factory=dict, description="Order details: id, amount, date, product")
    policy_context: str = Field(default="", description="Relevant company policies")
    conversation_history: List[Dict[str, Any]] = Field(default_factory=list, description="Prior messages in ticket")
    ticket_id: str = Field(default="", description="Unique ticket identifier")
    customer_satisfaction: float = Field(default=1.0, description="Satisfaction score 0.0-1.0")
    issue_type: str = Field(default="", description="Type: refund, return, billing, delivery")
    elapsed_time: int = Field(default=0, description="Seconds spent on ticket")
