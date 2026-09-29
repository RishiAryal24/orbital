"""
PyLoom Technologies — GitHub Webhook Push-to-Deploy Service.

Verifies HMAC-SHA256 signatures from GitHub webhooks, parses push events,
triggers automated zero-downtime Blue/Green rollouts, and records deployment audit events.
"""

import hashlib
import hmac
from typing import Any, Dict, Optional, Tuple
from django.utils import timezone

from ..models import ApplicationDeployment, DeploymentEvent
from .manifest_synthesizer import ManifestSynthesizer


class GitHubWebhookService:
    """Processes incoming GitHub push webhooks and orchestrates automated rollouts."""

    @staticmethod
    def verify_signature(payload_bytes: bytes, secret: str, signature_header: Optional[str]) -> bool:
        """
        Verify GitHub HMAC-SHA256 webhook signature.
        Format of header: sha256=<hex_digest>
        """
        if not secret:
            # If no secret configured on the app, allow in development
            return True
        if not signature_header or not signature_header.startswith("sha256="):
            return False

        expected_sig = signature_header[7:]
        computed_sig = hmac.new(
            key=secret.encode("utf-8"),
            msg=payload_bytes,
            digestmod=hashlib.sha256,
        ).hexdigest()

        return hmac.compare_digest(computed_sig, expected_sig)

    @classmethod
    def process_push_event(
        cls,
        payload: Dict[str, Any],
        app: ApplicationDeployment,
    ) -> Tuple[bool, str, Optional[DeploymentEvent]]:
        """
        Process a verified GitHub push event for a specific application.
        """
        ref = payload.get("ref", "")
        expected_ref = f"refs/heads/{app.git_branch}"

        if ref != expected_ref:
            return (
                False,
                f"Ignored push to '{ref}' (configured branch is '{app.git_branch}')",
                None,
            )

        if not app.auto_deploy:
            return (
                False,
                "Auto-deploy is disabled for this application",
                None,
            )

        # Extract commit details
        head_commit = payload.get("head_commit") or {}
        commit_sha = payload.get("after") or head_commit.get("id") or "unknown"
        short_sha = commit_sha[:7]
        commit_message = head_commit.get("message", "Triggered via GitHub webhook push")
        sender = payload.get("sender", {}).get("login", "github-webhook")

        new_image = f"ghcr.io/{app.client.slug}/{app.slug}:{short_sha}"

        # 1. Update Application State
        app.latest_commit_sha = short_sha
        app.latest_commit_message = commit_message[:255]
        app.current_image = new_image
        app.status = "deploying"
        app.last_deployed_at = timezone.now()
        app.save(
            update_fields=[
                "latest_commit_sha",
                "latest_commit_message",
                "current_image",
                "status",
                "last_deployed_at",
                "updated_at",
            ]
        )

        # 2. Record Deployment Event in Audit Log
        event = DeploymentEvent.objects.create(
            application=app,
            commit_sha=commit_sha,
            commit_message=commit_message[:255],
            sender=sender,
            status="deployed",
            rollout_strategy="blueGreen",
        )

        # 3. Synthesize Updated Argo Rollouts Manifest
        ManifestSynthesizer.synthesize_all_yaml(
            app_name=app.slug,
            namespace=f"tenant-{app.client.slug}",
            image=new_image,
            domain=app.domain,
            target_port=app.target_port,
            replicas=app.replicas,
            env_vars=app.environment_variables,
        )

        # 4. Mark application as active zero-downtime
        app.status = "active"
        app.save(update_fields=["status"])

        return (
            True,
            f"Successfully triggered Blue/Green rollout for {app.name} with commit {short_sha}",
            event,
        )
