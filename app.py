import os
from flask import Flask, render_template, abort, send_from_directory,jsonify,request
import json

app = Flask(__name__)

MEDIA_ROOT = os.path.join(app.root_path, "media")

IMAGE_EXTS = {".jpg", ".jpeg", ".png", ".gif", ".webp"}
VIDEO_EXTS = {".mp4", ".webm", ".mov"}
FAVORITES_FILE = os.path.join(app.root_path, "favorites.json")

# --------------------------------
# HELPERS
# --------------------------------


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


def list_media(folder_path, rel_path):
    favorites = load_favorites()

    images = []
    videos = []

    for name in sorted(os.listdir(folder_path)):
        full = os.path.join(folder_path, name)
        if not os.path.isfile(full):
            continue

        ext = os.path.splitext(name)[1].lower()
        rel_file = f"{rel_path}/{name}"

        item = {
            "name": name,
            "path": rel_file,
            "favorite": rel_file in favorites
        }

        if ext in IMAGE_EXTS:
            images.append(item)
        elif ext in VIDEO_EXTS:
            videos.append(item)

    # Favorites first
    images.sort(key=lambda x: not x["favorite"])
    videos.sort(key=lambda x: not x["favorite"])

    return images, videos


def count_media_files(folder):
    count = 0
    for name in os.listdir(folder):
        full = os.path.join(folder, name)
        if os.path.isfile(full):
            ext = os.path.splitext(name)[1].lower()
            if ext in IMAGE_EXTS or ext in VIDEO_EXTS:
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

def build_media_tree(base_path, rel_path=""):
    abs_path = os.path.join(base_path, rel_path)
    tree = []

    for name in sorted(os.listdir(abs_path)):
        full = os.path.join(abs_path, name)
        if not os.path.isdir(full):
            continue

        sub_rel = os.path.join(rel_path, name) if rel_path else name

        children = build_media_tree(base_path, sub_rel)

        node = {
            "name": name,
            "path": sub_rel.replace("\\", "/"),
            "file_count": count_media_files(full),
            "folder_count": len(children),
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


# ----------------------------------
# GALLERY
# ----------------------------------

@app.route("/gallery/<path:folder_path>")
def gallery(folder_path):
    folder = os.path.join(MEDIA_ROOT, folder_path)

    if not is_safe_path(folder) or not os.path.isdir(folder):
        abort(404)

    images, videos = list_media(folder, folder_path)

    breadcrumbs = build_breadcrumbs(*folder_path.split("/"))

    tree = build_media_tree(MEDIA_ROOT)
    mark_active(tree, folder_path)

    return render_template(
        "gallery.html",
        images=images,
        videos=videos,
        breadcrumbs=breadcrumbs,
        tree=tree,
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
    app.run(debug=True)
