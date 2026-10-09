from django.conf import settings
from django.db import models


class AuditEvent(models.Model):
    """One thing someone did in Lumina. Append-only: rows are never edited or deleted from the app.

    Banks must be able to show who looked at or changed customer data, and when.
    """

    LOGIN = "login"
    LOGIN_FAILED = "login_failed"
    LOGOUT = "logout"
    VIEW_CUSTOMER = "view_customer"
    EXPORT = "export"
    SYNC_SOURCE = "sync_source"
    UPDATE_SOURCE = "update_source"
    MERGE = "merge"
    KEEP_APART = "keep_apart"
    DENIED = "denied"
    CORRECTION_PROPOSED = "corr_proposed"
    CORRECTION_APPROVED = "corr_approved"
    CORRECTION_REJECTED = "corr_rejected"
    REVEAL = "reveal"

    ACTION_CHOICES = [
        (LOGIN, "Signed in"),
        (LOGIN_FAILED, "Sign-in failed"),
        (LOGOUT, "Signed out"),
        (VIEW_CUSTOMER, "Viewed customer"),
        (EXPORT, "Exported customers"),
        (SYNC_SOURCE, "Synced source"),
        (UPDATE_SOURCE, "Changed source"),
        (MERGE, "Merged records"),
        (KEEP_APART, "Kept records apart"),
        (DENIED, "Access denied"),
        (CORRECTION_PROPOSED, "Proposed correction"),
        (CORRECTION_APPROVED, "Approved correction"),
        (CORRECTION_REJECTED, "Rejected correction"),
        (REVEAL, "Revealed identity number"),
    ]

    at = models.DateTimeField(auto_now_add=True, db_index=True)
    actor = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL)
    actor_name = models.CharField(max_length=150)  # kept even if the user is deleted later
    role = models.CharField(max_length=40, blank=True)
    action = models.CharField(max_length=20, choices=ACTION_CHOICES, db_index=True)
    target = models.CharField(max_length=100, blank=True)  # e.g. "C-10001" or "source flexcube"
    detail = models.JSONField(default=dict, blank=True)
    ip = models.GenericIPAddressField(null=True, blank=True)

    class Meta:
        ordering = ["-at", "-id"]

    def save(self, *args, **kwargs):
        if self.pk is not None:
            raise ValueError("Audit events cannot be changed.")
        super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        raise ValueError("Audit events cannot be deleted.")

    def __str__(self):
        return f"{self.at:%Y-%m-%d %H:%M} {self.actor_name} {self.action} {self.target}"
