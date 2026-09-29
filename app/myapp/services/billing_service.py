"""
PyLoom Technologies — Stripe Billing & Subscription Quota Service.

Manages recurring subscription billing ($9 Starter, $29 Growth, $79 Team/Agency),
generates Stripe Checkout & Customer Portal sessions, processes payment webhooks,
and creates invoice records.
"""

from decimal import Decimal
import os
from typing import Any, Dict, Optional, Tuple
from django.utils import timezone

from ..models import BillingInvoice, ClientAccount


class BillingService:
    """Orchestrates Stripe Checkout, Customer Portal, and Webhook processing."""

    TIER_PRICES = {
        "starter": {"name": "Starter Tier", "amount_cents": 900, "price_id": "price_starter_9usd"},
        "growth": {"name": "Growth Tier", "amount_cents": 2900, "price_id": "price_growth_29usd"},
        "pro": {"name": "Growth Tier (Legacy)", "amount_cents": 2900, "price_id": "price_growth_29usd"},
        "team": {"name": "Team / Agency Tier", "amount_cents": 7900, "price_id": "price_team_79usd"},
    }

    def __init__(self, api_key: Optional[str] = None):
        self.api_key = api_key or os.environ.get("STRIPE_SECRET_KEY", "")

    @property
    def is_live_configured(self) -> bool:
        """Returns True if real Stripe API keys are configured."""
        return bool(self.api_key and self.api_key.startswith("sk_"))

    def create_checkout_session(
        self,
        client: ClientAccount,
        tier: str,
        success_url: str,
        cancel_url: str,
    ) -> Dict[str, Any]:
        """
        Create a Stripe Checkout Session for a recurring subscription.
        Returns a checkout URL for redirecting the user.
        """
        tier_key = tier.lower()
        tier_info = self.TIER_PRICES.get(tier_key, self.TIER_PRICES["starter"])

        if not self.is_live_configured:
            # Emulated checkout session for local development and test environments
            session_id = f"sim_cs_{client.slug}_{tier_key}"
            checkout_url = f"https://checkout.stripe.com/c/pay/{session_id}"
            return {
                "success": True,
                "session_id": session_id,
                "checkout_url": checkout_url,
                "tier": tier_key,
                "amount": tier_info["amount_cents"] / 100,
                "simulated": True,
            }

        # Real Stripe integration when STRIPE_SECRET_KEY is present
        try:
            import stripe
            stripe.api_key = self.api_key
            customer_id = client.stripe_customer_id
            if not customer_id:
                cust = stripe.Customer.create(email=client.contact_email, name=client.name, metadata={"client_id": client.id, "slug": client.slug})
                customer_id = cust.id
                client.stripe_customer_id = customer_id
                client.save(update_fields=["stripe_customer_id"])

            session = stripe.checkout.Session.create(
                customer=customer_id,
                payment_method_types=["card"],
                line_items=[{"price": tier_info["price_id"], "quantity": 1}],
                mode="subscription",
                success_url=success_url,
                cancel_url=cancel_url,
                metadata={"client_id": client.id, "tier": tier_key},
            )
            return {
                "success": True,
                "session_id": session.id,
                "checkout_url": session.url,
                "tier": tier_key,
                "simulated": False,
            }
        except Exception as e:
            return {"success": False, "error": str(e)}

    def create_customer_portal_session(self, client: ClientAccount, return_url: str) -> Dict[str, Any]:
        """Generate a Stripe billing customer portal URL for self-service subscription management."""
        if not self.is_live_configured:
            return {
                "success": True,
                "portal_url": f"https://billing.stripe.com/p/session/sim_portal_{client.slug}",
                "simulated": True,
            }

        try:
            import stripe
            stripe.api_key = self.api_key
            portal = stripe.billing_portal.Session.create(
                customer=client.stripe_customer_id,
                return_url=return_url,
            )
            return {"success": True, "portal_url": portal.url, "simulated": False}
        except Exception as e:
            return {"success": False, "error": str(e)}

    @classmethod
    def handle_webhook_event(cls, event_data: Dict[str, Any]) -> Tuple[bool, str]:
        """
        Process incoming Stripe webhook events (checkout completed, subscription updated/canceled, invoice paid).
        """
        event_type = event_data.get("type", "")
        obj = event_data.get("data", {}).get("object", {})

        if event_type == "checkout.session.completed":
            metadata = obj.get("metadata", {})
            client_id = metadata.get("client_id")
            tier = metadata.get("tier", "growth")
            sub_id = obj.get("subscription", "")
            cust_id = obj.get("customer", "")

            try:
                client = ClientAccount.objects.get(pk=client_id) if client_id else ClientAccount.objects.get(stripe_customer_id=cust_id)
                client.tier = tier
                if sub_id:
                    client.stripe_subscription_id = sub_id
                if cust_id:
                    client.stripe_customer_id = cust_id
                client.subscription_status = "active"
                client.save(update_fields=["tier", "stripe_subscription_id", "stripe_customer_id", "subscription_status", "updated_at"])
                return True, f"Client {client.name} upgraded to {tier} tier."
            except ClientAccount.DoesNotExist:
                return False, f"Client account not found for customer {cust_id}"

        elif event_type == "customer.subscription.deleted":
            sub_id = obj.get("id")
            try:
                client = ClientAccount.objects.get(stripe_subscription_id=sub_id)
                client.tier = "free"
                client.subscription_status = "canceled"
                client.save(update_fields=["tier", "subscription_status", "updated_at"])
                return True, f"Subscription {sub_id} canceled; client downgraded to free."
            except ClientAccount.DoesNotExist:
                return False, "Subscription not mapped to client."

        elif event_type == "invoice.payment_succeeded":
            inv_id = obj.get("id")
            cust_id = obj.get("customer")
            amount = Decimal(str(obj.get("amount_paid", 0))) / Decimal("100")
            hosted_url = obj.get("hosted_invoice_url", "")
            currency = obj.get("currency", "usd")

            try:
                client = ClientAccount.objects.get(stripe_customer_id=cust_id)
                BillingInvoice.objects.get_or_create(
                    stripe_invoice_id=inv_id,
                    defaults={
                        "client": client,
                        "amount_paid": amount,
                        "currency": currency,
                        "status": "paid",
                        "hosted_invoice_url": hosted_url,
                        "paid_at": timezone.now(),
                    },
                )
                return True, f"Invoice {inv_id} recorded for {client.name}."
            except ClientAccount.DoesNotExist:
                return False, f"Client not found for customer {cust_id}"

        return True, f"Event '{event_type}' acknowledged."
