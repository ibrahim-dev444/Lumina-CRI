"""Remove the built-in demo sources (fake FLEXCUBE, Salesforce export, branch files) from one organization.

Used when a bank should see only its real systems (the hosted demo sets DEMO_SOURCES=off). Runs inside the
current organization's schema. Safe to run again: with nothing left to remove it changes nothing.
"""

from dataclasses import dataclass

from django.db import transaction

from .connectors.catalog import DEMO_TYPES


@dataclass
class RetireResult:
    sources: int = 0
    records: int = 0
    customers_removed: int = 0
    corrections_removed: int = 0


def demo_sources():
    from sources.models import Source

    return Source.objects.filter(connector_type__in=DEMO_TYPES)


def _only_demo_customers():
    """Customers that no other source describes: they disappear with the demo sources."""
    from mdm.models import Customer

    described = Customer.objects.filter(links__source_record__source__in=_other_sources()).values("id")
    return Customer.objects.exclude(id__in=described)


def _other_sources():
    from sources.models import Source

    return Source.objects.exclude(connector_type__in=DEMO_TYPES)


def plan():
    """What remove_demo_sources() would remove, without changing anything."""
    from ingestion.models import SourceRecord
    from mdm.models import FieldCorrection

    sources = demo_sources()
    customers = _only_demo_customers()
    return RetireResult(
        sources=sources.count(),
        records=SourceRecord.objects.filter(source__in=sources).count(),
        customers_removed=customers.count(),
        corrections_removed=FieldCorrection.objects.filter(customer__in=customers).count(),
    )


@transaction.atomic
def remove_demo_sources():
    """Delete the demo sources, their records and the customers that only they described, then rebuild."""
    from ingestion.models import RawRecord, SourceRecord
    from mdm.models import FieldCorrection, GoldenField
    from mdm.services import build_customers

    result = plan()
    if not result.sources:
        return result
    sources = list(demo_sources())
    customers = list(_only_demo_customers().values_list("id", flat=True))

    GoldenField.objects.filter(source__in=sources).delete()  # rebuilt below from the remaining sources
    SourceRecord.objects.filter(source__in=sources).delete()  # their customer links and match suggestions go too
    RawRecord.objects.filter(source__in=sources).delete()
    for source in sources:
        source.delete()  # sync history and uploads go with it

    # Corrections to customers that no longer exist described data that is gone too.
    from mdm.models import Customer

    from interactions.models import Interaction

    FieldCorrection.objects.filter(customer_id__in=customers).delete()
    Interaction.objects.filter(customer_id__in=customers).delete()
    Customer.objects.filter(id__in=customers).delete()

    build_customers()
    return result
