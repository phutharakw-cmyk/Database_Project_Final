"""
Movie list / Movie detail + showtimes / Admin - movies & showtimes (Owner: Phoom)

Public
  /                                movies.index
  /movies/<id>                     movies.detail
Admin
  /admin/movies                    movies.admin_movies        (list + add)
  /admin/movies/<id>/edit          movies.admin_edit_movie
  /admin/movies/<id>/poster        movies.admin_upload_poster
  /admin/movies/<id>/delete        movies.admin_delete_movie
  /admin/movies/<id>/showtimes     movies.admin_showtimes     (list + add)
  /admin/showtimes/<id>/edit       movies.admin_edit_showtime
  /admin/showtimes/<id>/delete     movies.admin_delete_showtime
"""
from datetime import datetime
from itertools import groupby

from flask import Blueprint, render_template, request, redirect, url_for, abort, current_app
from werkzeug.routing import BuildError

from routes import admin_required, run
from services import movies as movie_svc
from services import showtimes as show_svc

bp = Blueprint("movies", __name__)


def _movie_or_404(movie_id):
    try:
        return movie_svc.get_movie(movie_id)
    except ValueError:
        abort(404)


def _showtime_or_404(showtime_id):
    try:
        return show_svc.get_showtime(showtime_id)
    except ValueError:
        abort(404)


def _seat_map_url(showtime_id):
    """Link to the booking screen if that blueprint is registered (owned by another member)."""
    if "booking.seat_map" not in current_app.view_functions:
        return None
    try:
        return url_for("booking.seat_map", showtime_id=showtime_id)
    except BuildError:
        return None


def _movie_form():
    f = request.form
    return {k: f.get(k) for k in ("title", "genre", "duration", "rating", "description", "status")}


# ================================================================ public
@bp.route("/")
@bp.route("/movies")
def index():
    status = request.args.get("status") or None
    if status not in (None, *movie_svc.STATUSES):
        status = None
    q = (request.args.get("q") or "").strip()
    movies = movie_svc.list_movies(status)
    if q:
        needle = q.lower()
        movies = [m for m in movies
                  if needle in m["title"].lower() or needle in m["genre"].lower()]
    return render_template("movies/index.html", movies=movies, status=status, q=q)


@bp.route("/movies/<int:movie_id>")
def detail(movie_id):
    movie = _movie_or_404(movie_id)
    shows = show_svc.list_showtimes(movie_id, upcoming_only=True)
    for s in shows:
        s["book_url"] = _seat_map_url(s["showtime_id"])
    days = [(day, list(items)) for day, items in groupby(shows, key=lambda s: s["start_time"].date())]
    return render_template("movies/detail.html", movie=movie, days=days)


# ================================================================ admin - movies
@bp.route("/admin/movies", methods=["GET", "POST"])
@admin_required
def admin_movies():
    if request.method == "POST":
        data = _movie_form()
        movie, ok = run(lambda: movie_svc.create_movie(**data), "Movie added")
        if ok:
            poster = request.files.get("poster")
            if poster and poster.filename:
                run(lambda: movie_svc.save_poster(movie["movie_id"], poster))
            return redirect(url_for("movies.admin_showtimes", movie_id=movie["movie_id"]))
    return render_template("movies/admin_movies.html", movies=movie_svc.list_movies(),
                           ratings=movie_svc.RATINGS, statuses=movie_svc.STATUSES,
                           form=request.form)


@bp.route("/admin/movies/<int:movie_id>/edit", methods=["GET", "POST"])
@admin_required
def admin_edit_movie(movie_id):
    movie = _movie_or_404(movie_id)
    if request.method == "POST":
        _, ok = run(lambda: movie_svc.update_movie(movie_id, **_movie_form()), "Movie updated")
        if ok:
            return redirect(url_for("movies.admin_movies"))
        movie = {**movie, **request.form}  # keep what the admin typed
    return render_template("movies/admin_movie_form.html", movie=movie,
                           ratings=movie_svc.RATINGS, statuses=movie_svc.STATUSES)


@bp.route("/admin/movies/<int:movie_id>/poster", methods=["POST"])
@admin_required
def admin_upload_poster(movie_id):
    run(lambda: movie_svc.save_poster(movie_id, request.files.get("poster")), "Poster updated")
    return redirect(url_for("movies.admin_edit_movie", movie_id=movie_id))


@bp.route("/admin/movies/<int:movie_id>/delete", methods=["POST"])
@admin_required
def admin_delete_movie(movie_id):
    run(lambda: movie_svc.delete_movie(movie_id), "Movie deleted")
    return redirect(url_for("movies.admin_movies"))


# ================================================================ admin - showtimes
@bp.route("/admin/movies/<int:movie_id>/showtimes", methods=["GET", "POST"])
@admin_required
def admin_showtimes(movie_id):
    movie = _movie_or_404(movie_id)
    if request.method == "POST":
        f = request.form
        _, ok = run(lambda: show_svc.create_showtime(movie_id, f.get("hall"), f.get("start_time"),
                                                     f.get("price")), "Showtime added")
        if ok:
            return redirect(url_for("movies.admin_showtimes", movie_id=movie_id))
    return render_template("movies/admin_showtimes.html", movie=movie,
                           showtimes=show_svc.list_showtimes(movie_id), form=request.form,
                           now=datetime.now(), cleanup_min=show_svc.CLEANUP_MIN)


@bp.route("/admin/showtimes/<int:showtime_id>/edit", methods=["GET", "POST"])
@admin_required
def admin_edit_showtime(showtime_id):
    show = _showtime_or_404(showtime_id)
    if request.method == "POST":
        f = request.form
        fields = {"price": f.get("price")}
        if not show["seats_sold"]:  # locked fields are not in the form when seats are sold
            fields.update(movie_id=f.get("movie_id"), hall=f.get("hall"),
                          start_time=f.get("start_time"))
        updated, ok = run(lambda: show_svc.update_showtime(showtime_id, **fields), "Showtime updated")
        if ok:
            return redirect(url_for("movies.admin_showtimes", movie_id=updated["movie_id"]))
    return render_template("movies/admin_showtime_form.html", show=show,
                           movies=[m for m in movie_svc.list_movies() if m["status"] != "ended"
                                   or m["movie_id"] == show["movie_id"]],
                           form=request.form)


@bp.route("/admin/showtimes/<int:showtime_id>/delete", methods=["POST"])
@admin_required
def admin_delete_showtime(showtime_id):
    show = _showtime_or_404(showtime_id)
    run(lambda: show_svc.delete_showtime(showtime_id), "Showtime deleted")
    return redirect(url_for("movies.admin_showtimes", movie_id=show["movie_id"]))
