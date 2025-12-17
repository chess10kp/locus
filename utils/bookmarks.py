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
