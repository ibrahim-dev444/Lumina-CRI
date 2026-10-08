from django.contrib import admin

from .models import Customer, CustomerLink, FieldWeight, GoldenField, MatchSuggestion
from .services import decide_suggestion


class CustomerLinkInline(admin.TabularInline):
    model = CustomerLink
    fields = ["source_record", "match_reason", "linked_at"]
    readonly_fields = fields
    extra = 0
    can_delete = False


class GoldenFieldInline(admin.TabularInline):
    model = GoldenField
    fields = ["field", "value", "source", "trust", "conflicts"]
    readonly_fields = fields
    extra = 0
    can_delete = False


@admin.register(Customer)
class CustomerAdmin(admin.ModelAdmin):
    list_display = ["code", "golden_name", "trust_score", "record_count", "score_updated_at"]
    inlines = [GoldenFieldInline, CustomerLinkInline]
    readonly_fields = ["trust_score", "score_updated_at"]

    @admin.display(description="Name")
    def golden_name(self, obj):
        field = obj.golden_fields.filter(field="name").first()
        return field.value if field else ""

    @admin.display(description="Records")
    def record_count(self, obj):
        return obj.links.count()


@admin.register(MatchSuggestion)
class MatchSuggestionAdmin(admin.ModelAdmin):
    list_display = ["record_a", "record_b", "points", "reason", "status"]
    list_filter = ["status"]
    readonly_fields = ["record_a", "record_b", "points", "reason", "status", "created_at", "decided_at"]
    actions = ["accept", "reject"]

    @admin.action(description="Accept: same person (merged on next build_customers)")
    def accept(self, request, queryset):
        for s in queryset:
            decide_suggestion(s, accept=True)

    @admin.action(description="Reject: different people")
    def reject(self, request, queryset):
        for s in queryset:
            decide_suggestion(s, accept=False)


@admin.register(FieldWeight)
class FieldWeightAdmin(admin.ModelAdmin):
    list_display = ["field", "weight"]
