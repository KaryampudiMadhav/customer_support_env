"""OpenEnv client for the Customer Support environment."""

from __future__ import annotations

from typing import Any, Dict

from openenv.core import EnvClient
from openenv.core.client_types import StepResult
from openenv.core.env_server.types import State

try:
    from .models import CustomerSupportAction, CustomerSupportObservation
except ImportError:
    from models import CustomerSupportAction, CustomerSupportObservation


class CustomerSupportEnv(
    EnvClient[CustomerSupportAction, CustomerSupportObservation, State]
):
    """Typed async client for interacting with the Customer Support environment."""

    def _step_payload(self, action: CustomerSupportAction) -> Dict[str, Any]:
        return action.model_dump()

    def _parse_result(self, payload: Dict[str, Any]) -> StepResult[CustomerSupportObservation]:
        # Normal OpenEnv payload: {"observation": ..., "reward": ..., "done": ...}
        # Backward-compat payloads may wrap observation deeper under "data".
        if "observation" in payload:
            observation_payload = payload.get("observation", {})
            reward = payload.get("reward")
            done = bool(payload.get("done", False))
        else:
            data = payload.get("data", {}) if isinstance(payload.get("data"), dict) else {}
            observation_payload = data.get("observation", payload)
            reward = data.get("reward", payload.get("reward"))
            done = bool(data.get("done", payload.get("done", False)))

        observation = CustomerSupportObservation(**observation_payload)
        return StepResult(observation=observation, reward=reward, done=done)

    def _parse_state(self, payload: Dict[str, Any]) -> State:
        return State(**payload)
