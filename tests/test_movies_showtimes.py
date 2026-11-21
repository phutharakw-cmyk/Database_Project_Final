import uuid
from datetime import datetime, timedelta
from decimal import Decimal

import pytest

from db import execute
from services import movies, showtimes


@pytest.fixture
def movie():
    m = movies.create_movie(f"PyTest Movie {uuid.uuid4().hex[:6]}", "Drama", 90, "PG", "test")
    yield m
    execute("DELETE FROM showtimes WHERE movie_id = %s", (m["movie_id"],))
    try:
        movies.delete_movie(m["movie_id"])
    except ValueError:
        pass


@pytest.fixture
def hall():
    return f"TH-{uuid.uuid4().hex[:8]}"


def future(days=40, hour=10):
    return (datetime.now() + timedelta(days=days)).replace(hour=hour, minute=0,
                                                           second=0, microsecond=0)


class TestValidation:
    @pytest.mark.parametrize("text", ["2030-05-01 19:30", "2030-05-01T19:30",
                                      "2030-05-01 19:30:45", " 2030-05-01 19:30 "])
    def test_parse_start_time_formats(self, text):
        assert showtimes.parse_start_time(text) == datetime(2030, 5, 1, 19, 30)

    def test_parse_start_time_datetime_drops_seconds(self):
        dt = datetime(2030, 5, 1, 19, 30, 59, 123)
        assert showtimes.parse_start_time(dt) == datetime(2030, 5, 1, 19, 30)

    @pytest.mark.parametrize("bad", ["", None, "tomorrow", "01/05/2030 19:30", "2030-13-01 10:00"])
    def test_parse_start_time_invalid(self, bad):
        with pytest.raises(ValueError, match="Start time"):
            showtimes.parse_start_time(bad)

    @pytest.mark.parametrize("value, expected", [("150", "150.00"), (99.999, "100.00"),
                                                 (0, "0.00"), (" 12.5 ", "12.50")])
    def test_clean_price_ok(self, value, expected):
        assert showtimes._clean_price(value) == Decimal(expected)

    @pytest.mark.parametrize("bad", ["abc", None, "", -1, "1000000"])
    def test_clean_price_invalid(self, bad):
        with pytest.raises(ValueError, match="Price"):
            showtimes._clean_price(bad)

    @pytest.mark.parametrize("bad", [0, -5, 601, "abc", None])
    def test_duration_invalid(self, bad):
        with pytest.raises(ValueError, match="Duration"):
            movies._clean_duration(bad)

    def test_duration_bounds_ok(self):
        assert movies._clean_duration("1") == 1
        assert movies._clean_duration(600) == 600

    def test_rating_normalised(self):
        assert movies._clean_rating(" pg-13 ") == "PG-13"
        assert movies._clean_rating(None) == "G"
        with pytest.raises(ValueError, match="Rating"):
            movies._clean_rating("X")

    def test_status(self):
        assert movies._clean_status(" coming_soon ") == "coming_soon"
        with pytest.raises(ValueError, match="Status"):
            movies._clean_status("showing")

    def test_title_and_description(self):
        with pytest.raises(ValueError, match="Title is required"):
            movies._clean_title("   ")
        with pytest.raises(ValueError, match="at most 200"):
            movies._clean_title("x" * 201)
        assert movies._clean_description("   ") is None
        with pytest.raises(ValueError, match="5000"):
            movies._clean_description("x" * 5001)


def test_create_movie_rejects_bad_input():
    with pytest.raises(ValueError, match="Duration"):
        movies.create_movie("Bad", "Drama", 0, "PG", "")
    with pytest.raises(ValueError, match="Rating"):
        movies.create_movie("Bad", "Drama", 90, "ZZ", "")


def test_get_movie_not_found():
    with pytest.raises(ValueError, match="Movie not found"):
        movies.get_movie(99999999)
    with pytest.raises(ValueError, match="must be a number"):
        movies.get_movie("abc")


def test_list_movies_filter_by_status(movie):
    movies.update_movie(movie["movie_id"], status="coming_soon")
    coming = movies.list_movies("coming_soon")
    assert all(m["status"] == "coming_soon" for m in coming)
    assert movie["movie_id"] in [m["movie_id"] for m in coming]
    assert movie["movie_id"] not in [m["movie_id"] for m in movies.list_movies("now_showing")]


