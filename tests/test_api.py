from pathlib import Path

import pandas as pd
import pytest

import main
from src import MovieStorage

def test_upload_csv(client, sample_csv_bytes):
    response = client.post(
        "/upload",
        files={"file": ("sample_movies.csv", sample_csv_bytes, "text/csv")},
    )
    assert response.status_code == 200
    assert response.json() == {
        "filename": "sample_movies.csv",
        "rows": 20,
        "columns": 4,
        "column_names": ["title", "release_year", "rating", "genre"],
    }


def test_get_movies_with_limit(client, uploaded_movies):
    response = client.get("/movies?limit=2")
    assert response.status_code == 200
    assert response.json() == {
        "data": [
            {"id": 1, "title": "Movie A", "release_year": 2020, "rating": 8.0, "genre": "Drama"},
            {"id": 2, "title": "Movie B", "release_year": 2021, "rating": 8.5, "genre": "Comedy"},
        ],
        "total_rows": 20,
    }


def test_get_movies_when_empty(client):
    response = client.get("/movies")
    assert response.status_code == 200
    assert response.json() == {"data": [], "total_rows": 0}


def test_search_movies(client, uploaded_movies):
    response = client.get("/movies/search?min_rating=8.5&limit=2")
    assert response.status_code == 200
    assert response.json() == [
        {"id": 4, "title": "Movie C"},
        {"id": 2, "title": "Movie B"},
    ]

    response = client.get("/movies/search?columns=title&columns=rating&min_rating=8.5&limit=2")
    assert response.status_code == 200
    assert response.json() == [
        {"id": 4, "title": "Movie C", "rating": 9.0},
        {"id": 2, "title": "Movie B", "rating": 8.5},
    ]


def test_search_unsupported_column(client, uploaded_movies):
    response = client.get("/movies/search?columns=budget")
    assert response.status_code == 400


def test_upload_again_replaces_collection(client, uploaded_movies, sample_csv_bytes):
    client.post(
        "/upload",
        files={"file": ("sample_movies.csv", sample_csv_bytes, "text/csv")},
    )
    response = client.get("/movies")
    assert response.json()["total_rows"] == 20


def test_unsupported_file_extension(client):
    response = client.post(
        "/upload",
        files={"file": ("movies.txt", b"hello", "text/plain")},
    )
    assert response.status_code == 400
    response = client.get("/health")
    assert response.status_code == 200


def test_process_movies(client, uploaded_movies, processing_body):
    response = client.post("/movies/process", json=processing_body)
    assert response.status_code == 200

    rows_after = response.json()["cleaning_report"]["rows_after"]
    response = client.get("/movies")
    assert response.json()["total_rows"] == rows_after

def test_movies_persist(client, test_storage, uploaded_movies):
    second_storage = MovieStorage(test_storage.db_path)
    df = second_storage.get()
    assert len(df) == 20
    assert second_storage.count_movies() == 20
    assert list(df.columns) == ["title", "release_year", "rating", "genre"]
    original = pd.read_csv(Path("fixtures") / "sample_movies.csv")
    assert list(df["title"]) == list(original["title"])
    db_rows = second_storage.select_columns(["title"], 100)
    db_ids = [row["id"] for row in db_rows]

    response = client.get("/movies?limit=100")
    assert response.status_code == 200
    api_ids = [row["id"] for row in response.json()["data"]]

    assert db_ids == list(range(1, 21))
    assert api_ids == list(range(1, 21))


def test_cache_and_processing(client, uploaded_movies, processing_body):
    response_100 = client.get("/movies?limit=100")
    assert response_100.status_code == 200
    assert main.cache.get(100) == response_100.json()

    response_1 = client.get("/movies?limit=1")
    assert response_1.status_code == 200
    assert main.cache.get(1) == response_1.json()

    repeat = client.get("/movies?limit=100")
    assert repeat.status_code == 200
    assert repeat.json() == response_100.json()

    response = client.post("/movies/process", json=processing_body)
    assert response.status_code == 200
    report = response.json()
    assert report["validation_rows_removed"] == 0
    assert report["cleaning_report"]["rows_before"] == 20
    assert report["cleaning_report"]["rows_after"] == 16
    assert main.cache.get(100) is None
    assert main.cache.get(1) is None

    response = client.get("/movies?limit=100")
    body = response.json()
    assert body["total_rows"] == 16

    titles = [row["title"] for row in body["data"]]
    expected_titles = [
        "Movie A", "Movie B", "Movie C", "Movie D", "Movie E", "Movie F", "Movie G", "Movie H",
        "Movie I", "Movie J", "Movie K", "Movie L", "Movie M", "Movie N", "Movie O", "Movie P",
    ]
    assert titles == expected_titles

    ids = [row["id"] for row in body["data"]]
    assert ids == list(range(1, 17))

    assert main.cache.get(100) == body


def test_cache_hit_skips_database(client, uploaded_movies, monkeypatch):
    first = client.get("/movies?limit=100")
    assert first.status_code == 200

    def fail_if_called(*args, **kwargs):
        pytest.fail("The database was used, but the answer should come from the cache")
    monkeypatch.setattr(main.storage, "select_columns", fail_if_called)
    monkeypatch.setattr(main.storage, "count_movies", fail_if_called)
    second = client.get("/movies?limit=100")
    assert second.status_code == 200
    assert second.json() == first.json()