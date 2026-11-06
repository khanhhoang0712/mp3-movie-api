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