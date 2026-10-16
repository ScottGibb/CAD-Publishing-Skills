import json
import sys
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import publish_release
from publishing_fixture import make_manifest


class PrintablesHandoffTests(unittest.TestCase):
    def test_execute_prepares_packet_and_hands_off_without_browser_upload(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            manifest = make_manifest(root)
            config = root / "settings.json"
            config.write_text(json.dumps({"printables": {"format": "json"}}))
            with (
                patch.object(
                    publish_release.subprocess,
                    "run",
                    return_value=SimpleNamespace(returncode=0),
                ) as run,
                patch.object(publish_release, "emit") as emit,
            ):
                result = publish_release.main(
                    [
                        "--manifest",
                        str(manifest),
                        "--config",
                        str(config),
                        "--platform",
                        "printables",
                        "--execute",
                    ]
                )
            self.assertEqual(result, 0)
            run.assert_called_once()
            command = run.call_args.args[0]
            self.assertTrue(
                any(
                    "prepare-printables-upload/scripts/upload_printables.py" in item
                    for item in command
                )
            )
            self.assertNotIn("--execute", command)
            self.assertEqual(
                emit.call_args.args[0]["next_skill"], "upload-printables-browser"
            )
            self.assertEqual(
                emit.call_args.args[0]["status"], "ready-for-manual-upload"
            )
