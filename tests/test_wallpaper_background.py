import unittest
from wallpaper_background import restore_legacy_background, is_legacy_wallpaper


class Value:
    def __init__(self, value):
        self.value = value

    def unpack(self):
        return self.value


class Settings:
    def __init__(self, values):
        self.values = values.copy()
        self.changed = []

    def get_string(self, key):
        return self.values[key]

    def get_default_value(self, key):
        return Value("file:///default-" + key + ".png")

    def set_string(self, key, value):
        self.values[key] = value
        self.changed.append(key)


class BackgroundTest(unittest.TestCase):
    def test_encoded_legacy_light_and_dark_restore_native_defaults(self):
        uri = "file:///mnt/PT-Storage/Tools%20%26%20Assets/Constellation/data/progretech-constellation.png"
        settings = Settings({"picture-uri": uri, "picture-uri-dark": uri})
        self.assertTrue(restore_legacy_background(settings))
        self.assertEqual(len(settings.changed), 2)
        self.assertEqual(
            settings.values["picture-uri"], "file:///default-picture-uri.png"
        )

    def test_unrelated_user_wallpaper_is_preserved(self):
        values = {
            "picture-uri": "file:///home/user/family.png",
            "picture-uri-dark": "file:///home/user/dark.png",
        }
        settings = Settings(values)
        self.assertFalse(restore_legacy_background(settings))
        self.assertEqual(settings.values, values)

    def test_other_scheme_and_near_match_are_not_legacy(self):
        self.assertFalse(is_legacy_wallpaper("file://["))
        self.assertFalse(
            is_legacy_wallpaper(
                "https://example/Constellation/data/progretech-constellation.png"
            )
        )
        self.assertFalse(
            is_legacy_wallpaper(
                "file:///Constellation/data/progretech-constellation.png.backup"
            )
        )
