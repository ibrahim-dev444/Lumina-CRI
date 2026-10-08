from decimal import Decimal

from django.db import migrations

# The three Phase 1 sources and their trust levels (see the Trust Console prototype).
SOURCES = [
    ("flexcube", "Oracle FLEXCUBE", "Core banking", Decimal("0.85")),
    ("salesforce", "Salesforce", "CRM", Decimal("0.55")),
    ("branch_csv", "Branch Uploads", "Files", Decimal("0.40")),
]


def add_sources(apps, schema_editor):
    Source = apps.get_model("sources", "Source")
    for code, name, category, trust in SOURCES:
        Source.objects.update_or_create(
            code=code, defaults={"name": name, "category": category, "trust": trust}
        )


def remove_sources(apps, schema_editor):
    Source = apps.get_model("sources", "Source")
    Source.objects.filter(code__in=[s[0] for s in SOURCES]).delete()


class Migration(migrations.Migration):
    dependencies = [
        ("sources", "0001_initial"),
    ]

    operations = [
        migrations.RunPython(add_sources, remove_sources),
    ]
