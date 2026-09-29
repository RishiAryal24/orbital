from django.contrib import admin
from django.urls import path, include

from .views import (
    ArticleDetailView,
    ArticleListView,
    ClientAccountDetailView,
    ClientAccountListView,
    DeploymentInquiryListView,
    HealthCheckView,
    HomeView,
    PlatformStatusView,
    ProjectServiceDetailView,
    ProjectServiceListView,
    ServerNodeListView,
    ServerNodeDetailView,
    ServerBootstrapScriptView,
    ApplicationDeploymentListView,
    ApplicationDeploymentDetailView,
    ManagedAddonListView,
    GitHubWebhookView,
    ApplicationEventsListView,
    LanguageDetectionView,
)

urlpatterns = [
    path("admin/", admin.site.urls),
    path("health/", HealthCheckView.as_view(), name="health-check"),
    path("", HomeView.as_view(), name="home"),
    path("dashboard/", HomeView.as_view(), name="dashboard"),
    # PyLoom Core Platform APIs
    path("api/status/", PlatformStatusView.as_view(), name="platform-status"),
    path("api/clients/", ClientAccountListView.as_view(), name="client-list"),
    path("api/clients/<int:pk>/", ClientAccountDetailView.as_view(), name="client-detail"),
    path("api/services/", ProjectServiceListView.as_view(), name="service-list"),
    path("api/services/<int:pk>/", ProjectServiceDetailView.as_view(), name="service-detail"),
    path("api/inquiries/", DeploymentInquiryListView.as_view(), name="inquiry-list"),
    # PaaS BYOVPS Endpoints
    path("api/servers/", ServerNodeListView.as_view(), name="server-list"),
    path("api/servers/<int:pk>/", ServerNodeDetailView.as_view(), name="server-detail"),
    path("api/servers/<int:pk>/bootstrap.sh", ServerBootstrapScriptView.as_view(), name="server-bootstrap"),
    path("api/apps/", ApplicationDeploymentListView.as_view(), name="app-list"),
    path("api/apps/detect/", LanguageDetectionView.as_view(), name="app-detect"),
    path("api/apps/<int:pk>/", ApplicationDeploymentDetailView.as_view(), name="app-detail"),
    path("api/apps/<int:pk>/events/", ApplicationEventsListView.as_view(), name="app-events"),
    path("api/addons/", ManagedAddonListView.as_view(), name="addon-list"),
    # Push-to-Deploy GitHub Webhook
    path("api/webhooks/github/<str:slug>/", GitHubWebhookView.as_view(), name="github-webhook"),
    # Backward compatibility endpoints
    path("api/articles/", ArticleListView.as_view(), name="article-list"),
    path("api/articles/<int:pk>/", ArticleDetailView.as_view(), name="article-detail"),
]

try:
    import django_prometheus
    urlpatterns.insert(1, path("", include("django_prometheus.urls")))
except ImportError:
    pass
