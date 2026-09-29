import json
from django.db import connection
from django.http import HttpResponse, JsonResponse
from django.shortcuts import render
from django.views import View
from django.views.decorators.csrf import csrf_exempt
from django.utils.decorators import method_decorator

from .models import (
    Article,
    ClientAccount,
    DeploymentInquiry,
    ProjectService,
    ServerNode,
    ApplicationDeployment,
    ManagedAddon,
)
from .services import (
    ManifestSynthesizer,
    AddonProvisioner,
    CloudflareService,
    VPSProvisioner,
)



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
    GET / and GET /dashboard/
    Renders the modern PyLoom Technologies Cloud Console for browser requests,
    or returns the JSON API directory for programmatic API callers.
    """

    def get(self, request):
        accept = request.headers.get("Accept", "")
        # Render visual dashboard for browser requests or explicit /dashboard/ path
        if "text/html" in accept or request.path.rstrip("/").endswith("dashboard"):
            context = {
                "services": ProjectService.objects.select_related("client").all(),
                "total_services": ProjectService.objects.count(),
                "healthy_services": ProjectService.objects.filter(status="healthy").count(),
                "total_clients": ClientAccount.objects.count(),
                "servers": ServerNode.objects.select_related("client").all(),
                "total_servers": ServerNode.objects.count(),
                "applications": ApplicationDeployment.objects.select_related("client", "server").all(),
                "total_applications": ApplicationDeployment.objects.count(),
                "addons": ManagedAddon.objects.select_related("client", "server").all(),
                "total_addons": ManagedAddon.objects.count(),
            }
            return render(request, "dashboard.html", context)

        return JsonResponse(
            {
                "message": "PyLoom Technologies Cloud Platform API",
                "service": "pyloom-services",
                "version": "1.0.0",
                "endpoints": {
                    "health": "/health/",
                    "dashboard": "/dashboard/",
                    "status": "/api/status/",
                    "clients": "/api/clients/",
                    "services": "/api/services/",
                    "inquiries": "/api/inquiries/",
                    "servers": "/api/servers/",
                    "apps": "/api/apps/",
                    "addons": "/api/addons/",
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
                    "servers": {
                        "total": ServerNode.objects.count(),
                        "ready": ServerNode.objects.filter(status="ready").count(),
                    },
                    "applications": {
                        "total": ApplicationDeployment.objects.count(),
                        "active": ApplicationDeployment.objects.filter(status="active").count(),
                    },
                    "addons": {
                        "total": ManagedAddon.objects.count(),
                        "running": ManagedAddon.objects.filter(status="running").count(),
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


# ─────────────────────────────────────────────────────────────────────────────
# PaaS Commercial BYOVPS Views: Servers, Applications, Add-ons
# ─────────────────────────────────────────────────────────────────────────────


@method_decorator(csrf_exempt, name="dispatch")
class ServerNodeListView(View):
    """
    GET  /api/servers/ → List connected server nodes.
    POST /api/servers/ → Register a new server node and generate connection command.
    """

    def get(self, request):
        servers = []
        for s in ServerNode.objects.select_related("client").all():
            servers.append(
                {
                    "id": s.id,
                    "client_id": s.client_id,
                    "client_name": s.client.name,
                    "name": s.name,
                    "ip_address": s.ip_address,
                    "ssh_port": s.ssh_port,
                    "ssh_user": s.ssh_user,
                    "status": s.status,
                    "k3s_version": s.k3s_version,
                    "cpu_cores": s.cpu_cores,
                    "ram_mb": s.ram_mb,
                    "disk_gb": s.disk_gb,
                    "cloudflare_tunnel_id": s.cloudflare_tunnel_id,
                    "created_at": s.created_at.isoformat(),
                }
            )
        return JsonResponse({"servers": servers, "total": len(servers)})

    def post(self, request):
        try:
            data = json.loads(request.body)
        except (ValueError, TypeError):
            return JsonResponse({"error": "Invalid JSON body"}, status=400)

        required_fields = ["name", "ip_address", "client_id"]
        for field in required_fields:
            if not data.get(field):
                return JsonResponse({"error": f"Field '{field}' is required"}, status=400)

        try:
            client = ClientAccount.objects.get(pk=data["client_id"])
        except ClientAccount.DoesNotExist:
            return JsonResponse({"error": "Client not found"}, status=404)

        # Check quota for client (e.g. Starter tier allows 1 server)
        if client.tier == "starter" and client.servers.count() >= 1:
            return JsonResponse(
                {"error": "Starter tier allows a maximum of 1 connected server. Please upgrade to Growth."},
                status=403,
            )

        cf_service = CloudflareService()
        tunnel_res = cf_service.create_tunnel(f"pyloom-{data['name'].lower().replace(' ', '-')}")
        tunnel_id = tunnel_res.get("result", {}).get("id", "")
        tunnel_token = tunnel_res.get("result", {}).get("token", "")

        server = ServerNode.objects.create(
            client=client,
            name=data["name"],
            ip_address=data["ip_address"],
            ssh_port=data.get("ssh_port", 22),
            ssh_user=data.get("ssh_user", "root"),
            ssh_credential=data.get("ssh_credential", ""),
            status=data.get("status", "pending"),
            cpu_cores=data.get("cpu_cores", 2),
            ram_mb=data.get("ram_mb", 4096),
            disk_gb=data.get("disk_gb", 50),
            cloudflare_tunnel_id=tunnel_id,
            cloudflare_tunnel_token=tunnel_token,
        )

        base_url = request.build_absolute_uri("/").rstrip("/")
        agent_command = VPSProvisioner.generate_agent_command(server.id, tunnel_token or "pyloom-token", base_url)

        return JsonResponse(
            {
                "id": server.id,
                "name": server.name,
                "ip_address": server.ip_address,
                "status": server.status,
                "tunnel_id": server.cloudflare_tunnel_id,
                "agent_command": agent_command,
                "message": "Server registered. Run the agent command on your VPS to complete provisioning.",
            },
            status=201,
        )


@method_decorator(csrf_exempt, name="dispatch")
class ServerNodeDetailView(View):
    """
    GET    /api/servers/<id>/ → Get server details.
    DELETE /api/servers/<id>/ → Remove server node.
    """

    def get(self, request, pk):
        try:
            s = ServerNode.objects.select_related("client").get(pk=pk)
        except ServerNode.DoesNotExist:
            return JsonResponse({"error": "Server not found"}, status=404)

        return JsonResponse(
            {
                "id": s.id,
                "name": s.name,
                "ip_address": s.ip_address,
                "status": s.status,
                "cpu_cores": s.cpu_cores,
                "ram_mb": s.ram_mb,
                "disk_gb": s.disk_gb,
                "applications_count": s.applications.count(),
                "addons_count": s.addons.count(),
                "created_at": s.created_at.isoformat(),
            }
        )

    def delete(self, request, pk):
        try:
            s = ServerNode.objects.get(pk=pk)
            s.delete()
            return JsonResponse({"id": pk, "deleted": True})
        except ServerNode.DoesNotExist:
            return JsonResponse({"error": "Server not found"}, status=404)


class ServerBootstrapScriptView(View):
    """
    GET /api/servers/<id>/bootstrap.sh
    Returns the executable bash bootstrap script to be piped directly into bash on the client's VPS.
    """

    def get(self, request, pk):
        try:
            server = ServerNode.objects.get(pk=pk)
        except ServerNode.DoesNotExist:
            return HttpResponse("#!/usr/bin/env bash\necho 'Server not found'\nexit 1\n", status=404, content_type="text/plain")

        script = VPSProvisioner.generate_bootstrap_script(
            server_name=server.name,
            k3s_version=server.k3s_version,
            tunnel_token=server.cloudflare_tunnel_token,
        )
        return HttpResponse(script, content_type="text/plain")


@method_decorator(csrf_exempt, name="dispatch")
class ApplicationDeploymentListView(View):
    """
    GET  /api/apps/ → List deployed applications.
    POST /api/apps/ → Deploy an application without writing Kubernetes YAML.
    """

    def get(self, request):
        apps = []
        for app in ApplicationDeployment.objects.select_related("client", "server").all():
            apps.append(
                {
                    "id": app.id,
                    "client_id": app.client_id,
                    "client_name": app.client.name,
                    "server_id": app.server_id if app.server else None,
                    "server_name": app.server.name if app.server else "Default Cluster",
                    "name": app.name,
                    "slug": app.slug,
                    "git_repo_url": app.git_repo_url,
                    "git_branch": app.git_branch,
                    "build_type": app.build_type,
                    "target_port": app.target_port,
                    "replicas": app.replicas,
                    "domain": app.domain,
                    "status": app.status,
                    "current_image": app.current_image,
                    "created_at": app.created_at.isoformat(),
                }
            )
        return JsonResponse({"applications": apps, "total": len(apps)})

    def post(self, request):
        try:
            data = json.loads(request.body)
        except (ValueError, TypeError):
            return JsonResponse({"error": "Invalid JSON body"}, status=400)

        required_fields = ["name", "slug", "git_repo_url", "client_id"]
        for field in required_fields:
            if not data.get(field):
                return JsonResponse({"error": f"Field '{field}' is required"}, status=400)

        try:
            client = ClientAccount.objects.get(pk=data["client_id"])
        except ClientAccount.DoesNotExist:
            return JsonResponse({"error": "Client not found"}, status=404)

        server = None
        if data.get("server_id"):
            try:
                server = ServerNode.objects.get(pk=data["server_id"])
            except ServerNode.DoesNotExist:
                return JsonResponse({"error": "Server not found"}, status=404)

        domain = data.get("domain", f"{data['slug']}.pyloomtech.com")
        target_port = int(data.get("target_port", 8000))
        replicas = int(data.get("replicas", 2))
        env_vars = data.get("environment_variables", {})

        # Synthesize zero-YAML manifests
        synthesized_yaml = ManifestSynthesizer.synthesize_all_yaml(
            app_name=data["slug"],
            namespace=f"tenant-{client.slug}",
            image=f"ghcr.io/{client.slug}/{data['slug']}:latest",
            domain=domain,
            target_port=target_port,
            replicas=replicas,
            env_vars=env_vars,
        )

        # Dynamic Cloudflare DNS routing
        cf_service = CloudflareService()
        cf_service.create_dns_cname(domain, "tunnel.pyloomtech.com")

        app = ApplicationDeployment.objects.create(
            client=client,
            server=server,
            name=data["name"],
            slug=data["slug"],
            git_repo_url=data["git_repo_url"],
            git_branch=data.get("git_branch", "main"),
            build_type=data.get("build_type", "dockerfile"),
            target_port=target_port,
            replicas=replicas,
            domain=domain,
            environment_variables=env_vars,
            status="active",
            current_image=f"ghcr.io/{client.slug}/{data['slug']}:latest",
            argo_app_name=f"rollout-{data['slug']}",
        )

        return JsonResponse(
            {
                "id": app.id,
                "name": app.name,
                "slug": app.slug,
                "status": app.status,
                "domain": app.domain,
                "manifest_preview": synthesized_yaml[:500] + "... (truncated)",
                "message": "Application synthesized and enrolled in Blue/Green zero-downtime pipeline.",
            },
            status=201,
        )


@method_decorator(csrf_exempt, name="dispatch")
class ApplicationDeploymentDetailView(View):
    """
    GET    /api/apps/<id>/ → Get application details and synthesized manifests.
    DELETE /api/apps/<id>/ → Delete application.
    """

    def get(self, request, pk):
        try:
            app = ApplicationDeployment.objects.select_related("client", "server").get(pk=pk)
        except ApplicationDeployment.DoesNotExist:
            return JsonResponse({"error": "Application not found"}, status=404)

        synthesized_yaml = ManifestSynthesizer.synthesize_all_yaml(
            app_name=app.slug,
            namespace=f"tenant-{app.client.slug}",
            image=app.current_image or f"ghcr.io/{app.client.slug}/{app.slug}:latest",
            domain=app.domain,
            target_port=app.target_port,
            replicas=app.replicas,
            env_vars=app.environment_variables,
        )

        return JsonResponse(
            {
                "id": app.id,
                "name": app.name,
                "slug": app.slug,
                "client": app.client.name,
                "server": app.server.name if app.server else "Default Cluster",
                "git_repo_url": app.git_repo_url,
                "git_branch": app.git_branch,
                "build_type": app.build_type,
                "target_port": app.target_port,
                "replicas": app.replicas,
                "domain": app.domain,
                "status": app.status,
                "synthesized_yaml": synthesized_yaml,
                "created_at": app.created_at.isoformat(),
            }
        )

    def delete(self, request, pk):
        try:
            app = ApplicationDeployment.objects.get(pk=pk)
            app.delete()
            return JsonResponse({"id": pk, "deleted": True})
        except ApplicationDeployment.DoesNotExist:
            return JsonResponse({"error": "Application not found"}, status=404)


@method_decorator(csrf_exempt, name="dispatch")
class ManagedAddonListView(View):
    """
    GET  /api/addons/ → List managed databases and caches.
    POST /api/addons/ → Provision a one-click database (PostgreSQL, Redis, MySQL, ClickHouse) with R2 backups.
    """

    def get(self, request):
        addons = []
        for addon in ManagedAddon.objects.select_related("client", "server").all():
            addons.append(
                {
                    "id": addon.id,
                    "client_id": addon.client_id,
                    "client_name": addon.client.name,
                    "server_id": addon.server_id,
                    "server_name": addon.server.name,
                    "name": addon.name,
                    "addon_type": addon.addon_type,
                    "status": addon.status,
                    "allocated_storage_gb": addon.allocated_storage_gb,
                    "r2_backup_enabled": addon.r2_backup_enabled,
                    "created_at": addon.created_at.isoformat(),
                }
            )
        return JsonResponse({"addons": addons, "total": len(addons)})

    def post(self, request):
        try:
            data = json.loads(request.body)
        except (ValueError, TypeError):
            return JsonResponse({"error": "Invalid JSON body"}, status=400)

        required_fields = ["name", "addon_type", "client_id", "server_id"]
        for field in required_fields:
            if not data.get(field):
                return JsonResponse({"error": f"Field '{field}' is required"}, status=400)

        try:
            client = ClientAccount.objects.get(pk=data["client_id"])
        except ClientAccount.DoesNotExist:
            return JsonResponse({"error": "Client not found"}, status=404)

        try:
            server = ServerNode.objects.get(pk=data["server_id"])
        except ServerNode.DoesNotExist:
            return JsonResponse({"error": "Server not found"}, status=404)

        addon_type = data["addon_type"]
        storage_gb = int(data.get("allocated_storage_gb", 10))

        # Synthesize database manifests with R2 backup CronJob
        manifests = AddonProvisioner.generate_addon_manifests(
            addon_name=data["name"].lower().replace(" ", "-"),
            namespace=f"tenant-{client.slug}",
            addon_type=addon_type,
            storage_gb=storage_gb,
        )

        conn_str = f"{addon_type}://{client.slug}:secret@{data['name'].lower().replace(' ', '-')}.tenant-{client.slug}.svc.cluster.local"

        addon = ManagedAddon.objects.create(
            client=client,
            server=server,
            name=data["name"],
            addon_type=addon_type,
            status="running",
            allocated_storage_gb=storage_gb,
            connection_uri=conn_str,
            r2_backup_enabled=True,
        )

        return JsonResponse(
            {
                "id": addon.id,
                "name": addon.name,
                "addon_type": addon.addon_type,
                "status": addon.status,
                "connection_uri": addon.connection_uri,
                "manifest_preview": manifests[:400] + "... (truncated)",
                "message": f"{addon.get_addon_type_display()} provisioned with automated Cloudflare R2 backup pipeline.",
            },
            status=201,
        )

