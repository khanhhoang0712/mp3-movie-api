import io
import logging
from pathlib import Path

import pandas as pd
from fastapi import FastAPI, File, HTTPException, Query, UploadFile

from data_pipeline import create_cleaning_report, process_data, validate_dataframe
from src import (
    MovieCache,
    MovieStorage,
    MovieUploadInfo,
    MovieDataResponse,
    MovieProcessingReport,
)
from src import HealthResponse, ProcessConfig, log_requests, setup_logging
from src.storage import MOVIE_COLUMNS

setup_logging(verbose=True)
logger = logging.getLogger(__name__)

app = FastAPI(title="Data Processing API", version="1.0.0")
app.middleware("http")(log_requests)
storage = MovieStorage()
cache = MovieCache()


@app.get("/health", response_model=HealthResponse)
def health_check():
    """Return the application status and version."""
    return HealthResponse(status="ok", version=app.version)


@app.post("/upload", response_model=MovieUploadInfo)
async def upload_movies(file: UploadFile = File(...)):
    """Read a CSV upload and replace the stored movie collection."""
    # 1. Check the file extension
    suffix = Path(file.filename or "").suffix.lower()
    if suffix != ".csv":
        logger.warning(f"Unsupported file format: {suffix or '(no extension)'}")
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported file format '{suffix}'. Please upload a .csv file.",
        )
    contents = await file.read()
    try:
        df = pd.read_csv(io.BytesIO(contents))
    except pd.errors.EmptyDataError as e:
        logger.warning(f"Empty CSV upload: {file.filename}")
        raise HTTPException(
            status_code=400, detail="The uploaded CSV file is empty."
        ) from e
    except pd.errors.ParserError as e:
        logger.warning(f"Could not parse CSV: {file.filename}")
        raise HTTPException(
            status_code=400,
            detail="Could not parse the CSV. Check that every row has the same number of columns.",
        ) from e
    except UnicodeDecodeError as e:
        logger.warning(f"CSV is not valid UTF-8 text: {file.filename}")
        raise HTTPException(
            status_code=400,
            detail="Could not read the file as text. Save it as a UTF-8 CSV and try again.",
        ) from e

    if sorted(df.columns) != sorted(MOVIE_COLUMNS):
        logger.warning(f"Wrong columns in {file.filename}: {list(df.columns)}")
        raise HTTPException(
            status_code=400,
            detail=f"The CSV must have exactly these columns: {MOVIE_COLUMNS}",
        )
    if df.empty:
        logger.warning(f"No data rows in {file.filename}")
        raise HTTPException(status_code=400, detail="The CSV has no data rows.")
    df = df[MOVIE_COLUMNS]
    storage.save(df)
    logger.info(f"Uploaded movies: filename={file.filename}, rows={len(df)}")

    return MovieUploadInfo(
        filename=file.filename,
        rows=len(df),
        columns=len(df.columns),
        column_names=list(df.columns),
    )


@app.get("/movies", response_model=MovieDataResponse)
def get_movies(limit: int = Query(default=100, ge=1)):
    """Return up to limit movies and the total number stored."""
    cached_response = cache.get(limit)
    if cached_response is not None:
        logger.info(f"Cache hit: returning saved movies for limit={limit}")
        return cached_response

    data = storage.select_columns(MOVIE_COLUMNS, limit)
    total_rows = storage.count_movies()
    response = {"data": data, "total_rows": total_rows}
    cache.set(limit, response)

    logger.info(f"Retrieved movies: returned_rows={len(data)}, total_rows={total_rows}")
    return response


@app.get("/movies/search", response_model=list[dict])
def query_movies(
    columns: list[str] = Query(default=["title"]),
    min_rating: float = Query(default=0, ge=0, le=10),
    limit: int = Query(default=100, ge=1),
):
    """Return movies rated at least min_rating, best-rated first."""
    try:
        results = storage.query_movies(columns, min_rating, limit)
    except ValueError as error:
        raise HTTPException(status_code=400, detail=str(error)) from error

    logger.info(
        f"Queried movies: columns={columns}, min_rating={min_rating}, "
        f"returned_rows={len(results)}"
    )
    return results


@app.post("/movies/process", response_model=MovieProcessingReport)
def process_movies(config: ProcessConfig):
    """Validate and clean the stored movies using MP1 functions."""
    df = storage.get()
    if df.empty:
        logger.warning("No movies to process")
        raise HTTPException(status_code=400, detail="No movies stored. Upload a CSV first.")
    config_dict = config.model_dump()
    required_columns = config_dict["validation"]["required_columns"]
    numeric_columns = config_dict["validation"]["numeric_columns"]

    for col in numeric_columns:
        if col not in df.columns:
            logger.warning(f"Numeric column not found: {col}")
            raise HTTPException(status_code=400, detail=f"Numeric column not found: {col}")

    try:
        validated_df = validate_dataframe(df, required_columns, numeric_columns)
        validation_rows_removed = len(df) - len(validated_df)
        df_before = validated_df.copy()
        processed_df = process_data(validated_df, config_dict)

    except ValueError as error:
        logger.warning(f"Processing failed: {error}")
        raise HTTPException(status_code=400, detail=str(error)) from error
    cleaning_report = create_cleaning_report(df_before, processed_df)

    storage.save(processed_df)

    logger.info(
        f"Processed movies: validation_removed={validation_rows_removed}, "
        f"rows_before={cleaning_report['rows_before']}, "
        f"rows_after={cleaning_report['rows_after']}"
    )
    return {
        "validation_rows_removed": validation_rows_removed,
        "cleaning_report": cleaning_report,
    }