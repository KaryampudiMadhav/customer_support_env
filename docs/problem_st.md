# Customer Support Environment - Problem Statement

## Overview

The **CustomerSupportEnv** is a realistic simulation of a customer support agent handling support tickets. Agents must resolve customer issues while following company policies, maintaining professional tone, and avoiding hallucinations or policy violations. This environment evaluates agent performance across communication quality, correctness of resolution, and adherence to support guidelines.

## Real-World Motivation

Customer support is a critical business function. Companies need to:
- Resolve customer issues quickly and accurately
- Maintain customer satisfaction through professional interactions
- Ensure compliance with refund policies and legal requirements
- Reduce hallucinations (agents inventing policies or facts)
- Minimize costly errors (over-refunding, wrong information)

This environment trains agents to balance these competing objectives, making it valuable for evaluating LLM-based customer support automation.

## Action Space

**CustomerSupportAction**:
```python
{
    "response": str,          # The agent's response to the customer
    "action_type": str,       # One of: "refund", "replace", "escalate", "deny", "partial_refund"
    "amount": float,          # For refund actions: amount in dollars
    "reason": str             # Justification for the action taken
}
```

## Observation Space

**CustomerSupportObservation**:
```python
{
    "customer_message": str,        # The customer's issue description
    "order_info": dict,            # Order details: {id, amount, date, product}
    "policy_context": str,         # Relevant company policies for this case
    "conversation_history": list,  # Previous exchanges in this ticket
    "ticket_id": str,              # Unique identifier for the support ticket
    "customer_satisfaction": float  # Running satisfaction score (0-1)
}
```

## Three Tasks with Grading Criteria

### Task 1: Simple Refund Processing (Easy)
**Difficulty**: Easy
**Target**: Test basic issue resolution and policy compliance

#### Scenario
Customer requests refund for unopened product within 30 days of purchase. Request is straightforward and clearly eligible.

**Objective**: Process the refund correctly while maintaining professional tone.

#### Grading Rubric (0.0 - 1.0 scale)
| Criterion | Points | Condition |
|-----------|--------|-----------|
| Correct Resolution | +0.4 | Full refund processed for eligible customer (exact amount matches order total) |
| Polite Tone | +0.3 | Response is professional, empathetic, uses appropriate customer service language |
| No Hallucination | +0.2 | No invented policies or false information in response |
| No Policy Violation | +0.1 | Follows 30-day return window (no early/late refunds) |
| **Total** | **1.0** | |

**Failure Cases** (reduce score):
- -0.4: Wrong refund amount or no refund
- -0.2: Rude, dismissive, or unprofessional tone
- -0.3: Invents a policy that doesn't exist
- -0.2: Refunds outside 30-day window without justification

#### Example
- **Input**: "I bought this on Jan 15, it's Jan 20 now, unopened. Refund please?"
- **Expected Output**: Refund of full order amount, polite confirmation
- **Score**: 1.0 (correct resolution + polite tone + policy compliance)

---

### Task 2: Complex Refund with Partial Eligibility (Medium)
**Difficulty**: Medium
**Target**: Test nuanced policy application and tone management with difficult customers

#### Scenario
Customer opened product, used it, now claims defect. Return window is closing (day 29 of 30). Defective items are refundable but used items incur 20% restocking fee. Customer is frustrated.

**Objective**: Apply correct refund policy (partial refund with restocking fee), de-escalate frustration, and explain decision clearly.

#### Grading Rubric (0.0 - 1.0 scale)
| Criterion | Points | Condition |
|-----------|--------|-----------|
| Correct Resolution | +0.35 | Partial refund calculated correctly: (order_amount × 0.8) for defective used item |
| Polite & Empathetic Tone | +0.35 | Acknowledges frustration, maintains professionalism despite customer frustration |
| Policy Explanation | +0.2 | Clearly explains restocking fee and return window deadline |
| No Hallucination | +0.1 | No invented policies; accurately states company policy |
| **Total** | **1.0** | |

**Failure Cases**:
- -0.35: Wrong refund amount (e.g., full refund instead of 80%, or no refund)
- -0.25: Dismissive or rude tone, fails to de-escalate
- -0.2: Doesn't explain the policy or mentions non-existent policies
- -0.15: Missed the 30-day window (day 30+)

