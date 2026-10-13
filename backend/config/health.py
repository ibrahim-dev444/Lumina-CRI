"""The health check answers before any other middleware runs.

The hosting platform and the keep-awake ping call it every few minutes. Going through the tenant middleware
would look up the organization in the database each time, so the free Neon database could never sleep and would
use up its monthly compute hours. Answering here touches no database at all.
"""

from django.http import JsonResponse

HEALTH_PATH = "/api/health/"


class HealthCheckMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if request.path == HEALTH_PATH and request.method in ("GET", "HEAD"):
            return JsonResponse({"status": "ok"})
        return self.get_response(request)
