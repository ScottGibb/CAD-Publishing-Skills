import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(
    0, str(Path(__file__).resolve().parents[2] / "publish-3d-model-release" / "tests")
)
from publishing_fixture import make_manifest, module

yt = module("youtube")
VIDEO_ID = "abcdefghijk"


class Response:
    def __init__(self, code, data=None, headers=None):
        self.status_code, self.data, self.headers = code, data or {}, headers or {}

    def json(self):
        return self.data


class UploadServer:
    def __init__(self, total):
        self.total, self.offset, self.starts = total, 0, 0
        self.received = bytearray()
        self.lose_final_response = False

    def post(self, url, **kwargs):
        self.starts += 1
        assert kwargs["json"]["status"]["privacyStatus"] == "private"
        return Response(
            200, headers={"Location": yt.UPLOAD + "?upload_id=fixture-session"}
        )

    def put(self, url, data, headers, **kwargs):
        if data:
            assert (
                headers["Content-Range"]
                == f"bytes {self.offset}-{self.offset + len(data) - 1}/{self.total}"
            )
            self.received.extend(data)
            self.offset += len(data)
            if self.offset == self.total and self.lose_final_response:
                self.lose_final_response = False
                raise ConnectionError("simulated lost response")
        if self.offset == self.total:
            return Response(200, {"id": VIDEO_ID})
        return Response(
            308, headers={"Range": f"bytes=0-{self.offset - 1}"} if self.offset else {}
        )


class YouTubeTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.folder = Path(self.temp.name)
        self.release = yt.Release(make_manifest(self.folder))
        self.state = yt.State(self.release, "youtube")
        self.session = self.folder / "private-session.json"

    def test_rejected_initiation_can_retry_but_server_failure_stays_uncertain(self):
        server = UploadServer((self.folder / "video.mp4").stat().st_size)
        for status in (401, 403, 503):
            with self.subTest(status=status):
                self.state.done()
                with (
                    patch.object(server, "post", return_value=Response(status)),
                    self.assertRaisesRegex(yt.PublishingError, f"HTTP {status}"),
                ):
                    yt.upload(self.release, self.state, server, self.session)
                saved = yt.State(self.release, "youtube")
                self.assertEqual(bool(saved.data.get("pending")), status == 503)
                self.assertFalse(self.session.exists())

    def test_lost_final_response_resumes_without_duplicate_upload(self):
        data = (self.folder / "video.mp4").read_bytes()
        server = UploadServer(len(data))
        server.lose_final_response = True
        with patch.object(yt, "emit"), patch.object(yt, "CHUNK_SIZE", 8):
            with self.assertRaises(ConnectionError):
                yt.upload(self.release, self.state, server, self.session)
            result = yt.upload(
                self.release, yt.State(self.release, "youtube"), server, self.session
            )
        self.assertEqual(result, VIDEO_ID)
        self.assertEqual(server.starts, 1)
        self.assertEqual(server.received, data)
        self.assertNotIn("url", json.loads(self.session.read_text()))
        self.assertEqual(self.session.stat().st_mode & 0o777, 0o600)

    def test_existing_partial_upload_continues_from_server_offset(self):
        data = (self.folder / "video.mp4").read_bytes()
        server = UploadServer(len(data))
        server.received.extend(data[:8])
        server.offset = 8
        yt.atomic_json(
            self.session,
            {
                "manifest_sha256": self.release.digest,
                "url": yt.UPLOAD + "?upload_id=existing",
            },
        )
        with patch.object(yt, "emit"), patch.object(yt, "CHUNK_SIZE", 8):
            yt.upload(self.release, self.state, server, self.session)
        self.assertEqual(server.starts, 0)
        self.assertEqual(server.received, data)

    def test_private_tags_and_category_are_included(self):
        body = yt.metadata(self.release)
        self.assertEqual(body["status"]["privacyStatus"], "private")
        self.assertEqual(body["snippet"]["tags"], ["towel rack", "bathroom"])
        self.assertEqual(body["snippet"]["categoryId"], "28")

    def test_tag_limit_counts_quoted_phrases_and_separators(self):
        self.release.manifest["publication"]["tags"] = ["a " * 250]
        with self.assertRaisesRegex(yt.PublishingError, "500"):
            yt.metadata(self.release)

    def test_unrecognized_upload_destination_is_rejected(self):
        for url in (
            "https://example.com/?upload_id=secret",
            "http://www.googleapis.com/upload/youtube/v3/videos?upload_id=x",
        ):
            with self.assertRaises(yt.PublishingError):
                yt.session_url(url)

    def test_failed_processing_does_not_record_success(self):
        body = yt.metadata(self.release)
        body["processingDetails"] = {"processingStatus": "failed"}

        class HTTP:
            def get(self, *args, **kwargs):
                return Response(200, {"items": [body]})

        with self.assertRaisesRegex(yt.PublishingError, "processing failed"):
            yt.verify(self.release, self.state, HTTP(), VIDEO_ID)
        self.assertFalse((self.folder / "publication-record.json").exists())

    def test_verification_preserves_other_platforms_and_rejects_public_video(self):
        record = self.folder / "publication-record.json"
        record.write_text(
            json.dumps({"schema": 1, "thingiverse": {"draft_url": "existing"}})
        )
        body = yt.metadata(self.release)
        body["processingDetails"] = {"processingStatus": "succeeded"}

        class HTTP:
            def get(self, *args, **kwargs):
                return Response(200, {"items": [body]})

        with patch.object(yt, "emit"):
            yt.verify(self.release, self.state, HTTP(), VIDEO_ID)
        self.assertEqual(
            json.loads(record.read_text())["thingiverse"]["draft_url"], "existing"
        )
        body["status"]["privacyStatus"] = "public"
        with self.assertRaisesRegex(yt.PublishingError, "not private"):
            yt.verify(self.release, self.state, HTTP(), VIDEO_ID)


if __name__ == "__main__":
    unittest.main()
