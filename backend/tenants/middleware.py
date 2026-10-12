from django.http import JsonResponse

from .models import Tenant


class SuspendedOrganizationMiddleware:
    """When the platform team suspends an organization, every request to it (/t/<code>/...) is refused,
    including for people who are already signed in. Runs right after the middleware that picks the tenant."""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        tenant = getattr(request, "tenant", None)
        if tenant is not None and tenant.schema_name != "public" and tenant.status != Tenant.ACTIVE:
            return JsonResponse(
                {"detail": "This organization's access is paused. Contact your administrator."}, status=403
            )
        return self.get_response(request)
