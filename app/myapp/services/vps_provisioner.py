"""
PyLoom Technologies — VPS Provisioner & Bootstrap Orchestrator.

Generates one-line connection agents and automates the SSH bootstrap process
for attaching raw Linux VPS nodes (Hetzner, DigitalOcean, Linode, OCI)
into the PyLoom K3s GitOps cluster.
"""

from typing import Any, Dict


class VPSProvisioner:
    """Orchestrates initial node bootstrapping and agent script generation."""

    @staticmethod
    def generate_agent_command(server_id: int, server_token: str, control_plane_url: str) -> str:
        """Generate a one-line curl command for the user to paste into their raw VPS."""
        return (
            f"curl -fsSL {control_plane_url}/api/servers/{server_id}/bootstrap.sh "
            f"| SERVER_TOKEN={server_token} bash"
        )

    @staticmethod
    def generate_bootstrap_script(
        server_name: str,
        k3s_version: str = "v1.30.0+k3s1",
        tunnel_token: str = "",
    ) -> str:
        """Generate the executable bash script executed on the client's VPS."""
        tunnel_block = ""
        if tunnel_token:
            tunnel_block = f"""
# 4. Install Cloudflare Zero Trust Ingress Tunnel
echo "🛡️ Installing Cloudflare Tunnel..."
curl -L --output cloudflared.deb https://github.com/cloudflare/cloudflared/releases/latest/download/cloudflared-linux-amd64.deb
sudo dpkg -i cloudflared.deb || sudo apt-get install -f -y
sudo cloudflared service install {tunnel_token}
sudo systemctl start cloudflared
"""

        return f"""#!/usr/bin/env bash
# ==============================================================================
# PyLoom Technologies — Remote VPS K3s & GitOps Agent
# Target Server: {server_name}
# ==============================================================================
set -euo pipefail

echo "=========================================================="
echo "🚀 Connecting Node: {server_name} to PyLoom Control Plane"
echo "=========================================================="

# 1. Update OS and Install Core Tooling
echo "📦 Updating system dependencies..."
sudo apt-get update -qq
sudo apt-get install -y -qq curl wget git jq iptables

# 2. Configure Firewall for K3s
echo "🛡️  Configuring network routing for Kubernetes..."
sudo iptables -F
sudo iptables -P INPUT ACCEPT
sudo iptables -P FORWARD ACCEPT
sudo iptables -P OUTPUT ACCEPT

# 3. Install K3s (Lightweight Kubernetes)
echo "☸️  Installing K3s ({k3s_version})..."
curl -sfL https://get.k3s.io | INSTALL_K3S_VERSION="{k3s_version}" sh -s - \\
    --write-kubeconfig-mode 644 \\
    --disable traefik

export KUBECONFIG=/etc/rancher/k3s/k3s.yaml

# Wait for node to be ready
echo "⏳ Waiting for cluster node to become ready..."
until kubectl get nodes | grep -q " Ready"; do
    sleep 2
done

# 4. Install Argo Rollouts (Zero-Downtime Blue/Green Engine)
echo "🐙 Deploying Argo Rollouts controller..."
kubectl create namespace argo-rollouts --dry-run=client -o yaml | kubectl apply -f -
kubectl apply -n argo-rollouts -f https://github.com/argoproj/argo-rollouts/releases/latest/download/install.yaml

{tunnel_block}

echo "=========================================================="
echo "✅ Node Successfully Attached to PyLoom Platform!"
echo "   Node Name: $(hostname)"
echo "   K8s Status: $(kubectl get nodes -o jsonpath='{{.items[0].status.conditions[-1].type}}')"
echo "=========================================================="
"""
