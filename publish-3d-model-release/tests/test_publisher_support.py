import contextlib
import io
import json
import sys
import tempfile
import unittest
from pathlib import Path

from publishing_fixture import ROOT, make_manifest, module

sys.path.insert(0, str(ROOT / "publish-3d-model-release" / "scripts"))
from publisher_support import PublishingError, Release, State, error_text


class PublisherSupportTests(unittest.TestCase):
    def test_each_platform_dry_run_leaves_release_and_records_untouched(self):
        with tempfile.TemporaryDirectory() as directory:
            path = make_manifest(directory)
            before = path.read_bytes()
            for platform in ("thingiverse", "printables", "youtube"):
                uploader = module(platform)
                args = ["--manifest", str(path)]
                if platform == "thingiverse":
                    args += ["--category", "Bathroom"]
                output = io.StringIO()
                with contextlib.redirect_stdout(output):
                    self.assertEqual(uploader.main(args), 0)
                result = json.loads(output.getvalue())
                self.assertEqual(result["mode"], "dry-run")
                if platform == "printables":
                    self.assertEqual(result["tags"], ["towel", "rack", "bathroom"])
            self.assertEqual(before, path.read_bytes())
            self.assertFalse((Path(directory) / ".publication-state").exists())
            self.assertFalse((Path(directory) / "publication-record.json").exists())

    def test_state_cannot_be_reused_for_another_manifest(self):
        with tempfile.TemporaryDirectory() as directory:
            path = make_manifest(directory)
            release = Release(path)
            State(release, "thingiverse").save()
            manifest = json.loads(path.read_text())
            manifest["publication"]["title"] = "Another release"
            path.write_text(json.dumps(manifest))
            with self.assertRaisesRegex(PublishingError, "another manifest"):
                State(Release(path), "thingiverse")

    def test_network_error_messages_are_redacted(self):
        error = OSError(
            "https://www.googleapis.com/upload/youtube/v3/videos?upload_id=private-secret"
        )
        self.assertEqual(error_text(error), "OSError")
        self.assertEqual(
            error_text(PublishingError("Missing category")), "Missing category"
        )


if __name__ == "__main__":
    unittest.main()
