"""
watchlists.py - MongoDB collection `watchlists` (Owner: Pen)

{ _id, user_id, movie_id, movie_title, note, added_at }
Unique index (user_id, movie_id).
"""
from datetime import datetime

from pymongo.errors import DuplicateKeyError

from db import get_mongo, query_one
from services import doc_to_dict, to_int


def add_to_watchlist(user_id, movie_id):
    user_id = to_int(user_id, "User id")
    movie_id = to_int(movie_id, "Movie id")
    movie = query_one("SELECT title FROM movies WHERE movie_id=%s", (movie_id,))
    if not movie:
        raise ValueError("Movie not found")
    doc = {"user_id": user_id, "movie_id": movie_id, "movie_title": movie["title"],
           "note": "", "added_at": datetime.now()}
    try:
        res = get_mongo().watchlists.insert_one(doc)
    except DuplicateKeyError:
        raise ValueError("This movie is already in your watchlist")
    doc["_id"] = res.inserted_id
    return doc_to_dict(doc)


def get_watchlist(user_id):
    cur = get_mongo().watchlists.find({"user_id": to_int(user_id, "User id")}).sort("added_at", -1)
    items = [doc_to_dict(d) for d in cur]
    for it in items:  # add live data from MySQL (poster, status)
        m = query_one("SELECT poster_path, status, genre FROM movies WHERE movie_id=%s", (it["movie_id"],))
        it.update(m or {"poster_path": None, "status": "ended", "genre": ""})
    return items


def is_in_watchlist(user_id, movie_id):
    doc = get_mongo().watchlists.find_one({"user_id": to_int(user_id, "User id"),
                                           "movie_id": to_int(movie_id, "Movie id")})
    return {"in_watchlist": doc is not None}


def update_note(user_id, movie_id, note):
    note = (note or "").strip()
    if len(note) > 300:
        raise ValueError("Note must be at most 300 characters")
    res = get_mongo().watchlists.find_one_and_update(
        {"user_id": to_int(user_id, "User id"), "movie_id": to_int(movie_id, "Movie id")},
        {"$set": {"note": note}},
        return_document=True,
    )
    if not res:
        raise ValueError("Movie is not in your watchlist")
    return doc_to_dict(res)


def remove_from_watchlist(user_id, movie_id):
    res = get_mongo().watchlists.delete_one(
        {"user_id": to_int(user_id, "User id"), "movie_id": to_int(movie_id, "Movie id")})
    if res.deleted_count == 0:
        raise ValueError("Movie is not in your watchlist")
    return {"movie_id": int(movie_id), "deleted": True}
