from django.urls import include, path
from rest_framework.routers import DefaultRouter

from . import admin_views, views

router = DefaultRouter()
router.register("sources", views.SourceViewSet, basename="source")
router.register("customers", views.CustomerViewSet, basename="customer")
router.register("suggestions", views.MatchSuggestionViewSet, basename="suggestion")
router.register("audit", views.AuditEventViewSet, basename="audit")
router.register("corrections", views.FieldCorrectionViewSet, basename="correction")
router.register("users", admin_views.UserViewSet, basename="user")

urlpatterns = [
    path("auth/csrf/", views.csrf),
    path("auth/login/", views.login_view),
    path("auth/logout/", views.logout_view),
    path("auth/me/", views.me),
    path("auth/change-password/", admin_views.change_password),
    path("settings/trust/", admin_views.trust_settings),
    path("settings/logo/", admin_views.organization_logo),
    path("overview/", views.overview),
    path("reference/", views.reference),
    path("compliance/", views.compliance_queue),
    path("", include(router.urls)),
]
