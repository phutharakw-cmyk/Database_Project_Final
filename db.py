"""
db.py - database connections (Owner: Mizt)

get_mysql()  -> new PyMySQL connection (DictCursor, autocommit OFF so we
                can run explicit transactions with commit / rollback)
get_mongo()  -> pymongo Database object (shared client)

Settings come from environment variables / .env (see .env.example).
"""
import os

import pymysql
from pymongo import MongoClient, ASCENDING, DESCENDING

try:  # .env is optional
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:  # pragma: no cover
    pass

MYSQL_CONFIG = {
    "host": os.getenv("MYSQL_HOST", "127.0.0.1"),
    "port": int(os.getenv("MYSQL_PORT", "3306")),
    "user": os.getenv("MYSQL_USER", "movie_app"),
    "password": os.getenv("MYSQL_PASSWORD", "movie_pass"),
    "database": os.getenv("MYSQL_DATABASE", "movie_ticket_system"),
}
MONGO_URI = os.getenv("MONGO_URI", "mongodb://127.0.0.1:27017")
MONGO_DB = os.getenv("MONGO_DB", "movie_ticket_system")

_mongo_client = None
_indexes_ready = False


def get_mysql():
    """Return a NEW MySQL connection. Caller must close it (use `with`)."""
    return pymysql.connect(
        host=MYSQL_CONFIG["host"],
        port=MYSQL_CONFIG["port"],
        user=MYSQL_CONFIG["user"],
        password=MYSQL_CONFIG["password"],
        database=MYSQL_CONFIG["database"],
        charset="utf8mb4",
        cursorclass=pymysql.cursors.DictCursor,
        autocommit=False,
    )


def get_mongo():
    """Return the MongoDB database (client is created once and reused)."""
    global _mongo_client, _indexes_ready
    if _mongo_client is None:
        _mongo_client = MongoClient(MONGO_URI, serverSelectionTimeoutMS=5000)
    db = _mongo_client[MONGO_DB]
    if not _indexes_ready:
        ensure_mongo_indexes(db)
        _indexes_ready = True
    return db


def ensure_mongo_indexes(db):
    """Create the indexes every collection relies on (safe to call many times)."""
    db.carts.create_index([("user_id", ASCENDING)], unique=True)
    db.reviews.create_index([("movie_id", ASCENDING), ("created_at", DESCENDING)])
    db.reviews.create_index([("user_id", ASCENDING), ("movie_id", ASCENDING)], unique=True)
    db.watchlists.create_index([("user_id", ASCENDING), ("movie_id", ASCENDING)], unique=True)
    db.notifications.create_index([("user_id", ASCENDING), ("created_at", DESCENDING)])


def query_all(sql, params=None):
    """Small helper: run a SELECT and return list of dicts."""
    with get_mysql() as conn:
        with conn.cursor() as cur:
            cur.execute(sql, params or ())
            return list(cur.fetchall())


def query_one(sql, params=None):
    """Small helper: run a SELECT and return one dict or None."""
    with get_mysql() as conn:
        with conn.cursor() as cur:
            cur.execute(sql, params or ())
            return cur.fetchone()


def execute(sql, params=None):
    """Small helper: run one INSERT/UPDATE/DELETE, commit, return (rowcount, lastrowid)."""
    with get_mysql() as conn:
        try:
            with conn.cursor() as cur:
                cur.execute(sql, params or ())
                result = (cur.rowcount, cur.lastrowid)
            conn.commit()
            return result
        except Exception:
            conn.rollback()
            raise
