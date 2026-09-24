"""
Test suite for PyLoom Technologies Cloud Platform service.

Run locally:
    python manage.py test myapp --verbosity=2
"""
import json

from django.test import Client, TestCase

from .models import Article, ClientAccount, DeploymentInquiry, ProjectService


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
