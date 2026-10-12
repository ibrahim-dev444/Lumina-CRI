from django.db import models


class Source(models.Model):
    """One bank system that Lumina reads customer data from (FLEXCUBE, Salesforce, a PostgreSQL database...).

    A source is one connector instance: its type (from the catalog), how to reach it, the encrypted
    password or token, and which of its columns feed which Lumina field.
    """

    code = models.SlugField(unique=True)  # "flexcube"
    name = models.CharField(max_length=100)  # "Oracle FLEXCUBE"
    category = models.CharField(max_length=50)  # "Core banking"
    trust = models.DecimalField(max_digits=3, decimal_places=2)  # 0.85
    enabled = models.BooleanField(default=True)
    last_synced_at = models.DateTimeField(null=True, blank=True)

    # Connector type from ingestion.connectors.catalog, e.g. "postgresql". The demo sources use demo_* types.
    connector_type = models.CharField(max_length=40, blank=True)
    # How to reach the system, without secrets: host, port, database, table, ...
    config = models.JSONField(default=dict, blank=True)
    # Password, token or connection string: encrypted JSON. Never sent back to the browser.
    secret = models.TextField(blank=True)
    # What to read: {"object": "public.customers", "id_column": "cust_id", "updated_column": "updated_at",
    #                "fields": {"name": "cust_name", "mobile": "mob_no", ...}}
    mapping = models.JSONField(default=dict, blank=True)

    class Meta:
        ordering = ["-trust", "name"]

    def __str__(self):
        return f"{self.name} ({self.trust})"


class SyncRun(models.Model):
    """One attempt to read a source: when, what happened, how many rows. Shown as the sync history."""

    OK = "ok"
    FAILED = "failed"

    source = models.ForeignKey(Source, on_delete=models.CASCADE, related_name="runs")
    started_at = models.DateTimeField(auto_now_add=True)
    finished_at = models.DateTimeField(null=True, blank=True)
    status = models.CharField(max_length=10, choices=[(OK, "Succeeded"), (FAILED, "Failed")])
    fetched = models.PositiveIntegerField(default=0)
    created = models.PositiveIntegerField(default=0)
    updated = models.PositiveIntegerField(default=0)
    error = models.CharField(max_length=500, blank=True)
    started_by = models.CharField(max_length=150, blank=True)

    class Meta:
        ordering = ["-started_at", "-id"]


class UploadedFile(models.Model):
    """A CSV file uploaded to a file-upload connector. The newest one is what the next sync reads."""

    source = models.ForeignKey(Source, on_delete=models.CASCADE, related_name="uploads")
    name = models.CharField(max_length=200)
    content = models.TextField()
    rows = models.PositiveIntegerField(default=0)
    uploaded_at = models.DateTimeField(auto_now_add=True)
    uploaded_by = models.CharField(max_length=150, blank=True)

    class Meta:
        ordering = ["-uploaded_at", "-id"]
