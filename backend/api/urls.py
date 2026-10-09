from django.urls import include, path
from rest_framework.routers import DefaultRouter

from . import views

router = DefaultRouter()
router.register("sources", views.SourceViewSet, basename="source")
router.register("customers", views.CustomerViewSet, basename="customer")
router.register("suggestions", views.MatchSuggestionViewSet, basename="suggestion")
router.register("audit", views.AuditEventViewSet, basename="audit")
router.register("corrections", views.FieldCorrectionViewSet, basename="correction")

urlpatterns = [
    path("auth/csrf/", views.csrf),
    path("auth/login/", views.login_view),
    path("auth/logout/", views.logout_view),
    path("auth/me/", views.me),
    path("overview/", views.overview),
    path("reference/", views.reference),
    path("", include(router.urls)),
]
