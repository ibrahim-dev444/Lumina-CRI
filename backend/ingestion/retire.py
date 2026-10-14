"""Removing connectors for good: one a bank's admin deletes, or the built-in demo sources (fake FLEXCUBE,
Salesforce export, branch files) when a bank should see only its real systems (DEMO_SOURCES=off).

Runs inside the current organization's schema. Removes the sources, everything read from them, and the
customers that no other system describes (with their conversations and corrections, which described data
that is gone). Customers another system still describes stay, rebuilt from what is left. Safe to run again.
"""

from dataclasses import dataclass

from django.db import transaction

from .connectors.catalog import DEMO_TYPES


@dataclass
class RetireResult:
    sources: int = 0
    records: int = 0
    products: int = 0
    customers_removed: int = 0
    corrections_removed: int = 0
    conversations_removed: int = 0


def demo_sources():
    from sources.models import Source

    return Source.objects.filter(connector_type__in=DEMO_TYPES)


def _only_these_customers(sources):
    """Customers that no other source describes (switched on or off): they go with these sources."""
    from mdm.models import Customer
    from sources.models import Source

    others = Source.objects.exclude(id__in=[s.id for s in sources])
    described = Customer.objects.filter(links__source_record__source__in=others).values("id")
    return Customer.objects.exclude(id__in=described)


def plan(sources=None):
    """What remove_sources() would remove, without changing anything. Default: the demo sources."""
    from ingestion.models import SourceRecord
    from interactions.models import Interaction
    from mdm.models import FieldCorrection
    from products.models import Holding

    sources = list(demo_sources() if sources is None else sources)
    customers = _only_these_customers(sources)
    return RetireResult(
        sources=len(sources),
        records=SourceRecord.objects.filter(source__in=sources).count(),
        products=Holding.objects.filter(source__in=sources).count(),
        customers_removed=customers.count(),
        corrections_removed=FieldCorrection.objects.filter(customer__in=customers).count(),
        conversations_removed=Interaction.objects.filter(customer__in=customers).count(),
    )


@transaction.atomic
def remove_sources(sources):
    """Delete these sources, everything read from them and the customers only they described, then rebuild."""
    from ingestion.models import RawRecord, SourceRecord
    from interactions.models import Interaction
    from mdm.models import Customer, FieldCorrection, GoldenField
    from mdm.services import build_customers

    sources = list(sources)
    result = plan(sources)
    if not sources:
        return result
    customers = list(_only_these_customers(sources).values_list("id", flat=True))

    GoldenField.objects.filter(source__in=sources).delete()  # rebuilt below from the remaining sources
    SourceRecord.objects.filter(source__in=sources).delete()  # their customer links and match suggestions go too
    RawRecord.objects.filter(source__in=sources).delete()
    for source in sources:
        source.delete()  # products, sync history, uploads and stored secrets go with it

    FieldCorrection.objects.filter(customer_id__in=customers).delete()
    Interaction.objects.filter(customer_id__in=customers).delete()
    Customer.objects.filter(id__in=customers).delete()

    build_customers()
    return result


def remove_demo_sources():
    """The hosted demo's start-up: remove the built-in demo sources if any are left."""
    return remove_sources(demo_sources())
