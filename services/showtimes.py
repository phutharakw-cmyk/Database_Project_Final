from datetime import datetime, timedelta
from decimal import Decimal, InvalidOperation

import pymysql

from db import query_all, query_one, execute
from services import require_text, to_int
from services.movies import get_movie

HALLS = ("Hall 1", "Hall 2", "Hall 3", "Hall 4", "Hall 5")

CLEANUP_MIN = 15
MAX_PRICE = Decimal("999999.99")

_SELECT = """
    SELECT s.showtime_id, s.movie_id, s.hall, s.start_time, s.price, s.created_at,
           m.title, m.genre, m.duration_min, m.rating, m.poster_path, m.status,
           DATE_ADD(s.start_time, INTERVAL m.duration_min MINUTE) AS end_time,
           (SELECT COUNT(*) FROM tickets t WHERE t.showtime_id = s.showtime_id) AS seats_sold
      FROM showtimes s
      JOIN movies m ON m.movie_id = s.movie_id
"""


def parse_start_time(value):
    if isinstance(value, datetime):
        return value.replace(second=0, microsecond=0)
    text = (value or "").strip().replace("T", " ")
    for fmt in ("%Y-%m-%d %H:%M", "%Y-%m-%d %H:%M:%S"):
        try:
            return datetime.strptime(text, fmt).replace(second=0)
        except ValueError:
            continue
    raise ValueError("Start time must look like 2026-12-31 19:30")


def _clean_future(start):
    if start <= datetime.now():
        raise ValueError("Start time must be in the future")
    return start


def _clean_hall(value):
    return require_text(value, "Hall", 20)


def _clean_price(value):
    try:
        price = Decimal(str(value).strip()).quantize(Decimal("0.01"))
    except (InvalidOperation, ValueError, AttributeError):
        raise ValueError("Price must be a number")
    if price < 0 or price > MAX_PRICE:
        raise ValueError("Price must be between 0 and 999,999.99")
    return price


def _check_hall_free(hall, start, duration_min, ignore_id=0):
    end = start + timedelta(minutes=duration_min + CLEANUP_MIN)
    clash = query_one(
        """SELECT s.showtime_id, s.start_time, m.title
             FROM showtimes s JOIN movies m ON m.movie_id = s.movie_id
            WHERE s.hall = %s AND s.showtime_id <> %s
              AND s.start_time < %s
              AND DATE_ADD(s.start_time, INTERVAL m.duration_min + %s MINUTE) > %s
            ORDER BY s.start_time LIMIT 1""",
        (hall, ignore_id, end, CLEANUP_MIN, start),
    )
    if clash:
        raise ValueError(f"{hall} is busy: '{clash['title']}' starts "
                         f"{clash['start_time']:%d %b %H:%M} (shows need {CLEANUP_MIN} min "
                         f"between them)")


def create_showtime(movie_id, hall, start_time, price):
    movie = get_movie(movie_id)
    if movie["status"] == "ended":
        raise ValueError("Cannot add a showtime to a movie that has ended")
    hall = _clean_hall(hall)
    start = _clean_future(parse_start_time(start_time))
    price = _clean_price(price)
    _check_hall_free(hall, start, movie["duration_min"])
    try:
        _, new_id = execute(
            "INSERT INTO showtimes (movie_id, hall, start_time, price) VALUES (%s, %s, %s, %s)",
            (movie["movie_id"], hall, start, price),
        )
    except pymysql.err.IntegrityError:
        raise ValueError(f"{hall} already has a show at that time")
    return get_showtime(new_id)


def list_showtimes(movie_id=None, upcoming_only=False):
    where, params = [], []
    if movie_id is not None:
        where.append("s.movie_id = %s")
        params.append(to_int(movie_id, "Movie id"))
    if upcoming_only:
        where.append("s.start_time > NOW()")
    sql = _SELECT + (" WHERE " + " AND ".join(where) if where else "")
    return query_all(sql + " ORDER BY s.start_time, s.hall", params)


def get_showtime(showtime_id):
    row = query_one(_SELECT + " WHERE s.showtime_id = %s",
                    (to_int(showtime_id, "Showtime id"),))
    if not row:
        raise ValueError("Showtime not found")
    return row


def update_showtime(showtime_id, **fields):
    show = get_showtime(showtime_id)
    allowed = {"movie_id", "hall", "start_time", "price"}
    unknown = set(fields) - allowed
    if unknown:
        raise ValueError(f"Unknown showtime field: {', '.join(sorted(unknown))}")

    movie_id = to_int(fields.get("movie_id", show["movie_id"]), "Movie id")
    hall = _clean_hall(fields["hall"]) if "hall" in fields else show["hall"]
    start = parse_start_time(fields["start_time"]) if "start_time" in fields else show["start_time"]
    price = _clean_price(fields["price"]) if "price" in fields else show["price"]

    moved = (movie_id != show["movie_id"] or hall != show["hall"] or start != show["start_time"])
    if moved:
        if show["seats_sold"]:
            raise ValueError(f"{show['seats_sold']} ticket(s) already sold - "
                             "only the price can be changed")
        movie = get_movie(movie_id)
        if movie_id != show["movie_id"] and movie["status"] == "ended":
            raise ValueError("Cannot move a showtime to a movie that has ended")
        if start != show["start_time"]:
            _clean_future(start)
        _check_hall_free(hall, start, movie["duration_min"], ignore_id=show["showtime_id"])

    try:
        execute("UPDATE showtimes SET movie_id=%s, hall=%s, start_time=%s, price=%s "
                "WHERE showtime_id=%s",
                (movie_id, hall, start, price, show["showtime_id"]))
    except pymysql.err.IntegrityError:
        raise ValueError(f"{hall} already has a show at that time")
    return get_showtime(show["showtime_id"])


def delete_showtime(showtime_id):
    show = get_showtime(showtime_id)
    booked = query_one("SELECT COUNT(*) AS n FROM bookings WHERE showtime_id = %s",
                       (show["showtime_id"],))["n"]
    if booked:
        raise ValueError("This showtime has bookings (including cancelled ones) "
                         "and cannot be deleted")
    try:
        execute("DELETE FROM showtimes WHERE showtime_id = %s", (show["showtime_id"],))
    except pymysql.err.IntegrityError:
        raise ValueError("This showtime has bookings and cannot be deleted")
    return {"showtime_id": show["showtime_id"], "deleted": True}
