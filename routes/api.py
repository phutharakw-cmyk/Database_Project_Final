"""
Small JSON API (same service functions as the web pages).
Auth = the normal login session cookie. Errors -> {"error": "..."} with HTTP 400.
"""
from flask import Blueprint, jsonify, request

from routes import current_user_id
from services import movies as movie_svc
from services import showtimes as st_svc
from services import bookings as booking_svc
from services import reviews as review_svc
from services import carts as cart_svc
from services import notifications as notif_svc

bp = Blueprint("api", __name__, url_prefix="/api")


@bp.errorhandler(ValueError)
def bad_request(exc):
    return jsonify({"error": str(exc)}), 400


def _need_login():
    uid = current_user_id()
    if not uid:
        raise ValueError("Login required")
    return uid


@bp.get("/movies")
def movies():
    return jsonify(movie_svc.list_movies(status=request.args.get("status"), search=request.args.get("q")))


@bp.get("/movies/<int:movie_id>")
def movie(movie_id):
    m = movie_svc.get_movie(movie_id)
    m["showtimes"] = st_svc.list_showtimes(movie_id, upcoming_only=True)
    m["rating_summary"] = review_svc.get_average_rating(movie_id)
    return jsonify(m)


@bp.get("/movies/<int:movie_id>/reviews")
def movie_reviews(movie_id):
    return jsonify(review_svc.list_reviews(movie_id))


@bp.get("/showtimes/<int:showtime_id>/booked-seats")
def booked_seats(showtime_id):
    return jsonify(booking_svc.get_booked_seats(showtime_id))


@bp.get("/me/cart")
def my_cart():
    return jsonify(cart_svc.get_cart(_need_login()))


@bp.get("/me/bookings")
def my_bookings():
    return jsonify(booking_svc.list_bookings(_need_login()))


@bp.get("/me/notifications")
def my_notifications():
    return jsonify(notif_svc.list_notifications(_need_login()))


@bp.post("/bookings")
def create_booking():
    """Body: {"showtime_id": 1, "seats": ["A1","A2"], "payment_method": "cash"}"""
    data = request.get_json(silent=True) or {}
    b = booking_svc.create_booking(_need_login(), data.get("showtime_id"), data.get("seats") or [],
                                   data.get("payment_method", "cash"))
    return jsonify(b), 201


@bp.post("/bookings/<int:booking_id>/cancel")
def cancel_booking(booking_id):
    return jsonify(booking_svc.cancel_booking(booking_id, _need_login()))
