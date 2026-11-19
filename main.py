"""
main.py - Flask application entry point (Owner: Debut)

    python main.py          -> http://127.0.0.1:5000

The work split's Tkinter `App.show_frame(name)` becomes Flask routes:
each "frame" is a URL + Jinja template, and `current_user` is loaded from
the session on every request (g.current_user, also available in templates).
"""
import logging
import os
from datetime import timedelta

from flask import Flask, g, session, render_template

from db import get_mongo
from services import users as user_service
from services.carts import get_cart
from services.notifications import unread_count

BASE_DIR = os.path.dirname(os.path.abspath(__file__))


def create_app():
    app = Flask(__name__, static_folder="static", template_folder="templates")
    app.config["SECRET_KEY"] = os.getenv("FLASK_SECRET_KEY", "dev-secret-change-me")
    app.config["MAX_CONTENT_LENGTH"] = int(os.getenv("MAX_UPLOAD_MB", "5")) * 1024 * 1024
    app.config["PERMANENT_SESSION_LIFETIME"] = timedelta(days=7)

    from routes.auth import bp as auth_bp
    from routes.movies import bp as movies_bp
    from routes.booking import bp as booking_bp
    from routes.social import bp as social_bp
    from routes.admin import bp as admin_bp
    from routes.api import bp as api_bp
    for bp in (auth_bp, movies_bp, booking_bp, social_bp, admin_bp, api_bp):
        app.register_blueprint(bp)

    @app.before_request
    def load_current_user():
        g.current_user = None
        uid = session.get("user_id")
        if uid:
            try:
                g.current_user = user_service.get_user(uid)
            except ValueError:          # user was deleted
                session.clear()

    @app.context_processor
    def inject_globals():
        user = g.get("current_user")
        badge = {"unread": 0, "cart": 0}
        if user:
            try:
                badge["unread"] = unread_count(user["user_id"])["unread"]
                badge["cart"] = len(get_cart(user["user_id"])["items"])
            except Exception:           # MongoDB down: still render the page
                pass
        return {"current_user": user, "badge": badge}

    @app.template_filter("dt")
    def format_dt(value, fmt="%a %d %b %Y, %H:%M"):
        return value.strftime(fmt) if value else ""

    @app.template_filter("baht")
    def format_baht(value):
        return f"฿{float(value or 0):,.2f}"

    @app.errorhandler(404)
    def not_found(_e):
        return render_template("error.html", code=404, message="Page not found"), 404

    @app.errorhandler(413)
    def too_large(_e):
        return render_template("error.html", code=413, message="File is too large"), 413

    return app


app = create_app()

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(name)s: %(message)s")
    try:
        get_mongo().command("ping")
    except Exception as exc:
        print("WARNING: cannot reach MongoDB:", exc)
    app.run(host="127.0.0.1", port=int(os.getenv("PORT", "5000")),
            debug=os.getenv("FLASK_DEBUG", "1") == "1")
