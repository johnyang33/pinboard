import os
from flask import Flask, render_template, abort, send_from_directory,jsonify,request
import json
from dotenv import load_dotenv

load_dotenv()

port = int(os.environ.get("FLASK_PORT", 6001))

app = Flask(__name__)


app = Flask(__name__)

MEDIA_ROOT = os.path.join(app.root_path, "media")

IMAGE_EXTS = {".jpg", ".jpeg", ".png", ".gif", ".webp"}
VIDEO_EXTS = {".mp4", ".webm", ".mov"}
AUDIO_EXTS = {".mp3", ".wav", ".ogg", ".m4a", ".opus"}
FAVORITES_FILE = os.path.join(app.root_path, "favorites.json")

RATINGS_FILE = os.path.join(app.root_path, "ratings.json")

# --------------------------------
# HELPERS
# --------------------------------

def load_ratings():
    if not os.path.exists(RATINGS_FILE):
        return {}
    with open(RATINGS_FILE, "r") as f:
        return json.load(f)

def save_ratings(ratings):
    with open(RATINGS_FILE, "w") as f:
        json.dump(ratings, f, indent=2)

def load_favorites():
    if not os.path.exists(FAVORITES_FILE):
        return {}
    with open(FAVORITES_FILE, "r") as f:
        return json.load(f)

def save_favorites(favs):
    with open(FAVORITES_FILE, "w") as f:
        json.dump(favs, f, indent=2)

def is_safe_path(path):
    # Prevent directory traversal
    abs_path = os.path.abspath(path)
    return abs_path.startswith(os.path.abspath(MEDIA_ROOT))

def list_media(folder_path, rel_path, favorites_only=False):
    favorites = load_favorites()
    ratings = load_ratings()  # ADD THIS

    images = []
    videos = []
    audios = []

    for name in sorted(os.listdir(folder_path)):
        full = os.path.join(folder_path, name)
        if not os.path.isfile(full):
            continue

        ext = os.path.splitext(name)[1].lower()
        rel_file = f"{rel_path}/{name}"
        is_fav = rel_file in favorites
        rating = ratings.get(rel_file, 0)  # ADD THIS
        display_name = os.path.splitext(name)[0].replace("_", " ").replace("-", " ").title()

        if favorites_only and not is_fav:
            continue

        item = {
            "name": name,
            "display_name": display_name,
            "path": rel_file,
            "favorite": is_fav,
            "rating": rating   # ADD THIS
        }

        if ext in IMAGE_EXTS:
            images.append(item)
        elif ext in VIDEO_EXTS:
            videos.append(item)
        elif ext in AUDIO_EXTS:
            audios.append(item)

    # Sort by rating (high → low), then favorite, then name
    def sort_key(item):
        return (-item["rating"], not item["favorite"], item["name"].lower())

    images.sort(key=sort_key)
    videos.sort(key=sort_key)
    audios.sort(key=sort_key)

    return images, videos, audios

def count_media_files(folder):
    count = 0
    for name in os.listdir(folder):
        full = os.path.join(folder, name)
        if os.path.isfile(full):
            ext = os.path.splitext(name)[1].lower()
            if ext in IMAGE_EXTS or ext in VIDEO_EXTS or ext in AUDIO_EXTS:
                count += 1
    return count

def mark_active(tree, current_path):
    """
    Marks nodes as active/open if they are in the current path
    """
    for node in tree:
        node["active"] = current_path.startswith(node["path"])
        if node["children"]:
            mark_active(node["children"], current_path)

def format_bytes(size):
    for unit in ("B", "KB", "MB", "GB", "TB"):
        if size < 1024:
            return f"{size:.2f} {unit}"
        size /= 1024

def get_folder_size(path):
    total = 0
    for root, dirs, files in os.walk(path):
        for f in files:
            try:
                fp = os.path.join(root, f)
                total += os.path.getsize(fp)
            except OSError:
                pass  # skip unreadable files
    return total

def build_media_tree(base_path, rel_path=""):
    abs_path = os.path.join(base_path, rel_path)
    tree = []

    for name in sorted(os.listdir(abs_path)):
        full = os.path.join(abs_path, name)
        if not os.path.isdir(full):
            continue

        sub_rel = os.path.join(rel_path, name) if rel_path else name

        children = build_media_tree(base_path, sub_rel)

        size = get_folder_size(full)

        node = {
            "name": name,
            "path": sub_rel.replace("\\", "/"),
            "file_count": count_media_files(full),
            "folder_count": len(children),
            "size_bytes": get_folder_size(full),
            "size": format_bytes(size),
            "children": children,
            "active": False
        }

        tree.append(node)

    return tree

# -------------------------------
# BREADCRUMBS
# -------------------------------

def build_breadcrumbs(*parts):
    crumbs = [{"name": "Home", "url": "/"}]
    path = ""

    for part in parts:
        path += f"/{part}"
        crumbs.append({
            "name": part,
            "url": f"/gallery{path}"
        })

    return crumbs

# -------------------------------
# ROUTES
# -------------------------------

