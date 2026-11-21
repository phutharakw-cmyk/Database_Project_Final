"""
reviews.py - MongoDB collection `reviews` (Owner: Pen)

{ _id, user_id, user_name, movie_id, rating (1-5), comment, created_at, updated_at }
Unique index (user_id, movie_id): one review per user per movie.
"""
from datetime import datetime

from pymongo.errors import DuplicateKeyError

from db import get_mongo, query_one
from services import doc_to_dict, to_object_id, to_int


def _check(rating, comment):
    rating = to_int(rating, "Rating")
    if not 1 <= rating <= 5:
        raise ValueError("Rating must be 1 to 5 stars")
    comment = (comment or "").strip()
    if len(comment) > 1000:
        raise ValueError("Comment must be at most 1000 characters")
    return rating, comment


def add_review(user_id, movie_id, rating, comment):
    user_id = to_int(user_id, "User id")
    movie_id = to_int(movie_id, "Movie id")
    rating, comment = _check(rating, comment)
    user = query_one("SELECT name FROM users WHERE user_id=%s", (user_id,))
    if not user:
        raise ValueError("User not found")
    if not query_one("SELECT 1 FROM movies WHERE movie_id=%s", (movie_id,)):
        raise ValueError("Movie not found")
    now = datetime.now()
    doc = {"user_id": user_id, "user_name": user["name"], "movie_id": movie_id,
           "rating": rating, "comment": comment, "created_at": now, "updated_at": now}
    try:
        res = get_mongo().reviews.insert_one(doc)
    except DuplicateKeyError:
        raise ValueError("You already reviewed this movie - edit your review instead")
    doc["_id"] = res.inserted_id
    return doc_to_dict(doc)


def list_reviews(movie_id):
    cur = get_mongo().reviews.find({"movie_id": to_int(movie_id, "Movie id")}).sort("created_at", -1)
    return [doc_to_dict(d) for d in cur]


def list_all_reviews():
    """Admin moderation list, with the movie title joined from MySQL."""
    titles = {}
    out = []
    for d in get_mongo().reviews.find().sort("created_at", -1):
        r = doc_to_dict(d)
        if r["movie_id"] not in titles:
            row = query_one("SELECT title FROM movies WHERE movie_id=%s", (r["movie_id"],))
            titles[r["movie_id"]] = row["title"] if row else "(deleted movie)"
        r["movie_title"] = titles[r["movie_id"]]
        out.append(r)
    return out


def get_average_rating(movie_id):
    movie_id = to_int(movie_id, "Movie id")
    result = list(get_mongo().reviews.aggregate([
        {"$match": {"movie_id": movie_id}},
        {"$group": {"_id": "$movie_id", "average": {"$avg": "$rating"}, "count": {"$sum": 1}}},
    ]))
    if not result:
        return {"movie_id": movie_id, "average": 0.0, "count": 0}
    return {"movie_id": movie_id, "average": round(result[0]["average"], 1), "count": result[0]["count"]}


def get_review(review_id):
    doc = get_mongo().reviews.find_one({"_id": to_object_id(review_id)})
    if not doc:
        raise ValueError("Review not found")
    return doc_to_dict(doc)


def update_review(review_id, user_id, rating, comment):
    review = get_review(review_id)
    if review["user_id"] != to_int(user_id, "User id"):
        raise ValueError("You can only edit your own review")
    rating, comment = _check(rating, comment)
    get_mongo().reviews.update_one(
        {"_id": to_object_id(review_id)},
        {"$set": {"rating": rating, "comment": comment, "updated_at": datetime.now()}},
    )
    return get_review(review_id)


def delete_review(review_id, user_id):
    """user_id=None means admin moderation."""
    review = get_review(review_id)
    if user_id is not None and review["user_id"] != to_int(user_id, "User id"):
        raise ValueError("You can only delete your own review")
    get_mongo().reviews.delete_one({"_id": to_object_id(review_id)})
    return {"id": review["id"], "deleted": True}
