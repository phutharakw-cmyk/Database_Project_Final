"""
bookings.py - SQL tables `bookings` + `tickets` (Owner: Mizt)

The important part of the project:

create_booking() runs ONE SQL transaction
    BEGIN
      INSERT bookings            (header)
      INSERT tickets  x N        (one row per seat, UNIQUE(showtime_id, seat_label))
      UPDATE bookings total
    COMMIT
If any seat is already taken, MySQL raises a duplicate-key error on the
UNIQUE constraint -> we ROLLBACK, so the booking header and every seat
inserted before the failure disappear. Example: A1 + A2 where A2 is taken
-> A1 stays free, no partial booking is saved.

After COMMIT (hybrid step, MongoDB):
    clear_cart(user_id)                     -> carts collection
    create_notification(user_id, ...)       -> notifications collection
"""
import logging
from datetime import datetime

import pymysql

from db import get_mysql, query_all, query_one
from services import to_int
from services.seats import is_valid_seat, SEAT_ROWS

log = logging.getLogger("bookings")
PAYMENT_METHODS = ("cash", "credit_card", "promptpay")
MAX_SEATS_PER_BOOKING = 10


class SeatTakenError(Exception):
    def __init__(self, seat):
        super().__init__(seat)
        self.seat = seat


def _seat_sort_key(label):
    return (SEAT_ROWS.find(label[0]), int(label[1:]))


def _notify(user_id, title, message):
    """Write a notification but never let a MongoDB problem break the SQL result."""
    try:
        from services.notifications import create_notification
        create_notification(user_id, title, message)
        return True
    except Exception as exc:  # pragma: no cover
        log.warning("notification failed: %s", exc)
        return False


# ---------------------------------------------------------------- READ

SEATS_SUBQUERY = """
    (SELECT GROUP_CONCAT(t.seat_label
                         ORDER BY LEFT(t.seat_label,1), CAST(SUBSTRING(t.seat_label,2) AS UNSIGNED)
                         SEPARATOR ', ')
       FROM tickets t WHERE t.booking_id = b.booking_id)
"""

BOOKING_SELECT = f"""
    SELECT b.*, s.start_time, s.hall, s.price AS seat_price,
           m.movie_id, m.title AS movie_title, m.poster_path,
           u.name AS user_name, u.email AS user_email,
           COALESCE({SEATS_SUBQUERY}, b.cancelled_seats) AS seats,
           (SELECT COUNT(*) FROM tickets t WHERE t.booking_id = b.booking_id) AS ticket_count
      FROM bookings b
      JOIN showtimes s ON s.showtime_id = b.showtime_id
      JOIN movies    m ON m.movie_id    = s.movie_id
      JOIN users     u ON u.user_id     = b.user_id
"""


def get_booked_seats(showtime_id):
    """List of dicts: [{'seat_label': 'A1', 'booking_id': 5}, ...]"""
    rows = query_all("SELECT seat_label, booking_id FROM tickets WHERE showtime_id = %s",
                     (to_int(showtime_id, "Showtime id"),))
    return sorted(rows, key=lambda r: _seat_sort_key(r["seat_label"]))


def list_bookings(user_id):
    return query_all(BOOKING_SELECT + " WHERE b.user_id = %s ORDER BY b.created_at DESC, b.booking_id DESC",
                     (to_int(user_id, "User id"),))


def list_all_bookings(showtime_id=None, status=None):
    sql = BOOKING_SELECT + " WHERE 1=1"
    params = []
    if showtime_id:
        sql += " AND b.showtime_id = %s"
        params.append(to_int(showtime_id, "Showtime id"))
    if status:
        sql += " AND b.status = %s"
        params.append(status)
    return query_all(sql + " ORDER BY b.booking_id DESC", params)


def get_booking(booking_id):
    booking = query_one(BOOKING_SELECT + " WHERE b.booking_id = %s",
                        (to_int(booking_id, "Booking id"),))
    if not booking:
        raise ValueError("Booking not found")
    booking["tickets"] = query_all(
        "SELECT ticket_id, seat_label, price FROM tickets WHERE booking_id = %s "
        "ORDER BY LEFT(seat_label,1), CAST(SUBSTRING(seat_label,2) AS UNSIGNED)",
        (booking["booking_id"],))
    return booking


