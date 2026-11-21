"""
demo_rollback.py - terminal demo of the booking transaction (good for the video).

    python scripts/demo_rollback.py            (uses showtime 1)
    python scripts/demo_rollback.py 5          (uses showtime 5)

1. deletes old bookings of the showtime
2. Bob books A2                -> COMMIT
3. Alice books A1 + A2         -> A2 duplicate -> ROLLBACK
4. prints the tickets table before / after  -> A1 is still free
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from services import bookings  # noqa: E402

ALICE, BOB = 2, 3


def show(title, sid):
    seats = [r["seat_label"] for r in bookings.get_booked_seats(sid)]
    print(f"\n{title}: tickets for showtime #{sid} -> {seats or '(none)'}")


def run(sid):
    for b in bookings.list_all_bookings(sid):
        bookings.delete_booking(b["booking_id"])
    show("RESET", sid)

    print("\n--- Bob books A2 ---")
    b = bookings.create_booking(BOB, sid, ["A2"])
    print("\n".join("   " + s for s in b["trace"]))
    show("AFTER BOB", sid)

    print("\n--- Alice books A1 + A2 ---")
    trace = []
    try:
        bookings.create_booking(ALICE, sid, ["A1", "A2"], trace=trace)
    except ValueError as exc:
        print("\n".join("   " + s for s in trace))
        print(f"\n   ValueError: {exc}")
    show("AFTER ALICE (rollback)", sid)
    print("\n=> A1 is still free, Alice has no partial booking.")


if __name__ == "__main__":
    run(int(sys.argv[1]) if len(sys.argv) > 1 else 1)
