from django.contrib import admin

from .models import Source


@admin.register(Source)
class SourceAdmin(admin.ModelAdmin):
    list_display = ["name", "code", "category", "trust", "enabled", "last_synced_at"]
    list_filter = ["category", "enabled"]
