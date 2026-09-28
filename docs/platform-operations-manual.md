# PyLoom Technologies — Cloud Platform Operations Manual (SOP & Feature Reference)

```
================================================================================
Document ID     : PLT-OPS-MAN-001
Classification  : Production Standard Operating Procedure (SOP) & Feature Catalog
System Name     : PyLoom Cloud-Native Delivery & FinOps GitOps Platform (Orbital)
Repository      : https://github.com/RishiAryal24/orbital.git
Version         : 2.4.0-Production
Author / Lead   : Rishi Aryal (aryalrishi15@gmail.com)
Organization    : PyLoom Technologies
Target Audience : System Administrators, Site Reliability Engineers, DevOps Architects
================================================================================
```

---

## Table of Contents

1. [Executive Summary & System Purpose](#1-executive-summary--system-purpose)
2. [End-to-End System Architecture](#2-end-to-end-system-architecture)
3. [Comprehensive Feature Catalog](#3-comprehensive-feature-catalog)
   - [3.1 Multi-Tenant Glassmorphism Control Plane](#31-multi-tenant-glassmorphism-control-plane)
   - [3.2 Dual-Mode REST API & Telemetry Engine](#32-dual-mode-rest-api--telemetry-engine)
   - [3.3 Zero-Downtime Blue/Green GitOps Engine (Argo Rollouts)](#33-zero-downtime-bluegreen-gitops-engine-argo-rollouts)
   - [3.4 DevSecOps Supply Chain Security (Trivy & Cosign)](#34-devsecops-supply-chain-security-trivy--cosign)
   - [3.5 Hardened Pod & Namespace Security Architecture](#35-hardened-pod--namespace-security-architecture)
   - [3.6 Zero-Egress Disaster Recovery (Cloudflare R2)](#36-zero-egress-disaster-recovery-cloudflare-r2)
   - [3.7 Zero-Open-Port Edge Security (Cloudflare Tunnel)](#37-zero-open-port-edge-security-cloudflare-tunnel)
   - [3.8 FinOps Cost Optimization Architecture](#38-finops-cost-optimization-architecture)
4. [Hardware & Infrastructure Sizing Matrix](#4-hardware--infrastructure-sizing-matrix)
5. [Standard Operating Procedures (SOPs)](#5-standard-operating-procedures-sops)
   - [SOP-01: Provisioning Cluster on a New VPS](#sop-01-provisioning-cluster-on-a-new-vps)
   - [SOP-02: Executing a Production Application Release](#sop-02-executing-a-production-application-release)
   - [SOP-03: Emergency Deployment Rollback (Under 10 Seconds)](#sop-03-emergency-deployment-rollback-under-10-seconds)
   - [SOP-04: Disaster Recovery & Database Restoration](#sop-04-disaster-recovery--database-restoration)
   - [SOP-05: Secret Rotation & Credential Management](#sop-05-secret-rotation--credential-management)
   - [SOP-06: Telemetry Inspection & Distributed Trace Analysis](#sop-06-telemetry-inspection--distributed-trace-analysis)
6. [Emergency Incident Response & Troubleshooting Runbook](#6-emergency-incident-response--troubleshooting-runbook)
7. [Compliance & Audit Verification Matrix](#7-compliance--audit-verification-matrix)

---

## 1. Executive Summary & System Purpose

The **PyLoom Cloud-Native Delivery & FinOps GitOps Platform (Orbital)** is an enterprise-grade application delivery, infrastructure automation, and cost-optimized orchestration system designed for high availability and zero-overhead operations.

### Key Objectives
* **Eliminate Deployment Downtime:** Guarantee zero `502 Bad Gateway` errors during application code releases and schema migrations using automated Blue/Green traffic shifting.
* **Radical Cost Reduction (FinOps):** Eliminate reliance on expensive cloud-managed services ($800–$2,500/month AWS EKS/RDS overhead) by utilizing lightweight CNCF-certified K3s, high resource density, and Cloudflare R2 object storage with zero egress fees.
* **Zero Trust & DevSecOps Compliance:** Protect the software supply chain through automated Trivy vulnerability scanning, Sigstore Cosign cryptographic container signing, locked-down non-root runtime environments, and zero open inbound firewall ports via Cloudflare Tunnels.

---

## 2. End-to-End System Architecture

The platform spans three primary tiers: **Edge / Perimeter Security**, **Cluster Runtime & Orchestration**, and **External Distributed Storage / Telemetry**.

```mermaid
flowchart TD
    subgraph Edge ["1. Edge Tier (Cloudflare Global Network)"]
        ClientUser["End Users & Clients"] -->|HTTPS / TLS 1.3| CF["Cloudflare Edge WAF & DDoS Shield"]
        CF -->|Encrypted Outbound Tunnel| CFTunnel["cloudflared Daemon (Zero Inbound Open Ports)"]
    end

    subgraph Cluster ["2. Cluster Runtime (K3s on Ubuntu VPS)"]
        CFTunnel --> Ingress["Ingress Controller / Service Routing"]
        
        subgraph AppNamespace ["Namespace: orbital"]
            Ingress --> ActiveSvc["Active Service (Port 8000)"]
            Ingress -.-> PreviewSvc["Preview Service (Testing)"]
            
            ActiveSvc --> Pod1["Orbital Pod A (Django/Gunicorn)"]
            ActiveSvc --> Pod2["Orbital Pod B (Django/Gunicorn)"]
            ActiveSvc --> Pod3["Orbital Pod C (Django/Gunicorn)"]
            
            Pod1 --> PostgresLocal["PostgreSQL 16 High-Performance DB"]
            Pod2 --> PostgresLocal
            Pod3 --> PostgresLocal
            
            BackupCron["db-backup CronJob (Every 24h)"] -->|pg_dump & gzip| PostgresLocal
        end

        subgraph GitOpsNamespace ["Namespace: argocd"]
            ArgoServer["ArgoCD Server UI"]
            ArgoController["Argo Rollouts Controller"]
        end

        ArgoController -->|Blue/Green Traffic Switch| ActiveSvc
    end

    subgraph External ["3. Storage, Registry & Telemetry Tier"]
        GitHub["GitHub Repository (Source of Truth)"] -->|Webhook / Poll| ArgoServer
        GHCR["GitHub Container Registry (ghcr.io)"] -->|Signed Images| Pod1
        BackupCron -->|Encrypted S3 API ($0 Egress)| R2["Cloudflare R2 Object Storage"]
        Pod1 -.->|OTLP Traces| Jaeger["Jaeger Distributed Tracing"]
    end
```

---

## 3. Comprehensive Feature Catalog

### 3.1 Multi-Tenant Glassmorphism Control Plane
* **Technology:** Django 5.x, Modern HTML5/CSS3 Custom Design System (Backdrop-filter blur, CSS variables, dark-mode native palette).
* **Location:** Accessible at root URL `/` and `/dashboard/`.
* **Capabilities:**
  1. **Real-Time Platform Vital Signs:** Displays live cluster status, active replica counts, database health status, and continuous delivery synchronization state.
  2. **Client Portfolio Management:** Multi-tenant registry tracking client accounts (`Enterprise`, `Pro`, `Starter`), allocated SLAs, and deployment regions.
  3. **Microservices Health Grid:** Real-time visibility into registered microservices (`Active`, `Degraded`, `Syncing`), live CPU/Memory utilization, and active version hashes.
  4. **Interactive Deployment Inquiry Engine:** Client onboarding form accepting new infrastructure deployment requests directly stored into PostgreSQL with validation.
  5. **Quick-Action Operations Bar:** Direct deep links to ArgoCD Console, OpenTelemetry Trace views, Cloudflare Tunnel management, and raw JSON metrics.

### 3.2 Dual-Mode REST API & Telemetry Engine
* **Technology:** Django REST Views with Content Negotiation (`application/json` vs `text/html`).
* **Endpoints:**
  * `GET /health/` — Liveness & Readiness probe verifying DB connectivity and host uptime (returns HTTP 200 `{"status": "ok"}`).
  * `GET /metrics/` — Prometheus scraper endpoint publishing HTTP latency histograms, database connection pool statistics, and request counts.
  * `GET /api/status/` — JSON payload containing live platform health, cluster mode, and current release commit SHA.
  * `GET /api/clients/` — JSON list of all registered tenant accounts and their active service contracts.
  * `GET /api/services/` — Real-time status of all running microservices.
  * `POST /api/inquiries/` — Programmatic ingestion of new infrastructure deployment tickets.

### 3.3 Zero-Downtime Blue/Green GitOps Engine (Argo Rollouts)
* **Configuration Manifests:** [`k8s/base/rollout.yaml`](file:///e:/Projects/orbital/k8s/base/rollout.yaml) & [`gitops/apps/production.yaml`](file:///e:/Projects/orbital/gitops/apps/production.yaml).
* **Capabilities:**
  1. **Two Co-Existing Service Environments:** Maintains an `Active` service (serving live customer traffic) and a `Preview` service (hosting the newly deployed candidate version).
  2. **Automated Pre-Promotion Verification:** Argo Rollouts keeps new candidate pods warm on preview for a configurable soak time (e.g. 30 seconds), running automated health checks.
  3. **Instant Traffic Switch:** Shifts 100% of production traffic instantly via Kubernetes service selector changes without dropping any active TCP connections.
  4. **Sub-10-Second Instant Rollback:** If an error rate or synthetic test triggers a failure, traffic immediately snaps back to the stable replica set with zero user impact.

### 3.4 DevSecOps Supply Chain Security (Trivy & Cosign)
* **Configuration:** [`.github/workflows/ci-cd.yml`](file:///e:/Projects/orbital/.github/workflows/ci-cd.yml).
* **Capabilities:**
  1. **Trivy Container CVE Gatekeeper:** Every built image is scanned against the national vulnerability database for `HIGH` and `CRITICAL` CVEs before deployment. Builds fail automatically if unresolved critical vulnerabilities exist.
  2. **Cryptographic Container Signing (Sigstore Cosign):** Container images pushed to GitHub Container Registry (`ghcr.io`) are signed cryptographically using keypairs.
  3. **Admission Attestation:** Cluster admission controllers verify container image signatures before allowing pods to be scheduled on worker nodes.

### 3.5 Hardened Pod & Namespace Security Architecture
* **Configuration:** [`k8s/base/deployment.yaml`](file:///e:/Projects/orbital/k8s/base/deployment.yaml), [`k8s/base/network-policy.yaml`](file:///e:/Projects/orbital/k8s/base/network-policy.yaml), [`k8s/base/pdb.yaml`](file:///e:/Projects/orbital/k8s/base/pdb.yaml).
* **Capabilities:**
  1. **Non-Root Execution:** Pods run under dedicated unprivileged UID/GID `1000:1000`.
  2. **Immutable Filesystem:** `readOnlyRootFilesystem: true` prevents malware or unauthorized runtime modifications. Dynamic writes are strictly constrained to a scoped `emptyDir` mount at `/tmp`.
  3. **Linux Capability Stripping:** Pods drop all root Linux kernel privileges (`drop: ["ALL"]`).
  4. **Network Isolation (Zero Trust):** Kubernetes `NetworkPolicy` blocks all inter-pod traffic except explicitly whitelisted communication between ingress controllers, application pods, and the database port `5432`.
  5. **Pod Disruption Budget (PDB):** Enforces `minAvailable: 1`, guaranteeing that node maintenance or autoscaling events can never terminate all application pods simultaneously.

### 3.6 Zero-Egress Disaster Recovery (Cloudflare R2)
* **Configuration:** [`k8s/base/db-backup-cronjob.yaml`](file:///e:/Projects/orbital/k8s/base/db-backup-cronjob.yaml) & [`scripts/restore-db.sh`](file:///e:/Projects/orbital/scripts/restore-db.sh).
* **Capabilities:**
  1. **Automated Scheduled Backups:** Runs daily at `02:00 UTC` via a Kubernetes CronJob.
  2. **Streamed Gzip Compression:** Direct in-memory compression of PostgreSQL dumps minimizing local disk I/O.
  3. **S3-Compatible Cloudflare R2 Upload:** Ships encrypted database archives to Cloudflare R2 object storage with **$0.00 data transfer (egress) fees** (eliminating AWS S3 egress penalties).
  4. **Automated Retention Lifecycle:** Archives older than 30 days are automatically expunged from the storage bucket.
  5. **One-Command Disaster Recovery:** The [`scripts/restore-db.sh`](file:///e:/Projects/orbital/scripts/restore-db.sh) utility downloads, verifies checksums, and restores the entire database in under 2 minutes.

### 3.7 Zero-Open-Port Edge Security (Cloudflare Tunnel)
* **Configuration:** [`k8s/base/cloudflared.yaml`](file:///e:/Projects/orbital/k8s/base/cloudflared.yaml).
* **Capabilities:**
  1. **No Public Inbound Ports:** The VPS firewall has ports `80`, `443`, and `22` completely blocked from public IP ingress.
  2. **Outbound Reverse Proxy:** The lightweight `cloudflared` daemon establishes four encrypted, multiplexed outbound connections directly to Cloudflare's nearest edge data centers.
  3. **Built-in DDoS & Bot Mitigation:** All traffic passes through Cloudflare Edge security, WAF, and automated SSL termination before touching the VPS.

### 3.8 FinOps Cost Optimization Architecture
* **Comparison:**
  * Traditional AWS EKS + Managed RDS + ALB + NAT Gateway: **\$850 – \$1,800/month**.
  * PyLoom Unified K3s + Cloudflare Architecture: **\$6 – \$25/month** (single high-performance VPS).
* **Capabilities:**
  1. Lightweight K3s memory footprint (< 800 MB RAM for control plane).
  2. Zero-cost SSL certificates (Cloudflare Edge SSL + Cert-Manager).
  3. Zero-cost container registry (GitHub Container Registry).
  4. Zero-cost backup egress (Cloudflare R2).

---

## 4. Hardware & Infrastructure Sizing Matrix

| Profile | Target Workload | CPU | RAM | Storage | Target Monthly Cost |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **Stage 1: Minimum Viable Showcase** | Dev, Demo, Client Presentations | 2 vCPU | 4 GB RAM (+ 2 GB Swap) | 25 GB NVMe SSD | ~\$4.50 – \$6.00 / month |
| **Stage 2: Production Standard (Recommended)** | 5–15 Microservices, 100k requests/mo | 2–4 vCPU | 8 GB RAM | 50 GB NVMe SSD | ~\$10.00 – \$16.00 / month |
| **Stage 3: Enterprise High-Density** | 20+ Microservices, Full ELK / Jaeger stack | 4–8 vCPU | 16–24 GB RAM | 100 GB NVMe SSD | ~\$25.00 – \$40.00 / month |

---

## 5. Standard Operating Procedures (SOPs)

### SOP-01: Provisioning Cluster on a New VPS

**Trigger:** New VPS provisioned with Ubuntu 22.04 / 24.04 LTS.

1. SSH into the freshly created VPS:
   ```bash
   ssh root@<YOUR_VPS_IP>
   ```
2. Execute the PyLoom automated provisioner:
   ```bash
   curl -fsSL https://raw.githubusercontent.com/RishiAryal24/orbital/main/scripts/setup-oci-k3s.sh | bash
   ```
3. Verify cluster readiness:
   ```bash
   export KUBECONFIG=/etc/rancher/k3s/k3s.yaml
   kubectl get nodes -o wide
   kubectl get pods -A
   ```
4. Save the ArgoCD admin password output displayed at the end of the script execution.

---

### SOP-02: Executing a Production Application Release

**Trigger:** New feature, bugfix, or configuration change approved for production.

1. Commit changes to your local branch:
   ```bash
   git add .
   git commit -m "feat(api): add new enterprise telemetry hooks"
   ```
2. Push to the GitHub repository `main` branch:
   ```bash
   git push origin main
   ```
3. GitHub Actions triggers automatically:
   * Executes 18 automated unit tests.
   * Compiles container image and runs Trivy CVE scan.
   * Signs container image cryptographically using Cosign.
   * Pushes image to `ghcr.io/rishiaryal24/orbital:<COMMIT_SHA>`.
4. ArgoCD detects the new image tag in Git within 60 seconds:
   * Deploys the new version into the `Preview` environment.
   * Conducts health checks.
   * Promotes the release to `Active` with zero downtime.

---

### SOP-03: Emergency Deployment Rollback (Under 10 Seconds)

**Trigger:** A bad release introduced unexpected business logic errors in production.

#### Method A: Via ArgoCD Command Line (Fastest)
```bash
# Undo the rollout to the previous healthy revision
kubectl argo rollouts undo rollout/orbital -n orbital
```

#### Method B: Via Git Revert (GitOps Standard)
```bash
git revert HEAD --no-edit
git push origin main
```
ArgoCD will immediately detect the revert and synchronize the cluster back to the previous stable state.

---

### SOP-04: Disaster Recovery & Database Restoration

**Trigger:** Accidental data truncation, database corruption, or VPS migration.

1. List available backup snapshots in Cloudflare R2:
   ```bash
   ./scripts/restore-db.sh --list
   ```
2. Restore the latest backup snapshot:
   ```bash
   ./scripts/restore-db.sh --latest
   ```
3. Or restore a specific historical timestamp:
   ```bash
   ./scripts/restore-db.sh --file orbital_backup_2026-09-28_020000.sql.gz
   ```
4. Verify database integrity:
   ```bash
   kubectl exec -it deployment/orbital -n orbital -- python manage.py check --database default
   ```

---

### SOP-05: Secret Rotation & Credential Management

**Trigger:** Periodic 90-day security credential rotation or incident containment.

1. Update the local secret manifest or environment variables:
   ```bash
   kubectl create secret generic orbital-secrets \
     --namespace=orbital \
     --from-literal=SECRET_KEY="<NEW_STRONG_KEY>" \
     --from-literal=DB_PASSWORD="<NEW_DB_PASSWORD>" \
     --dry-run=client -o yaml | kubectl apply -f -
   ```
2. Trigger a graceful rolling restart of the application pods:
   ```bash
   kubectl rollout restart deployment/orbital -n orbital
   ```
3. Monitor status to ensure new pods boot cleanly:
   ```bash
   kubectl rollout status deployment/orbital -n orbital
   ```

---

### SOP-06: Telemetry Inspection & Distributed Trace Analysis

**Trigger:** User reports degraded response times or HTTP 500 errors.

1. Inspect live application pod logs:
   ```bash
   kubectl logs -n orbital -l app=orbital -c orbital --tail=100 -f
   ```
2. Forward the Jaeger tracing console to inspect request traces:
   ```bash
   kubectl port-forward svc/jaeger-query -n monitoring 16686:16686 --address 0.0.0.0
   ```
3. Open `http://<VPS_IP>:16686` in your browser. Inspect trace spans for database query latencies or slow network calls.

---

## 6. Emergency Incident Response & Troubleshooting Runbook

| Alert / Symptom | Root Cause Possibilities | Triage & Remediation Command |
| :--- | :--- | :--- |
| **`CrashLoopBackOff`** | Database unreachable or migration failure | `kubectl describe pod -l app=orbital -n orbital`<br>`kubectl logs -l app=orbital -n orbital --previous` |
| **`OOMKilled` (Exit 137)** | Pod exceeded 512Mi memory limit | Inspect memory usage: `kubectl top pods -n orbital`<br>Increase memory limit in [`k8s/base/deployment.yaml`](file:///e:/Projects/orbital/k8s/base/deployment.yaml) |
| **`502 Bad Gateway` at Cloudflare** | `cloudflared` daemon stopped or disconnected | Check tunnel status: `systemctl status cloudflared`<br>Restart service: `sudo systemctl restart cloudflared` |
| **ArgoCD `OutOfSync`** | Git drift or unapplied manifest syntax error | Inspect sync diff: `argocd app diff orbital`<br>Force hard refresh: `argocd app get orbital --hard-refresh` |
| **PostgreSQL Connection Exhaustion** | Leaked database connections | Check connection count:<br>`kubectl exec -it svc/postgres -n orbital -- psql -U orbital -c "SELECT count(*) FROM pg_stat_activity;"` |

---

## 7. Compliance & Audit Verification Matrix

This matrix can be presented directly to client auditors, CTOs, and SOC-2/HIPAA compliance officers:

| Security Domain | PyLoom Platform Implementation | Audit Verification Command |
| :--- | :--- | :--- |
| **Supply Chain Integrity** | Sigstore Cosign signed container images | `cosign verify --key cosign.pub ghcr.io/rishiaryal24/orbital:latest` |
| **Vulnerability Management** | Automated Trivy scanner with build-blocking thresholds | GitHub Actions CI Execution Logs |
| **Least Privilege Execution** | Container drops `ALL` capabilities; runs as non-root `UID 1000` | `kubectl get pod -n orbital -o jsonpath='{.items[0].spec.securityContext}'` |
| **Filesystem Immutability** | `readOnlyRootFilesystem: true` enforced at runtime | `kubectl exec -it deploy/orbital -n orbital -- touch /test_file` (Returns Read-only error) |
| **Disaster Recovery SLA** | Automated daily encrypted backup to offsite Cloudflare R2 | S3 API Bucket Verification via AWS CLI / Cloudflare Dashboard |
| **Zero Inbound Attack Surface** | No public open ports; ingress strictly via encrypted tunnel | `nmap -Pn <VPS_PUBLIC_IP>` (All ports show filtered/closed) |

---

*PyLoom Technologies Cloud Platform Operations Manual — Maintained by Rishi Aryal (aryalrishi15@gmail.com)*
