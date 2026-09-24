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
)

urlpatterns = [
    path("admin/", admin.site.urls),
    path("health/", HealthCheckView.as_view(), name="health-check"),
    path("", HomeView.as_view(), name="home"),
    # PyLoom Core Platform APIs
    path("api/status/", PlatformStatusView.as_view(), name="platform-status"),
    path("api/clients/", ClientAccountListView.as_view(), name="client-list"),
    path("api/clients/<int:pk>/", ClientAccountDetailView.as_view(), name="client-detail"),
    path("api/services/", ProjectServiceListView.as_view(), name="service-list"),
    path("api/services/<int:pk>/", ProjectServiceDetailView.as_view(), name="service-detail"),
    path("api/inquiries/", DeploymentInquiryListView.as_view(), name="inquiry-list"),
    # Backward compatibility endpoints
    path("api/articles/", ArticleListView.as_view(), name="article-list"),
    path("api/articles/<int:pk>/", ArticleDetailView.as_view(), name="article-detail"),
]

try:
    import django_prometheus
    urlpatterns.insert(1, path("", include("django_prometheus.urls")))
except ImportError:
    pass
