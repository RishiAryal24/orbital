#!/usr/bin/env bash
# ==============================================================================
# PyLoom Technologies — Oracle Cloud Always-Free K3s & GitOps Provisioner
# Runs on Ubuntu 22.04/24.04 ARM64 (4 vCPU, 24 GB RAM)
#
# Usage on Oracle Cloud Instance:
#   curl -fsSL https://raw.githubusercontent.com/RishiAryal24/orbital/main/scripts/setup-oci-k3s.sh | bash
# ==============================================================================
set -euo pipefail

echo "=========================================================="
echo "🚀 PyLoom Technologies Cloud Platform — OCI K3s Provisioner"
echo "=========================================================="

# 1. Update OS and install prerequisites
echo "📦 Updating system packages..."
sudo apt-get update -qq
sudo apt-get install -y -qq curl wget git jq iptables

# 2. Adjust Oracle Linux / Ubuntu firewall rules for Kubernetes
echo "🛡️  Configuring network rules for K3s..."
sudo iptables -F
sudo iptables -P INPUT ACCEPT
sudo iptables -P FORWARD ACCEPT
sudo iptables -P OUTPUT ACCEPT

# Make iptables rules persistent across reboots
if command -v netfilter-persistent &> /dev/null; then
    sudo netfilter-persistent save
fi

# 3. Install K3s (Lightweight CNCF-certified Kubernetes)
echo "☸️  Installing K3s (lightweight Kubernetes)..."
curl -sfL https://get.k3s.io | sh -s - \
    --write-kubeconfig-mode 644 \
    --disable traefik

export KUBECONFIG=/etc/rancher/k3s/k3s.yaml

# Wait for node to be ready
echo "⏳ Waiting for cluster node to become ready..."
until kubectl get nodes | grep -q " Ready"; do
    sleep 3
done
kubectl get nodes -o wide

# 4. Install ArgoCD (Declarative GitOps Engine)
echo "🐙 Deploying ArgoCD into the cluster..."
kubectl create namespace argocd --dry-run=client -o yaml | kubectl apply -f -
kubectl apply -n argocd -f https://raw.githubusercontent.com/argoproj/argo-cd/stable/manifests/install.yaml

echo "⏳ Waiting for ArgoCD server to start up..."
kubectl wait --for=condition=available deployment/argocd-server -n argocd --timeout=300s

# Retrieve initial ArgoCD admin password
ARGOCD_PASS=$(kubectl -n argocd get secret argocd-initial-admin-secret -o jsonpath="{.data.password}" | base64 -d)

# 5. Connect PyLoom Technologies Production Application via GitOps
echo "📦 Connecting PyLoom Technologies GitOps repository..."
kubectl apply -f https://raw.githubusercontent.com/RishiAryal24/orbital/main/gitops/apps/production.yaml

echo ""
echo "=========================================================="
echo "✅ PyLoom Technologies Cloud Platform Deployed on K3s!"
echo "=========================================================="
echo ""
echo "Cluster Specs:"
echo "  • Node:   $(kubectl get nodes -o jsonpath='{.items[0].metadata.name}')"
echo "  • Memory: 24 GB RAM Allocated"
echo "  • K8s:    $(kubectl version --short 2>/dev/null || kubectl version -o json | jq -r '.serverVersion.gitVersion')"
echo ""
echo "ArgoCD GitOps Console:"
echo "  • Username: admin"
echo "  • Password: ${ARGOCD_PASS}"
echo "  • Port Forward Command (to view in browser):"
echo "      kubectl port-forward svc/argocd-server -n argocd 8080:443 --address 0.0.0.0"
echo ""
echo "Next Step — Connect to your domain with zero-cost Cloudflare Tunnel:"
echo "  curl -L --output cloudflared.deb https://github.com/cloudflare/cloudflared/releases/latest/download/cloudflared-linux-arm64.deb"
echo "  sudo dpkg -i cloudflared.deb"
echo "  cloudflared tunnel login"
echo "=========================================================="
