import io
import gzip
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import MagicMock, patch
import urllib.error

from scripts import roblox_publish as pub


class PublisherTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        root_patch = patch.object(pub, "ROOT", self.root)
        root_patch.start()
        self.addCleanup(root_patch.stop)

    def place(self, contents):
        path = self.root / "map.rbxlx"
        path.write_bytes(contents)
        return path.name

    def response(self, value):
        response = io.BytesIO(json.dumps(value).encode())
        response.status = 200
        return response

    def test_xml_is_sent_without_modifying_bytes(self):
        original = b'<roblox version="4">\r\n<Item class="Workspace" /></roblox>\r\n'
        data, content_type, info = pub.inspect_place(self.place(original))
        opener = MagicMock()
        opener.open.return_value = self.response({"versionNumber": 7})
        with patch.object(pub.urllib.request, "build_opener", return_value=opener):
            version = pub.publish(data, content_type, "123", "456", "test-key")
        request = opener.open.call_args.args[0]
        self.assertEqual(request.data, original)
        self.assertEqual(request.get_method(), "POST")
        self.assertEqual(request.get_header("Content-type"), "application/xml")
        self.assertEqual(request.get_header("X-api-key"), "test-key")
        self.assertEqual(request.full_url, "https://apis.roblox.com/universes/v1/123/places/456/versions?versionType=Published")
        self.assertEqual(version, 7)
        self.assertEqual(info["instances"], 1)
        opener.open.assert_called_once()

    def test_invalid_destination_or_missing_key_never_sends(self):
        with patch.object(pub.urllib.request, "build_opener") as opener:
            for universe, place, key in [
                ("", "456", "key"), ("123", "0", "key"),
                ("123?x=1", "456", "key"), ("123", "456", ""),
                ("١٢٣", "456", "key"), ("123", "456", "key\nother"),
            ]:
                with self.subTest(universe=universe, place=place):
                    with self.assertRaises(pub.PublishError):
                        pub.publish(b"data", "application/xml", universe, place, key)
            opener.assert_not_called()

    def test_gzip_preserves_exact_original_place(self):
        original = b'<roblox version="4">\r\n<Item class="Workspace" /></roblox>\r\n'
        path = self.root / "map.rbxlx.gz"
        path.write_bytes(gzip.compress(original, mtime=0))
        data, content_type, info = pub.inspect_place(path.name)
        self.assertEqual(data, original)
        self.assertEqual(content_type, "application/xml")
        self.assertEqual(info["bytes"], len(original))

    def test_only_confirmed_version_is_success(self):
        for body in [{}, {"versionNumber": 0}, {"versionNumber": True}, {"versionNumber": "7"}, []]:
            with self.subTest(body=body):
                opener = MagicMock()
                opener.open.return_value = self.response(body)
                with patch.object(pub.urllib.request, "build_opener", return_value=opener):
                    with self.assertRaises(pub.PublishError):
                        pub.publish(b"data", "application/xml", "123", "456", "key")

    def test_error_cannot_expose_secret(self):
        opener = MagicMock()
        opener.open.side_effect = urllib.error.HTTPError(
            "https://apis.roblox.com", 403, "do-not-print-test-secret", {},
            io.BytesIO(b"do-not-print-test-secret"),
        )
        with patch.object(pub.urllib.request, "build_opener", return_value=opener):
            with self.assertRaises(pub.PublishError) as caught:
                pub.publish(b"data", "application/xml", "123", "456", "do-not-print-test-secret")
        self.assertIn("403", str(caught.exception))
        self.assertNotIn("do-not-print-test-secret", str(caught.exception))

    def test_ambiguous_timeout_is_not_retried(self):
        opener = MagicMock()
        opener.open.side_effect = TimeoutError()
        with patch.object(pub.urllib.request, "build_opener", return_value=opener):
            with self.assertRaisesRegex(pub.PublishError, "status is unknown"):
                pub.publish(b"data", "application/xml", "123", "456", "key")
        opener.open.assert_called_once()

    def test_redirect_does_not_forward_credentials(self):
        self.assertIsNone(pub.NoRedirect().redirect_request(None, None, 302, "", {}, "https://example.com"))

    def test_invalid_or_unsupported_xml_is_rejected(self):
        for contents in [
            b"<broken>", b'<roblox version="4" />',
            b'<roblox version="4"><Item class="Workspace" /><Item class="UnionOperation" /></roblox>',
            b'<!DOCTYPE roblox [<!ENTITY x "x">]><roblox version="4"><Item class="Workspace" /></roblox>',
        ]:
            with self.subTest(contents=contents):
                with self.assertRaises(pub.PublishError):
                    pub.inspect_place(self.place(contents))

    def test_outside_repository_and_empty_file_are_rejected(self):
        with tempfile.TemporaryDirectory() as outside:
            path = Path(outside) / "outside.rbxlx"
            path.write_bytes(b"outside")
            with self.assertRaises(pub.PublishError):
                pub.inspect_place(str(path))
        with self.assertRaises(pub.PublishError):
            pub.inspect_place(self.place(b""))


if __name__ == "__main__":
    unittest.main()