def test_update_movie_rules(movie):
    assert movies.update_movie(movie["movie_id"])["title"] == movie["title"]
    with pytest.raises(ValueError, match="Unknown movie field"):
        movies.update_movie(movie["movie_id"], director="Nolan")
    updated = movies.update_movie(movie["movie_id"], rating="r", description="  ")
    assert (updated["rating"], updated["description"]) == ("R", None)


def test_upcoming_showtimes_counted_on_movie(movie, hall):
    showtimes.create_showtime(movie["movie_id"], hall, future(hour=10), 150)
    showtimes.create_showtime(movie["movie_id"], hall, future(hour=14), 150)
    m = movies.get_movie(movie["movie_id"])
    assert m["upcoming_showtimes"] == 2
    assert m["next_showtime"] == future(hour=10)


def test_delete_movie(movie):
    assert movies.delete_movie(movie["movie_id"]) == {"movie_id": movie["movie_id"], "deleted": True}
    with pytest.raises(ValueError, match="not found"):
        movies.get_movie(movie["movie_id"])


def test_create_showtime_fields(movie, hall):
    start = future()
    st = showtimes.create_showtime(movie["movie_id"], hall, start.strftime("%Y-%m-%dT%H:%M"), "180.5")
    assert st["hall"] == hall and st["start_time"] == start
    assert st["price"] == Decimal("180.50")
    assert st["end_time"] == start + timedelta(minutes=90)
    assert st["seats_sold"] == 0 and st["title"] == movie["title"]


def test_create_showtime_in_past_rejected(movie, hall):
    with pytest.raises(ValueError, match="future"):
        showtimes.create_showtime(movie["movie_id"], hall, datetime.now() - timedelta(hours=1), 150)


def test_create_showtime_for_ended_movie_rejected(movie, hall):
    movies.update_movie(movie["movie_id"], status="ended")
    with pytest.raises(ValueError, match="ended"):
        showtimes.create_showtime(movie["movie_id"], hall, future(), 150)


def test_hall_clash_respects_cleanup_gap(movie, hall):
    start = future()
    showtimes.create_showtime(movie["movie_id"], hall, start, 150)
    with pytest.raises(ValueError, match="busy"):
        showtimes.create_showtime(movie["movie_id"], hall, start + timedelta(minutes=100), 150)
    with pytest.raises(ValueError, match="busy"):
        showtimes.create_showtime(movie["movie_id"], hall, start - timedelta(minutes=30), 150)
    ok = showtimes.create_showtime(movie["movie_id"], hall,
                                   start + timedelta(minutes=90 + showtimes.CLEANUP_MIN), 150)
    assert ok["showtime_id"]


def test_same_time_different_hall_is_fine(movie, hall):
    start = future()
    showtimes.create_showtime(movie["movie_id"], hall, start, 150)
    other = showtimes.create_showtime(movie["movie_id"], hall + "b", start, 150)
    assert other["hall"] == hall + "b"


def test_list_showtimes_sorted_and_filtered(movie, hall):
    late = showtimes.create_showtime(movie["movie_id"], hall, future(hour=18), 150)
    early = showtimes.create_showtime(movie["movie_id"], hall, future(hour=9), 150)
    ids = [s["showtime_id"] for s in showtimes.list_showtimes(movie["movie_id"], upcoming_only=True)]
    assert ids == [early["showtime_id"], late["showtime_id"]]


def test_update_showtime_rules(movie, hall):
    st = showtimes.create_showtime(movie["movie_id"], hall, future(hour=10), 150)
    with pytest.raises(ValueError, match="Unknown showtime field"):
        showtimes.update_showtime(st["showtime_id"], seats=50)
    with pytest.raises(ValueError, match="future"):
        showtimes.update_showtime(st["showtime_id"], start_time=datetime.now() - timedelta(days=1))

    moved = showtimes.update_showtime(st["showtime_id"], start_time=future(hour=15), price=200)
    assert moved["start_time"] == future(hour=15) and moved["price"] == Decimal("200.00")

    showtimes.create_showtime(movie["movie_id"], hall, future(hour=20), 150)
    with pytest.raises(ValueError, match="busy"):
        showtimes.update_showtime(st["showtime_id"], start_time=future(hour=20))


def test_delete_showtime(movie, hall):
    st = showtimes.create_showtime(movie["movie_id"], hall, future(), 150)
    assert showtimes.delete_showtime(st["showtime_id"])["deleted"]
    with pytest.raises(ValueError, match="Showtime not found"):
        showtimes.get_showtime(st["showtime_id"])
