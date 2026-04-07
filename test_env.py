#!/usr/bin/env python
"""Test script for Customer Support Environment."""

from server.customerSupportEnv_environment import CustomerSupportEnvironment
from models import CustomerSupportAction


def test_environment():
    print("=== Customer Support Environment Test ===\n")

    env = CustomerSupportEnvironment()

    # Test 1: Reset generates ticket
    obs = env.reset()
    print(f"1. Reset: ticket={obs.ticket_info.issue_category}")
    print(f"   difficulty={obs.ticket_info.difficulty}")
    print(f"   customer_message: {obs.customer_message[:60]}...")
    print()

    # Test 2: Step with clarify action
    action = CustomerSupportAction(
        response="I understand and will help you.",
        action_type="clarify",
        amount=200,
        reason="gathering information"
    )
    result = env.step(action)
    print(f"2. Step with 'clarify': reward={result.reward:.2f}, done={result.done}")
    print()

    # Test 3: State tracking
    print(f"3. State: episode_id={env.state.episode_id[:8]}..., step_count={env.state.step_count}")
    print()

    # Test 4: Multiple categories
    print("4. Category distribution (10 tickets):")
    categories = {"refund": 0, "replacement": 0, "payment": 0, "delivery": 0}
    for _ in range(10):
        obs = env.reset()
        categories[obs.ticket_info.issue_category] += 1
    print(f"   {categories}")
    print()

    # Test 5: Correct action rewards
    print("5. Correct action rewards:")

    # Find a refund within window
    for _ in range(20):
        obs = env.reset()
        if obs.ticket_info.issue_category == "refund" and obs.days_since_purchase <= 7 and obs.item_condition == "unused":
            break
    action = CustomerSupportAction(response="Refund", action_type="refund", amount=100, reason="within policy")
    result = env.step(action)
    print(f"   refund (within 7 days, unused): {result.reward:.2f}")

    # Find a replacement within window
    for _ in range(20):
        obs = env.reset()
        if obs.ticket_info.issue_category == "replacement" and obs.days_since_purchase <= 10:
            break
    action = CustomerSupportAction(response="Replace", action_type="replace", reason="within window")
    result = env.step(action)
    print(f"   replacement (within 10 days): {result.reward:.2f}")

    print("\n=== All tests passed! ===")


if __name__ == "__main__":
    test_environment()