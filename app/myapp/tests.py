"""
Test suite for PyLoom Technologies Cloud Platform service.

Run locally:
    python manage.py test myapp --verbosity=2
"""
import hashlib
import hmac
import json

from django.test import Client, TestCase

from .models import (
    Article,
    ClientAccount,
    DeploymentInquiry,
    ProjectService,
    ServerNode,
    ApplicationDeployment,
    ManagedAddon,
    DeploymentEvent,
)
from .services import LanguageDetector



# ─────────────────────────────────────────────────────────────────────────────
# 1. Health & Platform Status Tests
# ─────────────────────────────────────────────────────────────────────────────
class HealthAndStatusTests(TestCase):
    def setUp(self):
        self.client = Client()

    def test_health_check_returns_200_and_pyloom_details(self):
        response = self.client.get("/health/")
        self.assertEqual(response.status_code, 200)
        data = json.loads(response.content)
        self.assertEqual(data["status"], "healthy")
        self.assertEqual(data["service"], "pyloom-services")
        self.assertEqual(data["organization"], "PyLoom Technologies")
        self.assertIn("database", data)

    def test_home_view_lists_all_pyloom_endpoints(self):
        response = self.client.get("/")
        self.assertEqual(response.status_code, 200)
        data = json.loads(response.content)
        self.assertIn("PyLoom Technologies", data["message"])
        self.assertIn("status", data["endpoints"])
        self.assertIn("clients", data["endpoints"])
        self.assertIn("services", data["endpoints"])
        self.assertIn("inquiries", data["endpoints"])

    def test_dashboard_renders_html_console(self):
        response = self.client.get("/dashboard/")
        self.assertEqual(response.status_code, 200)
        self.assertIn("PyLoom Technologies", response.content.decode())
        self.assertIn("Cloud Platform Console", response.content.decode())

    def test_platform_status_aggregates_metrics(self):
        client = ClientAccount.objects.create(
            name="Test Client", slug="test-client", contact_email="test@client.com"
        )
        ProjectService.objects.create(
            client=client, name="API Service", slug="api-svc", environment="prod", status="healthy"
        )
        ProjectService.objects.create(
            client=client, name="Staging Worker", slug="staging-worker", environment="staging", status="degraded"
        )
        DeploymentInquiry.objects.create(
            client_name="Prospect", contact_email="prospect@co.com", project_name="New App", requirements="Cloud setup"
        )

        response = self.client.get("/api/status/")
        self.assertEqual(response.status_code, 200)
        data = json.loads(response.content)
        self.assertEqual(data["status"], "operational")
        self.assertEqual(data["stats"]["clients"]["total"], 1)
        self.assertEqual(data["stats"]["services"]["total"], 2)
        self.assertEqual(data["stats"]["services"]["healthy"], 1)
        self.assertEqual(data["stats"]["services"]["environments"]["production"], 1)
        self.assertEqual(data["stats"]["services"]["environments"]["staging"], 1)
        self.assertEqual(data["stats"]["inquiries"]["pending"], 1)


# ─────────────────────────────────────────────────────────────────────────────
# 2. Client Account API Tests
# ─────────────────────────────────────────────────────────────────────────────
class ClientAccountAPITests(TestCase):
    def setUp(self):
        self.client = Client()
        self.client_account = ClientAccount.objects.create(
            name="Alpha Corp", slug="alpha-corp", contact_email="admin@alpha.com", tier="enterprise"
        )

    def test_list_clients(self):
        response = self.client.get("/api/clients/")
        self.assertEqual(response.status_code, 200)
        data = json.loads(response.content)
        self.assertEqual(len(data["clients"]), 1)
        self.assertEqual(data["clients"][0]["name"], "Alpha Corp")

    def test_create_client_success(self):
        payload = {
            "name": "Beta Inc",
            "slug": "beta-inc",
            "contact_email": "ops@beta.com",
            "tier": "pro",
        }
        response = self.client.post(
            "/api/clients/", data=json.dumps(payload), content_type="application/json"
        )
        self.assertEqual(response.status_code, 201)
        data = json.loads(response.content)
        self.assertEqual(data["slug"], "beta-inc")
        self.assertTrue(ClientAccount.objects.filter(slug="beta-inc").exists())

    def test_create_client_duplicate_slug_returns_409(self):
        payload = {
            "name": "Duplicate Alpha",
            "slug": "alpha-corp",
            "contact_email": "other@alpha.com",
        }
        response = self.client.post(
            "/api/clients/", data=json.dumps(payload), content_type="application/json"
        )
        self.assertEqual(response.status_code, 409)

    def test_create_client_missing_fields_returns_400(self):
        response = self.client.post(
            "/api/clients/", data=json.dumps({"name": "No Slug"}), content_type="application/json"
        )
        self.assertEqual(response.status_code, 400)

    def test_get_client_detail_with_services(self):
        ProjectService.objects.create(
            client=self.client_account,
            name="Alpha API",
            slug="alpha-api",
            service_type="api",
            environment="prod",
            status="healthy",
        )
        response = self.client.get(f"/api/clients/{self.client_account.id}/")
        self.assertEqual(response.status_code, 200)
        data = json.loads(response.content)
        self.assertEqual(data["name"], "Alpha Corp")
        self.assertEqual(len(data["services"]), 1)
        self.assertEqual(data["services"][0]["slug"], "alpha-api")

    def test_patch_client(self):
        response = self.client.patch(
            f"/api/clients/{self.client_account.id}/",
            data=json.dumps({"tier": "starter"}),
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 200)
        self.client_account.refresh_from_db()
        self.assertEqual(self.client_account.tier, "starter")

    def test_delete_client_soft_deactivates(self):
        response = self.client.delete(f"/api/clients/{self.client_account.id}/")
        self.assertEqual(response.status_code, 200)
        self.client_account.refresh_from_db()
        self.assertFalse(self.client_account.is_active)


