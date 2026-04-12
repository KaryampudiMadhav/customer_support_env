# Copyright (c) Meta Platforms, Inc. and affiliates.
# All rights reserved.
#
# This source code is licensed under the BSD-style license found in the
# LICENSE file in the root directory of this source tree.

"""Customersupportenv Environment Client."""

from typing import Dict

from openenv.core import EnvClient
from openenv.core.client_types import StepResult
from openenv.core.env_server.types import State

try:
    from .models import CustomersupportenvAction, CustomersupportenvObservation
except (ImportError, ValueError):
    from models import CustomersupportenvAction, CustomersupportenvObservation


class CustomersupportenvEnv(
    EnvClient[CustomersupportenvAction, CustomersupportenvObservation, State]
):
    """
    Client for the Customersupportenv Environment.

    This client maintains a persistent WebSocket connection to the environment server,
    enabling efficient multi-step interactions with lower latency.
    Each client instance has its own dedicated environment session on the server.

    Example:
        >>> # Connect to a running server
        >>> with CustomersupportenvEnv(base_url="http://localhost:8000") as client:
        ...     result = client.reset()
        ...     print(result.observation.echoed_message)
        ...
        ...     result = client.step(CustomersupportenvAction(message="Hello!"))
        ...     print(result.observation.echoed_message)

    Example with Docker:
        >>> # Automatically start container and connect
        >>> client = CustomersupportenvEnv.from_docker_image("openenv-customersupportenv:latest")
        >>> try:
        ...     result = client.reset()
        ...     result = client.step(CustomersupportenvAction(message="Test"))
        ... finally:
        ...     client.close()
    """

    def _step_payload(self, action: CustomersupportenvAction) -> Dict:
        """
        Convert CustomersupportenvAction to JSON payload for step message.
        """
        # Return fields directly without 'action' wrapper for WS bridge compatibility
        return {
            "response": action.response,
            "action_type": action.action_type,
            "amount": action.amount,
            "reason": action.reason
        }

    def _parse_result(self, payload: Dict) -> StepResult[CustomersupportenvObservation]:
        """
        Parse server response into StepResult[CustomersupportenvObservation].
        """
        obs_data = payload.get("observation", {})
        observation = CustomersupportenvObservation(
            customer_message=obs_data.get("customer_message", ""),
            order_info=obs_data.get("order_info", {}),
            policy_context=obs_data.get("policy_context", ""),
            conversation_history=obs_data.get("conversation_history", []),
            ticket_id=obs_data.get("ticket_id", ""),
            customer_satisfaction=obs_data.get("customer_satisfaction", 0.99),
            issue_type=obs_data.get("issue_type", ""),
            elapsed_time=obs_data.get("elapsed_time", 0)
        )

        return StepResult(
            observation=observation,
            reward=payload.get("reward", 0.01),
            done=payload.get("done", False),
        )

    def _parse_state(self, payload: Dict) -> State:
        """
        Parse server response into State object.

        Args:
            payload: JSON response from state request

        Returns:
            State object with episode_id and step_count
        """
        return State(
            episode_id=payload.get("episode_id"),
            step_count=payload.get("step_count", 0),
        )