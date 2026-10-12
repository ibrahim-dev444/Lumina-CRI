"""Addresses outside any organization: no /t/<org>/ prefix. Runs in the shared "public" schema."""

from django.contrib import admin
from django.urls import path

from tenants import views

urlpatterns = [
    path('admin/', admin.site.urls),
    path('api/health/', views.health),
    path('api/organizations/<slug:code>/', views.organization),
]
