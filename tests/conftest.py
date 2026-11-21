"""
Tests run against the REAL local MySQL + MongoDB from docker-compose
(seeded with database/seed.sql). Each test creates its own showtime and
removes everything it created afterwards.
"""
import os
import sys
from datetime import datetime, timedelta

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from db import execute, query_one  # noqa: E402
from services import showtimes as st_svc  # noqa: E402

ALICE, BOB = 2, 3      # customers from database/seed.sql


@pytest.fixture
def showtime():
    """A brand-new empty showtime (movie 1) in a test hall, deleted after the test."""
    start = (datetime.now() + timedelta(days=30)).replace(second=0, microsecond=0)
    start += timedelta(minutes=os.getpid() % 500)            # unique per run
    st = st_svc.create_showtime(1, "Test Hall", start, 100)
    yield st
    sid = st["showtime_id"]
    execute("DELETE t FROM tickets t WHERE t.showtime_id = %s", (sid,))
    execute("DELETE FROM bookings WHERE showtime_id = %s", (sid,))
    execute("DELETE FROM showtimes WHERE showtime_id = %s", (sid,))


def count_bookings(user_id, showtime_id):
    return query_one("SELECT COUNT(*) AS n FROM bookings WHERE user_id=%s AND showtime_id=%s",
                     (user_id, showtime_id))["n"]
