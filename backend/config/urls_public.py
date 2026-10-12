"""Addresses outside any organization: no /t/<org>/ prefix. Runs in the shared "public" schema."""

from django.contrib import admin
from django.urls import path

from tenants import platform_views, scheduler_views, views

urlpatterns = [
    path('admin/', admin.site.urls),
    path('api/health/', views.health),
    path('api/organizations/<slug:code>/', views.organization),
    # Platform console (super admin): organizations, their health, the platform activity log.
    path('api/platform/auth/csrf/', platform_views.csrf),
    path('api/platform/auth/login/', platform_views.platform_login),
    path('api/platform/auth/logout/', platform_views.platform_logout),
    path('api/platform/auth/me/', platform_views.platform_me),
    path('api/platform/organizations/', platform_views.organization_list),
    path('api/platform/organizations/<slug:code>/', platform_views.organization_detail),
    path('api/platform/events/', platform_views.platform_events),
    # Hourly scheduled syncs, protected by SYNC_RUNNER_TOKEN.
    path('api/internal/run-due-syncs/', scheduler_views.run_scheduled_syncs),
]
