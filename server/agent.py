from typing import Dict, Any
try:
    from models import CustomerSupportAction, CustomerSupportObservation
except ImportError:
    from ..models import CustomerSupportAction, CustomerSupportObservation

class RuleBasedAgent:
    """A simple agent that suggests actions based on rules and policy."""

    def predict(self, observation: CustomerSupportObservation) -> CustomerSupportAction:
        """Predict the next action based on the observation."""
        category = observation.ticket_info.issue_category.lower()
        message = observation.customer_message.lower()
        
        # Default action
        action_type = "clarify"
        response = "I'm looking into this for you. Could you please provide more details?"
        reason = "Clarifying request to gather context."

        if category == "refund":
            days = observation.days_since_purchase
            condition = observation.item_condition
            
            if days <= 7 and condition == "unused":
                action_type = "refund"
                response = f"I've processed your refund for Order {observation.order_info.order_id}. You should see it in 3-5 days."
                reason = "Eligible for full refund (within 7 days, unused)."
            else:
                action_type = "deny"
                response = "I've reviewed your request, but per our policy, we cannot offer a refund for items used or purchased more than 7 days ago."
                reason = "Ineligible for refund per policy constraints."

        elif category == "replacement":
            if "defect" in message or "broken" in message:
                action_type = "replace"
                response = "I'm so sorry to hear the item was defective. I've initiated a replacement for you."
                reason = "Issue indicates defect; replacement approved."
            else:
                action_type = "clarify"
                response = "Could you please tell me more about the issue with the item?"
                reason = "Need more details to determine replacement eligibility."

        elif category == "payment":
            if "failed" in observation.transaction_status:
                action_type = "clarify"
                response = "I see a failed payment on our end. Could you please check with your bank or try another card?"
                reason = "Investigating failed payment status."

        elif category == "delivery":
            if observation.delivery_delayed_days > 0:
                action_type = "clarify"
                response = f"I apologize for the delay. Your delivery is currently {observation.delivery_delayed_days} days behind schedule. I am investigating the cause."
                reason = "Acknowledging and investigating delivery delay."

        return CustomerSupportAction(
            action_type=action_type,
            response=response,
            reason=reason
        )
