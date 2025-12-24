# pyright: reportMissingTypeStubs=false
# pyright: reportUnknownMemberType=false
# pyright: reportUntypedBaseClass=false
# pyright: reportAttributeAccessIssue=false
# pyright: reportUnusedCallResult=false
# pyright: reportUnknownVariableType=false
# pyright: reportMissingImports=false
# ruff: ignore

from gi.repository import GObject


class WrappedSearchResult(GObject.Object):
    """Wrapper to make search results compatible with GObject-based ListStore."""

    def __init__(self, search_result):
        super().__init__()
        self.search_result = search_result

    @property
    def title(self):
        return self.search_result.title

    @property
    def subtitle(self):
        return self.search_result.subtitle

    @property
    def result_type(self):
        return self.search_result.result_type

    @property
    def index(self):
        return self.search_result.index

    @property
    def app(self):
        return getattr(self.search_result, "app", None)

    @property
    def command(self):
        return getattr(self.search_result, "command", None)

    @property
    def hook_data(self):
        return self.search_result.hook_data

    @property
    def action_data(self):
        return self.search_result.action_data

    @property
    def image_path(self):
        return getattr(self.search_result, "image_path", None)

    @property
    def icon_name(self):
        icon_name = getattr(self.search_result, "icon_name", None)
        return icon_name

    @property
    def icon_pixbuf(self):
        pixbuf = getattr(self.search_result, "icon_pixbuf", None)
        return pixbuf

    @icon_pixbuf.setter
    def icon_pixbuf(self, value):
        setattr(self.search_result, "icon_pixbuf", value)

    @property
    def pixbuf(self):
        return getattr(self.search_result, "pixbuf", None)

    @property
    def grid_metadata(self):
        return getattr(self.search_result, "grid_metadata", {})