@app.route("/")
def index():
    tree = build_media_tree(MEDIA_ROOT)
    mark_active(tree, "")
    return render_template("index.html", tree=tree)


# DELETE 
@app.route("/media/delete", methods=["POST"])
def delete_media():
    data = request.json
    rel_path = data.get("path")

    if not rel_path:
        return jsonify({"error": "Missing path"}), 400

    full_path = os.path.join(MEDIA_ROOT, rel_path)

    if not is_safe_path(full_path):
        return jsonify({"error": "Invalid path"}), 400

    if not os.path.isfile(full_path):
        return jsonify({"error": "File not found"}), 404

    try:
        os.remove(full_path)

        # Remove from favorites if it exists
        favorites = load_favorites()
        if rel_path in favorites:
            del favorites[rel_path]
            save_favorites(favorites)

        ratings = load_ratings()
        if rel_path in ratings:
            del ratings[rel_path]
            save_ratings(ratings)

        return jsonify({"success": True})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

# SET RATING
@app.route("/rating/set", methods=["POST"])
def set_rating():
    data = request.json
    rel_path = data.get("path")
    rating = int(data.get("rating", 0))

    if not rel_path or rating < 0 or rating > 10:
        return jsonify({"error": "Invalid input"}), 400

    full_path = os.path.join(MEDIA_ROOT, rel_path)

    if not is_safe_path(full_path):
        return jsonify({"error": "Invalid path"}), 400

    ratings = load_ratings()

    if rating == 0:
        ratings.pop(rel_path, None)
    else:
        ratings[rel_path] = rating

    save_ratings(ratings)

    return jsonify({"success": True, "rating": rating})


# RENAME 
@app.route("/media/rename", methods=["POST"])
def rename_media():
    data = request.json
    old_rel_path = data.get("old_path")
    new_name = data.get("new_name")

    if not old_rel_path or not new_name:
        return jsonify({"error": "Missing data"}), 400

    old_full_path = os.path.join(MEDIA_ROOT, old_rel_path)

    if not is_safe_path(old_full_path):
        return jsonify({"error": "Invalid path"}), 400

    if not os.path.isfile(old_full_path):
        return jsonify({"error": "File not found"}), 404

    # Prevent path traversal in new name
    new_name = os.path.basename(new_name)

    # Preserve extension if user removed it
    old_ext = os.path.splitext(old_full_path)[1]
    if not new_name.lower().endswith(old_ext.lower()):
        new_name += old_ext

    folder = os.path.dirname(old_full_path)
    new_full_path = os.path.join(folder, new_name)

    try:
        if os.path.exists(new_full_path):
            return jsonify({"error": "File already exists"}), 400
        os.rename(old_full_path, new_full_path)

        # Update favorites
        favorites = load_favorites()
        ratings = load_ratings()

        old_key = old_rel_path
        new_rel_path = os.path.join(
            os.path.dirname(old_rel_path),
            new_name
        ).replace("\\", "/")

        if old_key in favorites:
            favorites[new_rel_path] = favorites.pop(old_key)
            save_favorites(favorites)

        if old_key in ratings:
            ratings[new_rel_path] = ratings.pop(old_key)
            save_ratings(ratings)

        return jsonify({"success": True})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

# ----------------------------------
# GALLERY
# ----------------------------------

@app.route("/gallery/<path:folder_path>")
def gallery(folder_path):
    folder = os.path.join(MEDIA_ROOT, folder_path)

    if not is_safe_path(folder) or not os.path.isdir(folder):
        abort(404)

    favorites_only = request.args.get("favorites") == "1"

    images, videos, audios = list_media(
        folder,
        folder_path,
        favorites_only=favorites_only
    )

    breadcrumbs = build_breadcrumbs(*folder_path.split("/"))

    tree = build_media_tree(MEDIA_ROOT)
    mark_active(tree, folder_path)

    return render_template(
        "gallery.html",
        images=images,
        videos=videos,
        audios=audios,
        breadcrumbs=breadcrumbs,
        tree=tree,
        favorites_only=favorites_only,
        current_path=folder_path
    )

# ----------------------------------
# FAVORITES
# ----------------------------------
@app.route("/favorite/toggle", methods=["POST"])
def toggle_favorite():
    data = request.json
    path = data.get("path")

    if not path:
        return jsonify({"error": "Missing path"}), 400

    favorites = load_favorites()

    if path in favorites:
        del favorites[path]
        state = False
    else:
        favorites[path] = True
        state = True

    save_favorites(favorites)

    return jsonify({"favorite": state})

# -------------------------------------------
# MEDIA
# -------------------------------------------

@app.route("/media/<path:filename>")
def media_file(filename):
    # Serve media files
    full_path = os.path.join(MEDIA_ROOT, filename)

    if not is_safe_path(full_path):
        abort(404)

    directory = os.path.dirname(full_path)
    file = os.path.basename(full_path)

    return send_from_directory(directory, file)

 # ---------------------------------------------
 # MAIN
 # ---------------------------------------------

if __name__ == "__main__":
    app.run(
        host="0.0.0.0",
        port = int(os.environ.get("FLASK_PORT", 6001)),
        debug=True
        )
