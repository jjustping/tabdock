"""Reference board for artists: pictures from a folder on the computer, shown on the tablet next to the canvas.

The folder is «Pictures/TabDock Референсы» unless another one is chosen in Settings; every subfolder is a board.
Only pictures inside that folder can be fetched; they are sent as resized JPEG copies made once and cached.
"""
import hashlib
import os

IMAGES = {".jpg", ".jpeg", ".png", ".webp", ".gif", ".heic", ".tif", ".tiff", ".bmp"}
SIZES = {"thumb": 420, "view": 2048}
LIMIT = 600


def default_dir():
    return os.path.join(os.path.expanduser("~"), "Pictures", "TabDock Референсы")


def listing(root):
    """{"dir", "exists", "boards": [{"name", "count"}], "items": [{"rel", "name", "board", "at"}]} — newest first."""
    out = {"dir": root, "exists": os.path.isdir(root), "boards": [], "items": []}
    if not out["exists"]:
        return out
    boards = {}
    for cur, dirs, files in os.walk(root):
        dirs[:] = sorted(d for d in dirs if not d.startswith("."))
        rel_dir = os.path.relpath(cur, root)
        depth = 0 if rel_dir == "." else rel_dir.count(os.sep) + 1
        if depth > 2:
            dirs[:] = []
            continue
        board = "" if rel_dir == "." else rel_dir.split(os.sep)[0]
        for f in files:
            if f.startswith(".") or os.path.splitext(f)[1].lower() not in IMAGES:
                continue
            p = os.path.join(cur, f)
            try:
                at = os.path.getmtime(p)
            except OSError:
                continue
            out["items"].append({"rel": os.path.relpath(p, root).replace(os.sep, "/"), "name": f, "board": board, "at": at})
            if board:
                boards[board] = boards.get(board, 0) + 1
    out["items"].sort(key=lambda i: -i["at"])
    out["items"] = out["items"][:LIMIT]
    out["boards"] = [{"name": b, "count": n} for b, n in sorted(boards.items())]
    return out


def resolve(root, rel):
    """The picture's path, only when it really is inside the folder (no «..», no links out of it)."""
    if not rel or not root:
        return None
    p = os.path.realpath(os.path.join(root, rel.replace("/", os.sep)))
    base = os.path.realpath(root)
    if not p.startswith(base + os.sep) or os.path.splitext(p)[1].lower() not in IMAGES or not os.path.isfile(p):
        return None
    return p


def image(root, rel, size, cache_dir):
    """A resized JPEG copy (made once, remade when the picture changes); None when it is not allowed or fails."""
    src = resolve(root, rel)
    if not src:
        return None
    px = SIZES.get(size, SIZES["thumb"])
    out = os.path.join(cache_dir, "refs", hashlib.sha1(("%s|%d" % (src, px)).encode()).hexdigest()[:20] + ".jpg")
    try:
        if not os.path.exists(out) or os.path.getmtime(out) < os.path.getmtime(src):
            os.makedirs(os.path.dirname(out), exist_ok=True)
            from .osutil import make_jpeg
            if not make_jpeg(src, out, px):
                return None
    except OSError:
        return None
    return out if os.path.exists(out) else None
