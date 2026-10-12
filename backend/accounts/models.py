from django.conf import settings
from django.db import models


class AccountProfile(models.Model):
    """Lumina's extra facts about a login. Lives in each organization's schema, like the login itself."""

    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="lumina_profile")
    # Set when an administrator creates the account or resets its password: the person must choose their own
    # password before they can do anything else.
    must_change_password = models.BooleanField(default=False)
    created_by = models.CharField(max_length=150, blank=True)

    def __str__(self):
        return f"profile of {self.user}"


def must_change_password(user):
    profile = getattr(user, "lumina_profile", None) if user and user.is_authenticated else None
    return bool(profile and profile.must_change_password)
