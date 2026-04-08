# # Copyright (c) Meta Platforms, Inc. and affiliates.
# # All rights reserved.
# #
# # This source code is licensed under the BSD-style license found in the
# # LICENSE file in the root directory of this source tree.

# """Customer Support Environment Client."""

# from typing import Dict
# import json
# from pathlib import Path

# from openenv.core import EnvClient
# from openenv.core.client_types import StepResult
# from openenv.core.env_server.types import State

# try:
#     from .models import CustomerSupportAction, CustomerSupportObservation
# except ImportError:
#     from models import CustomerSupportAction, CustomerSupportObservation  # type: ignore[no-redef]


# class CustomerSupportEnv(
#     EnvClient[CustomerSupportAction, CustomerSupportObservation, State]
# ):
#     """
#     Client for the Customer Support Environment.

#     This client maintains a persistent WebSocket connection to the environment server,
#     enabling efficient multi-step interactions with lower latency.
#     Each client instance has its own dedicated environment session on the server.

#     Example:
#         >>> # Connect to a running server
#         >>> with CustomerSupportEnv(base_url="http://localhost:8000") as client:
#         ...     result = client.reset()
#         ...     print(result.observation.customer_message)
#         ...     print(result.observation.ticket_info)
#         ...
#         ...     result = client.step(CustomerSupportAction(
#         ...         response="I'd be happy to help with your refund.",
#         ...         action_type="refund",
#         ...         amount=99.99,
#         ...         reason="Within return window"
#         ...     ))
#         ...     print(result.observation.reward)

#     Example with Docker:
#         >>> # Automatically start container and connect
#         >>> client = CustomerSupportEnv.from_docker_image("customer-support-env:latest")
#         >>> try:
#         ...     result = client.reset()
#         ...     result = client.step(CustomerSupportAction(
#         ...         response="...",
#         ...         action_type="...",
#         ...         reason="..."
#         ...     ))
#         ... finally:
#         ...     client.close()
#     """

#     def _step_payload(self, action: CustomerSupportAction) -> Dict:
#         """
#         Convert CustomerSupportAction to JSON payload for step message.

#         Args:
#             action: CustomerSupportAction instance

#         Returns:
#             Dictionary representation suitable for JSON encoding
#         """
#         return {
#             "response": action.response,
#             "action_type": action.action_type,
#             "amount": action.amount,
#             "reason": action.reason,
#         }

#     def _parse_result(self, payload: Dict) -> StepResult[CustomerSupportObservation]:
#         """
#         Parse server response into StepResult[CustomerSupportObservation].

#         Args:
#             payload: JSON response data from server

#         Returns:
#             StepResult with CustomerSupportObservation
#         """
#         # DEBUG: dump raw payload for troubleshooting
#         try:
#             Path("d:/customer_support_env/payload_debug.json").write_text(json.dumps(payload, indent=2))
#         except Exception:
#             pass

#         obs_data = payload.get("observation", {})

#         ticket_data = obs_data.get("ticket_info", {})
#         order_data = obs_data.get("order_info", {})
#         customer_data = obs_data.get("customer_info", {})

#         observation = CustomerSupportObservation(
#             customer_message=obs_data.get("customer_message", ""),
#             ticket_info=ticket_data,
#             order_info=order_data,
#             customer_info=customer_data,
#             policy_context=obs_data.get("policy_context", ""),
#             conversation_history=obs_data.get("conversation_history", []),
#             days_since_purchase=obs_data.get("days_since_purchase", 0),
#             item_condition=obs_data.get("item_condition", "unused"),
#             user_reason=obs_data.get("user_reason", ""),
#             done=payload.get("done", False),
#             reward=payload.get("reward"),
#             metadata=obs_data.get("metadata", {}),
#         )

#         return StepResult(
#             observation=observation,
#             reward=payload.get("reward"),
#             done=payload.get("done", False),
#         )

#     def _parse_state(self, payload: Dict) -> State:
#         """
#         Parse server response into State object.

#         Args:
#             payload: JSON response from state request

#         Returns:
#             State object with episode_id and step_count
#         """
#         return State(
#             episode_id=payload.get("episode_id"),
#             step_count=payload.get("step_count", 0),
#         )