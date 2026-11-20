"""
carts.py - MongoDB collection `carts` (Owner: Pooh1tap)

One cart document per user, holding seats for ONE showtime:
{
  _id, user_id: 2, showtime_id: 8,
  items: [ {seat_label: "F5", price: 150.0}, ... ],
  updated_at: ISODate
}
Seats in a cart are NOT reserved - the SQL transaction decides at confirm time.
"""
from datetime import datetime

from db import get_mongo
from services import doc_to_dict, to_int
from services.seats import is_valid_seat, SEAT_ROWS

MAX_ITEMS = 10


def _sort_items(items):
    return sorted(items, key=lambda i: (SEAT_ROWS.find(i["seat_label"][0]), int(i["seat_label"][1:])))


def get_cart(user_id):
    user_id = to_int(user_id, "User id")
    doc = get_mongo().carts.find_one({"user_id": user_id})
    if not doc:
        return {"id": None, "user_id": user_id, "showtime_id": None, "items": [],
                "total": 0.0, "updated_at": None}
    cart = doc_to_dict(doc)
    cart["items"] = _sort_items(cart.get("items", []))
    cart["total"] = round(sum(float(i["price"]) for i in cart["items"]), 2)
    return cart


def add_seat(user_id, showtime_id, seat_label, price):
    user_id = to_int(user_id, "User id")
    showtime_id = to_int(showtime_id, "Showtime id")
    seat_label = (seat_label or "").strip().upper()
    if not is_valid_seat(seat_label):
        raise ValueError(f"Invalid seat {seat_label}")
    price = float(price)
    carts = get_mongo().carts
    cart = carts.find_one({"user_id": user_id})

    if cart and cart.get("showtime_id") != showtime_id:
        # switching to another showtime starts a fresh cart
        carts.delete_one({"_id": cart["_id"]})
        cart = None
    items = cart["items"] if cart else []
    if any(i["seat_label"] == seat_label for i in items):
        raise ValueError(f"Seat {seat_label} is already in your cart")
    if len(items) >= MAX_ITEMS:
        raise ValueError(f"A cart can hold at most {MAX_ITEMS} seats")

    carts.update_one(
        {"user_id": user_id},
        {"$set": {"showtime_id": showtime_id, "updated_at": datetime.now()},
         "$push": {"items": {"seat_label": seat_label, "price": price}}},
        upsert=True,
    )
    return get_cart(user_id)


def remove_seat(user_id, seat_label):
    user_id = to_int(user_id, "User id")
    seat_label = (seat_label or "").strip().upper()
    res = get_mongo().carts.update_one(
        {"user_id": user_id},
        {"$pull": {"items": {"seat_label": seat_label}}, "$set": {"updated_at": datetime.now()}},
    )
    if res.matched_count == 0:
        raise ValueError("Your cart is empty")
    cart = get_cart(user_id)
    if not cart["items"]:
        clear_cart(user_id)
        return get_cart(user_id)
    return cart


def clear_cart(user_id):
    user_id = to_int(user_id, "User id")
    res = get_mongo().carts.delete_one({"user_id": user_id})
    return {"user_id": user_id, "deleted": res.deleted_count}


def list_all_carts():
    """Admin view of every active cart."""
    out = []
    for doc in get_mongo().carts.find().sort("updated_at", -1):
        c = doc_to_dict(doc)
        c["items"] = _sort_items(c.get("items", []))
        c["total"] = round(sum(float(i["price"]) for i in c["items"]), 2)
        out.append(c)
    return out
