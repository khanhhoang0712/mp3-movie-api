import sqlite3
from pathlib import Path


def get_connection(db_path):
    folder = Path(db_path).parent
    folder.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(db_path)
    connection.row_factory = sqlite3.Row

    return connection


def initialize_database(db_path):
    connection = get_connection(db_path)

    connection.execute("""
        CREATE TABLE IF NOT EXISTS movies (
            id INTEGER PRIMARY KEY,
            title TEXT,
            release_year INTEGER,
            rating REAL,
            genre TEXT
        )
    """)

    connection.commit()
    connection.close()