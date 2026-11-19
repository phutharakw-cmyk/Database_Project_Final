"""
users.py - SQL table `users` (Owner: Debut)
"""
import re

import pymysql
from werkzeug.security import generate_password_hash, check_password_hash

from db import get_mysql, get_mongo, query_all, query_one, execute
from services import require_text, to_int
from services.uploads import save_image, delete_image

EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
PUBLIC_COLS = "user_id, name, email, phone, role, avatar_path, created_at"


def _clean_email(email):
    email = require_text(email, "Email", 150).lower()
    if not EMAIL_RE.match(email):
        raise ValueError("Email format is not valid")
    return email


def _check_password(password):
    if not password or len(password) < 6:
        raise ValueError("Password must be at least 6 characters")


def register(name, email, password):
    name = require_text(name, "Name", 100)
    email = _clean_email(email)
    _check_password(password)
    try:
        _, new_id = execute(
            "INSERT INTO users (name, email, password_hash) VALUES (%s, %s, %s)",
            (name, email, generate_password_hash(password, method="pbkdf2:sha256")),
        )
    except pymysql.err.IntegrityError:
        raise ValueError("This email is already registered")
    return get_user(new_id)


def login(email, password):
    email = (email or "").strip().lower()
    row = query_one("SELECT * FROM users WHERE email = %s", (email,))
    if not row or not check_password_hash(row["password_hash"], password or ""):
        raise ValueError("Invalid email or password")
    row.pop("password_hash", None)
    return row


def get_user(user_id):
    row = query_one(f"SELECT {PUBLIC_COLS} FROM users WHERE user_id = %s",
                    (to_int(user_id, "User id"),))
    if not row:
        raise ValueError("User not found")
    return row


def list_users():
    return query_all(
        f"""SELECT {PUBLIC_COLS},
                   (SELECT COUNT(*) FROM bookings b
                     WHERE b.user_id = u.user_id AND b.status = 'confirmed') AS booking_count
              FROM users u ORDER BY user_id"""
    )


def update_user(user_id, name, email, phone):
    user_id = to_int(user_id, "User id")
    name = require_text(name, "Name", 100)
    email = _clean_email(email)
    phone = (phone or "").strip() or None
    if phone and not re.fullmatch(r"[0-9+\- ]{6,20}", phone):
        raise ValueError("Phone may contain only digits, +, - and spaces")
    get_user(user_id)
    try:
        execute("UPDATE users SET name=%s, email=%s, phone=%s WHERE user_id=%s",
                (name, email, phone, user_id))
    except pymysql.err.IntegrityError:
        raise ValueError("This email is already used by another account")
    return get_user(user_id)


def set_role(user_id, role):
    if role not in ("customer", "admin"):
        raise ValueError("Role must be customer or admin")
    execute("UPDATE users SET role=%s WHERE user_id=%s", (role, to_int(user_id, "User id")))
    return get_user(user_id)


def change_password(user_id, old, new):
    user_id = to_int(user_id, "User id")
    row = query_one("SELECT password_hash FROM users WHERE user_id=%s", (user_id,))
    if not row:
        raise ValueError("User not found")
    if not check_password_hash(row["password_hash"], old or ""):
        raise ValueError("Current password is incorrect")
    _check_password(new)
    execute("UPDATE users SET password_hash=%s WHERE user_id=%s",
            (generate_password_hash(new, method="pbkdf2:sha256"), user_id))
    return {"user_id": user_id, "changed": True}


def save_avatar(user_id, file_path):
    """file_path = uploaded FileStorage or a local file path."""
    user = get_user(user_id)
    new_path = save_image(file_path, "avatars")
    execute("UPDATE users SET avatar_path=%s WHERE user_id=%s", (new_path, user["user_id"]))
    delete_image(user.get("avatar_path"))
    return get_user(user["user_id"])


def delete_user(user_id):
    """Delete the user (bookings + tickets cascade in SQL) and their MongoDB documents."""
    user = get_user(user_id)
    uid = user["user_id"]
    if user["role"] == "admin":
        admins = query_one("SELECT COUNT(*) AS n FROM users WHERE role='admin'")["n"]
        if admins <= 1:
            raise ValueError("Cannot delete the last admin account")

    conn = get_mysql()
    try:
        with conn.cursor() as cur:
            conn.begin()
            cur.execute("DELETE t FROM tickets t JOIN bookings b ON b.booking_id = t.booking_id "
                        "WHERE b.user_id = %s", (uid,))
            cur.execute("DELETE FROM bookings WHERE user_id = %s", (uid,))
            cur.execute("DELETE FROM users WHERE user_id = %s", (uid,))
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()

    mongo = get_mongo()
    for coll in ("carts", "reviews", "watchlists", "notifications"):
        mongo[coll].delete_many({"user_id": uid})
    delete_image(user.get("avatar_path"))
    return {"user_id": uid, "deleted": True}
