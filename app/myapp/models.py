from django.db import models
from django.utils import timezone


class ClientAccount(models.Model):
    """Represents a PyLoom Technologies client or organization."""

    TIER_CHOICES = [
        ("free", "Free Evaluation"),
        ("starter", "Starter Tier"),
        ("pro", "Professional Tier"),
        ("enterprise", "Enterprise Cloud"),
    ]

    name          = models.CharField(max_length=150)
    slug          = models.SlugField(max_length=150, unique=True)
    contact_email = models.EmailField()
    tier          = models.CharField(max_length=30, choices=TIER_CHOICES, default="starter")
    is_active     = models.BooleanField(default=True)
    created_at    = models.DateTimeField(default=timezone.now)
    updated_at    = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self) -> str:
        return f"{self.name} ({self.tier})"


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
