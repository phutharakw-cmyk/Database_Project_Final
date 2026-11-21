"""
seats.py - hall seat layout shared by the seat map, cart and booking (Owner: Pooh1tap)

Every hall uses the same layout: rows A-H, seats 1-10  ->  80 seats.
"""
SEAT_ROWS = "ABCDEFGH"
SEATS_PER_ROW = 10
TOTAL_SEATS = len(SEAT_ROWS) * SEATS_PER_ROW


def seat_layout():
    """[['A1'..'A10'], ['B1'..], ...]"""
    return [[f"{r}{n}" for n in range(1, SEATS_PER_ROW + 1)] for r in SEAT_ROWS]


def is_valid_seat(label):
    label = (label or "").upper()
    return (len(label) >= 2 and label[0] in SEAT_ROWS and label[1:].isdigit()
            and 1 <= int(label[1:]) <= SEATS_PER_ROW)


def seat_sort_key(label):
    return (SEAT_ROWS.find(label[0]), int(label[1:]))