# ─────────────────────────────────────────────────────────────────────────────
# 3. Project Service API Tests
# ─────────────────────────────────────────────────────────────────────────────
class ProjectServiceAPITests(TestCase):
    def setUp(self):
        self.client = Client()
        self.client_account = ClientAccount.objects.create(
            name="Gamma Tech", slug="gamma-tech", contact_email="ops@gamma.com"
        )
        self.svc1 = ProjectService.objects.create(
            client=self.client_account,
            name="Gamma Core API",
            slug="gamma-api",
            service_type="api",
            environment="prod",
            status="healthy",
            version="1.0.0",
        )
        self.svc2 = ProjectService.objects.create(
            client=self.client_account,
            name="Gamma Worker",
            slug="gamma-worker",
            service_type="worker",
            environment="staging",
            status="degraded",
            version="1.1.0",
        )

    def test_list_services_and_filters(self):
        # All services
        res = self.client.get("/api/services/")
        data = json.loads(res.content)
        self.assertEqual(len(data["services"]), 2)

        # Filter by status
        res_healthy = self.client.get("/api/services/?status=healthy")
        data_healthy = json.loads(res_healthy.content)
        self.assertEqual(len(data_healthy["services"]), 1)
        self.assertEqual(data_healthy["services"][0]["slug"], "gamma-api")

        # Filter by environment
        res_staging = self.client.get("/api/services/?env=staging")
        data_staging = json.loads(res_staging.content)
        self.assertEqual(len(data_staging["services"]), 1)
        self.assertEqual(data_staging["services"][0]["slug"], "gamma-worker")

    def test_create_service_success(self):
        payload = {
            "client_id": self.client_account.id,
            "name": "Gamma Redis",
            "slug": "gamma-redis",
            "service_type": "database",
            "environment": "prod",
            "version": "7.0",
        }
        res = self.client.post(
            "/api/services/", data=json.dumps(payload), content_type="application/json"
        )
        self.assertEqual(res.status_code, 201)
        data = json.loads(res.content)
        self.assertEqual(data["slug"], "gamma-redis")

    def test_create_duplicate_service_slug_returns_409(self):
        payload = {
            "client_id": self.client_account.id,
            "name": "Gamma Core Duplicate",
            "slug": "gamma-api",
        }
        res = self.client.post(
            "/api/services/", data=json.dumps(payload), content_type="application/json"
        )
        self.assertEqual(res.status_code, 409)

    def test_patch_service_status_and_version(self):
        res = self.client.patch(
            f"/api/services/{self.svc1.id}/",
            data=json.dumps({"status": "deploying", "version": "1.0.1"}),
            content_type="application/json",
        )
        self.assertEqual(res.status_code, 200)
        self.svc1.refresh_from_db()
        self.assertEqual(self.svc1.status, "deploying")
        self.assertEqual(self.svc1.version, "1.0.1")

    def test_delete_service(self):
        pk = self.svc2.id
        res = self.client.delete(f"/api/services/{pk}/")
        self.assertEqual(res.status_code, 200)
        self.assertFalse(ProjectService.objects.filter(pk=pk).exists())


