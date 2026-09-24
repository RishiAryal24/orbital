# PyLoom Technologies Cloud Platform — Zero-Cost Architecture & Runbook

> **Strategic Objective:** Deliver an enterprise-grade cloud-native platform (Kubernetes, GitOps, Blue-Green deployments, distributed tracing, and DevSecOps) at **$0.00/month ongoing infrastructure cost**, serving as PyLoom Technologies' flagship solution showcase.

---

## 1. What This Architecture Demonstrates for PyLoom

* **High Architectural Maturity:** Unlike standard tutorial setups, this runs a declarative GitOps workflow (ArgoCD), canary/blue-green promotions, container signing with Cosign, automated vulnerability scanning (Trivy), and distributed request tracing (OpenTelemetry + Jaeger).
* **FinOps Mastery:** Delivering bank-grade reliability and observability without incurring $200–$500/month AWS bills proves that PyLoom Technologies builds hyper-efficient, cost-optimized architectures.
* **Internal Developer Platform (IDP):** Any future service, client project, or SaaS API developed by PyLoom Technologies can plug directly into this operational backbone.

---

## 2. Zero-Cost Infrastructure Matrix

| Layer | Traditional Paid Setup (AWS) | PyLoom Zero-Cost Stack | Cost |
| :--- | :--- | :--- | :--- |
| **Compute & K8s** | AWS EKS + EC2 ($150–$250/mo) | **Oracle Cloud (OCI) Always-Free + K3s**<br>• 4 ARM Ampere vCPUs, 24 GB RAM, 200 GB Storage | **$0.00** |
| **Ingress & TLS** | AWS ALB ($20/mo) + NAT Gateway ($32/mo) | **Cloudflare Tunnel (`cloudflared`)**<br>• Zero open ports, free automated SSL, DDoS defense | **$0.00** |
| **Container Registry**| AWS ECR ($0.10/GB + transfer) | **GitHub Container Registry (GHCR)**<br>• Integrated with GitHub Actions, free unlimited public | **$0.00** |
| **CI/CD & Security** | Dedicated CI runners ($30–$50/mo) | **GitHub Actions Free Tier (2,000 mins/mo)**<br>• Trivy, Checkov, pip-audit, Gitleaks, Hadolint | **$0.00** |
| **GitOps Deployment**| Managed ArgoCD ($50–$100/mo) | **In-Cluster ArgoCD on K3s**<br>• Self-healing, automated sync, Blue-Green rollouts | **$0.00** |
| **Observability** | AWS CloudWatch + Managed Prometheus | **Prometheus + Grafana + Jaeger inside K3s**<br>• Golden metrics, p95/p99 latency, full request traces | **$0.00** |
| **Database** | AWS RDS PostgreSQL ($25–$50/mo) | **In-Cluster PostgreSQL StatefulSet** + automated backups to Cloudflare R2 *(or Neon / Supabase Free Tier)* | **$0.00** |

**Total Estimated Monthly Cost:** **$0.00 / month**

---

## 3. Step-by-Step Deployment Runbook

### Step 1: Provision Oracle Cloud Always Free VM
1. Sign up for an **Oracle Cloud Infrastructure (OCI)** account.
2. Navigate to **Compute → Instances → Create Instance**.
3. Select **Ampere (ARM)** architecture:
   * **Shape:** `VM.Standard.A1.Flex`
   * **OCPUs:** 4
   * **Memory:** 24 GB RAM
   * **OS:** Ubuntu 22.04 LTS (aarch64)
   * **Boot Volume:** 100–200 GB (within the 200 GB free tier allowance).

### Step 2: Install K3s (Lightweight Kubernetes)
SSH into your free OCI instance and run:
```bash
# Install K3s (lightweight, production-grade CNCF Kubernetes)
curl -sfL https://get.k3s.io | sh -s - --write-kubeconfig-mode 644

# Verify cluster is running
kubectl get nodes
```

### Step 3: Connect Cloudflare Tunnel (Zero-Cost Ingress & SSL)
Cloudflare Tunnel exposes your cluster securely to your domain (e.g., `api.pyloomtech.com`) without opening any firewall ports or paying for an AWS Application Load Balancer.

1. Install `cloudflared`:
```bash
curl -L --output cloudflared.deb https://github.com/cloudflare/cloudflared/releases/latest/download/cloudflared-linux-arm64.deb
sudo dpkg -i cloudflared.deb
```
2. Login and create a tunnel:
```bash
cloudflared tunnel login
cloudflared tunnel create pyloom-cluster
```
3. Route traffic to the local Ingress controller:
```yaml
# ~/.cloudflared/config.yml
tunnel: <TUNNEL_ID>
credentials-file: /root/.cloudflared/<TUNNEL_ID>.json

ingress:
  - hostname: api.pyloomtech.com
    service: http://localhost:80
  - service: http_status:404
```
4. Start tunnel as a system service:
```bash
sudo cloudflared service install
sudo systemctl start cloudflared
```

### Step 4: Install ArgoCD (GitOps Engine)
Deploy ArgoCD into K3s:
```bash
kubectl create namespace argocd
kubectl apply -n argocd -f https://raw.githubusercontent.com/argoproj/argo-cd/stable/manifests/install.yaml

# Wait for pods
kubectl wait --for=condition=ready pod -l app.kubernetes.io/name=argocd-server -n argocd --timeout=300s

# Get admin password
kubectl -n argocd get secret argocd-initial-admin-secret -o jsonpath="{.data.password}" | base64 -d
```

### Step 5: Connect PyLoom GitOps Repository
Apply the PyLoom production application manifest:
```bash
kubectl apply -f gitops/apps/production.yaml
```
ArgoCD will immediately detect your repository, sync the Kubernetes manifests from `k8s/overlays/production/`, pull the Docker image from GitHub Container Registry (`ghcr.io`), and start the application.

### Step 6: Deploy Observability & Mesh
1. **Linkerd (Service Mesh):**
   ```bash
   curl -sL run.linkerd.io/install | sh
   linkerd check --pre
   linkerd install --crds | kubectl apply -f -
   linkerd install | kubectl apply -f -
   ```
2. **Prometheus & Grafana:**
   Deploy the pre-configured manifests in `monitoring/`:
   ```bash
   kubectl apply -k monitoring/
   ```
3. **Jaeger Distributed Tracing:**
   Deploy the tracing stack in `tracing/`:
   ```bash
   kubectl apply -k tracing/
   ```

---

## 4. Verification & Testing

Verify that all services are operational:
```bash
# Verify pods in the pyloom / orbital namespace
kubectl get pods -n orbital

# Test the health check endpoint
curl -s https://api.pyloomtech.com/health/ | jq .
```

Expected JSON response:
```json
{
  "status": "healthy",
  "service": "pyloom-services",
  "organization": "PyLoom Technologies",
  "version": "1.0.0"
}
```
