from rest_framework.decorators import api_view, authentication_classes, permission_classes
from rest_framework.permissions import AllowAny
from rest_framework.response import Response

from .models import Domain, Tenant


@api_view(["GET"])
@authentication_classes([])
@permission_classes([AllowAny])
def health(request):
    """GET /api/health/  Used by the hosting platform and the keep-awake ping. Touches no tenant data."""
    return Response({"status": "ok"})


@api_view(["GET"])
@authentication_classes([])
@permission_classes([AllowAny])
def organization(request, code):
    """GET /api/organizations/<code>/  Public: the sign-in page asks whether an organization code exists and
    how to brand its sign-in screen. Answers one code at a time; there is no way to list organizations."""
    domain = Domain.objects.select_related("tenant").filter(domain=code.lower()).first()
    tenant = domain.tenant if domain else None
    if tenant is None or tenant.schema_name == "public":
        return Response({"detail": "No organization with that code."}, status=404)
    if tenant.status != Tenant.ACTIVE:
        return Response({"detail": "This organization's access is paused. Contact your administrator."}, status=403)
    return Response(
        {"code": domain.domain, "name": tenant.name, "brand_color": tenant.brand_color, "logo": safe_logo(tenant.logo)}
    )


def safe_logo(value):
    """Only image addresses the browser shows as a picture: https:// links or data:image/ URLs.
    Anything else (for example raw SVG markup that could carry scripts) is dropped."""
    value = (value or "").strip()
    return value if value.startswith(("https://", "data:image/")) else ""