# ─────────────────────────────────────────────────────────────────────────────
# 4. Deployment Inquiry API Tests
# ─────────────────────────────────────────────────────────────────────────────
class DeploymentInquiryAPITests(TestCase):
    def setUp(self):
        self.client = Client()

    def test_submit_and_list_inquiry(self):
        payload = {
            "client_name": "Delta Enterprise",
            "contact_email": "cto@delta.com",
            "project_name": "Zero-Cost Cloud Platform",
            "service_type": "cloud-infrastructure",
            "requirements": "Need K3s with Cloudflare Tunnels and ArgoCD GitOps",
        }
        res = self.client.post(
            "/api/inquiries/", data=json.dumps(payload), content_type="application/json"
        )
        self.assertEqual(res.status_code, 201)
        data = json.loads(res.content)
        self.assertEqual(data["status"], "pending")

        list_res = self.client.get("/api/inquiries/?status=pending")
        self.assertEqual(list_res.status_code, 200)
        list_data = json.loads(list_res.content)
        self.assertEqual(len(list_data["inquiries"]), 1)
        self.assertEqual(list_data["inquiries"][0]["client_name"], "Delta Enterprise")


# ─────────────────────────────────────────────────────────────────────────────
# 5. Backward Compatibility (Article API)
# ─────────────────────────────────────────────────────────────────────────────
class ArticleCompatibilityTests(TestCase):
    def setUp(self):
        self.client = Client()
        self.article = Article.objects.create(
            title="PyLoom Architecture", body="High-performance cloud services.", published=True
        )

    def test_list_and_detail(self):
        res = self.client.get("/api/articles/")
        self.assertEqual(res.status_code, 200)
        data = json.loads(res.content)
        self.assertEqual(len(data["articles"]), 1)

        res_detail = self.client.get(f"/api/articles/{self.article.id}/")
        self.assertEqual(res_detail.status_code, 200)


# ─────────────────────────────────────────────────────────────────────────────
# 6. Commercial PaaS Tests: Servers, Zero-YAML Manifests, Add-ons
# ─────────────────────────────────────────────────────────────────────────────
class PaaSServerAndAppTests(TestCase):
    def setUp(self):
        self.client = Client()
        self.account = ClientAccount.objects.create(
            name="Acme Corp", slug="acmecorp", contact_email="dev@acme.com", tier="starter"
        )
        self.growth_account = ClientAccount.objects.create(
            name="Mega Corp", slug="megacorp", contact_email="dev@mega.com", tier="pro"
        )

    def test_register_server_generates_agent_command(self):
        payload = {
            "name": "Hetzner-Node-1",
            "ip_address": "159.69.100.50",
            "client_id": self.account.id,
            "cpu_cores": 4,
            "ram_mb": 8192,
        }
        res = self.client.post("/api/servers/", data=json.dumps(payload), content_type="application/json")
        self.assertEqual(res.status_code, 201)
        data = json.loads(res.content)
        self.assertEqual(data["name"], "Hetzner-Node-1")
        self.assertIn("agent_command", data)
        self.assertIn("curl -fsSL", data["agent_command"])

    def test_starter_tier_enforces_one_server_quota(self):
        # First server succeeds
        payload = {"name": "Server-1", "ip_address": "10.0.0.1", "client_id": self.account.id}
        res1 = self.client.post("/api/servers/", data=json.dumps(payload), content_type="application/json")
        self.assertEqual(res1.status_code, 201)

        # Second server on starter tier must be rejected with 403
        payload2 = {"name": "Server-2", "ip_address": "10.0.0.2", "client_id": self.account.id}
        res2 = self.client.post("/api/servers/", data=json.dumps(payload2), content_type="application/json")
        self.assertEqual(res2.status_code, 403)
        self.assertIn("Starter tier allows a maximum of 1", json.loads(res2.content)["error"])

    def test_server_bootstrap_script_endpoint_returns_bash(self):
        payload = {"name": "Ubuntu-Node", "ip_address": "10.0.0.5", "client_id": self.growth_account.id}
        res = self.client.post("/api/servers/", data=json.dumps(payload), content_type="application/json")
        server_id = json.loads(res.content)["id"]

        script_res = self.client.get(f"/api/servers/{server_id}/bootstrap.sh")
        self.assertEqual(script_res.status_code, 200)
        self.assertIn("#!/usr/bin/env bash", script_res.content.decode())
        self.assertIn("Installing K3s", script_res.content.decode())
        self.assertIn("argo-rollouts", script_res.content.decode())

    def test_deploy_application_synthesizes_zero_yaml_blue_green(self):
        payload = {
            "name": "Payments API",
            "slug": "payments-api",
            "git_repo_url": "https://github.com/acme/payments.git",
            "client_id": self.account.id,
            "target_port": 8000,
            "replicas": 3,
            "domain": "pay.acmecorp.com",
            "environment_variables": {"STRIPE_ENV": "production"},
        }
        res = self.client.post("/api/apps/", data=json.dumps(payload), content_type="application/json")
        self.assertEqual(res.status_code, 201)
        data = json.loads(res.content)
        self.assertEqual(data["slug"], "payments-api")
        self.assertEqual(data["domain"], "pay.acmecorp.com")
        self.assertEqual(data["status"], "active")

        # Verify application detail returns full synthesized YAML
        app_id = data["id"]
        detail_res = self.client.get(f"/api/apps/{app_id}/")
        self.assertEqual(detail_res.status_code, 200)
        detail_data = json.loads(detail_res.content)
        yaml_content = detail_data["synthesized_yaml"]
        self.assertIn("kind: Rollout", yaml_content)
        self.assertIn("blueGreen:", yaml_content)
        self.assertIn("payments-api-active", yaml_content)
        self.assertIn("payments-api-preview", yaml_content)
        self.assertIn("kind: Ingress", yaml_content)

    def test_provision_database_addon_with_r2_backups(self):
        # Register a server first
        s_payload = {"name": "DB-Server", "ip_address": "10.0.0.9", "client_id": self.growth_account.id}
        s_res = self.client.post("/api/servers/", data=json.dumps(s_payload), content_type="application/json")
        server_id = json.loads(s_res.content)["id"]

        addon_payload = {
            "name": "Production Postgres",
            "addon_type": "postgres",
            "client_id": self.growth_account.id,
            "server_id": server_id,
            "allocated_storage_gb": 20,
        }
        res = self.client.post("/api/addons/", data=json.dumps(addon_payload), content_type="application/json")
        self.assertEqual(res.status_code, 201)
        data = json.loads(res.content)
        self.assertEqual(data["addon_type"], "postgres")
        self.assertEqual(data["status"], "running")
        self.assertIn("postgres://megacorp", data["connection_uri"])


