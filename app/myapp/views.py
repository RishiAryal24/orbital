import json
from django.db import connection
from django.http import JsonResponse
from django.views import View
from django.views.decorators.csrf import csrf_exempt
from django.utils.decorators import method_decorator

from .models import Article, ClientAccount, DeploymentInquiry, ProjectService


class HealthCheckView(View):
    """
    GET /health/
    Used by load balancers, orchestrators, and monitors to verify service health.
    """

    def get(self, request):
        db_status = "connected"
        try:
            with connection.cursor() as cursor:
                cursor.execute("SELECT 1")
        except Exception as exc:
            db_status = f"error: {str(exc)}"

        return JsonResponse(
            {
                "status": "healthy",
                "service": "pyloom-services",
                "organization": "PyLoom Technologies",
                "version": "1.0.0",
                "database": db_status,
            }
        )


class HomeView(View):
    """
    GET /
    API root — directory of PyLoom Technologies endpoints.
    """

    def get(self, request):
        return JsonResponse(
            {
                "message": "PyLoom Technologies Cloud Platform API",
                "service": "pyloom-services",
                "version": "1.0.0",
                "endpoints": {
                    "health": "/health/",
                    "status": "/api/status/",
                    "clients": "/api/clients/",
                    "services": "/api/services/",
                    "inquiries": "/api/inquiries/",
                    "articles": "/api/articles/",
                    "metrics": "/metrics/",
                },
            }
        )


class PlatformStatusView(View):
    """
    GET /api/status/
    Returns real-time platform statistics for PyLoom Technologies services.
    """

    def get(self, request):
        total_clients = ClientAccount.objects.count()
        active_clients = ClientAccount.objects.filter(is_active=True).count()
        total_services = ProjectService.objects.count()
        healthy_services = ProjectService.objects.filter(status="healthy").count()
        pending_inquiries = DeploymentInquiry.objects.filter(status="pending").count()

        prod_count = ProjectService.objects.filter(environment="prod").count()
        staging_count = ProjectService.objects.filter(environment="staging").count()
        dev_count = ProjectService.objects.filter(environment="dev").count()

        return JsonResponse(
            {
                "platform": "PyLoom Technologies Cloud Platform",
                "status": "operational",
                "stats": {
                    "clients": {
                        "total": total_clients,
                        "active": active_clients,
                    },
                    "services": {
                        "total": total_services,
                        "healthy": healthy_services,
                        "environments": {
                            "production": prod_count,
                            "staging": staging_count,
                            "development": dev_count,
                        },
                    },
                    "inquiries": {
                        "pending": pending_inquiries,
                        "total": DeploymentInquiry.objects.count(),
                    },
                },
            }
        )


@method_decorator(csrf_exempt, name="dispatch")
class ClientAccountListView(View):
    """
    GET  /api/clients/  → List client accounts (filter ?all=true to show inactive)
    POST /api/clients/  → Register a new client account
    """

    def get(self, request):
        show_all = request.GET.get("all", "false").lower() == "true"
        queryset = ClientAccount.objects.all() if show_all else ClientAccount.objects.filter(is_active=True)

        clients = []
        for c in queryset:
            clients.append(
                {
                    "id": c.id,
                    "name": c.name,
                    "slug": c.slug,
                    "contact_email": c.contact_email,
                    "tier": c.tier,
                    "is_active": c.is_active,
                    "service_count": c.services.count(),
                    "created_at": c.created_at.isoformat(),
                }
            )
        return JsonResponse({"clients": clients})

    def post(self, request):
        try:
            data = json.loads(request.body)
        except json.JSONDecodeError:
            return JsonResponse({"error": "Invalid JSON"}, status=400)

        name = data.get("name", "").strip()
        slug = data.get("slug", "").strip()
        contact_email = data.get("contact_email", "").strip()
        tier = data.get("tier", "starter").strip()

        if not name or not slug or not contact_email:
            return JsonResponse(
                {"error": "name, slug, and contact_email are required"}, status=400
            )

        if ClientAccount.objects.filter(slug=slug).exists():
            return JsonResponse({"error": f"Client with slug '{slug}' already exists"}, status=409)

        client = ClientAccount.objects.create(
            name=name,
            slug=slug,
            contact_email=contact_email,
            tier=tier,
        )
        return JsonResponse(
            {
                "id": client.id,
                "name": client.name,
                "slug": client.slug,
                "contact_email": client.contact_email,
                "tier": client.tier,
                "is_active": client.is_active,
                "created_at": client.created_at.isoformat(),
            },
            status=201,
        )


