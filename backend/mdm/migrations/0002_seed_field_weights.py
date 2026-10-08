from decimal import Decimal

from django.db import migrations

# How much each field counts in the trust score (see the Trust Console prototype). Adds up to 1.00.
WEIGHTS = {
    "name": Decimal("0.25"),
    "mobile": Decimal("0.25"),
    "address": Decimal("0.20"),
    "email": Decimal("0.15"),
    "dob": Decimal("0.15"),
}


def add_weights(apps, schema_editor):
    FieldWeight = apps.get_model("mdm", "FieldWeight")
    for field, weight in WEIGHTS.items():
        FieldWeight.objects.update_or_create(field=field, defaults={"weight": weight})


def remove_weights(apps, schema_editor):
    apps.get_model("mdm", "FieldWeight").objects.filter(field__in=WEIGHTS).delete()


class Migration(migrations.Migration):
    dependencies = [
        ("mdm", "0001_initial"),
    ]

    operations = [
        migrations.RunPython(add_weights, remove_weights),
    ]
