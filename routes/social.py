"""Reviews, Watchlist and Notifications screens (Owner: Pen)"""
from flask import Blueprint, render_template, request, redirect, url_for

from routes import login_required, run, current_user_id, back
from services import reviews as review_svc
from services import watchlists as wl_svc
from services import notifications as notif_svc

bp = Blueprint("social", __name__)


# ---------------- reviews (box on the movie detail page)

@bp.route("/movies/<int:movie_id>/reviews", methods=["POST"])
@login_required
def add_review(movie_id):
    run(lambda: review_svc.add_review(current_user_id(), movie_id, request.form.get("rating"),
                                      request.form.get("comment")), "Review posted")
    return redirect(url_for("movies.detail", movie_id=movie_id) + "#reviews")


@bp.route("/reviews/<review_id>/edit", methods=["POST"])
@login_required
def edit_review(review_id):
    r, _ = run(lambda: review_svc.update_review(review_id, current_user_id(), request.form.get("rating"),
                                                request.form.get("comment")), "Review updated")
    return back() if not r else redirect(url_for("movies.detail", movie_id=r["movie_id"]) + "#reviews")


@bp.route("/reviews/<review_id>/delete", methods=["POST"])
@login_required
def delete_review(review_id):
    run(lambda: review_svc.delete_review(review_id, current_user_id()), "Review deleted")
    return back()


# ---------------- watchlist

@bp.route("/watchlist")
@login_required
def watchlist():
    return render_template("social/watchlist.html", items=wl_svc.get_watchlist(current_user_id()))


@bp.route("/watchlist/<int:movie_id>/add", methods=["POST"])
@login_required
def watchlist_add(movie_id):
    run(lambda: wl_svc.add_to_watchlist(current_user_id(), movie_id), "Added to your watchlist")
    return back()


@bp.route("/watchlist/<int:movie_id>/note", methods=["POST"])
@login_required
def watchlist_note(movie_id):
    run(lambda: wl_svc.update_note(current_user_id(), movie_id, request.form.get("note")), "Note saved")
    return redirect(url_for("social.watchlist"))


@bp.route("/watchlist/<int:movie_id>/remove", methods=["POST"])
@login_required
def watchlist_remove(movie_id):
    run(lambda: wl_svc.remove_from_watchlist(current_user_id(), movie_id), "Removed from watchlist")
    return back("social.watchlist")


# ---------------- notifications

@bp.route("/notifications")
@login_required
def notifications():
    return render_template("social/notifications.html",
                           items=notif_svc.list_notifications(current_user_id()))


@bp.route("/notifications/<notif_id>/read", methods=["POST"])
@login_required
def notification_read(notif_id):
    run(lambda: notif_svc.mark_as_read(notif_id, current_user_id()))
    return redirect(url_for("social.notifications"))


@bp.route("/notifications/read-all", methods=["POST"])
@login_required
def notification_read_all():
    run(lambda: notif_svc.mark_all_read(current_user_id()), "All notifications marked as read")
    return redirect(url_for("social.notifications"))


@bp.route("/notifications/<notif_id>/delete", methods=["POST"])
@login_required
def notification_delete(notif_id):
    run(lambda: notif_svc.delete_notification(notif_id, current_user_id()), "Notification deleted")
    return redirect(url_for("social.notifications"))
