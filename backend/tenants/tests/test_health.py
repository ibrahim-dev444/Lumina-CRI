"""The health check must not touch the database: it is called every few minutes, and a free database that is
woken that often never sleeps and runs out of its monthly compute hours."""

from rest_framework.test import APIClient


def test_health_answers_without_any_database_query(db, django_assert_num_queries):
    with django_assert_num_queries(0):
        response = APIClient().get("/api/health/")
    assert response.status_code == 200 and response.json() == {"status": "ok"}