# ─────────────────────────────────────────────────────────────────────────────
# 7. GitHub Webhook Push-to-Deploy & Audit Event Tests
# ─────────────────────────────────────────────────────────────────────────────
class GitHubWebhookPushToDeployTests(TestCase):
    def setUp(self):
        self.client = Client()
        self.account = ClientAccount.objects.create(
            name="SaaS Labs", slug="saaslabs", contact_email="ops@saaslabs.io", tier="pro"
        )
        self.secret = "super_webhook_secret_999"
        self.app = ApplicationDeployment.objects.create(
            client=self.account,
            name="Billing Microservice",
            slug="billing-ms",
            git_repo_url="https://github.com/saaslabs/billing.git",
            git_branch="main",
            webhook_secret=self.secret,
            auto_deploy=True,
            status="active",
        )

    def _compute_sig(self, payload_bytes: bytes) -> str:
        digest = hmac.new(self.secret.encode("utf-8"), payload_bytes, hashlib.sha256).hexdigest()
        return f"sha256={digest}"

    def test_github_webhook_ping_returns_pong(self):
        body_bytes = b"{}"
        sig = self._compute_sig(body_bytes)
        res = self.client.post(
            f"/api/webhooks/github/{self.app.slug}/",
            data=body_bytes,
            content_type="application/json",
            HTTP_X_GITHUB_EVENT="ping",
            HTTP_X_HUB_SIGNATURE_256=sig,
        )
        self.assertEqual(res.status_code, 200)
        self.assertEqual(json.loads(res.content)["status"], "pong")

    def test_github_webhook_push_triggers_blue_green_deployment(self):
        payload = {
            "ref": "refs/heads/main",
            "after": "a1b2c3d4e5f678901234567890abcdef12345678",
            "head_commit": {
                "id": "a1b2c3d4e5f678901234567890abcdef12345678",
                "message": "feat(stripe): add support for recurring customer billing",
            },
            "sender": {"login": "rishiaryal"},
        }
        body_bytes = json.dumps(payload).encode("utf-8")
        sig = self._compute_sig(body_bytes)

        res = self.client.post(
            f"/api/webhooks/github/{self.app.slug}/",
            data=body_bytes,
            content_type="application/json",
            HTTP_X_GITHUB_EVENT="push",
            HTTP_X_HUB_SIGNATURE_256=sig,
        )
        self.assertEqual(res.status_code, 200)
        data = json.loads(res.content)
        self.assertTrue(data["success"])
        self.assertEqual(data["commit_sha"], "a1b2c3d")
        self.assertIn("ghcr.io/saaslabs/billing-ms:a1b2c3d", data["image"])

        # Check app database state
        self.app.refresh_from_db()
        self.assertEqual(self.app.latest_commit_sha, "a1b2c3d")
        self.assertEqual(self.app.latest_commit_message, "feat(stripe): add support for recurring customer billing")
        self.assertEqual(self.app.status, "active")

        # Check audit event was recorded
        events_res = self.client.get(f"/api/apps/{self.app.id}/events/")
        self.assertEqual(events_res.status_code, 200)
        events_data = json.loads(events_res.content)
        self.assertEqual(events_data["total_events"], 1)
        self.assertEqual(events_data["events"][0]["sender"], "rishiaryal")
        self.assertEqual(events_data["events"][0]["status"], "deployed")

    def test_github_webhook_rejects_invalid_hmac_signature(self):
        payload = {"ref": "refs/heads/main"}
        body_bytes = json.dumps(payload).encode("utf-8")

        res = self.client.post(
            f"/api/webhooks/github/{self.app.slug}/",
            data=body_bytes,
            content_type="application/json",
            HTTP_X_GITHUB_EVENT="push",
            HTTP_X_HUB_SIGNATURE_256="sha256=invalid_tampered_signature_hex",
        )
        self.assertEqual(res.status_code, 401)
        self.assertIn("Invalid webhook HMAC signature", json.loads(res.content)["error"])

    def test_github_webhook_ignores_unrelated_branches(self):
        payload = {
            "ref": "refs/heads/feature-wip",
            "head_commit": {"id": "111222333444", "message": "wip"},
        }
        body_bytes = json.dumps(payload).encode("utf-8")
        sig = self._compute_sig(body_bytes)

        res = self.client.post(
            f"/api/webhooks/github/{self.app.slug}/",
            data=body_bytes,
            content_type="application/json",
            HTTP_X_GITHUB_EVENT="push",
            HTTP_X_HUB_SIGNATURE_256=sig,
        )
        self.assertEqual(res.status_code, 400)
        self.assertFalse(json.loads(res.content)["success"])
        self.assertIn("Ignored push", json.loads(res.content)["message"])


