"""
seed_mongo.py - seed the 4 MongoDB collections (Owner: จอมมารปาแปง)

Run from the project root:
    python database/seed_mongo.py

Collections: carts, reviews, watchlists, notifications
user_id / movie_id / showtime_id values match the MySQL seed (database/seed.sql).
"""
import os
import sys
from datetime import datetime, timedelta

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from db import get_mongo, ensure_mongo_indexes  # noqa: E402


def seed_mongo():
    db = get_mongo()
    now = datetime.now()

    for name in ("carts", "reviews", "watchlists", "notifications"):
        db[name].delete_many({})
    ensure_mongo_indexes(db)

    # carts: one active cart per user (seats for ONE showtime)
    db.carts.insert_many([
        {
            "user_id": 2,
            "showtime_id": 8,
            "items": [
                {"seat_label": "F5", "price": 150.0},
                {"seat_label": "F6", "price": 150.0},
            ],
            "updated_at": now,
        },
    ])

    # reviews: flexible text + rating per user per movie
    db.reviews.insert_many([
        {"user_id": 2, "user_name": "Alice Customer", "movie_id": 1, "rating": 5,
         "comment": "Amazing visuals, the last 20 minutes are intense!",
         "created_at": now - timedelta(days=2), "updated_at": now - timedelta(days=2)},
        {"user_id": 3, "user_name": "Bob Customer", "movie_id": 1, "rating": 4,
         "comment": "Great sound design. A bit long in the middle.",
         "created_at": now - timedelta(days=1), "updated_at": now - timedelta(days=1)},
        {"user_id": 3, "user_name": "Bob Customer", "movie_id": 3, "rating": 5,
         "comment": "Best chase scene through Yaowarat ever.",
         "created_at": now - timedelta(hours=10), "updated_at": now - timedelta(hours=10)},
        {"user_id": 2, "user_name": "Alice Customer", "movie_id": 2, "rating": 4,
         "comment": "Bring tissues.",
         "created_at": now - timedelta(hours=5), "updated_at": now - timedelta(hours=5)},
    ])

    # watchlists: one document per (user, movie) with an optional note
    db.watchlists.insert_many([
        {"user_id": 2, "movie_id": 6, "movie_title": "Coffee & Code",
         "note": "Watch with the dev team when it opens", "added_at": now - timedelta(days=3)},
        {"user_id": 2, "movie_id": 5, "movie_title": "Echoes in the Hall",
         "note": "", "added_at": now - timedelta(days=1)},
        {"user_id": 3, "movie_id": 4, "movie_title": "Paper Lanterns",
         "note": "Take my niece", "added_at": now - timedelta(hours=8)},
    ])

    # notifications: async messages, unread count shown in the navbar
    db.notifications.insert_many([
        {"user_id": 2, "title": "Welcome to MovieTicketSystem",
         "message": "Browse movies, pick a showtime and choose your seats.",
         "is_read": True, "created_at": now - timedelta(days=4)},
        {"user_id": 2, "title": "Booking confirmed #2",
         "message": "Seats D4, D5 for The Last Monsoon are confirmed.",
         "is_read": False, "created_at": now - timedelta(days=1)},
        {"user_id": 3, "title": "Booking confirmed #1",
         "message": "Seats E5, E6 for Starfall Protocol are confirmed.",
         "is_read": False, "created_at": now - timedelta(days=1)},
        {"user_id": 3, "title": "Booking confirmed #3",
         "message": "Seat C7 for Bangkok Midnight Run is confirmed.",
         "is_read": False, "created_at": now - timedelta(hours=6)},
    ])

    counts = {name: db[name].count_documents({})
              for name in ("carts", "reviews", "watchlists", "notifications")}
    print("MongoDB seeded:", counts)
    return counts


if __name__ == "__main__":
    seed_mongo()
