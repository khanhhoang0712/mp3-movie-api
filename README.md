This project is a FastAPI REST API for uploading, storing, cleaning, and retrieving a collection of movies. `POST /upload` accepts a CSV with the columns title, release_year, rating, and genre, and replaces the stored collection with it. The movies are saved in a SQLite database (`data/movies.db`) through the `MovieStorage` class in `src/storage.py`, so the data survives server restarts. `GET /movies` returns up to `limit` movies with the total count, and `GET /movies/search` filters and sorts movies with SQL. `POST /movies/process` validates and cleans the stored movies using my reusable MP1 modules in `data_pipeline/` (duplicate removal, missing-value handling, and outlier removal), then saves the cleaned result. Responses from `GET /movies` are cached for 90 seconds by the `MovieCache` class in `src/cache.py`, which uses FakeRedis, and the cache is cleared after every successful upload or processing so it never returns outdated data. A logging middleware gives each request an ID and logs its status and duration.

## How to run

Install the packages:

```
python -m pip install -r requirements.txt
```

Start the API, then open http://127.0.0.1:8000/docs:

```
python -m uvicorn main:app --reload
```

Run the tests:

```
python -m pytest tests -v
```

## Sample processing request

After uploading `fixtures/sample_movies.csv`, send this body to `POST /movies/process`:

```json
{
  "validation": {
    "required_columns": ["title", "release_year", "rating", "genre"],
    "numeric_columns": ["release_year", "rating"]
  },
  "processing": {
    "remove_duplicates": true,
    "missing": {"enabled": true, "axis": "rows"},
    "outliers": {"enabled": true, "columns": ["rating"], "method": "iqr", "threshold": 1.5}
  }
}
```