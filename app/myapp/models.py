from django.db import models
from django.utils import timezone


class ClientAccount(models.Model):
    """Represents a PyLoom Technologies client or organization."""

    TIER_CHOICES = [
        ("free", "Free Evaluation"),
        ("starter", "Starter Tier ($9/mo)"),
        ("growth", "Growth Tier ($29/mo)"),
        ("pro", "Professional Tier (Legacy Growth)"),
        ("team", "Team / Agency Tier ($79/mo)"),
        ("enterprise", "Enterprise Cloud"),
    ]

    name                   = models.CharField(max_length=150)
    slug                   = models.SlugField(max_length=150, unique=True)
    contact_email          = models.EmailField()
    tier                   = models.CharField(max_length=30, choices=TIER_CHOICES, default="starter")
    is_active              = models.BooleanField(default=True)
    stripe_customer_id     = models.CharField(max_length=100, blank=True)
    stripe_subscription_id = models.CharField(max_length=100, blank=True)
    subscription_status    = models.CharField(max_length=30, default="active")
    current_period_end     = models.DateTimeField(null=True, blank=True)
    created_at             = models.DateTimeField(default=timezone.now)
    updated_at             = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self) -> str:
        return f"{self.name} ({self.tier})"

    def can_add_server(self) -> tuple[bool, str]:
        """Check if client tier allows connecting an additional VPS node."""
        current_count = self.servers.count()
        tier = self.tier.lower()
        if tier == "starter" and current_count >= 1:
            return False, "Starter tier allows a maximum of 1 connected server. Please upgrade to Growth ($29/mo)."
        if tier in ["growth", "pro"] and current_count >= 3:
            return False, "Growth tier allows a maximum of 3 connected servers. Please upgrade to Team/Agency ($79/mo)."
        if tier == "free" and current_count >= 1:
            return False, "Free tier allows a maximum of 1 evaluation node."
        return True, ""

    def can_add_application(self) -> tuple[bool, str]:
        """Check if client tier allows deploying an additional application."""
        current_count = self.applications.count()
        tier = self.tier.lower()
        if tier == "starter" and current_count >= 5:
            return False, "Starter tier allows a maximum of 5 applications. Please upgrade to Growth ($29/mo) for unlimited apps."
        if tier == "free" and current_count >= 1:
            return False, "Free tier allows a maximum of 1 application."
        return True, ""

    def can_add_database(self) -> tuple[bool, str]:
        """Check if client tier allows provisioning an additional database add-on."""
        current_count = self.addons.count()
        tier = self.tier.lower()
        if tier == "starter" and current_count >= 2:
            return False, "Starter tier allows a maximum of 2 databases. Please upgrade to Growth ($29/mo) for unlimited databases."
        if tier == "free" and current_count >= 1:
            return False, "Free tier allows a maximum of 1 database."
        return True, ""


class BillingInvoice(models.Model):
    """Tracks customer payment invoices from Stripe."""

    client             = models.ForeignKey(ClientAccount, related_name="invoices", on_delete=models.CASCADE)
    stripe_invoice_id  = models.CharField(max_length=100, unique=True)
    amount_paid        = models.DecimalField(max_digits=10, decimal_places=2, default=0.00)
    currency           = models.CharField(max_length=10, default="usd")
    status             = models.CharField(max_length=30, default="paid")
    hosted_invoice_url = models.URLField(blank=True, max_length=500)
    paid_at            = models.DateTimeField(default=timezone.now)
    created_at         = models.DateTimeField(default=timezone.now)

    class Meta:
        ordering = ["-paid_at"]

    def __str__(self) -> str:
        return f"Invoice {self.stripe_invoice_id} - ${self.amount_paid} ({self.client.name})"


