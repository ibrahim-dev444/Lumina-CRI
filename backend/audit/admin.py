from django.contrib import admin

from .models import AuditEvent


@admin.register(AuditEvent)
class AuditEventAdmin(admin.ModelAdmin):
    list_display = ["at", "actor_name", "role", "action", "target", "ip"]
    list_filter = ["action", "role"]
    search_fields = ["actor_name", "target"]

    # Read-only everywhere: the audit trail is evidence.
    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False
