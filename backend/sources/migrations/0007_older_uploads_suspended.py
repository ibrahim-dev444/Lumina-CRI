from django.db import migrations


def keep_only_newest_active(apps, schema_editor):
    """Until now a sync read only the newest file. Older files start suspended so nothing changes on upgrade."""
    UploadedFile = apps.get_model("sources", "UploadedFile")
    newest = {}
    for f in UploadedFile.objects.order_by("source_id", "-uploaded_at", "-id"):
        if f.source_id in newest:
            f.status = "suspended"
            f.save(update_fields=["status"])
        else:
            newest[f.source_id] = f.id


class Migration(migrations.Migration):
    dependencies = [("sources", "0006_uploadedfile_status")]
    operations = [migrations.RunPython(keep_only_newest_active, migrations.RunPython.noop)]
