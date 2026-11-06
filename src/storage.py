import logging
import sqlite3

import pandas as pd

from .database import get_connection, initialize_database

logger = logging.getLogger(__name__)
MOVIE_COLUMNS = ["title", "release_year", "rating", "genre"]


class MovieStorage:
    def __init__(self, db_path="data/movies.db"):
        self.db_path = db_path
        initialize_database(self.db_path)

    def save(self, df):
        """Replace all movie rows in one transaction."""
        df = df.reindex(columns=MOVIE_COLUMNS)
        df = df.astype(object)
        df = df.where(df.notna(), None)
        rows = df.values.tolist()

        connection = get_connection(self.db_path)
        try:
            connection.execute("DELETE FROM movies")

            for row in rows:
                connection.execute(
                    "INSERT INTO movies (title, release_year, rating, genre) VALUES (?, ?, ?, ?)",
                    row,
                )
            connection.commit()
            logger.debug(f"Stored movies in SQLite: rows={len(rows)}")
        except sqlite3.Error:
            connection.rollback()
            logger.error("Saving movies failed, changes were rolled back")
            raise
        finally:
            connection.close()

    def get(self):
        connection = get_connection(self.db_path)
        try:
            cursor = connection.execute(
                "SELECT title, release_year, rating, genre FROM movies ORDER BY id"
            )
            rows = cursor.fetchall()
            records = []
            for row in rows:
                records.append(dict(row))
            return pd.DataFrame(records, columns=MOVIE_COLUMNS)
        finally:
            connection.close()

    def count_movies(self):
        connection = get_connection(self.db_path)
        try:
            cursor = connection.execute("SELECT COUNT(*) FROM movies")
            row = cursor.fetchone()
            return row[0]
        finally:
            connection.close()

    def select_columns(self, columns, limit=5):
        if not columns:
            logger.error("Select at least one column")
            raise ValueError("Select at least one column")

        for column in columns:
            if column not in MOVIE_COLUMNS:
                logger.error(f"Unsupported column: {column}")
                raise ValueError(f"Unsupported column: {column}")

        selected_columns = ", ".join(["id"] + columns)
        connection = get_connection(self.db_path)
        try:
            sql = f"SELECT {selected_columns} FROM movies ORDER BY id LIMIT ?"
            cursor = connection.execute(sql, [limit])
            rows = cursor.fetchall()

            results = []
            for row in rows:
                results.append(dict(row))

            logger.debug(f"Selected movies: columns={columns}, rows={len(results)}")
            return results
        finally:
            connection.close()

    def query_movies(self, columns, min_rating, limit):
        if not columns:
            logger.error("Select at least one column")
            raise ValueError("Select at least one column")

        for column in columns:
            if column not in MOVIE_COLUMNS:
                logger.error(f"Unsupported column: {column}")
                raise ValueError(f"Unsupported column: {column}")

        selected_columns = ", ".join(["id"] + columns)
        connection = get_connection(self.db_path)
        try:
            sql = f"""
                SELECT {selected_columns}
                FROM movies
                WHERE rating >= ?
                ORDER BY rating DESC, id ASC
                LIMIT ?
            """
            cursor = connection.execute(sql, [min_rating, limit])
            rows = cursor.fetchall()

            results = []
            for row in rows:
                results.append(dict(row))

            logger.debug(f"Queried movies: columns={columns}, rows={len(results)}")
            return results
        finally:
            connection.close()