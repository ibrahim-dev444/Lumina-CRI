"""Data profiling API: how each column's values look as the bank's systems send them, and the records behind any
check. Every role may use it; contact details are masked for roles that see them masked elsewhere, and identity
numbers are only ever kept masked."""

from collections import Counter

from django.db.models import Q
from rest_framework.decorators import api_view, permission_classes
from rest_framework.response import Response

from accounts.masking import MASKERS, mask
from accounts.roles import can
from ingestion.models import SourceRecord
from ingestion.profiling import CHECKS, EMPTY, LABELS
from sources.models import Source

from .permissions import HasRole

PAGE_SIZES = (10, 50)


def _records(request):
    """Live records (switched-on sources, active rows), optionally from one source."""
    qs = SourceRecord.objects.filter(source__enabled=True, active=True)
    code = request.query_params.get("source", "").strip()
    if code and code != "all":
        qs = qs.filter(source__code=code)
    return qs


def _filters(request):
    """?check=mobile.digits:9 digits&check=name.title:Mrs  Values of one check are alternatives (OR); different
    checks must all hold (AND)."""
    chosen = {}
    for raw in request.query_params.getlist("check"):
        key, _, value = raw.partition(":")
        if key in LABELS and value:
            chosen.setdefault(key, []).append(value)
    return chosen


@api_view(["GET"])
@permission_classes([HasRole])
def summary(request):
    """GET /api/profiling/?source=<code|all>  For every check: each value, how many records and what share."""
    rows = list(_records(request).values_list("profile", flat=True))
    counts = {key: Counter() for key, _, _ in CHECKS}
    for checks in rows:
        for key, value in (checks or {}).items():
            if key in counts:
                counts[key][value] += 1
    checks = []
    for key, column, label in CHECKS:
        found = counts[key]
        total = sum(found.values())
        if not total:
            continue  # no connector in scope maps this column
        values = sorted(found.items(), key=lambda kv: (kv[0] == EMPTY, -kv[1], kv[0]))
        checks.append({
            "key": key, "column": column, "label": label, "records": total,
            "values": [{"value": v, "count": n, "share": round(100 * n / total, 1)} for v, n in values],
        })
    sources = [{"code": s.code, "name": s.name} for s in Source.objects.filter(enabled=True).order_by("name")]
    return Response({"records": len(rows), "checks": checks, "sources": sources,
                     "profiled": sum(1 for r in rows if r)})


@api_view(["GET"])
@permission_classes([HasRole])
def records(request):
    """GET /api/profiling/records/?source=&check=key:value&page=1&page_size=10|50
    The records matching every chosen check: the first 10 by default, or every match 50 at a time."""
    qs = _records(request)
    for key, values in _filters(request).items():
        either = Q()
        for value in values:
            either |= Q(profile__contains={key: value})
        qs = qs.filter(either)
    try:
        size = int(request.query_params.get("page_size", 10))
        page = max(int(request.query_params.get("page", 1)), 1)
    except ValueError:
        size, page = 10, 1
    size = size if size in PAGE_SIZES else 10
    total = qs.count()
    rows = qs.select_related("source", "customer_link").order_by("source__name", "source_record_id")
    rows = rows[(page - 1) * size: page * size]
    pii = can(request.user, "view_pii")
    results = []
    for r in rows:
        values = dict(r.sent_values or {})
        if not pii:
            for field in MASKERS:
                if values.get(field):
                    values[field] = mask(field, values[field])
        link = getattr(r, "customer_link", None)
        results.append({
            "id": r.id, "source_code": r.source.code, "source_name": r.source.name,
            "record_id": r.source_record_id, "values": values, "checks": r.profile,
            "customer": {"id": link.customer_id, "code": f"C-{10000 + link.customer_id}"} if link else None,
        })
    return Response({"count": total, "page": page, "page_size": size, "results": results, "masked": not pii})