class ProjectService(models.Model):
    """Represents an active cloud project or service managed by PyLoom Technologies."""

    SERVICE_TYPE_CHOICES = [
        ("api", "Web API / Microservice"),
        ("worker", "Background Worker / Queue"),
        ("database", "Managed Database / Storage"),
        ("frontend", "Frontend SPA / Edge App"),
    ]

    ENV_CHOICES = [
        ("dev", "Development"),
        ("staging", "Staging"),
        ("prod", "Production"),
    ]

    STATUS_CHOICES = [
        ("healthy", "Healthy"),
        ("deploying", "Deploying / Upgrading"),
        ("degraded", "Degraded Performance"),
        ("stopped", "Stopped / Maintenance"),
    ]

    client       = models.ForeignKey(ClientAccount, related_name="services", on_delete=models.CASCADE)
    name         = models.CharField(max_length=150)
    slug         = models.SlugField(max_length=150)
    service_type = models.CharField(max_length=30, choices=SERVICE_TYPE_CHOICES, default="api")
    environment  = models.CharField(max_length=20, choices=ENV_CHOICES, default="prod")
    status       = models.CharField(max_length=20, choices=STATUS_CHOICES, default="healthy")
    version      = models.CharField(max_length=50, default="1.0.0")
    endpoint_url = models.URLField(blank=True, null=True)
    created_at   = models.DateTimeField(default=timezone.now)
    updated_at   = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]
        unique_together = ["client", "slug"]

    def __str__(self) -> str:
        return f"{self.name} [{self.environment}] - {self.status}"


class DeploymentInquiry(models.Model):
    """Client inquiries and deployment requests submitted through PyLoom platform."""

    INQUIRY_STATUS_CHOICES = [
        ("pending", "Pending Review"),
        ("in_review", "In Review"),
        ("approved", "Approved for Deployment"),
        ("completed", "Deployed & Completed"),
        ("rejected", "Declined"),
    ]

    client_name   = models.CharField(max_length=150)
    contact_email = models.EmailField()
    project_name  = models.CharField(max_length=150)
    service_type  = models.CharField(max_length=50, default="api")
    requirements  = models.TextField()
    status        = models.CharField(max_length=30, choices=INQUIRY_STATUS_CHOICES, default="pending")
    submitted_at  = models.DateTimeField(default=timezone.now)

    class Meta:
        ordering = ["-submitted_at"]

    def __str__(self) -> str:
        return f"Inquiry: {self.project_name} by {self.client_name}"


class Article(models.Model):
    """Retained for backward compatibility with existing tests and reference material."""

    title      = models.CharField(max_length=200)
    body       = models.TextField()
    published  = models.BooleanField(default=False)
    created_at = models.DateTimeField(default=timezone.now)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self) -> str:
        return self.title

    def publish(self) -> None:
        """Mark the article as published and persist only the changed fields."""
        self.published = True
        self.save(update_fields=["published", "updated_at"])


class ServerNode(models.Model):
    """Represents a connected client VPS node (BYOVPS model)."""

    STATUS_CHOICES = [
        ("pending", "Pending Registration"),
        ("provisioning", "Provisioning K3s & GitOps"),
        ("ready", "Ready (Active Cluster Node)"),
        ("failed", "Provisioning Failed"),
        ("offline", "Node Offline"),
    ]

    client                  = models.ForeignKey(ClientAccount, related_name="servers", on_delete=models.CASCADE)
    name                    = models.CharField(max_length=150)
    ip_address              = models.GenericIPAddressField()
    ssh_port                = models.IntegerField(default=22)
    ssh_user                = models.CharField(max_length=50, default="root")
    ssh_auth_type           = models.CharField(max_length=20, default="key")
    ssh_credential          = models.TextField(blank=True, help_text="Encrypted SSH private key or password")
    status                  = models.CharField(max_length=30, choices=STATUS_CHOICES, default="pending")
    k3s_version             = models.CharField(max_length=50, default="v1.30.0+k3s1")
    cpu_cores               = models.IntegerField(default=2)
    ram_mb                  = models.IntegerField(default=4096)
    disk_gb                 = models.IntegerField(default=50)
    cloudflare_tunnel_id    = models.CharField(max_length=100, blank=True)
    cloudflare_tunnel_token = models.TextField(blank=True)
    created_at              = models.DateTimeField(default=timezone.now)
    updated_at              = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self) -> str:
        return f"{self.name} ({self.ip_address}) - {self.status}"


