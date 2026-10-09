from decimal import Decimal

from django.db import migrations

# Field weights from the Lumina prototype. They add up to 1.00. Identity numbers and contact details
# carry the most weight; occupation and income the least.
WEIGHTS = {
    "name": "0.14",
    "father_name": "0.06",
    "dob": "0.10",
    "gender": "0.03",
    "pan": "0.14",
    "aadhaar": "0.10",
    "ckyc": "0.05",
    "mobile": "0.14",
    "email": "0.07",
    "address": "0.09",
    "perm_address": "0.05",
    "occupation": "0.02",
    "income": "0.01",
}
OLD = {"name": "0.25", "mobile": "0.25", "address": "0.20", "email": "0.15", "dob": "0.15"}


def set_weights(apps, schema_editor):
    FieldWeight = apps.get_model("mdm", "FieldWeight")
    assert sum(Decimal(w) for w in WEIGHTS.values()) == Decimal("1.00")
    for field, weight in WEIGHTS.items():
        FieldWeight.objects.update_or_create(field=field, defaults={"weight": Decimal(weight)})


def restore_old_weights(apps, schema_editor):
    FieldWeight = apps.get_model("mdm", "FieldWeight")
    FieldWeight.objects.exclude(field__in=OLD).delete()
    for field, weight in OLD.items():
        FieldWeight.objects.update_or_create(field=field, defaults={"weight": Decimal(weight)})


class Migration(migrations.Migration):
    dependencies = [
        ("mdm", "0004_alter_fieldcorrection_field_alter_fieldweight_field_and_more"),
    ]

    operations = [
        migrations.RunPython(set_weights, restore_old_weights),
    ]
