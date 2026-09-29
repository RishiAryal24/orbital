"""
PyLoom Technologies — Cloudflare Dynamic Ingress & DNS Service.

Integrates with Cloudflare API v4 to dynamically provision DNS CNAME records,
Cloudflare Zero Trust tunnels, and edge SSL certificates for customer domains
without manual configuration or server reboots.
"""

import os
from typing import Any, Dict, Optional
import urllib.request
import json


class CloudflareService:
    """Manages Cloudflare Tunnels and DNS records via Cloudflare REST API v4."""

    API_BASE = "https://api.cloudflare.com/client/v4"

    def __init__(
        self,
        api_token: Optional[str] = None,
        account_id: Optional[str] = None,
        zone_id: Optional[str] = None,
    ):
        self.api_token = api_token or os.environ.get("CLOUDFLARE_API_TOKEN", "")
        self.account_id = account_id or os.environ.get("CLOUDFLARE_ACCOUNT_ID", "")
        self.zone_id = zone_id or os.environ.get("CLOUDFLARE_ZONE_ID", "")

    @property
    def is_configured(self) -> bool:
        """Return True if real Cloudflare credentials are configured in the environment."""
        return bool(self.api_token and (self.account_id or self.zone_id))

    def create_dns_cname(
        self,
        domain_name: str,
        target_cname: str,
        proxied: bool = True,
    ) -> Dict[str, Any]:
        """Create or update a DNS CNAME record pointing a custom domain to a Cloudflare Tunnel."""
        if not self.is_configured:
            # Emulated response for development/testing
            return {
                "success": True,
                "result": {
                    "name": domain_name,
                    "type": "CNAME",
                    "content": target_cname,
                    "proxied": proxied,
                    "id": f"simulated_dns_{domain_name.replace('.', '_')}",
                },
                "messages": ["Simulated Cloudflare API response (no CLOUDFLARE_API_TOKEN set)"],
            }

        url = f"{self.API_BASE}/zones/{self.zone_id}/dns_records"
        payload = json.dumps(
            {
                "type": "CNAME",
                "name": domain_name,
                "content": target_cname,
                "proxied": proxied,
                "ttl": 1,
            }
        ).encode("utf-8")

        req = urllib.request.Request(
            url,
            data=payload,
            headers={
                "Authorization": f"Bearer {self.api_token}",
                "Content-Type": "application/json",
            },
            method="POST",
        )

        try:
            with urllib.request.urlopen(req, timeout=10) as resp:
                return json.loads(resp.read().decode("utf-8"))
        except Exception as e:
            return {"success": False, "errors": [{"message": str(e)}]}

    def create_tunnel(self, tunnel_name: str) -> Dict[str, Any]:
        """Create a new Cloudflare Zero Trust Tunnel for a connected server node."""
        if not self.is_configured:
            return {
                "success": True,
                "result": {
                    "id": f"sim-tunnel-{tunnel_name}",
                    "name": tunnel_name,
                    "token": f"sim-token-{tunnel_name}-jwt",
                },
                "messages": ["Simulated tunnel creation"],
            }

        url = f"{self.API_BASE}/accounts/{self.account_id}/cfd_tunnel"
        payload = json.dumps({"name": tunnel_name, "config_src": "cloudflare"}).encode("utf-8")

        req = urllib.request.Request(
            url,
            data=payload,
            headers={
                "Authorization": f"Bearer {self.api_token}",
                "Content-Type": "application/json",
            },
            method="POST",
        )

        try:
            with urllib.request.urlopen(req, timeout=10) as resp:
                return json.loads(resp.read().decode("utf-8"))
        except Exception as e:
            return {"success": False, "errors": [{"message": str(e)}]}
