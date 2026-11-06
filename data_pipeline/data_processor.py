# data_processor.py
import logging
import pandas as pd

logger = logging.getLogger(__name__)


def remove_duplicates(df):
    """Remove duplicate rows."""
    rows_before = len(df)
    df = df.drop_duplicates()
    rows_after = len(df)
    logger.debug(f"remove_duplicates: {rows_before} -> {rows_after} rows (removed {rows_before - rows_after})")
    return df


def handle_missing(df, axis="rows"):
    """Drop rows or columns containing missing values."""
    if axis == "rows":
        rows_before = len(df)
        df = df.dropna(axis=0)
        rows_after = len(df)
        logger.debug(f"handle_missing: {rows_before} -> {rows_after} rows (removed {rows_before - rows_after})")
    elif axis == "columns":
        cols_before = len(df.columns)
        df = df.dropna(axis=1)
        cols_after = len(df.columns)
        logger.debug(f"handle_missing: {cols_before} -> {cols_after} columns (removed {cols_before - cols_after})")
    else:
        logger.error(f"Unsupported axis: {axis}")
        raise ValueError(f"Unsupported axis: {axis}")
    return df


def remove_outliers(df, columns, method, threshold):
    """Remove outliers from the specified numeric columns."""
    if method not in ("iqr", "zscore"):
        logger.error(f"Unsupported outlier method: {method}")
        raise ValueError(f"Unsupported outlier method: {method}")

    for col in columns:
        if col not in df.columns:
            logger.warning(f"Column not found: {col}")
            continue
        if not pd.api.types.is_numeric_dtype(df[col]):
            logger.warning(f"Column is not numeric: {col}")
            continue

        rows_before = len(df)

        if method == "iqr":
            q1 = df[col].quantile(0.25)
            q3 = df[col].quantile(0.75)
            iqr = q3 - q1
            lower = q1 - threshold * iqr
            upper = q3 + threshold * iqr
        else:
            mean = df[col].mean()
            std = df[col].std()
            lower = mean - threshold * std
            upper = mean + threshold * std

        df = df[df[col].between(lower, upper) | df[col].isna()]

        removed = rows_before - len(df)
        logger.debug(f"{col}: method={method}, threshold={threshold}, removed={removed}")

    return df


def process_data(df, config):
    """Apply the processing steps enabled in the configuration."""
    settings = config["processing"]

    if settings["remove_duplicates"]:
        df = remove_duplicates(df)

    if settings["missing"]["enabled"]:
        df = handle_missing(df, axis=settings["missing"]["axis"])

    if settings["outliers"]["enabled"]:
        df = remove_outliers(
            df,
            columns=settings["outliers"]["columns"],
            method=settings["outliers"]["method"],
            threshold=settings["outliers"]["threshold"],
        )

    return df

def create_cleaning_report(df_before, df_after):
    """Return a dictionary summarizing the cleaning results."""
    rows_before = len(df_before)
    rows_after = len(df_after)
    columns_before = len(df_before.columns)
    columns_after = len(df_after.columns)

    return {
        "rows_before": rows_before,
        "rows_after": rows_after,
        "rows_removed": rows_before - rows_after,
        "columns_before": columns_before,
        "columns_after": columns_after,
        "columns_removed": columns_before - columns_after,
    }