class ApplicationDeployment(models.Model):
    """Represents a dynamic Git-to-Deploy application with automated Blue/Green Rollouts."""

    BUILD_CHOICES = [
        ("dockerfile", "Dockerfile"),
        ("nixpacks", "Nixpacks (Auto-Detect)"),
        ("python", "Python / WSGI / ASGI"),
        ("nodejs", "Node.js / Next.js"),
        ("go", "Golang Static Binary"),
    ]

    STATUS_CHOICES = [
        ("pending", "Pending Deployment"),
        ("building", "Building & Scanning Image"),
        ("deploying", "Deploying Rollout"),
        ("active", "Active (Zero-Downtime)"),
        ("degraded", "Degraded Performance"),
        ("rolled_back", "Rolled Back to Stable"),
    ]

    client                = models.ForeignKey(ClientAccount, related_name="applications", on_delete=models.CASCADE)
    server                = models.ForeignKey(ServerNode, related_name="applications", on_delete=models.SET_NULL, null=True, blank=True)
    name                  = models.CharField(max_length=150)
    slug                  = models.SlugField(max_length=150)
    git_repo_url          = models.URLField()
    git_branch            = models.CharField(max_length=100, default="main")
    build_type            = models.CharField(max_length=30, choices=BUILD_CHOICES, default="dockerfile")
    target_port           = models.IntegerField(default=8000)
    replicas              = models.IntegerField(default=2)
    domain                = models.CharField(max_length=255, blank=True)
    environment_variables = models.JSONField(default=dict, blank=True)
    status                = models.CharField(max_length=30, choices=STATUS_CHOICES, default="pending")
    current_image         = models.CharField(max_length=255, blank=True)
    argo_app_name         = models.CharField(max_length=150, blank=True)
    webhook_secret        = models.CharField(max_length=100, blank=True)
    auto_deploy           = models.BooleanField(default=True)
    latest_commit_sha     = models.CharField(max_length=40, blank=True)
    latest_commit_message = models.CharField(max_length=255, blank=True)
    last_deployed_at      = models.DateTimeField(null=True, blank=True)
    created_at            = models.DateTimeField(default=timezone.now)
    updated_at            = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]
        unique_together = ["client", "slug"]

    def __str__(self) -> str:
        return f"{self.name} [{self.build_type}] - {self.status}"


class DeploymentEvent(models.Model):
    """Tracks continuous delivery Git push events and rollout executions."""

    STATUS_CHOICES = [
        ("queued", "Queued"),
        ("building", "Building & Scanning"),
        ("deployed", "Blue/Green Deployed"),
        ("failed", "Failed / Rolled Back"),
    ]

    application      = models.ForeignKey(ApplicationDeployment, related_name="events", on_delete=models.CASCADE)
    commit_sha       = models.CharField(max_length=40)
    commit_message   = models.CharField(max_length=255, blank=True)
    sender           = models.CharField(max_length=100, default="github")
    status           = models.CharField(max_length=30, choices=STATUS_CHOICES, default="queued")
    rollout_strategy = models.CharField(max_length=30, default="blueGreen")
    created_at       = models.DateTimeField(default=timezone.now)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self) -> str:
        return f"{self.application.name} [{self.commit_sha[:7]}] - {self.status}"


class ManagedAddon(models.Model):
    """Represents a one-click database or cache add-on with automated R2 backups."""

    ADDON_CHOICES = [
        ("postgres", "PostgreSQL 16 High-Performance DB"),
        ("redis", "Redis 7 In-Memory Cache"),
        ("mysql", "MySQL 8 Relational Database"),
        ("clickhouse", "ClickHouse Analytical OLAP DB"),
    ]

    STATUS_CHOICES = [
        ("provisioning", "Provisioning"),
        ("running", "Running & Healthy"),
        ("backup_active", "Running (Backups Active)"),
        ("stopped", "Stopped"),
    ]

    client               = models.ForeignKey(ClientAccount, related_name="addons", on_delete=models.CASCADE)
    server               = models.ForeignKey(ServerNode, related_name="addons", on_delete=models.CASCADE)
    name                 = models.CharField(max_length=150)
    addon_type           = models.CharField(max_length=30, choices=ADDON_CHOICES, default="postgres")
    status               = models.CharField(max_length=30, choices=STATUS_CHOICES, default="provisioning")
    allocated_storage_gb = models.IntegerField(default=10)
    connection_uri       = models.CharField(max_length=500, blank=True)
    r2_backup_enabled    = models.BooleanField(default=True)
    last_backup_at       = models.DateTimeField(null=True, blank=True)
    created_at           = models.DateTimeField(default=timezone.now)
    updated_at           = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self) -> str:
        return f"{self.name} ({self.addon_type}) - {self.status}"

