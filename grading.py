"""
Grading utilities for the Customer Support Environment.

Adapted from a generic RL grading module; all SQL/DB concepts have been
translated to their customer-support equivalents:

  SQL result match         → action_type valid & episode resolved
  Query cost improvement   → customer satisfaction improvement
  No SELECT *              → no over-use of the 'clarify' action
  Step efficiency          → fewer steps to resolve the ticket
  Required index           → hard tickets must end with a decisive action
"""

from __future__ import annotations

from typing import Any, Dict, Optional

try:
    from models import VALID_ACTION_TYPES
except ImportError:
    from .models import VALID_ACTION_TYPES  # type: ignore[no-redef]

# Decisive action types that close a ticket (analogous to a query returning rows)
_DECISIVE_ACTIONS = {"refund", "partial_refund", "replace", "escalate", "deny"}


def strict_score(value: float) -> float:
    """Clamp a score to the open interval (0, 1).

    Scores of exactly 0.0 become 0.01 and scores of exactly 1.0 become 0.99
    so downstream log-transforms remain finite.
    """
    v = max(0.0, min(1.0, float(value)))
    if v <= 0.0:
        return 0.01
    if v >= 1.0:
        return 0.99
    return v


def _action_type_valid(action_type: str) -> bool:
    """Return True if action_type is one of the known valid types."""
    return str(action_type).strip().lower() in VALID_ACTION_TYPES


def _episode_resolved(obs: Dict[str, Any]) -> bool:
    """Return True when the episode ended with a resolved phase."""
    phase = str(obs.get("phase", "")).strip().lower()
    done = bool(obs.get("done", False))
    return done and phase == "resolved"


def final_grade(
    action_type: str,
    final_obs: Dict[str, Any],
    baseline_satisfaction: float,
    steps_used: int,
    requires_decisive: bool = False,
) -> float:
    """
    Return an episode score in [0.0, 1.0].

    Scoring break-down (mirrors the SQL grader's rubric):

    Component                          Points   Analogy
    ─────────────────────────────────  ───────  ───────────────────────────────
    Episode resolved with valid action   0.40   Exact result-set match
    Satisfaction improvement             0.20   Query cost improvement (≤ 0.20)
    Not over-using 'clarify'             0.10   No SELECT *
    Step efficiency                      0.30   Step efficiency bonus
      ≤ 3 steps                          0.30
      ≤ 5 steps                          0.20
      ≤ 8 steps                          0.10
    Hard ticket – decisive required      0.00   Required index check (hard gate)

    Args:
        action_type: The last action taken by the agent.
        final_obs: The observation dict from the final env step
                   (``observation.model_dump()``).
        baseline_satisfaction: Customer satisfaction at episode start (0-1).
        steps_used: Total number of env steps taken.
        requires_decisive: When True (hard tickets), the agent must have used a
                           decisive action or the score collapses to ~0.

    Returns:
        A float in (0.01, 0.99).
    """
    # Hard gate: decisive action required (analogous to required index)
    if requires_decisive and action_type not in _DECISIVE_ACTIONS:
        return strict_score(0.0)

    # Base: action valid + episode resolved (analogous to result-set match)
    if not _action_type_valid(action_type) or not _episode_resolved(final_obs):
        return strict_score(0.0)

    score = 0.40

    # Satisfaction improvement bonus (analogous to cost reduction)
    final_satisfaction = float(
        final_obs.get("customer_info", {}).get("satisfaction", baseline_satisfaction)
        if isinstance(final_obs.get("customer_info"), dict)
        else baseline_satisfaction
    )
    if baseline_satisfaction > 0.0:
        improvement = max(
            0.0, (final_satisfaction - baseline_satisfaction) / baseline_satisfaction
        )
        score += min(0.20, 0.20 * improvement)

    # No over-use of 'clarify' (analogous to no SELECT *)
    history: list = final_obs.get("action_history", []) or []
    clarify_count = sum(
        1
        for entry in history
        if isinstance(entry, dict) and entry.get("action_type") == "clarify"
    )
    total_actions = max(1, len(history))
    clarify_ratio = clarify_count / total_actions
    if clarify_ratio < 0.5:  # fewer than half of all steps were 'clarify'
        score += 0.10

    # Step efficiency (analogous to step count bonus)
    if steps_used <= 3:
        score += 0.30
    elif steps_used <= 5:
        score += 0.20
    elif steps_used <= 8:
        score += 0.10

    return strict_score(score)


def partial_reward(
    previous_obs: Optional[Dict[str, Any]],
    new_obs: Dict[str, Any],
    action_type: str,
) -> float:
    """
    Compute a shaped shaping reward for a single env transition.

    Designed to complement the environment's own reward signal during
    training.  Maps directly to the SQL grader's ``partial_reward``:

      Error cleared            → +0.05   (matches "syntax error fixed")
      More turns resolved      → +0.20   (matches "more rows matched")
      Satisfaction improved    → +0.03   (matches "index reduced cost")
      Repeated same action     → −0.02   (matches "repeated SQL penalty")

    Args:
        previous_obs: Observation dict from the *previous* step, or None on
                      the very first step.
        new_obs: Observation dict from the *current* step.
        action_type: The action type string that produced ``new_obs``.

    Returns:
        A shaped reward float (may be negative).
    """
    reward = 0.0

    # --- Error cleared (analogous to syntax error fixed) ---
    old_phase = str((previous_obs or {}).get("phase", "")).strip().lower()
    new_phase = str(new_obs.get("phase", "")).strip().lower()
    # Treat "unassigned" → anything else as clearing an unhandled state
    if old_phase in ("unassigned", "") and new_phase not in ("unassigned", ""):
        reward += 0.05

    # --- More progress toward resolution (analogous to more rows matched) ---
    phase_score = {"unassigned": 0, "in progress": 1, "resolved": 2}
    prev_progress = phase_score.get(old_phase, 0) if previous_obs else 0
    new_progress = phase_score.get(new_phase, 0)
    if new_progress > prev_progress:
        reward += min(0.20, (new_progress - prev_progress) * 0.10)

    # --- Customer satisfaction improved (analogous to query cost reduced) ---
    prev_sat = float(
        (previous_obs or {}).get("customer_info", {}).get("satisfaction", 0.0)
        if isinstance((previous_obs or {}).get("customer_info"), dict)
        else 0.0
    )
    new_sat = float(
        new_obs.get("customer_info", {}).get("satisfaction", 0.0)
        if isinstance(new_obs.get("customer_info"), dict)
        else 0.0
    )
    if action_type in _DECISIVE_ACTIONS and prev_sat > 0.0 and new_sat > prev_sat:
        reward += 0.03

    # --- Repeated action penalty (analogous to repeated SQL penalty) ---
    history: list = new_obs.get("action_history", []) or []
    if len(history) >= 2:
        last_two = [
            str(e.get("action_type", "")) for e in history[-2:] if isinstance(e, dict)
        ]
        if len(last_two) == 2 and last_two[0] == last_two[1] == action_type:
            reward -= 0.02

    return reward