# ─────────────────────────────────────────────────────────────────────────────
# 8. Language & Framework Auto-Detection Tests
# ─────────────────────────────────────────────────────────────────────────────
class LanguageAutoDetectionTests(TestCase):
    def setUp(self):
        self.client = Client()

    def test_detect_python_django_project(self):
        files = ["manage.py", "requirements.txt", "myproject/settings.py", "myproject/wsgi.py"]
        result = LanguageDetector.detect(files)
        self.assertEqual(result["language"], "python")
        self.assertEqual(result["framework"], "django")
        self.assertEqual(result["target_port"], 8000)
        self.assertIn("gunicorn", result["start_command"])
        self.assertIn("FROM python:3.12-slim", result["generated_dockerfile"])

    def test_detect_python_fastapi_project(self):
        files = ["main.py", "requirements.txt"]
        contents = {"requirements.txt": "fastapi>=0.100.0\nuvicorn>=0.22.0"}
        result = LanguageDetector.detect(files, contents)
        self.assertEqual(result["language"], "python")
        self.assertEqual(result["framework"], "fastapi")
        self.assertIn("uvicorn", result["start_command"])

    def test_detect_nodejs_nextjs_project(self):
        files = ["package.json", "next.config.js", "pages/index.tsx"]
        result = LanguageDetector.detect(files)
        self.assertEqual(result["language"], "nodejs")
        self.assertEqual(result["framework"], "nextjs")
        self.assertEqual(result["target_port"], 3000)
        self.assertIn("FROM node:20-alpine", result["generated_dockerfile"])

    def test_detect_golang_project(self):
        files = ["go.mod", "go.sum", "main.go"]
        result = LanguageDetector.detect(files)
        self.assertEqual(result["language"], "go")
        self.assertEqual(result["target_port"], 8080)
        self.assertIn("FROM golang:1.22-alpine", result["generated_dockerfile"])

    def test_detect_dockerfile_passthrough(self):
        files = ["Dockerfile", "app.py"]
        result = LanguageDetector.detect(files)
        self.assertEqual(result["language"], "dockerfile")
        self.assertEqual(result["confidence"], 1.0)

    def test_detect_api_endpoint(self):
        payload = {
            "files": ["package.json", "server.js"],
            "file_contents": {"package.json": '{"dependencies": {"express": "^4.18.2"}}'},
        }
        res = self.client.post("/api/apps/detect/", data=json.dumps(payload), content_type="application/json")
        self.assertEqual(res.status_code, 200)
        data = json.loads(res.content)
        self.assertEqual(data["language"], "nodejs")
        self.assertEqual(data["framework"], "express")
        self.assertEqual(data["target_port"], 3000)



