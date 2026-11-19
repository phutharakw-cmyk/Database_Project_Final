"""
uploads.py - store images on the app server's own disk (no external hosting).

Files go to  static/uploads/<subfolder>/<uuid>.<ext>
The DB stores the path relative to /static, e.g. "uploads/posters/ab12.png".
"""
import os
import shutil
import uuid

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
STATIC_DIR = os.path.join(BASE_DIR, "static")
UPLOAD_ROOT = os.path.join(BASE_DIR, os.getenv("UPLOAD_FOLDER", "static/uploads"))
ALLOWED_EXT = {"png", "jpg", "jpeg", "gif", "webp"}


def _ext(filename):
    if not filename or "." not in filename:
        raise ValueError("Please choose an image file (png, jpg, jpeg, gif, webp)")
    ext = filename.rsplit(".", 1)[1].lower()
    if ext not in ALLOWED_EXT:
        raise ValueError("Only png, jpg, jpeg, gif or webp images are allowed")
    return ext


def save_image(source, subfolder):
    """
    source = a Werkzeug FileStorage (from a web form) OR a path to a local file.
    Returns the path relative to /static.
    """
    if source is None:
        raise ValueError("No file selected")
    filename = getattr(source, "filename", None) or str(source)
    ext = _ext(os.path.basename(filename))
    folder = os.path.join(UPLOAD_ROOT, subfolder)
    os.makedirs(folder, exist_ok=True)
    new_name = f"{uuid.uuid4().hex}.{ext}"
    dest = os.path.join(folder, new_name)

    if hasattr(source, "save"):          # uploaded through the browser
        source.save(dest)
    else:                                 # local path (scripts / tests)
        if not os.path.isfile(source):
            raise ValueError("File not found")
        shutil.copyfile(source, dest)

    rel_upload = os.path.relpath(UPLOAD_ROOT, STATIC_DIR).replace(os.sep, "/")
    return f"{rel_upload}/{subfolder}/{new_name}"


def delete_image(rel_path):
    """Delete an uploaded file (seed images are kept)."""
    if not rel_path or os.path.basename(rel_path).startswith("seed_"):
        return
    full = os.path.join(STATIC_DIR, rel_path)
    if os.path.isfile(full):
        os.remove(full)
