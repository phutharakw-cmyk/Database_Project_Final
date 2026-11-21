"""
Create / Read / Update / Delete for every SQL table and MongoDB collection.
"""
import uuid

import pytest

from services import users, movies, showtimes, carts, reviews, watchlists, notifications
from tests.conftest import ALICE


def test_users_crud():
    email = f"test_{uuid.uuid4().hex[:8]}@example.com"
    u = users.register("Test User", email, "secret1")                       # C
    assert users.login(email, "secret1")["user_id"] == u["user_id"]          # R
    with pytest.raises(ValueError, match="already registered"):
        users.register("Again", email, "secret1")
    u2 = users.update_user(u["user_id"], "Renamed", email, "0812345678")    # U
    assert u2["name"] == "Renamed"
    users.change_password(u["user_id"], "secret1", "secret2")
    with pytest.raises(ValueError):
        users.login(email, "secret1")
    assert users.delete_user(u["user_id"])["deleted"]                       # D
    with pytest.raises(ValueError):
        users.get_user(u["user_id"])


def test_movies_and_showtimes_crud():
    m = movies.create_movie("Test Movie", "Drama", 90, "PG", "desc")         # C
    assert movies.get_movie(m["movie_id"])["title"] == "Test Movie"          # R
    m = movies.update_movie(m["movie_id"], title="Test Movie 2", duration=95)   # U
    assert (m["title"], m["duration_min"]) == ("Test Movie 2", 95)

    st = showtimes.create_showtime(m["movie_id"], "Hall 9", "2030-01-01 10:00", 150)
    assert showtimes.list_showtimes(m["movie_id"])[0]["showtime_id"] == st["showtime_id"]
    st = showtimes.update_showtime(st["showtime_id"], price=175)
    assert float(st["price"]) == 175.0
    with pytest.raises(ValueError, match="busy|already has"):
        showtimes.create_showtime(m["movie_id"], "Hall 9", "2030-01-01 10:00", 150)
    showtimes.delete_showtime(st["showtime_id"])
    assert movies.delete_movie(m["movie_id"])["deleted"]                    # D


def test_cart_crud():
    carts.clear_cart(ALICE)
    carts.add_seat(ALICE, 1, "B2", 220)                                      # C
    carts.add_seat(ALICE, 1, "B1", 220)
    c = carts.get_cart(ALICE)                                                # R
    assert [i["seat_label"] for i in c["items"]] == ["B1", "B2"] and c["total"] == 440
    with pytest.raises(ValueError, match="already in your cart"):
        carts.add_seat(ALICE, 1, "B1", 220)
    assert [i["seat_label"] for i in carts.remove_seat(ALICE, "B2")["items"]] == ["B1"]   # U
    c = carts.add_seat(ALICE, 2, "A1", 260)        # other showtime -> fresh cart
    assert c["showtime_id"] == 2 and len(c["items"]) == 1
    assert carts.clear_cart(ALICE)["deleted"] == 1                           # D


def test_reviews_crud():
    m = movies.create_movie("Review Test", "Comedy", 80, "G", "")
    try:
        r = reviews.add_review(ALICE, m["movie_id"], 4, "Nice")              # C
        with pytest.raises(ValueError, match="already reviewed"):
            reviews.add_review(ALICE, m["movie_id"], 5, "Again")
        assert reviews.list_reviews(m["movie_id"])[0]["comment"] == "Nice"   # R
        assert reviews.get_average_rating(m["movie_id"]) == {"movie_id": m["movie_id"], "average": 4.0, "count": 1}
        assert reviews.update_review(r["id"], ALICE, 2, "Meh")["rating"] == 2   # U
        with pytest.raises(ValueError):
            reviews.update_review(r["id"], 3, 5, "not mine")
        assert reviews.delete_review(r["id"], ALICE)["deleted"]               # D
    finally:
        movies.delete_movie(m["movie_id"])


def test_watchlist_crud():
    watchlists.remove_from_watchlist(ALICE, 3) if watchlists.is_in_watchlist(ALICE, 3)["in_watchlist"] else None
    assert watchlists.add_to_watchlist(ALICE, 3)["movie_title"]              # C
    assert any(w["movie_id"] == 3 for w in watchlists.get_watchlist(ALICE))  # R
    assert watchlists.update_note(ALICE, 3, "with friends")["note"] == "with friends"   # U
    assert watchlists.remove_from_watchlist(ALICE, 3)["deleted"]             # D


def test_notifications_crud():
    n = notifications.create_notification(ALICE, "Test", "Hello")           # C
    assert notifications.list_notifications(ALICE)[0]["id"] == n["id"]       # R
    assert notifications.mark_as_read(n["id"], ALICE)["is_read"] is True    # U
    assert notifications.delete_notification(n["id"], ALICE)["deleted"]     # D
