from django.db import migrations

# The three demo sources keep their hand-written connectors; give them a connector type so the catalog
# and the connectors page can describe them.
DEMO_TYPES = {"flexcube": "demo_core_banking", "salesforce": "demo_salesforce", "branch_csv": "demo_branch_files"}


def label_demo_sources(apps, schema_editor):
    Source = apps.get_model("sources", "Source")
    for code, connector_type in DEMO_TYPES.items():
        Source.objects.filter(code=code, connector_type="").update(connector_type=connector_type)


class Migration(migrations.Migration):
    dependencies = [("sources", "0003_connector_engine")]

    operations = [migrations.RunPython(label_demo_sources, migrations.RunPython.noop)]
