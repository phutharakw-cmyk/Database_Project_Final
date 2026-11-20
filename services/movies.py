"""
movies.py - SQL table `movies` (Owner: Phoom)

create_movie(title, genre, duration, rating, description)
list_movies(status=None)
get_movie(movie_id)
update_movie(movie_id, **fields)
delete_movie(movie_id)
save_poster(movie_id, file_path)
"""
from db import get_mysql, get_mongo, query_all, query_one, execute
from services import require_text, to_int
from services.uploads import save_image, delete_image

STATUSES = ("now_showing", "coming_soon", "ended")
RATINGS = ("G", "PG", "PG-13", "R", "NC-17")

# columns + "next upcoming showtime" summary used by list/get
_SELECT = """
    SELECT m.movie_id, m.title, m.genre, m.duration_min, m.rating, m.description,
           m.poster_path, m.status, m.created_at,
           COUNT(s.showtime_id) AS upcoming_showtimes,
           MIN(s.start_time)    AS next_showtime
      FROM movies m
      LEFT JOIN showtimes s
             ON s.movie_id = m.movie_id AND s.start_time > NOW()
"""


# ---------------------------------------------------------------- validation
def _clean_title(value):
    return require_text(value, "Title", 200)


def _clean_genre(value):
    return require_text(value, "Genre", 100)


def _clean_duration(value):
    minutes = to_int(value, "Duration")
    if minutes <= 0 or minutes > 600:
        raise ValueError("Duration must be between 1 and 600 minutes")
    return minutes


def _clean_rating(value):
    value = (value or "G").strip().upper()
    if value not in RATINGS:
        raise ValueError(f"Rating must be one of: {', '.join(RATINGS)}")
    return value


def _clean_status(value):
    value = (value or "").strip()
    if value not in STATUSES:
        raise ValueError("Status must be now_showing, coming_soon or ended")
    return value


def _clean_description(value):
    value = (value or "").strip()
    if len(value) > 5000:
        raise ValueError("Description must be at most 5000 characters")
    return value or None


# form field name -> (db column, cleaner)
_FIELDS = {
    "title": ("title", _clean_title),
    "genre": ("genre", _clean_genre),
    "duration": ("duration_min", _clean_duration),
    "duration_min": ("duration_min", _clean_duration),
    "rating": ("rating", _clean_rating),
    "description": ("description", _clean_description),
    "status": ("status", _clean_status),
}


# ---------------------------------------------------------------- CRUD
def create_movie(title, genre, duration, rating, description, status="now_showing"):
    _, new_id = execute(
        """INSERT INTO movies (title, genre, duration_min, rating, description, status)
           VALUES (%s, %s, %s, %s, %s, %s)""",
        (_clean_title(title), _clean_genre(genre), _clean_duration(duration),
         _clean_rating(rating), _clean_description(description), _clean_status(status)),
    )
    return get_movie(new_id)


def list_movies(status=None):
    """All movies (optionally one status), now showing first, with next showtime info."""
    sql, params = _SELECT, []
    if status:
        sql += " WHERE m.status = %s"
        params.append(_clean_status(status))
    sql += """ GROUP BY m.movie_id
               ORDER BY FIELD(m.status, 'now_showing', 'coming_soon', 'ended'), m.title"""
    return query_all(sql, params)


def get_movie(movie_id):
    row = query_one(_SELECT + " WHERE m.movie_id = %s GROUP BY m.movie_id",
                    (to_int(movie_id, "Movie id"),))
    if not row:
        raise ValueError("Movie not found")
    return row


def update_movie(movie_id, **fields):
    """update_movie(3, title="New", duration=120, status="ended") - only given fields change."""
    movie = get_movie(movie_id)
    changes = {}  # db column -> cleaned value
    for key, value in fields.items():
        if key not in _FIELDS:
            raise ValueError(f"Unknown movie field: {key}")
        column, cleaner = _FIELDS[key]
        changes[column] = cleaner(value)
    if not changes:
        return movie
    assignments = ", ".join(f"{column}=%s" for column in changes)  # names come from _FIELDS only
    execute(f"UPDATE movies SET {assignments} WHERE movie_id=%s",
            (*changes.values(), movie["movie_id"]))
    return get_movie(movie["movie_id"])


def delete_movie(movie_id):
    """
    Delete a movie and its showtimes (ON DELETE CASCADE).
    Refused if any showtime has bookings: bookings -> showtimes is RESTRICT,
    so booking history is never lost. Mark the movie 'ended' instead.
    """
    movie = get_movie(movie_id)
    mid = movie["movie_id"]
    conn = get_mysql()
    try:
        with conn.cursor() as cur:
            conn.begin()
            cur.execute("""SELECT COUNT(*) AS n FROM bookings b
                             JOIN showtimes s ON s.showtime_id = b.showtime_id
                            WHERE s.movie_id = %s FOR UPDATE""", (mid,))
            if cur.fetchone()["n"]:
                raise ValueError("This movie has bookings and cannot be deleted. "
                                 "Set its status to 'ended' instead.")
            cur.execute("DELETE FROM movies WHERE movie_id = %s", (mid,))
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()

    try:  # MongoDB documents that point at this movie
        mongo = get_mongo()
        for coll in ("reviews", "watchlists"):
            mongo[coll].delete_many({"movie_id": mid})
    except Exception:
        pass  # SQL delete already done; Mongo leftovers are harmless
    delete_image(movie.get("poster_path"))
    return {"movie_id": mid, "deleted": True}


def save_poster(movie_id, file_path):
    """file_path = uploaded FileStorage or a local file path."""
    movie = get_movie(movie_id)
    new_path = save_image(file_path, "posters")
    execute("UPDATE movies SET poster_path=%s WHERE movie_id=%s", (new_path, movie["movie_id"]))
    delete_image(movie.get("poster_path"))
    return get_movie(movie["movie_id"])
