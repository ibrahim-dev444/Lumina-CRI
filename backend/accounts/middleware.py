class IdleTimeoutMiddleware:
    """Sign people out after SESSION_COOKIE_AGE (30 minutes) without activity.

    Each request from a signed-in person marks their session as changed, so it is saved with a fresh expiry.
    Anonymous requests are left alone on purpose: with Django's SESSION_SAVE_EVERY_REQUEST, a request to a public
    address (for example the organization look-up, which runs in the shared schema where a bank's session does
    not exist) would save an empty session and replace the bank's session cookie, signing the person out.
    """

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        response = self.get_response(request)
        user = getattr(request, "user", None)
        if user is not None and user.is_authenticated and hasattr(request, "session"):
            request.session.modified = True
        return response
