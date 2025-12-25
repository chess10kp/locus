import os


def get_bookmarks():
    bookmark_file = os.path.expanduser("~/.bookmarks")
    bookmarks = []
    if os.path.exists(bookmark_file):
        with open(bookmark_file, "r") as f:
            for line in f:
                cleaned = line.strip()
                if cleaned:
                    # Normalize whitespace: replace multiple spaces with single space
                    cleaned = " ".join(cleaned.split())
                    bookmarks.append(cleaned)
    return bookmarks


def add_bookmark(bookmark):
    bookmarks = get_bookmarks()
    if bookmark not in bookmarks:
        bookmark_file = os.path.expanduser("~/.bookmarks")
        with open(bookmark_file, "a") as f:
            f.write(bookmark + "\n")


def remove_bookmark(bookmark):
    bookmarks = get_bookmarks()
    if bookmark in bookmarks:
        bookmarks.remove(bookmark)
        bookmark_file = os.path.expanduser("~/.bookmarks")
        with open(bookmark_file, "w") as f:
            for b in bookmarks:
                f.write(b + "\n")
