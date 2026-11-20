"""Seat map, Cart and My Bookings screens (Owner: Pooh1tap)"""
from flask import Blueprint, render_template, request, redirect, url_for, flash, g

from routes import login_required, run, current_user_id
from services import showtimes as st_svc
from services import carts as cart_svc
from services import bookings as booking_svc
from services.seats import seat_layout, TOTAL_SEATS

bp = Blueprint("booking", __name__)


def _showtime(showtime_id):
    """get_showtime() plus the fields the booking screens show."""
    st = st_svc.get_showtime(showtime_id)
    st["movie_title"] = st["title"]
    st["seats_left"] = TOTAL_SEATS - st["seats_sold"]
    return st


@bp.route("/showtimes/<int:showtime_id>/seats", methods=["GET", "POST"])
def seat_map(showtime_id):
    try:
        st = _showtime(showtime_id)
    except ValueError as exc:
        flash(str(exc), "danger")
        return redirect(url_for("movies.index"))

    booked = {r["seat_label"] for r in booking_svc.get_booked_seats(showtime_id)}
    uid = current_user_id()

    if request.method == "POST":
        if not uid:
            flash("Please log in to choose seats.", "warning")
            return redirect(url_for("auth.login", next=request.path))
        selected = [s.upper() for s in request.form.getlist("seats")]
        cart = cart_svc.get_cart(uid)
        current = {i["seat_label"] for i in cart["items"]} if cart["showtime_id"] == showtime_id else set()
        try:
            for seat in current - set(selected):
                cart_svc.remove_seat(uid, seat)
            for seat in selected:
                if seat in booked:
                    raise ValueError(f"Seat {seat} is already booked")
                if seat not in current:
                    cart_svc.add_seat(uid, showtime_id, seat, st["price"])
        except ValueError as exc:
            flash(str(exc), "danger")
            return redirect(url_for("booking.seat_map", showtime_id=showtime_id))
        if not selected:
            flash("No seats selected - cart updated.", "info")
            return redirect(url_for("booking.seat_map", showtime_id=showtime_id))
        flash(f"{len(selected)} seat(s) in your cart.", "success")
        return redirect(url_for("booking.cart"))

    in_cart = set()
    if uid:
        cart = cart_svc.get_cart(uid)
        if cart["showtime_id"] == showtime_id:
            in_cart = {i["seat_label"] for i in cart["items"]}
    return render_template("booking/seat_map.html", st=st, layout=seat_layout(),
                           booked=booked, in_cart=in_cart)


@bp.route("/cart")
@login_required
def cart():
    c = cart_svc.get_cart(current_user_id())
    st, taken = None, set()
    if c["showtime_id"]:
        try:
            st = _showtime(c["showtime_id"])
            booked = {r["seat_label"] for r in booking_svc.get_booked_seats(c["showtime_id"])}
            taken = {i["seat_label"] for i in c["items"]} & booked
        except ValueError:
            cart_svc.clear_cart(current_user_id())
            c = cart_svc.get_cart(current_user_id())
    return render_template("booking/cart.html", cart=c, st=st, taken=taken,
                           methods=booking_svc.PAYMENT_METHODS)


@bp.route("/cart/remove", methods=["POST"])
@login_required
def cart_remove():
    run(lambda: cart_svc.remove_seat(current_user_id(), request.form.get("seat_label")), "Seat removed")
    return redirect(url_for("booking.cart"))


@bp.route("/cart/clear", methods=["POST"])
@login_required
def cart_clear():
    run(lambda: cart_svc.clear_cart(current_user_id()), "Cart cleared")
    return redirect(url_for("booking.cart"))


@bp.route("/cart/confirm", methods=["POST"])
@login_required
def cart_confirm():
    uid = current_user_id()
    c = cart_svc.get_cart(uid)
    if not c["items"]:
        flash("Your cart is empty", "warning")
        return redirect(url_for("booking.cart"))
    seats = [i["seat_label"] for i in c["items"]]
    booking, ok = run(lambda: booking_svc.create_booking(
        uid, c["showtime_id"], seats, request.form.get("payment_method", "cash")))
    if ok:
        flash(f"Booking #{booking['booking_id']} confirmed!", "success")
        return redirect(url_for("booking.booking_detail", booking_id=booking["booking_id"], new=1))
    return redirect(url_for("booking.cart"))


@bp.route("/bookings")
@login_required
def my_bookings():
    return render_template("booking/my_bookings.html",
                           bookings=booking_svc.list_bookings(current_user_id()),
                           methods=booking_svc.PAYMENT_METHODS)


@bp.route("/bookings/<int:booking_id>")
@login_required
def booking_detail(booking_id):
    try:
        b = booking_svc.get_booking(booking_id)
    except ValueError as exc:
        flash(str(exc), "danger")
        return redirect(url_for("booking.my_bookings"))
    if b["user_id"] != current_user_id() and g.current_user["role"] != "admin":
        flash("This is not your booking", "danger")
        return redirect(url_for("booking.my_bookings"))
    return render_template("booking/booking_detail.html", b=b, is_new=request.args.get("new"),
                           methods=booking_svc.PAYMENT_METHODS)


@bp.route("/bookings/<int:booking_id>/payment", methods=["POST"])
@login_required
def booking_payment(booking_id):
    run(lambda: booking_svc.update_payment_method(booking_id, request.form.get("payment_method"),
                                                  current_user_id()), "Payment method updated")
    return redirect(request.referrer or url_for("booking.my_bookings"))


@bp.route("/bookings/<int:booking_id>/cancel", methods=["POST"])
@login_required
def booking_cancel(booking_id):
    run(lambda: booking_svc.cancel_booking(booking_id, current_user_id()),
        f"Booking #{booking_id} cancelled - seats released")
    return redirect(url_for("booking.my_bookings"))