@method_decorator(csrf_exempt, name="dispatch")
class ClientAccountDetailView(View):
    """
    GET    /api/clients/<id>/  → Retrieve client details and services
    PATCH  /api/clients/<id>/  → Update client info
    DELETE /api/clients/<id>/  → Soft-deactivate client account
    """

    def _get_client(self, pk):
        try:
            return ClientAccount.objects.get(pk=pk)
        except ClientAccount.DoesNotExist:
            return None

    def get(self, request, pk):
        client = self._get_client(pk)
        if not client:
            return JsonResponse({"error": "Client not found"}, status=404)

        services = [
            {
                "id": s.id,
                "name": s.name,
                "slug": s.slug,
                "service_type": s.service_type,
                "environment": s.environment,
                "status": s.status,
                "version": s.version,
                "endpoint_url": s.endpoint_url,
            }
            for s in client.services.all()
        ]

        return JsonResponse(
            {
                "id": client.id,
                "name": client.name,
                "slug": client.slug,
                "contact_email": client.contact_email,
                "tier": client.tier,
                "is_active": client.is_active,
                "created_at": client.created_at.isoformat(),
                "services": services,
            }
        )

    def patch(self, request, pk):
        client = self._get_client(pk)
        if not client:
            return JsonResponse({"error": "Client not found"}, status=404)

        try:
            data = json.loads(request.body)
        except json.JSONDecodeError:
            return JsonResponse({"error": "Invalid JSON"}, status=400)

        if "name" in data:
            client.name = data["name"].strip()
        if "contact_email" in data:
            client.contact_email = data["contact_email"].strip()
        if "tier" in data:
            client.tier = data["tier"].strip()
        if "is_active" in data:
            client.is_active = bool(data["is_active"])

        client.save()
        return JsonResponse(
            {
                "id": client.id,
                "name": client.name,
                "contact_email": client.contact_email,
                "tier": client.tier,
                "is_active": client.is_active,
            }
        )

    def delete(self, request, pk):
        client = self._get_client(pk)
        if not client:
            return JsonResponse({"error": "Client not found"}, status=404)
        client.is_active = False
        client.save(update_fields=["is_active", "updated_at"])
        return JsonResponse({"message": f"Client '{client.name}' deactivated successfully"})


@method_decorator(csrf_exempt, name="dispatch")
class ProjectServiceListView(View):
    """
    GET  /api/services/  → List services (filter by ?client=<id>, ?status=<status>, ?env=<env>)
    POST /api/services/  → Deploy/register a new service
    """

    def get(self, request):
        queryset = ProjectService.objects.select_related("client").all()

        client_id = request.GET.get("client")
        status_filter = request.GET.get("status")
        env_filter = request.GET.get("env")

        if client_id:
            queryset = queryset.filter(client_id=client_id)
        if status_filter:
            queryset = queryset.filter(status=status_filter)
        if env_filter:
            queryset = queryset.filter(environment=env_filter)

        services = [
            {
                "id": s.id,
                "client": {"id": s.client.id, "name": s.client.name},
                "name": s.name,
                "slug": s.slug,
                "service_type": s.service_type,
                "environment": s.environment,
                "status": s.status,
                "version": s.version,
                "endpoint_url": s.endpoint_url,
                "created_at": s.created_at.isoformat(),
            }
            for s in queryset
        ]
        return JsonResponse({"services": services})

    def post(self, request):
        try:
            data = json.loads(request.body)
        except json.JSONDecodeError:
            return JsonResponse({"error": "Invalid JSON"}, status=400)

        client_id = data.get("client_id")
        name = data.get("name", "").strip()
        slug = data.get("slug", "").strip()
        service_type = data.get("service_type", "api").strip()
        environment = data.get("environment", "prod").strip()
        version = data.get("version", "1.0.0").strip()
        endpoint_url = data.get("endpoint_url", "").strip() or None

        if not client_id or not name or not slug:
            return JsonResponse(
                {"error": "client_id, name, and slug are required"}, status=400
            )

        try:
            client = ClientAccount.objects.get(pk=client_id)
        except ClientAccount.DoesNotExist:
            return JsonResponse({"error": f"Client id {client_id} does not exist"}, status=404)

        if ProjectService.objects.filter(client=client, slug=slug).exists():
            return JsonResponse(
                {"error": f"Service with slug '{slug}' already exists for this client"},
                status=409,
            )

        service = ProjectService.objects.create(
            client=client,
            name=name,
            slug=slug,
            service_type=service_type,
            environment=environment,
            version=version,
            endpoint_url=endpoint_url,
            status="healthy",
        )

        return JsonResponse(
            {
                "id": service.id,
                "client_id": client.id,
                "name": service.name,
                "slug": service.slug,
                "service_type": service.service_type,
                "environment": service.environment,
                "status": service.status,
                "version": service.version,
                "endpoint_url": service.endpoint_url,
                "created_at": service.created_at.isoformat(),
            },
            status=201,
        )


