#!/usr/bin/env python
"""Test API with curl-compatible format."""

import requests
import json

BASE_URL = "http://localhost:8000"


def test_api():
    print("=== Test Customer Support API ===\n")

    # Reset
    print("1. POST /reset")
    r = requests.post(f"{BASE_URL}/reset")
    obs = r.json().get("observation", {})
    print(f"   Status: {r.status_code}")
    print(f"   Ticket: {obs.get('ticket_info', {}).get('issue_category')}")
    print()

    # Step with correct format (action wrapped)
    print("2. POST /step (wrapped format)")
    payload = {
        "action": {
            "response": "I will help with your refund.",
            "action_type": "refund",
            "amount": 100.0,
            "reason": "within 7-day policy"
        }
    }
    r = requests.post(f"{BASE_URL}/step", json=payload)
    print(f"   Status: {r.status_code}")
    if r.status_code == 200:
        result = r.json()
        print(f"   Reward: {result.get('reward')}")
        print(f"   Done: {result.get('done')}")
    else:
        print(f"   Error: {r.text[:200]}")
    print()

    # Alternative: plain format
    print("3. POST /step (plain format)")
    payload = {
        "response": "I will help with your refund.",
        "action_type": "refund",
        "amount": 100.0,
        "reason": "within 7-day policy"
    }
    r = requests.post(f"{BASE_URL}/step", json=payload)
    print(f"   Status: {r.status_code}")
    if r.status_code == 200:
        result = r.json()
        print(f"   Reward: {result.get('reward')}")
    else:
        print(f"   Error: {r.text[:200]}")
    print()

    # Get state
    print("4. GET /state")
    r = requests.get(f"{BASE_URL}/state")
    print(f"   Status: {r.status_code}")
    print(f"   {r.text[:100]}")


if __name__ == "__main__":
    test_api()