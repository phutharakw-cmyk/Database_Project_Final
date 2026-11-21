"""
Admin screens:
  movies / showtimes (Phoom), bookings + transaction demo (Mizt), users (Debut),
  reviews / notifications (Verity), carts (Pooh1tap)
"""
from flask import Blueprint, render_template, request, redirect, url_for, flash, g

from db import get_mongo, query_one, query_all
from routes import admin_required, run
from services import movies as movie_svc
from services import showtimes as st_svc
from services import bookings as booking_svc
from services import users as user_svc
from services import reviews as review_svc
from services import notifications as notif_svc
from services import carts as cart_svc

bp = Blueprint("admin", __name__, url_prefix="/admin")


@bp.route("/")
@admin_required
def dashboard():
    sql = query_one("""
        SELECT (SELECT COUNT(*) FROM users)     AS users,
               (SELECT COUNT(*) FROM movies)    AS movies,
               (SELECT COUNT(*) FROM showtimes) AS showtimes,
               (SELECT COUNT(*) FROM bookings WHERE status='confirmed') AS bookings,
               (SELECT COUNT(*) FROM tickets)   AS tickets,
               (SELECT COALESCE(SUM(total_amount),0) FROM bookings WHERE status='confirmed') AS revenue""")
    mongo = get_mongo()
    nosql = {c: mongo[c].count_documents({}) for c in ("carts", "reviews", "watchlists", "notifications")}
    top = query_all("""
        SELECT m.title, COUNT(t.ticket_id) AS sold, COALESCE(SUM(t.price),0) AS revenue
          FROM movies m
          LEFT JOIN showtimes s ON s.movie_id = m.movie_id
          LEFT JOIN tickets t   ON t.showtime_id = s.showtime_id
         GROUP BY m.movie_id, m.title ORDER BY sold DESC LIMIT 5""")
    recent = booking_svc.list_all_bookings()[:8]
    return render_template("admin/dashboard.html", sql=sql, nosql=nosql, top=top, recent=recent)


# ------------------------------------------------------------ movies

@bp.route("/movies", methods=["GET", "POST"])
@admin_required
def movies():
    if request.method == "POST":
        f = request.form
        movie, ok = run(lambda: movie_svc.create_movie(f.get("title"), f.get("genre"), f.get("duration_min"),
                                                       f.get("rating"), f.get("description"),
                                                       f.get("status", "now_showing")),
                        "Movie created")
        if ok and request.files.get("poster") and request.files["poster"].filename:
            run(lambda: movie_svc.save_poster(movie["movie_id"], request.files["poster"]))
        return redirect(url_for("admin.movies"))
    return render_template("admin/movies.html", movies=movie_svc.list_movies(),
                           genres=movie_svc.GENRES, ratings=movie_svc.RATINGS, statuses=movie_svc.STATUSES)


@bp.route("/movies/<int:movie_id>/edit", methods=["GET", "POST"])
@admin_required
def movie_edit(movie_id):
    if request.method == "POST":
        f = request.form
        _, ok = run(lambda: movie_svc.update_movie(
            movie_id, title=f.get("title"), genre=f.get("genre"), duration_min=f.get("duration_min"),
            rating=f.get("rating"), description=f.get("description"), status=f.get("status")),
            "Movie updated")
        if ok and request.files.get("poster") and request.files["poster"].filename:
            run(lambda: movie_svc.save_poster(movie_id, request.files["poster"]), "Poster uploaded")
        return redirect(url_for("admin.movie_edit", movie_id=movie_id))
    try:
        movie = movie_svc.get_movie(movie_id)
    except ValueError as exc:
        flash(str(exc), "danger")
        return redirect(url_for("admin.movies"))
    return render_template("admin/movie_edit.html", movie=movie, showtimes=st_svc.list_showtimes(movie_id),
                           genres=movie_svc.GENRES, ratings=movie_svc.RATINGS, statuses=movie_svc.STATUSES)


