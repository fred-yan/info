import os
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "django_api.settings")

import django
django.setup()

from unittest.mock import patch

import pytest
from django.test import Client
from django.urls import resolve

from parser_api.views import economist_view


# ---------------------------------------------------------------------------
# Task 5.2 — URL routing
# ---------------------------------------------------------------------------

def test_economist_url_resolves_to_economist_view():
    """Verify /economist/ resolves to economist_view."""
    match = resolve("/economist/")
    assert match.func == economist_view


# ---------------------------------------------------------------------------
# Task 5.3 — parse() raises exception → 500
# ---------------------------------------------------------------------------

def test_parse_exception_returns_500():
    """When parse() raises RuntimeError, the view must return HTTP 500 with JSON."""
    client = Client()
    with patch("parser_api.views.parse", side_effect=RuntimeError("test error")):
        response = client.get("/economist/")

    assert response.status_code == 500
    assert "application/json" in response["Content-Type"]


# ---------------------------------------------------------------------------
# Task 5.4 — Non-GET methods return 405
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("method", ["post", "put", "delete"])
def test_non_get_methods_return_405(method):
    """POST, PUT, DELETE to /economist/ must return HTTP 405."""
    client = Client()
    response = getattr(client, method)("/economist/")
    assert response.status_code == 405
