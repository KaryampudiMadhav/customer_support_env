---
title: Customer Support Environment
emoji: 🎧
colorFrom: blue
colorTo: green
sdk: docker
pinned: false
app_port: 8000
base_path: /web
tags:
  - openenv
  - customer-support
  - policy-evaluation
---

# Customer Support Environment

A realistic simulation of a customer support agent handling support tickets. The environment evaluates agent performance across communication quality, correctness of resolution, and adherence to support policies.

## Policy Difficulty Classification

| Category | File | Difficulty | Rationale |
|----------|------|------------|-----------|
| Refund | policies/1.json | **Medium** | 3 rules + 2 exceptions + edge cases + escalation |
| Replacement | policies/2.json | **Medium** | 4 rules + 2 exceptions |
| Payment | policies/3.json | **Medium-Hard** | Fraud detection, escalation |
| Delivery | policies/4.json | **Easy** | Simple 2-rule policy |

## Quick Start

```python
from customerSupportEnv import CustomerSupportEnv, CustomerSupportAction

# Create environment (from Docker or running server)
env = CustomerSupportEnv(base_url="http://localhost:8000")

# Reset - generates a random support ticket
result = env.reset()
obs = result.observation

print(f"Ticket: {obs.ticket_info.issue_category}")
print(f"Difficulty: {obs.ticket_info.difficulty}")
print(f"Customer message: {obs.customer_message}")
print(f"Order amount: ${obs.order_info.amount}")

# Evaluate agent response
action = CustomerSupportAction(
    response="I understand your concern and will help resolve this.",
    action_type="clarify",  # refund, partial_refund, replace, escalate, clarify, deny
    amount=99.99,  # optional, for refund actions
    reason="within policy guidelines"
)

result = env.step(action)
print(f"Reward: {result.reward}")
print(f"Done: {result.done}")
```

## API Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/reset` | Initialize new ticket |
| POST | `/step` | Execute action |
| GET | `/state` | Get current state |
| GET | `/schema` | Get schemas |
| GET | `/health` | Health check |
| GET | `/ws` | WebSocket |

## API Usage

### Python Client

```python
from customerSupportEnv import CustomerSupportEnv, CustomerSupportAction

env = CustomerSupportEnv(base_url="http://localhost:8000")
result = env.reset()
print(result.observation.customer_message)

action = CustomerSupportAction(
    response="I will help.",
    action_type="refund",
    amount=100.0,
    reason="within policy"
)
result = env.step(action)
print(f"Reward: {result.reward}")
```

### cURL

**Reset:**
```bash
curl -X POST http://localhost:8000/reset
```

**Step (action wrapped in `action` key):**
```bash
curl -X POST http://localhost:8000/step \
  -H "Content-Type: application/json" \
  -d '{
    "action": {
      "response": "I will help.",
      "action_type": "refund",
      "amount": 100.0,
      "reason": "within policy"
    }
  }'
``` |

## Action Schema

```json
{
  "type": "object",
  "required": ["response", "action_type", "reason"],
  "properties": {
    "response": {
      "type": "string",
      "description": "Agent's message to customer"
    },
    "action_type": {
      "type": "string",
      "enum": ["refund", "partial_refund", "replace", "escalate", "clarify", "deny"],
      "description": "Action to take"
    },
    "amount": {
      "type": "number",
      "description": "Refund amount in USD (optional)"
    },
    "reason": {
      "type": "string",
      "description": "Justification for the decision"
    }
  }
}
```

## Observation Schema

The observation includes:
- `customer_message`: Current customer request
- `ticket_info`: Ticket ID, category, difficulty
- `order_info`: Order ID, amount, date, product, status
- `customer_info`: Customer ID, name, email, satisfaction
- `policy_context`: Relevant policy text
- `days_since_purchase`: Days since order
- `item_condition`: unused, used, or damaged
- `user_reason`: Customer's stated reason
- `transaction_status`: For payment tickets
- `delivery_status`: For delivery tickets

## Running the Server

```bash
# From source
uvicorn server.app:app --host 0.0.0.0 --port 8000

# Or via module
python -m server.app --port 8000

# Docker
docker build -t customer-support-env .
docker run -p 8000:8000 customer-support-env
```

## Testing

```bash
python test_env.py
```

Output:
```
=== Customer Support Environment Test ===

1. Reset: ticket=payment
2. Step with 'clarify': reward=0.30, done=True
3. State: episode_id=d2d6cc3b..., step_count=1

=== All tests passed! ===
```

## Reward Calculation

Rewards are based on policy compliance:

| Action | Condition | Reward |
|--------|-----------|--------|
| refund | Within 7 days, unused | 0.8 |
| replace | Within 10 days | 0.8 |
| clarify | Need more info | 0.3-0.5 |
| escalate | Manager review needed | 0.3 |
| deny | Outside policy window | 0.7-0.8 |

Hallucinations (inventing policies) incur -0.3 penalty.

## Policies

The environment loads company policies from the `policies/` directory:
- Refund policy (7-day window, unused condition)
- Replacement policy (10-day window)
- Payment policy (duplicate charges, failed payments)
- Delivery policy (delays, lost packages)