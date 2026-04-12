---
title: Customersupportenv Environment Server
emoji: 🥈
colorFrom: indigo
colorTo: yellow
sdk: docker
pinned: false
app_port: 8000
base_path: /web
tags:
  - openenv
  - pytorch-hackathon
---

# Customersupportenv Environment

An advanced evaluation environment for customer support AI agents, specifically engineered for the Meta PyTorch Hackathon. This environment evaluates agents against strict company policies, featuring a deterministic grading engine, manual debugging UI, and robust validation for Phase 2 deep verification.

## Key Features

- Strict Compliance: All task scores are strictly within the open interval (0, 1), ensuring compatibility with hackathon validation pipelines.
- Deterministic Grading: Comprehensive policy engine that evaluates response tone, amount accuracy, and action alignment.
- Multi-Task Scenarios: 8+ unique ticket scenarios covering refunds, replacements, delivery delays, and billing disputes.
- Interactive Dashboard: Manual debugging UI at /web for real-time interaction and observation tracing.
- Production-Ready: Built-in Hugging Face Spaces support for seamless deployment.

## Quick Start

The simplest way to interact with the environment is using the CustomersupportenvEnv client:

```python
from client import CustomersupportenvAction, CustomersupportenvEnv

# Connect to the local server or Docker image
with CustomersupportenvEnv(base_url="http://localhost:8000") as env:
    # 1. Start a new ticket session
    result = env.reset()
    print(f"Ticket: {result.observation.ticket_id} | Issue: {result.observation.issue_type}")
    print(f"Customer: {result.observation.customer_message}")

    # 2. Respond according to policy
    action = CustomersupportenvAction(
        action_type="approve_refund",
        response="I've processed your refund as per our policy.",
        reason="Item was returned within the 7-day window.",
        amount=result.observation.order_info['amount']
    )
    
    result = env.step(action)
    print(f"Reward: {result.reward} | Done: {result.done}")
```

## Performance and Validation (Phase 2)

This environment is fully verified for the Meta PyTorch Hackathon x Scaler School of Technology Phase 2 deep validation.

- Score Range: Guaranteed strictly between 0.01 and 0.99.
- Signal Variance: The engine provides distinct reward signals (e.g., 0.99, 0.81, 0.41) to help policies learn nuanced differences.
- Termination Logic: Clear episode termination on terminal actions (Refund/Replace/Escalate), while allowing multi-turn dialogue for clarification.

## Environment Specification

### Observation Space
- customer_message: The latest text from the customer.
- order_info: JSON object with id, amount, product, and status.
- policy_context: Domain-specific rules (Refund rules, Replacement thresholds).
- conversation_history: List of all previous messages in the current session.
- customer_satisfaction: Current satisfaction score (clamped to 0.99 max).

### Action Space
Valid actions include:
- approve_refund: Process a financial return.
- initiate_replacement: Ship a new item.
- request_clarification: Ask for more details (Non-terminal).
- apologize_and_inform: Provide status updates.
- escalate: Transfer to a senior agent.

### Reward Engine
- Policy Alignment (+0.6): Correct action type chosen based on logic.
- Calculation Accuracy (+0.2): Correct match for refund amounts.
- Tone and Conciseness (+0.2): Evaluation of the response quality.
- Hallucination Penalty (-0.5): Immediate negative signal if the agent invents data.

## Deployment

### Build Locally
```bash
openenv build --tag openenv-customersupportenv
```

### Run with Inference
```bash
uv run inference.py
```

### Push to Hugging Face
```bash
openenv push --repo-id my-org/customersupportenv
```

## Project Structure

```text
customerSupportEnv/
├── client.py              # WebSocket/HTTP Environment Client
├── models.py              # Pydantic Actions and Observations
├── inference.py           # Multi-task evaluation script
├── server/
│   ├── customersupportenv_environment.py  # Core Logic and Grader
│   ├── app.py             # FastAPI Server and Dashboard
│   └── Dockerfile         # Container Spec
└── tasks/                 # Task definitions for scenarios
```

---
*Created for the Meta PyTorch Hackathon 2026.*
