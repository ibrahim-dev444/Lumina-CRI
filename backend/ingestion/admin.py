from django.contrib import admin

from .models import RawRecord, SourceRecord


@admin.register(SourceRecord)
class SourceRecordAdmin(admin.ModelAdmin):
    list_display = ["source_record_id", "source", "name", "mobile", "email", "dob", "synced_at"]
    list_filter = ["source"]
    search_fields = ["source_record_id", "name", "mobile", "email"]


@admin.register(RawRecord)
class RawRecordAdmin(admin.ModelAdmin):
    list_display = ["source_record_id", "source", "fetched_at"]
    list_filter = ["source"]
    search_fields = ["source_record_id"]
    readonly_fields = ["source", "source_record_id", "payload", "fetched_at"]  # raw data is proof; never edit it
