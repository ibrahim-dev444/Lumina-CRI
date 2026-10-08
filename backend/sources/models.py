from django.db import models


class Source(models.Model):
    """One bank system that Lumina reads customer data from (FLEXCUBE, Salesforce, ...)."""

    code = models.SlugField(unique=True)  # "flexcube"
    name = models.CharField(max_length=100)  # "Oracle FLEXCUBE"
    category = models.CharField(max_length=50)  # "Core banking"
    trust = models.DecimalField(max_digits=3, decimal_places=2)  # 0.85
    enabled = models.BooleanField(default=True)
    last_synced_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-trust", "name"]

    def __str__(self):
        return f"{self.name} ({self.trust})"