@method_decorator(csrf_exempt, name="dispatch")
class ProjectServiceDetailView(View):
    """
    GET    /api/services/<id>/  → Retrieve service details
    PATCH  /api/services/<id>/  → Update status, version, or endpoint
    DELETE /api/services/<id>/  → Remove service
    """

    def _get_service(self, pk):
        try:
            return ProjectService.objects.select_related("client").get(pk=pk)
        except ProjectService.DoesNotExist:
            return None

    def get(self, request, pk):
        service = self._get_service(pk)
        if not service:
            return JsonResponse({"error": "Service not found"}, status=404)
        return JsonResponse(
            {
                "id": service.id,
                "client": {"id": service.client.id, "name": service.client.name},
                "name": service.name,
                "slug": service.slug,
                "service_type": service.service_type,
                "environment": service.environment,
                "status": service.status,
                "version": service.version,
                "endpoint_url": service.endpoint_url,
                "created_at": service.created_at.isoformat(),
                "updated_at": service.updated_at.isoformat(),
            }
        )

    def patch(self, request, pk):
        service = self._get_service(pk)
        if not service:
            return JsonResponse({"error": "Service not found"}, status=404)

        try:
            data = json.loads(request.body)
        except json.JSONDecodeError:
            return JsonResponse({"error": "Invalid JSON"}, status=400)

        if "status" in data:
            service.status = data["status"].strip()
        if "version" in data:
            service.version = data["version"].strip()
        if "endpoint_url" in data:
            service.endpoint_url = data["endpoint_url"].strip() or None

        service.save()
        return JsonResponse(
            {
                "id": service.id,
                "status": service.status,
                "version": service.version,
                "endpoint_url": service.endpoint_url,
                "updated_at": service.updated_at.isoformat(),
            }
        )

    def delete(self, request, pk):
        service = self._get_service(pk)
        if not service:
            return JsonResponse({"error": "Service not found"}, status=404)
        service.delete()
        return JsonResponse({"message": "Service deleted successfully"})


@method_decorator(csrf_exempt, name="dispatch")
class DeploymentInquiryListView(View):
    """
    GET  /api/inquiries/  → List deployment inquiries (filter ?status=<status>)
    POST /api/inquiries/  → Submit a new deployment request
    """

    def get(self, request):
        queryset = DeploymentInquiry.objects.all()
        status_filter = request.GET.get("status")
        if status_filter:
            queryset = queryset.filter(status=status_filter)

        inquiries = [
            {
                "id": i.id,
                "client_name": i.client_name,
                "contact_email": i.contact_email,
                "project_name": i.project_name,
                "service_type": i.service_type,
                "requirements": i.requirements,
                "status": i.status,
                "submitted_at": i.submitted_at.isoformat(),
            }
            for i in queryset
        ]
        return JsonResponse({"inquiries": inquiries})

    def post(self, request):
        try:
            data = json.loads(request.body)
        except json.JSONDecodeError:
            return JsonResponse({"error": "Invalid JSON"}, status=400)

        client_name = data.get("client_name", "").strip()
        contact_email = data.get("contact_email", "").strip()
        project_name = data.get("project_name", "").strip()
        service_type = data.get("service_type", "api").strip()
        requirements = data.get("requirements", "").strip()

        if not client_name or not contact_email or not project_name:
            return JsonResponse(
                {"error": "client_name, contact_email, and project_name are required"},
                status=400,
            )

        inquiry = DeploymentInquiry.objects.create(
            client_name=client_name,
            contact_email=contact_email,
            project_name=project_name,
            service_type=service_type,
            requirements=requirements,
        )
        return JsonResponse(
            {
                "id": inquiry.id,
                "client_name": inquiry.client_name,
                "project_name": inquiry.project_name,
                "status": inquiry.status,
                "submitted_at": inquiry.submitted_at.isoformat(),
            },
            status=201,
        )


# ─────────────────────────────────────────────────────────────────────────────
# Backward compatibility views
# ─────────────────────────────────────────────────────────────────────────────
@method_decorator(csrf_exempt, name="dispatch")
class ArticleListView(View):
    def get(self, request):
        articles = Article.objects.filter(published=True).values(
            "id", "title", "body", "created_at"
        )
        return JsonResponse({"articles": list(articles)})

    def post(self, request):
        try:
            data = json.loads(request.body)
        except json.JSONDecodeError:
            return JsonResponse({"error": "Invalid JSON"}, status=400)

        title = data.get("title", "").strip()
        body = data.get("body", "").strip()

        if not title or not body:
            return JsonResponse({"error": "title and body are required"}, status=400)

        article = Article.objects.create(title=title, body=body)
        return JsonResponse(
            {
                "id": article.id,
                "title": article.title,
                "body": article.body,
                "published": article.published,
                "created_at": article.created_at.isoformat(),
            },
            status=201,
        )


@method_decorator(csrf_exempt, name="dispatch")
class ArticleDetailView(View):
    def _get_article(self, pk):
        try:
            return Article.objects.get(pk=pk)
        except Article.DoesNotExist:
            return None

    def get(self, request, pk):
        article = self._get_article(pk)
        if not article:
            return JsonResponse({"error": "Not found"}, status=404)
        return JsonResponse(
            {
                "id": article.id,
                "title": article.title,
                "body": article.body,
                "published": article.published,
                "created_at": article.created_at.isoformat(),
                "updated_at": article.updated_at.isoformat(),
            }
        )

    def patch(self, request, pk):
        article = self._get_article(pk)
        if not article:
            return JsonResponse({"error": "Not found"}, status=404)
        article.publish()
        return JsonResponse({"id": article.id, "published": True})

    def delete(self, request, pk):
        article = self._get_article(pk)
        if not article:
            return JsonResponse({"error": "Not found"}, status=404)
        article.delete()
        return JsonResponse({"id": pk, "deleted": True})