# ---------------------------------------------------------------- CREATE (transaction)

def create_booking(user_id, showtime_id, seat_labels, payment_method="cash", trace=None):
    """
    Book several seats in ONE transaction. All-or-nothing.
    `trace` (optional list) receives each SQL step - used by the transaction demo page.
    """
    steps = trace if trace is not None else []

    def step(msg):
        steps.append(msg)
        log.info(msg)

    user_id = to_int(user_id, "User id")
    showtime_id = to_int(showtime_id, "Showtime id")
    if isinstance(seat_labels, str):
        seat_labels = seat_labels.replace(" ", "").split(",")
    seats = []
    for s in seat_labels or []:
        s = (s or "").strip().upper()
        if s and s not in seats:
            seats.append(s)
    if not seats:
        raise ValueError("Please select at least one seat")
    if len(seats) > MAX_SEATS_PER_BOOKING:
        raise ValueError(f"You can book at most {MAX_SEATS_PER_BOOKING} seats at once")
    bad = [s for s in seats if not is_valid_seat(s)]
    if bad:
        raise ValueError(f"Invalid seat(s): {', '.join(bad)}")
    if payment_method not in PAYMENT_METHODS:
        raise ValueError("Invalid payment method")

    conn = get_mysql()
    booking_id = None
    movie_title = ""
    try:
        with conn.cursor() as cur:
            conn.begin()
            step("START TRANSACTION")

            cur.execute(
                "SELECT s.showtime_id, s.price, s.start_time, m.title "
                "FROM showtimes s JOIN movies m ON m.movie_id = s.movie_id "
                "WHERE s.showtime_id = %s LOCK IN SHARE MODE", (showtime_id,))
            st = cur.fetchone()
            if not st:
                raise ValueError("Showtime not found")
            if st["start_time"] <= datetime.now():
                raise ValueError("This showtime has already started")
            movie_title = st["title"]
            step(f"SELECT showtime #{showtime_id} ({movie_title}) price={st['price']}")

            cur.execute("SELECT 1 FROM users WHERE user_id = %s", (user_id,))
            if not cur.fetchone():
                raise ValueError("User not found")

            cur.execute(
                "INSERT INTO bookings (user_id, showtime_id, total_amount, payment_method, status) "
                "VALUES (%s, %s, 0, %s, 'confirmed')", (user_id, showtime_id, payment_method))
            booking_id = cur.lastrowid
            step(f"INSERT INTO bookings -> booking_id={booking_id}")

            for seat in seats:
                try:
                    cur.execute(
                        "INSERT INTO tickets (booking_id, showtime_id, seat_label, price) "
                        "VALUES (%s, %s, %s, %s)", (booking_id, showtime_id, seat, st["price"]))
                    step(f"INSERT INTO tickets seat {seat} -> OK")
                except pymysql.err.IntegrityError as exc:
                    if exc.args and exc.args[0] == 1062:   # ER_DUP_ENTRY
                        step(f"INSERT INTO tickets seat {seat} -> FAILED "
                             f"(Duplicate entry on UNIQUE(showtime_id, seat_label))")
                        raise SeatTakenError(seat)
                    raise

            total = st["price"] * len(seats)
            cur.execute("UPDATE bookings SET total_amount = %s WHERE booking_id = %s",
                        (total, booking_id))
            step(f"UPDATE bookings SET total_amount={total}")
        conn.commit()
        step("COMMIT")
    except SeatTakenError as exc:
        conn.rollback()
        step(f"ROLLBACK -> booking #{booking_id} and every ticket inserted before {exc.seat} are undone")
        _notify(user_id, "Booking failed",
                f"Seat {exc.seat} was already taken, so nothing was booked for "
                f"{', '.join(seats)}. Please pick other seats.")
        raise ValueError(
            f"Seat {exc.seat} is already booked. The whole transaction was rolled back, "
            f"so none of the seats ({', '.join(seats)}) were reserved.")
    except ValueError:
        conn.rollback()
        step("ROLLBACK")
        raise
    except Exception as exc:
        conn.rollback()
        step(f"ROLLBACK ({exc})")
        raise ValueError(f"Booking failed and was rolled back: {exc}")
    finally:
        conn.close()

    # ---- hybrid step: MongoDB, only after the SQL commit succeeded
    try:
        from services.carts import clear_cart
        clear_cart(user_id)
        step("MongoDB carts.deleteOne({user_id}) -> cart cleared")
    except Exception as exc:  # pragma: no cover
        step(f"MongoDB cart clear failed: {exc}")
    if _notify(user_id, f"Booking confirmed #{booking_id}",
               f"Seats {', '.join(sorted(seats, key=_seat_sort_key))} for {movie_title} are confirmed."):
        step("MongoDB notifications.insertOne -> confirmation sent")

    booking = get_booking(booking_id)
    booking["trace"] = steps
    return booking


