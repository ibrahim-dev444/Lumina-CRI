from django.urls import include, path
from rest_framework.routers import DefaultRouter

from . import admin_views, connector_views, ingest_views, views

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
    path("connectors/catalog/", connector_views.catalog),
    path("connectors/", connector_views.create_connector),
    path("connectors/<slug:code>/", connector_views.update_connector),
    path("connectors/<slug:code>/test/", connector_views.test_connector),
    path("connectors/<slug:code>/discover/", connector_views.discover),
    path("connectors/<slug:code>/mapping/", connector_views.save_mapping),
    path("connectors/<slug:code>/accounts-mapping/", connector_views.save_accounts_mapping),
    path("connectors/<slug:code>/upload/", connector_views.upload_file),
    path("connectors/<slug:code>/runs/", connector_views.sync_runs),
    path("connectors/<slug:code>/api-key/", connector_views.create_api_key),
    # Push API: a bank system sends records with its connector's API key (no sign-in session).
    path("ingest/<slug:code>/", ingest_views.ingest),
    path("overview/", views.overview),
    path("reference/", views.reference),
    path("compliance/", views.compliance_queue),
    path("", include(router.urls)),
]
