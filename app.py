import os
from flask import Flask, render_template, abort, send_from_directory

app = Flask(__name__)

MEDIA_ROOT = os.path.join(app.root_path, "media")

IMAGE_EXTS = {".jpg", ".jpeg", ".png", ".gif", ".webp"}
VIDEO_EXTS = {".mp4", ".webm", ".mov"}


# --------------------------------
# HELPERS
# --------------------------------


def is_safe_path(path):
    # Prevent directory traversal
    abs_path = os.path.abspath(path)
    return abs_path.startswith(os.path.abspath(MEDIA_ROOT))


def list_media(folder_path):
    images = []
    videos = []

    for name in sorted(os.listdir(folder_path)):
        full = os.path.join(folder_path, name)
        if not os.path.isfile(full):
            continue

        ext = os.path.splitext(name)[1].lower()
        if ext in IMAGE_EXTS:
            images.append(name)
        elif ext in VIDEO_EXTS:
            videos.append(name)

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


def build_media_tree(base_path, rel_path=""):
    """
    Returns a tree like:
    {
        "name": "watercolor",
        "path": "watercolor",
        "count": 0,
        "children": [...]
    }
    """
    abs_path = os.path.join(base_path, rel_path)
    tree = []

    for name in sorted(os.listdir(abs_path)):
        full = os.path.join(abs_path, name)
        if not os.path.isdir(full):
            continue

        sub_rel = os.path.join(rel_path, name) if rel_path else name
        file_count = count_media_files(full)

        node = {
            "name": name,
            "path": sub_rel.replace("\\", "/"),
            "count": file_count,
            "children": build_media_tree(base_path, sub_rel)
        }
        tree.append(node)

    return tree


# -------------------------------
# BREADCRUMBS
# -------------------------------

def build_breadcrumbs(*parts):
    """
    Input: ("watercolor", "nature")
    Output:
    [
      {"name": "Home", "url": "/"},
      {"name": "watercolor", "url": "/watercolor"},
      {"name": "nature", "url": "/watercolor/nature"}
    ]
    """
    crumbs = [{"name": "Home", "url": "/"}]
    path = ""

    for part in parts:
        path += f"/{part}"
        crumbs.append({
            "name": part,
            "url": path
        })

    return crumbs

# -------------------------------
# ROUTES
# -------------------------------

@app.route("/")
def index():
    tree = build_media_tree(MEDIA_ROOT)
    return render_template("index.html", tree=tree)


# ----------------------------------
# GALLERY
# ----------------------------------

@app.route("/<category>/<subcategory>")
def gallery(category, subcategory):
    folder = os.path.join(MEDIA_ROOT, category, subcategory)

    if not is_safe_path(folder) or not os.path.isdir(folder):
        abort(404)

    images, videos = list_media(folder)
    breadcrumbs = build_breadcrumbs(category, subcategory)

    return render_template(
        "gallery.html",
        category=category,
        subcategory=subcategory,
        images=images,
        videos=videos,
        breadcrumbs=breadcrumbs
    )
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
