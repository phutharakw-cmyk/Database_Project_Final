"""Shared helpers for all route blueprints."""
from functools import wraps

from flask import g, session, flash, redirect, url_for, request


def login_required(view):
    @wraps(view)
    def wrapper(*args, **kwargs):
        if g.get("current_user") is None:
            flash("Please log in first.", "warning")
            return redirect(url_for("auth.login", next=request.path))
        return view(*args, **kwargs)
    return wrapper


def admin_required(view):
    @wraps(view)
    def wrapper(*args, **kwargs):
        user = g.get("current_user")
        if user is None:
            flash("Please log in first.", "warning")
            return redirect(url_for("auth.login", next=request.path))
        if user["role"] != "admin":
            flash("Admins only.", "danger")
            return redirect(url_for("movies.index"))
        return view(*args, **kwargs)
    return wrapper


def current_user_id():
    user = g.get("current_user")
    return user["user_id"] if user else None


def back(default_endpoint="movies.index", **kwargs):
    """Redirect to the page the form came from (same host only)."""
    ref = request.form.get("next") or request.referrer
    if ref and ref.startswith(request.host_url):
        return redirect(ref)
    return redirect(url_for(default_endpoint, **kwargs))


def run(action, success_msg=None):
    """
    Call a service function. ValueError -> flash as error (this is the web
    version of 'show it in a messagebox'). Returns (result, ok).
    """
    try:
        result = action()
        if success_msg:
            flash(success_msg, "success")
        return result, True
    except ValueError as exc:
        flash(str(exc), "danger")
        return None, False


def login_user(user):
    session.clear()
    session["user_id"] = user["user_id"]
    session.permanent = True
