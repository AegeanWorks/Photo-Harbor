import base64
import shutil
import tempfile
import unittest
from pathlib import Path

from photo_harbor.details import read_details
from photo_harbor.pillow_support import load_image
from photo_harbor.records import PhotoRecord

PNG = base64.b64decode(
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+/p9sAAAAASUVORK5CYII=")


def record_for(path: Path, name: str = "one.jpg", media_type: str = "image/jpeg") -> PhotoRecord:
    return PhotoRecord(
        sha256="a" * 64, rel_path=f"main/2026/2026-05/{name}", size=path.stat().st_size,
        original_name=name, media_type=media_type, taken_at="2026-05-01T10:00:00",
        received_at="2026-05-01T11:00:00")


class DetailsTest(unittest.TestCase):
    def setUp(self):
        self.root = Path(tempfile.mkdtemp(prefix="harbor_details_"))
        self.addCleanup(shutil.rmtree, self.root, True)

    def test_file_facts_survive_an_unreadable_image(self):
        path = self.root / "broken.jpg"
        path.write_bytes(b"not really a jpeg")
        details = read_details(record_for(path, "broken.jpg"), path)
        self.assertEqual((details["name"], details["type"], details["size"]),
                         ("broken.jpg", "image/jpeg", path.stat().st_size))
        self.assertIsNone(details["width"])
        self.assertIsNone(details["camera"])

    def test_a_video_has_no_image_facts(self):
        path = self.root / "clip.mp4"
        path.write_bytes(PNG)
        details = read_details(record_for(path, "clip.mp4", "video/mp4"), path)
        self.assertEqual(details["type"], "video/mp4")
        self.assertIsNone(details["width"])

    @unittest.skipUnless(load_image() is not None, "Pillow is not installed")
    def test_pillow_reads_dimensions_and_camera_tags(self):
        from PIL import Image
        path = self.root / "camera.jpg"
        image = Image.new("RGB", (12, 8), "white")
        exif = Image.Exif()
        exif[0x010F] = "Acme"
        exif[0x0110] = "Cam 1"
        exif[0x8827] = 200
        exif[0x829A] = 1 / 250
        exif[0x829D] = 2.8
        exif[0x920A] = 35
        image.save(path, "JPEG", exif=exif)
        details = read_details(record_for(path, "camera.jpg"), path)
        self.assertEqual((details["width"], details["height"]), (12, 8))
        self.assertEqual(details["camera"], "Acme Cam 1")
        self.assertEqual(details["iso"], "200")
        self.assertEqual(details["aperture"], "f/2.8")
        self.assertTrue(details["exposure"].endswith(" s"))
        self.assertEqual(details["focal_length"], "35 mm")