@bp.route("/movies/<int:movie_id>/delete", methods=["POST"])
@admin_required
def movie_delete(movie_id):
    run(lambda: movie_svc.delete_movie(movie_id), "Movie deleted")
    return redirect(url_for("admin.movies"))


# ------------------------------------------------------------ showtimes

@bp.route("/showtimes", methods=["GET", "POST"])
@admin_required
def showtimes():
    if request.method == "POST":
        f = request.form
        run(lambda: st_svc.create_showtime(f.get("movie_id"), f.get("hall"), f.get("start_time"), f.get("price")),
            "Showtime created")
        return redirect(url_for("admin.showtimes"))
    return render_template("admin/showtimes.html", showtimes=st_svc.list_showtimes(),
                           movies=movie_svc.list_movies(), halls=st_svc.HALLS,
                           preselect=request.args.get("movie_id", type=int))


@bp.route("/showtimes/<int:showtime_id>/edit", methods=["GET", "POST"])
@admin_required
def showtime_edit(showtime_id):
    if request.method == "POST":
        f = request.form
        _, ok = run(lambda: st_svc.update_showtime(showtime_id, movie_id=f.get("movie_id"), hall=f.get("hall"),
                                                   start_time=f.get("start_time"), price=f.get("price")),
                    "Showtime updated")
        if ok:
            return redirect(url_for("admin.showtimes"))
    try:
        st = st_svc.get_showtime(showtime_id)
    except ValueError as exc:
        flash(str(exc), "danger")
        return redirect(url_for("admin.showtimes"))
    return render_template("admin/showtime_edit.html", st=st, movies=movie_svc.list_movies(), halls=st_svc.HALLS)


@bp.route("/showtimes/<int:showtime_id>/delete", methods=["POST"])
@admin_required
def showtime_delete(showtime_id):
    run(lambda: st_svc.delete_showtime(showtime_id), "Showtime deleted")
    return redirect(url_for("admin.showtimes"))


# ------------------------------------------------------------ bookings

@bp.route("/bookings")
@admin_required
def bookings():
    sid = request.args.get("showtime_id", type=int)
    status = request.args.get("status") or None
    return render_template("admin/bookings.html",
                           bookings=booking_svc.list_all_bookings(sid, status),
                           showtimes=st_svc.list_showtimes(), sid=sid, status=status,
                           methods=booking_svc.PAYMENT_METHODS)


@bp.route("/bookings/<int:booking_id>/payment", methods=["POST"])
@admin_required
def booking_payment(booking_id):
    run(lambda: booking_svc.update_payment_method(booking_id, request.form.get("payment_method")),
        "Payment method updated")
    return redirect(request.referrer or url_for("admin.bookings"))


@bp.route("/bookings/<int:booking_id>/cancel", methods=["POST"])
@admin_required
def booking_cancel(booking_id):
    run(lambda: booking_svc.cancel_booking(booking_id, None), f"Booking #{booking_id} cancelled")
    return redirect(request.referrer or url_for("admin.bookings"))


@bp.route("/bookings/<int:booking_id>/delete", methods=["POST"])
@admin_required
def booking_delete(booking_id):
    run(lambda: booking_svc.delete_booking(booking_id), f"Booking #{booking_id} deleted")
    return redirect(request.referrer or url_for("admin.bookings"))


