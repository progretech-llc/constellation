"""Undo only the legacy Constellation static-wallpaper assignment."""

from urllib.parse import unquote, urlparse


def is_legacy_wallpaper(uri):
    try:
        parsed = urlparse(uri)
    except ValueError:
        return False
    return parsed.scheme == "file" and unquote(parsed.path).endswith(
        "/Constellation/data/progretech-constellation.png"
    )


def restore_legacy_background(settings=None):
    if settings is None:
        from gi.repository import Gio

        settings = Gio.Settings.new("org.gnome.desktop.background")
    changed = False
    for key in ["picture-uri", "picture-uri-dark"]:
        if is_legacy_wallpaper(settings.get_string(key)):
            settings.set_string(key, settings.get_default_value(key).unpack())
            changed = True
    return changed
