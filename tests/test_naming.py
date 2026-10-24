import unittest
from datetime import datetime

from photo_harbor.naming import media_type, month_folder, parse_taken, safe_name


class SafeNameTest(unittest.TestCase):
    def test_keeps_an_ordinary_name_and_lowercases_the_extension(self):
        self.assertEqual(safe_name("IMG_1234.HEIC"), "IMG_1234.heic")

    def test_strips_directories_from_either_separator(self):
        self.assertEqual(safe_name("..\\..\\evil/IMG_1.jpg"), "IMG_1.jpg")

    def test_replaces_characters_windows_forbids(self):
        self.assertEqual(safe_name('a<b>:c?.jpg'), "a_b__c_.jpg")

    def test_prefixes_reserved_device_names(self):
        self.assertEqual(safe_name("CON.jpg"), "_CON.jpg")

    def test_falls_back_when_nothing_is_left(self):
        self.assertEqual(safe_name("..."), "photo")


class ParseTakenTest(unittest.TestCase):
    def test_reads_shortcuts_iso_with_zulu(self):
        self.assertEqual(parse_taken("2026-05-01T10:20:30Z").year, 2026)

    def test_unreadable_text_is_unknown(self):
        self.assertIsNone(parse_taken("yesterday"))

    def test_month_folder_is_zero_padded(self):
        self.assertEqual(month_folder(datetime(2026, 3, 9)), "2026/03")


class MediaTypeTest(unittest.TestCase):
    def test_knows_iphone_formats(self):
        self.assertEqual(media_type("a.HEIC"), "image/heic")
        self.assertEqual(media_type("clip.mov"), "video/quicktime")