@bp.route("/transaction-demo", methods=["GET", "POST"])
@admin_required
def transaction_demo():
    """Run create_booking() and show tickets BEFORE / SQL steps / tickets AFTER."""
    sid = request.values.get("showtime_id", 1, type=int)
    result = None
    before = booking_svc.get_booked_seats(sid) if query_one(
        "SELECT 1 FROM showtimes WHERE showtime_id=%s", (sid,)) else []

    if request.method == "POST" and request.form.get("action") == "reset":
        n = 0
        for b in booking_svc.list_all_bookings(sid):
            booking_svc.delete_booking(b["booking_id"])
            n += 1
        flash(f"Demo reset: {n} booking(s) for showtime #{sid} deleted.", "info")
        return redirect(url_for("admin.transaction_demo", showtime_id=sid))

    if request.method == "POST":
        trace = []
        seats = request.form.get("seats", "")
        uid = request.form.get("user_id", type=int)
        try:
            booking = booking_svc.create_booking(uid, sid, seats, "cash", trace=trace)
            result = {"ok": True, "message": f"COMMIT - booking #{booking['booking_id']} saved "
                                             f"with seats {booking['seats']}", "trace": trace}
        except ValueError as exc:
            result = {"ok": False, "message": str(exc), "trace": trace}

    after = booking_svc.get_booked_seats(sid) if result else None
    return render_template("admin/transaction_demo.html", sid=sid, before=before, after=after,
                           result=result, users=user_svc.list_users(),
                           showtimes=st_svc.list_showtimes(upcoming_only=True),
                           form=request.form)


# ------------------------------------------------------------ users

@bp.route("/users")
@admin_required
def users():
    return render_template("admin/users.html", users=user_svc.list_users())


@bp.route("/users/<int:user_id>/edit", methods=["GET", "POST"])
@admin_required
def user_edit(user_id):
    if request.method == "POST":
        f = request.form
        _, ok = run(lambda: user_svc.update_user(user_id, f.get("name"), f.get("email"), f.get("phone")))
        if ok and f.get("role") and user_id != g.current_user["user_id"]:
            run(lambda: user_svc.set_role(user_id, f.get("role")))
        if ok:
            flash("User updated", "success")
            return redirect(url_for("admin.users"))
    try:
        user = user_svc.get_user(user_id)
    except ValueError as exc:
        flash(str(exc), "danger")
        return redirect(url_for("admin.users"))
    return render_template("admin/user_edit.html", user=user, bookings=booking_svc.list_bookings(user_id))


@bp.route("/users/<int:user_id>/delete", methods=["POST"])
@admin_required
def user_delete(user_id):
    if user_id == g.current_user["user_id"]:
        flash("You cannot delete your own admin account here.", "danger")
    else:
        run(lambda: user_svc.delete_user(user_id), "User deleted (with bookings, cart, reviews, watchlist, notifications)")
    return redirect(url_for("admin.users"))


# ------------------------------------------------------------ reviews / notifications / carts (MongoDB)

@bp.route("/reviews")
@admin_required
def reviews():
    return render_template("admin/reviews.html", reviews=review_svc.list_all_reviews())


@bp.route("/reviews/<review_id>/delete", methods=["POST"])
@admin_required
def review_delete(review_id):
    run(lambda: review_svc.delete_review(review_id, None), "Review removed")
    return redirect(url_for("admin.reviews"))


@bp.route("/notifications", methods=["GET", "POST"])
@admin_required
def notifications():
    if request.method == "POST":
        f = request.form
        if f.get("user_id") == "all":
            res, ok = run(lambda: notif_svc.broadcast_notification(f.get("title"), f.get("message")))
            if ok:
                flash(f"Sent to {len(res)} customer(s)", "success")
        else:
            run(lambda: notif_svc.create_notification(f.get("user_id"), f.get("title"), f.get("message")),
                "Notification sent")
        return redirect(url_for("admin.notifications"))
    return render_template("admin/notifications.html", items=notif_svc.list_all_notifications(),
                           users=user_svc.list_users())


@bp.route("/notifications/<notif_id>/delete", methods=["POST"])
@admin_required
def notification_delete(notif_id):
    run(lambda: notif_svc.delete_notification(notif_id, None), "Notification deleted")
    return redirect(url_for("admin.notifications"))


@bp.route("/carts")
@admin_required
def carts():
    names = {u["user_id"]: u["name"] for u in user_svc.list_users()}
    return render_template("admin/carts.html", carts=cart_svc.list_all_carts(), names=names)


@bp.route("/carts/<int:user_id>/clear", methods=["POST"])
@admin_required
def cart_clear(user_id):
    run(lambda: cart_svc.clear_cart(user_id), "Cart cleared")
    return redirect(url_for("admin.carts"))
