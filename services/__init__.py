"""
Service layer. Every public function:
  * returns a dict or a list of dicts on success
  * raises ValueError("message") on a user-facing error (the route shows it)
"""
from bson import ObjectId
from bson.errors import InvalidId


def doc_to_dict(doc):
    """Convert a MongoDB document to a plain dict with a string `id`."""
    if doc is None:
        return None
    out = dict(doc)
    out["id"] = str(out.pop("_id"))
    return out


def to_object_id(value):
    """Parse a string id from a URL/form into an ObjectId or raise ValueError."""
    try:
        return ObjectId(str(value))
    except (InvalidId, TypeError):
        raise ValueError("Invalid id")


def to_int(value, field):
    try:
        return int(value)
    except (TypeError, ValueError):
        raise ValueError(f"{field} must be a number")


def require_text(value, field, max_len=None):
    value = (value or "").strip()
    if not value:
        raise ValueError(f"{field} is required")
    if max_len and len(value) > max_len:
        raise ValueError(f"{field} must be at most {max_len} characters")
    return value