#### Example
- **Input**: "This is ridiculous! Your product broke after 2 weeks! I want my money back NOW! I'm on day 29."
- **Expected Output**: Acknowledge frustration, approve partial refund (80% of $99.99 = $79.99), explain 20% restocking fee, note urgency
- **Score**: 0.95 (correct resolution -0.05 for minor tone issue)

---

### Task 3: Multi-Issue Escalation Decision (Hard)
**Difficulty**: Hard
**Target**: Test complex reasoning, policy boundaries, and escalation judgment

#### Scenario
Customer with multiple issues: defective product (eligible for refund), shipping delay (compensation available), and complaint about support (potential brand damage). Refund window is closed. Decision: partial refund for defect, shipping credit, or escalate to manager for policy exception?

**Objective**: Decide whether to resolve within authority, escalate appropriately, and justify the decision. Balance policy compliance with customer retention.

#### Grading Rubric (0.0 - 1.0 scale)
| Criterion | Points | Condition |
|-----------|--------|-----------|
| Correct Decision | +0.3 | Recognizes closed window → escalation OR offers alternative solution (shipping credit) within policy |
| Justification Quality | +0.25 | Clearly explains decision logic and policy boundaries to customer |
| Appropriate Tone | +0.25 | Empathetic, professional; validates customer concerns without admitting fault |
| No Hallucination | +0.1 | Accurately states policies; doesn't invent exceptions |
| Escalation Judgment | +0.1 | If escalating: uses correct language; doesn't escalate trivial issues |
| **Total** | **1.0** | |

**Failure Cases**:
- -0.3: Processes refund outside window without escalation (policy violation)
- -0.2: Dismisses legitimate concerns; tone damages brand
- -0.2: Invents a "loyalty discount" or unauthorized exception
- -0.15: Escalates a trivial issue that could be resolved
- -0.1: Doesn't explain why resolution is limited

#### Example
- **Input**: "It's been 35 days. Your product was defective AND shipping took forever. I want a full refund and compensation!"
- **Expected Output**: "I understand your frustration. The defect alone justifies a review, but we're outside the 30-day window. I'm escalating this to my manager to explore options. You should hear back within 24 hours."
- **Score**: 0.95 (correct escalation decision, good tone, clear explanation)

---

## Reward Function

The reward for each step combines task-specific grading with temporal penalties:

```
reward = base_task_score - (step_count × 0.02) - hallucination_penalty
```

Where:
- **base_task_score**: 0.0–1.0 (from task grader)
- **step_count**: Penalizes verbose or inefficient responses (2% per step)
- **hallucination_penalty**: -0.3 for invented policies/facts

**Episode Structure**:
- Episode length: 1 turn (agent writes one response, gets scored)
- Done flag: True after agent submits response
- Max steps per episode: 1 (single-turn task)

## Evaluation Metrics

Each task produces:
- **Score**: 0.0–1.0 (from grader)
- **Resolution Type**: "refund" | "partial_refund" | "escalate" | "deny"
- **Amount**: Dollar amount if applicable
- **Tone Grade**: "poor" | "neutral" | "good" | "excellent"
- **Policy Compliance**: "pass" | "fail"
- **Hallucination Detected**: bool

## Baseline Agent Expectations

| Task | Easy | Medium | Hard |
|------|------|--------|------|
| Expected Score | 0.8–1.0 | 0.6–0.85 | 0.4–0.7 |
| Typical Resolution | Full refund | Partial refund | Escalate |
| Difficulty for Frontier LLM | Trivial | Moderate | Challenging |

---

## Implementation Notes

- **Graders**: Each task uses keyword-heuristic tone evaluation + rule-based checkers (refund amount, policy compliance)
- **Policy Database**: Hardcoded rules for return window, restocking fees, eligibility
- **State Management**: Ticket ID tracks conversation; reset() generates new random ticket
- **Reproducibility**: Seed-based ticket generation is supported via constructor seed or CUSTOMER_SUPPORT_ENV_SEED
