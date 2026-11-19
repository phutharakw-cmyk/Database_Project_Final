"""Login / Register / Profile screens (Owner: Debut)"""
from flask import Blueprint, render_template, request, redirect, url_for, flash, session, g

from routes import login_required, run, login_user, current_user_id
from services import users as svc

bp = Blueprint("auth", __name__)


@bp.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        user, ok = run(lambda: svc.login(request.form.get("email"), request.form.get("password")))
        if ok:
            login_user(user)
            flash(f"Welcome back, {user['name']}!", "success")
            nxt = request.args.get("next")
            if nxt and nxt.startswith("/"):
                return redirect(nxt)
            return redirect(url_for("admin.dashboard" if user["role"] == "admin" else "movies.index"))
    return render_template("auth/login.html")


@bp.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        if request.form.get("password") != request.form.get("confirm"):
            flash("Passwords do not match", "danger")
        else:
            user, ok = run(lambda: svc.register(request.form.get("name"), request.form.get("email"),
                                                request.form.get("password")))
            if ok:
                login_user(user)
                from services.notifications import create_notification
                try:
                    create_notification(user["user_id"], "Welcome to MovieTicketSystem",
                                        "Browse movies, pick a showtime and choose your seats.")
                except Exception:
                    pass
                flash("Account created. Enjoy the movies!", "success")
                return redirect(url_for("movies.index"))
    return render_template("auth/register.html")


@bp.route("/logout")
def logout():
    session.clear()
    flash("You have logged out.", "info")
    return redirect(url_for("auth.login"))


@bp.route("/profile", methods=["GET", "POST"])
@login_required
def profile():
    if request.method == "POST":
        run(lambda: svc.update_user(current_user_id(), request.form.get("name"),
                                    request.form.get("email"), request.form.get("phone")),
            "Profile updated")
        return redirect(url_for("auth.profile"))
    return render_template("auth/profile.html", user=g.current_user)


@bp.route("/profile/password", methods=["POST"])
@login_required
def change_password():
    if request.form.get("new") != request.form.get("confirm"):
        flash("New passwords do not match", "danger")
    else:
        run(lambda: svc.change_password(current_user_id(), request.form.get("old"),
                                        request.form.get("new")), "Password changed")
    return redirect(url_for("auth.profile"))


@bp.route("/profile/avatar", methods=["POST"])
@login_required
def upload_avatar():
    run(lambda: svc.save_avatar(current_user_id(), request.files.get("avatar")), "Avatar updated")
    return redirect(url_for("auth.profile"))


@bp.route("/profile/delete", methods=["POST"])
@login_required
def delete_account():
    _, ok = run(lambda: svc.delete_user(current_user_id()))
    if ok:
        session.clear()
        flash("Your account was deleted.", "info")
        return redirect(url_for("auth.login"))
    return redirect(url_for("auth.profile"))