# ---------------------------------------------------------------- UPDATE

def update_payment_method(booking_id, method, user_id=None):
    booking = get_booking(booking_id)
    if user_id is not None and booking["user_id"] != int(user_id):
        raise ValueError("This is not your booking")
    if method not in PAYMENT_METHODS:
        raise ValueError("Invalid payment method")
    if booking["status"] != "confirmed":
        raise ValueError("Only confirmed bookings can be changed")
    with get_mysql() as conn:
        with conn.cursor() as cur:
            cur.execute("UPDATE bookings SET payment_method=%s WHERE booking_id=%s",
                        (method, booking["booking_id"]))
        conn.commit()
    return get_booking(booking["booking_id"])


def cancel_booking(booking_id, user_id):
    """
    Transaction: lock booking -> DELETE its tickets (frees the seats) ->
    UPDATE booking status='cancelled'. user_id=None means admin.
    """
    booking_id = to_int(booking_id, "Booking id")
    conn = get_mysql()
    try:
        with conn.cursor() as cur:
            conn.begin()
            cur.execute(
                "SELECT b.*, s.start_time, m.title FROM bookings b "
                "JOIN showtimes s ON s.showtime_id = b.showtime_id "
                "JOIN movies m ON m.movie_id = s.movie_id "
                "WHERE b.booking_id = %s FOR UPDATE", (booking_id,))
            b = cur.fetchone()
            if not b:
                raise ValueError("Booking not found")
            if user_id is not None and b["user_id"] != int(user_id):
                raise ValueError("This is not your booking")
            if b["status"] == "cancelled":
                raise ValueError("Booking is already cancelled")
            if b["start_time"] <= datetime.now():
                raise ValueError("Cannot cancel a showtime that has already started")

            cur.execute("SELECT seat_label FROM tickets WHERE booking_id = %s", (booking_id,))
            seats = sorted((r["seat_label"] for r in cur.fetchall()), key=_seat_sort_key)
            cur.execute("DELETE FROM tickets WHERE booking_id = %s", (booking_id,))
            cur.execute(
                "UPDATE bookings SET status='cancelled', cancelled_at=NOW(), cancelled_seats=%s "
                "WHERE booking_id = %s", (", ".join(seats), booking_id))
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()

    _notify(b["user_id"], f"Booking cancelled #{booking_id}",
            f"Seats {', '.join(seats)} for {b['title']} were released.")
    return get_booking(booking_id)


# ---------------------------------------------------------------- DELETE

def delete_booking(booking_id):
    """Admin: permanently remove a booking and its tickets (one transaction)."""
    booking = get_booking(booking_id)
    conn = get_mysql()
    try:
        with conn.cursor() as cur:
            conn.begin()
            cur.execute("DELETE FROM tickets  WHERE booking_id = %s", (booking["booking_id"],))
            cur.execute("DELETE FROM bookings WHERE booking_id = %s", (booking["booking_id"],))
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()
    return {"booking_id": booking["booking_id"], "deleted": True}
