from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from main import app, storage
from src.database import initialize_database


@pytest.fixture
def client(tmp_path):
    # Give every test its own new, empty database in a temporary folder,
    # so the tests never change the real data/movies.db
    storage.db_path = str(tmp_path / "test_movies.db")
    initialize_database(storage.db_path)

    with TestClient(app) as test_client:
        yield test_client


@pytest.fixture
def sample_csv_bytes():
    filepath = Path("fixtures") / "sample_movies.csv"
    return filepath.read_bytes()


@pytest.fixture
def uploaded_movies(client, sample_csv_bytes):
    response = client.post(
        "/upload",
        files={"file": ("sample_movies.csv", sample_csv_bytes, "text/csv")},
    )
    assert response.status_code == 200
    return response.json()


@pytest.fixture
def processing_body():
    return {
        "validation": {
            "required_columns": ["title", "release_year", "rating", "genre"],
            "numeric_columns": ["release_year", "rating"],
        },
        "processing": {
            "remove_duplicates": True,
            "missing": {"enabled": True, "axis": "rows"},
            "outliers": {"enabled": False, "columns": [], "method": "iqr", "threshold": 1.5},
        },
    }