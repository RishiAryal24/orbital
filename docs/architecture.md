# Architecture & Design Decisions (ADRs)

```
================================================================================
Platform        : PyLoom Cloud-Native Delivery & FinOps GitOps Platform (Orbital)
Organization    : PyLoom Technologies
Lead Architect  : Rishi Aryal (aryalrishi15@gmail.com)
Repository      : https://github.com/RishiAryal24/orbital.git
Status          : Production-Active
================================================================================
```

This document records the architectural decisions, trade-offs, and governance policies behind PyLoom Technologies' cloud platform.

---

## 1. System Overview & Delivery Lifecycle

```
Developer Workspace
  │
  │  git push origin main
  ▼
GitHub Repository (Single Source of Truth)
  │
  ├── Pull Request Opened → pr-checks.yml
  │     ruff / flake8 · bandit SAST · pytest suite (18/18) · container build check
  │
  └── Merged to main → ci-cd.yml
        │
        ├── Job 1: Test & Code Quality
        │     Postgres service container · migrations · pytest with coverage
        │
        ├── Job 2: Build & Supply-Chain Hardening
        │     Docker buildx (linux/amd64 + linux/arm64)
        │     Trivy container CVE vulnerability scan (blocking HIGH/CRITICAL)
        │     Push image → GitHub Container Registry (ghcr.io)
        │     Cosign cryptographic container signing (keypair attestation)
        │
        └── Job 3: GitOps Automated Deployment
              Updates Kubernetes manifest image digest in Git
              ArgoCD detects Git commit within 60s
              Argo Rollouts executes Blue/Green zero-downtime traffic shift
```

---

## 2. Architecture Decision Records (ADRs)

### ADR-001: K3s over Managed Cloud Kubernetes (EKS / GKE / AKS)

* **Decision:** Deploy lightweight CNCF-certified Kubernetes (**K3s**) directly on high-performance Linux VPS nodes instead of AWS EKS or GCP GKE.
* **FinOps Rationale:**
  * AWS EKS charges \$73.00/month *just for the control plane*, before factoring in EC2 worker nodes, NAT Gateways (\$32/mo each), and ALB controllers (\$25/mo each). A minimal production cluster on AWS costs \$300–\$800/month.
  * K3s packages the complete Kubernetes API, containerd, and SQLite/etcd into a single binary running under 600 MB of RAM, allowing production workloads to run reliably on high-performance VPS for under \$15/month.
* **Operational Benefit:** Full standard Kubernetes API compatibility with 90% less infrastructure overhead and zero vendor lock-in.

---

### ADR-002: Declarative GitOps via ArgoCD over Push-Based SSH Deployments

* **Decision:** Declarative GitOps using **ArgoCD & Argo Rollouts** rather than imperative SSH scripts in CI pipelines.
* **Security & Reliability Rationale:**
  * Imperative SSH deployments require storing sensitive production SSH keys inside GitHub Actions secrets. If a runner is compromised, the production server is vulnerable.
  * ArgoCD runs *inside* the cluster and pulls configuration from Git. No inbound firewall ports or SSH access are exposed to third-party CI runners.
  * Provides automated drift detection, visual cluster topology, and one-click instant rollbacks.

---

### ADR-003: Zero-Cost Ingress via Cloudflare Tunnel over Public Load Balancers

* **Decision:** Ingress through **Cloudflare Tunnel (`cloudflared`)** instead of cloud Application Load Balancers (ALBs) or public node ports.
* **Zero Trust Rationale:**
  * Traditional load balancers require public IP addresses and open inbound firewall ports (`80`, `443`), making the server targets for port scans and DDoS attacks.
  * Cloudflare Tunnel establishes outbound encrypted TLS tunnels from within the cluster directly to Cloudflare's nearest edge data center.
  * The VPS firewall can completely close all public inbound ports while still delivering global HTTPS traffic protected by Cloudflare Edge WAF, DDoS mitigation, and edge caching at **$0.00 infrastructure cost**.

---

### ADR-004: Zero-Egress Database Disaster Recovery via Cloudflare R2

* **Decision:** Offsite automated database backups shipped to **Cloudflare R2** object storage using S3 API integration.
* **FinOps Rationale:**
  * AWS S3 imposes egress data transfer fees (\$0.09/GB) whenever backups are downloaded or transferred across regions.
  * Cloudflare R2 provides 10 GB of free storage and **zero egress bandwidth charges**, meaning emergency disaster recovery downloads incur zero financial penalties.

---

### ADR-005: Dual-Mode REST API & Server-Rendered Glassmorphism UI

* **Decision:** Unified Django 5.x application serving both a rich Glassmorphism dashboard (HTML/CSS) and a strict REST API (JSON) via content negotiation.
* **Architectural Rationale:**
  * Eliminates the need for maintaining separate Node.js/React frontend microservices and extra reverse proxies for small-to-medium enterprise portals.
  * Browsers requesting `/` receive a modern, responsive Glassmorphism operations console; automated curl scripts and monitoring systems requesting `Accept: application/json` receive structured machine-readable metrics.

---

### ADR-006: Hardened Defense-in-Depth Pod Security

* **Decision:** Enforce read-only root filesystems, non-root user execution, and capability dropping on all application pods.
* **Security Rationale:**
  * `runAsNonRoot: true` and `runAsUser: 1000` prevent privilege escalation even if an application dependency has an unpatched remote code execution vulnerability.
  * `readOnlyRootFilesystem: true` blocks attackers from dropping executable binaries onto the filesystem. Dynamic write operations are restricted to an isolated `emptyDir` mount at `/tmp`.
  * `capabilities: drop: ["ALL"]` strips all Linux root capabilities from the container runtime.

---

## 3. Backup and Recovery Matrix

| Target | Mechanism | Schedule | Storage Target | Egress Cost |
| :--- | :--- | :--- | :--- | :--- |
| **PostgreSQL Database** | `pg_dump` compressed with gzip | Daily at 02:00 UTC | Cloudflare R2 | **\$0.00 (Zero Egress)** |
| **Cluster Manifests** | Git version control | On every commit | GitHub Repository | **\$0.00** |
| **Signed Container Images** | Cosign + Trivy hardened builds | On merge to main | GitHub Container Registry (ghcr.io) | **\$0.00** |

---

## 4. Security & Compliance Controls Summary

| Security Control | Implementation Standard | Verification |
| :--- | :--- | :--- |
| **Container CVE Gate** | Aqua Security Trivy | Fails CI pipeline on critical severity vulnerabilities |
| **Image Authenticity** | Sigstore Cosign | Cryptographic signature verification via public key |
| **Network Isolation** | Kubernetes NetworkPolicy | Blocks all inter-namespace traffic except port 5432 and ingress |
| **DDoS & Perimeter Shield** | Cloudflare Edge WAF & Outbound Tunnels | No open listening ports on host VPS |
| **Least Privilege Secrets** | Kubernetes Secrets injected via envFrom | Plaintext secrets never committed to Git |
| **Fault Resilience** | PodDisruptionBudget (`minAvailable: 1`) | Prevents downtime during cluster node maintenance |

---

*Maintained by PyLoom Technologies — Architectural documentation approved by Rishi Aryal.*
