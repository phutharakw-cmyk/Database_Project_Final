"""
Booking transaction tests (Owner: จอมมารปาแปง)

    pytest -v
"""
import pymysql
import pytest

from db import get_mysql
from services import bookings, carts, notifications
from tests.conftest import ALICE, BOB, count_bookings


def seats_of(showtime_id):
    return [r["seat_label"] for r in bookings.get_booked_seats(showtime_id)]


def test_booking_success(showtime):
    sid = showtime["showtime_id"]
    carts.add_seat(ALICE, sid, "A1", showtime["price"])
    carts.add_seat(ALICE, sid, "A2", showtime["price"])
    unread_before = notifications.unread_count(ALICE)["unread"]

    b = bookings.create_booking(ALICE, sid, ["A1", "A2"], "promptpay")

    assert b["status"] == "confirmed"
    assert [t["seat_label"] for t in b["tickets"]] == ["A1", "A2"]
    assert float(b["total_amount"]) == 200.0
    assert seats_of(sid) == ["A1", "A2"]
    assert "COMMIT" in b["trace"]
    # hybrid step: MongoDB cart cleared + notification created
    assert carts.get_cart(ALICE)["items"] == []
    assert notifications.unread_count(ALICE)["unread"] == unread_before + 1


def test_booking_rollback(showtime):
    """A1 + A2 where A2 is already booked -> nothing saved, A1 still free."""
    sid = showtime["showtime_id"]
    bookings.create_booking(BOB, sid, ["A2"])
    assert seats_of(sid) == ["A2"]

    trace = []
    with pytest.raises(ValueError, match="A2 is already booked"):
        bookings.create_booking(ALICE, sid, ["A1", "A2"], trace=trace)

    assert seats_of(sid) == ["A2"]                 # A1 was rolled back
    assert count_bookings(ALICE, sid) == 0         # no partial booking header
    assert any("A1 -> OK" in s for s in trace)     # A1 really was inserted first...
    assert any(s.startswith("ROLLBACK") for s in trace)   # ...then undone

    # A1 is still available for anyone
    b = bookings.create_booking(ALICE, sid, ["A1"])
    assert b["seats"] == "A1"


def test_cancel_booking(showtime):
    sid = showtime["showtime_id"]
    b = bookings.create_booking(ALICE, sid, ["C3", "C4"])

    with pytest.raises(ValueError, match="not your booking"):
        bookings.cancel_booking(b["booking_id"], BOB)

    c = bookings.cancel_booking(b["booking_id"], ALICE)
    assert c["status"] == "cancelled"
    assert c["tickets"] == []
    assert c["cancelled_seats"] == "C3, C4"
    assert seats_of(sid) == []                     # seats released

    with pytest.raises(ValueError, match="already cancelled"):
        bookings.cancel_booking(b["booking_id"], ALICE)

    # released seats can be booked again
    assert bookings.create_booking(BOB, sid, ["C3"])["seats"] == "C3"


def test_unique_constraint_blocks_double_booking(showtime):
    sid = showtime["showtime_id"]
    b = bookings.create_booking(ALICE, sid, ["H10"])
    with get_mysql() as conn, conn.cursor() as cur:
        with pytest.raises(pymysql.err.IntegrityError):
            cur.execute("INSERT INTO tickets (booking_id, showtime_id, seat_label, price) "
                        "VALUES (%s, %s, 'H10', 100)", (b["booking_id"], sid))
        conn.rollback()


def test_invalid_seats_rejected(showtime):
    sid = showtime["showtime_id"]
    with pytest.raises(ValueError, match="Invalid seat"):
        bookings.create_booking(ALICE, sid, ["Z99"])
    with pytest.raises(ValueError, match="at least one seat"):
        bookings.create_booking(ALICE, sid, [])
    assert count_bookings(ALICE, sid) == 0


def test_update_payment_and_delete(showtime):
    sid = showtime["showtime_id"]
    b = bookings.create_booking(ALICE, sid, ["D1"])
    assert bookings.update_payment_method(b["booking_id"], "credit_card", ALICE)["payment_method"] == "credit_card"
    assert bookings.delete_booking(b["booking_id"])["deleted"] is True
    assert seats_of(sid) == []
    with pytest.raises(ValueError):
        bookings.get_booking(b["booking_id"])
