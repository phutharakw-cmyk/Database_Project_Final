"""
notifications.py - MongoDB collection `notifications` (Owner: Pen)

{ _id, user_id, title, message, is_read, created_at }
Written automatically after booking / cancel / failed booking, or by an admin.
"""
from datetime import datetime

from db import get_mongo, query_all
from services import doc_to_dict, to_object_id, to_int, require_text


def create_notification(user_id, title, message):
    user_id = to_int(user_id, "User id")
    doc = {"user_id": user_id,
           "title": require_text(title, "Title", 120),
           "message": require_text(message, "Message", 1000),
           "is_read": False,
           "created_at": datetime.now()}
    res = get_mongo().notifications.insert_one(doc)
    doc["_id"] = res.inserted_id
    return doc_to_dict(doc)


def broadcast_notification(title, message):
    """Admin: send the same notification to every customer."""
    users = query_all("SELECT user_id FROM users WHERE role='customer'")
    return [create_notification(u["user_id"], title, message) for u in users]


def list_notifications(user_id):
    cur = get_mongo().notifications.find({"user_id": to_int(user_id, "User id")}).sort("created_at", -1)
    return [doc_to_dict(d) for d in cur]


def list_all_notifications(limit=100):
    names = {u["user_id"]: u["name"] for u in query_all("SELECT user_id, name FROM users")}
    out = []
    for d in get_mongo().notifications.find().sort("created_at", -1).limit(limit):
        n = doc_to_dict(d)
        n["user_name"] = names.get(n["user_id"], "(deleted user)")
        out.append(n)
    return out


def unread_count(user_id):
    n = get_mongo().notifications.count_documents({"user_id": to_int(user_id, "User id"), "is_read": False})
    return {"user_id": int(user_id), "unread": n}


def _get_owned(notif_id, user_id):
    doc = get_mongo().notifications.find_one({"_id": to_object_id(notif_id)})
    if not doc:
        raise ValueError("Notification not found")
    if user_id is not None and doc["user_id"] != to_int(user_id, "User id"):
        raise ValueError("This notification is not yours")
    return doc


def mark_as_read(notif_id, user_id=None):
    doc = _get_owned(notif_id, user_id)
    get_mongo().notifications.update_one({"_id": doc["_id"]}, {"$set": {"is_read": True}})
    doc["is_read"] = True
    return doc_to_dict(doc)


def mark_all_read(user_id):
    res = get_mongo().notifications.update_many({"user_id": to_int(user_id, "User id"), "is_read": False},
                                                {"$set": {"is_read": True}})
    return {"user_id": int(user_id), "updated": res.modified_count}


def delete_notification(notif_id, user_id=None):
    doc = _get_owned(notif_id, user_id)
    get_mongo().notifications.delete_one({"_id": doc["_id"]})
    return {"id": str(doc["_id"]), "deleted": True}
