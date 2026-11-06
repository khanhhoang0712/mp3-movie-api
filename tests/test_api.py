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