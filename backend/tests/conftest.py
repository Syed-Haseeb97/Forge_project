import pytest
import os
import sys

# Ensure backend directory is in path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

# ISOLATE TESTS: Force a dedicated local SQLite database for pytest so production DB is never touched
os.environ["DATABASE_URL"] = "sqlite+aiosqlite:///./test_fordge_isolated.db"
os.environ["DEV_MODE"] = "true"

from unittest.mock import patch
from fastapi.testclient import TestClient
from main import app
from auth import create_access_token


@pytest.fixture(autouse=True)
def disable_watchdog_in_tests():
    """Prevent continuous watchdog worker loop from holding the event loop open during test runs."""
    with patch("main.start_watchdog_background_task"):
        yield


@pytest.fixture(scope="session")
def client():
    with TestClient(app) as c:
        yield c


@pytest.fixture
def citizen_token():
    return create_access_token(email="citizen@janaawaz.in", role="citizen")


@pytest.fixture
def authority_token():
    return create_access_token(email="commissioner@delhi.gov.in", role="authority")


@pytest.fixture
def citizen_headers(citizen_token):
    return {"Authorization": f"Bearer {citizen_token}"}


@pytest.fixture
def authority_headers(authority_token):
    return {"Authorization": f"Bearer {authority_token}"}
