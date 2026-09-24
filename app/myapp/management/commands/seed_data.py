"""
management/commands/seed_data.py

Populates the database with realistic PyLoom Technologies demo client accounts,
cloud services, deployment inquiries, and reference articles.
Safe to run multiple times — clears existing data first unless --no-clear is passed.

Usage:
    python manage.py seed_data
    python manage.py seed_data --no-clear
"""
from django.core.management.base import BaseCommand
from django.utils import timezone

from myapp.models import Article, ClientAccount, DeploymentInquiry, ProjectService

SEED_CLIENTS = [
    {
        "name": "Apex Global Logistics",
        "slug": "apex-logistics",
        "contact_email": "infra@apexlogistics.io",
        "tier": "enterprise",
        "services": [
            {
                "name": "Fleet Telematics & Tracking API",
                "slug": "fleet-tracking-api",
                "service_type": "api",
                "environment": "prod",
                "status": "healthy",
                "version": "2.4.0",
                "endpoint_url": "https://api.apexlogistics.io/v2",
            },
            {
                "name": "GPS Telemetry Ingestion Worker",
                "slug": "gps-telemetry-worker",
                "service_type": "worker",
                "environment": "prod",
                "status": "healthy",
                "version": "2.4.0",
                "endpoint_url": None,
            },
            {
                "name": "High-Throughput TimescaleDB Cluster",
                "slug": "timeseries-db",
                "service_type": "database",
                "environment": "prod",
                "status": "healthy",
                "version": "15.4-alpine",
                "endpoint_url": None,
            },
        ],
    },
    {
        "name": "Nexus HealthTech",
        "slug": "nexus-health",
        "contact_email": "devops@nexushealth.org",
        "tier": "pro",
        "services": [
            {
                "name": "Patient Clinical Record API",
                "slug": "clinical-record-api",
                "service_type": "api",
                "environment": "prod",
                "status": "healthy",
                "version": "1.8.2",
                "endpoint_url": "https://api.nexushealth.org",
            },
            {
                "name": "HL7 / FHIR Data Exchange Service",
                "slug": "fhir-sync-service",
                "service_type": "worker",
                "environment": "staging",
                "status": "deploying",
                "version": "1.9.0-rc2",
                "endpoint_url": None,
            },
            {
                "name": "Clinical Doctor Portal UI",
                "slug": "doctor-portal",
                "service_type": "frontend",
                "environment": "prod",
                "status": "healthy",
                "version": "3.1.0",
                "endpoint_url": "https://portal.nexushealth.org",
            },
        ],
    },
    {
        "name": "Quantum Stream Media",
        "slug": "quantum-stream",
        "contact_email": "ops@quantumstream.tv",
        "tier": "starter",
        "services": [
            {
                "name": "Video Transcoding Pipeline API",
                "slug": "transcode-api",
                "service_type": "api",
                "environment": "dev",
                "status": "degraded",
                "version": "0.9.4",
                "endpoint_url": "https://dev-transcode.quantumstream.tv",
            },
        ],
    },
]

SEED_INQUIRIES = [
    {
        "client_name": "Aegis Cyber Security",
        "contact_email": "security-lead@aegiscyber.net",
        "project_name": "Kubernetes Zero-Trust Service Mesh & GitOps Setup",
        "service_type": "cloud-infrastructure",
        "requirements": "Need zero-downtime blue-green ArgoCD deployment pipeline with Linkerd mTLS and automated SOC2 container scanning.",
        "status": "in_review",
    },
    {
        "client_name": "Vanguard FinTech",
        "contact_email": "cto@vanguardfin.com",
        "project_name": "Payment Gateway Microservices High Availability",
        "service_type": "microservices",
        "requirements": "Looking for sub-10ms p99 latency SLA, Jaeger distributed request tracing, and 99.99% availability.",
        "status": "pending",
    },
]

SEED_ARTICLES = [
    {
        "title": "Zero-Cost Cloud-Native Architecture with K3s and Cloudflare Tunnels",
        "body": "Deploying production-grade Kubernetes, GitOps with ArgoCD, and distributed tracing on Oracle Cloud Always-Free tier at $0 monthly cost.",
        "published": True,
    },
    {
        "title": "Why Blue-Green Deployments are Critical for Zero-Downtime Database Migrations",
        "body": "Rolling updates risk schema mismatches when old and new pods query the same database concurrently. Blue-green rollouts guarantee atomic traffic cutover.",
        "published": True,
    },
]


class Command(BaseCommand):
    help = "Seed the database with PyLoom Technologies demo clients, services, and inquiries"

    def add_arguments(self, parser):
        parser.add_argument(
            "--no-clear",
            action="store_true",
            default=False,
            help="Skip clearing existing data before seeding",
        )

    def handle(self, *args, **options):
        if not options["no_clear"]:
            ClientAccount.objects.all().delete()
            DeploymentInquiry.objects.all().delete()
            Article.objects.all().delete()
            self.stdout.write(self.style.WARNING("  Cleared existing PyLoom data."))

        client_count = 0
        service_count = 0
        for cdata in SEED_CLIENTS:
            services_data = cdata.pop("services")
            client, _ = ClientAccount.objects.get_or_create(
                slug=cdata["slug"],
                defaults=cdata,
            )
            client_count += 1
            for sdata in services_data:
                ProjectService.objects.get_or_create(
                    client=client,
                    slug=sdata["slug"],
                    defaults=sdata,
                )
                service_count += 1

        inquiry_count = 0
        for idata in SEED_INQUIRIES:
            DeploymentInquiry.objects.create(**idata)
            inquiry_count += 1

        for adata in SEED_ARTICLES:
            Article.objects.create(**adata)

        self.stdout.write(
            self.style.SUCCESS(
                f"\n[OK] PyLoom Technologies database seeded:\n"
                f"   - {client_count} client accounts\n"
                f"   - {service_count} cloud services\n"
                f"   - {inquiry_count} deployment inquiries\n"
                f"   - {len(SEED_ARTICLES)} reference articles"
            )
        )
