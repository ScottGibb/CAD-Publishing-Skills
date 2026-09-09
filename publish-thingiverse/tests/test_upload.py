import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import httpx

sys.path.insert(
    0, str(Path(__file__).resolve().parents[2] / "publish-3d-model-release" / "tests")
)
from publishing_fixture import make_manifest, module

tv = module("thingiverse")


class ThingiverseTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.folder = Path(self.temp.name)
        self.release = tv.Release(make_manifest(self.folder))
        self.state = tv.State(self.release, "thingiverse")

    def test_upload_preserves_field_order_and_separates_authorization(self):
        api_calls, storage_calls = [], []
        fields = {
            "key": "uploads/part.stl",
            "policy": "example-policy",
            "signature": "example-signature",
            "success_action_redirect": tv.API + "/files/91/finalize",
        }

        def api_handler(request):
            api_calls.append(request)
            self.assertEqual(request.headers["authorization"], "Bearer fixture-token")
            if request.url.path.endswith("/files"):
                return httpx.Response(
                    200,
                    json={
                        "action": "https://www.thingiverse.com/upload_file_storage",
                        "fields": fields,
                    },
                )
            self.assertEqual(json.loads(request.content), fields)
            return httpx.Response(200, json={"id": 91})

        def storage_handler(request):
            storage_calls.append(request)
            self.assertNotIn("authorization", request.headers)
            body = request.read().decode()
            offsets = [body.index(f'name="{key}"') for key in (*fields, "file")]
            self.assertEqual(offsets, sorted(offsets))
            self.assertIn("synthetic upload fixture", body)
            return httpx.Response(200)

        api = tv.Thingiverse(
            "fixture-token",
            httpx.Client(transport=httpx.MockTransport(api_handler)),
            httpx.Client(transport=httpx.MockTransport(storage_handler)),
        )
        self.assertEqual(
            api.upload(42, self.release.assets("thingiverse")[0])["id"], 91
        )
        self.assertEqual(len(api_calls), 2)
        self.assertEqual(len(storage_calls), 1)

    def test_publish_and_foreign_api_destinations_are_rejected(self):
        api = tv.Thingiverse("fixture-token")
        for method, path in (
            ("POST", "/things/42/publish"),
            ("DELETE", "/things/42"),
            ("GET", "https://example.com"),
        ):
            with self.assertRaises(tv.PublishingError):
                api.request(method, path)

    def test_work_in_progress_is_not_a_draft(self):
        for remote in (
            {"is_wip": True},
            {"is_wip": True, "is_published": 1},
            {"is_published": None},
        ):
            with self.assertRaises(tv.PublishingError):
                tv.draft_only(remote)
        tv.draft_only({"is_published": 0})

    def test_changed_asset_is_rejected_before_any_network(self):
        (self.folder / "part.stl").write_text("changed")
        with self.assertRaises(tv.PublishingError):
            tv.Release(self.release.path)

    def test_gcode_is_only_routed_to_printables(self):
        self.assertFalse(
            any(
                a["name"].endswith(".gcode") for a in self.release.assets("thingiverse")
            )
        )
        self.assertTrue(
            any(a["name"].endswith(".gcode") for a in self.release.assets("printables"))
        )

    def test_successful_repeat_does_not_create_or_upload_again(self):
        class FakeAPI:
            def __init__(self):
                self.remote, self.files, self.images = {}, [], []
                self.creates, self.uploads = 0, 0

            def request(inner, method, path, **kwargs):
                if method == "POST":
                    inner.creates += 1
                    inner.remote = {**kwargs["json"], "id": 42, "is_published": 0}
                if method == "PATCH":
                    inner.remote.update(kwargs["json"])
                if path.endswith("/files"):
                    return inner.files
                if path.endswith("/images"):
                    return inner.images
                if path.endswith("/tags"):
                    return inner.remote["tags"]
                if path.endswith("/categories"):
                    return [{"name": inner.remote["category"]}]
                return inner.remote

            def upload(inner, thing_id, asset):
                inner.uploads += 1
                item = {"id": inner.uploads, "name": asset["name"]}
                (inner.images if asset["kind"] == "image" else inner.files).append(item)
                return item

        api = FakeAPI()
        with patch.object(tv, "emit"):
            tv.run(self.release, self.state, api, "Bathroom")
            tv.run(self.release, tv.State(self.release, "thingiverse"), api, "Bathroom")
        self.assertEqual(api.creates, 1)
        self.assertEqual(api.uploads, len(self.release.assets("thingiverse")))
        self.assertEqual(
            json.loads((self.folder / "publication-record.json").read_text())[
                "thingiverse"
            ]["visibility"],
            "draft",
        )

    def test_rejected_create_can_retry_but_server_failure_stays_uncertain(self):
        for status in (401, 403, 503):
            with self.subTest(status=status):
                self.state.done()
                with httpx.Client(
                    transport=httpx.MockTransport(
                        lambda request, status=status: httpx.Response(status)
                    )
                ) as client:
                    api = tv.Thingiverse("fixture-token", client=client, storage=client)
                    with self.assertRaisesRegex(tv.PublishingError, f"HTTP {status}"):
                        tv.run(self.release, self.state, api, "Bathroom")
                saved = tv.State(self.release, "thingiverse")
                self.assertEqual(bool(saved.data.get("pending")), status == 503)
                self.assertNotIn("id", saved.data)

    def test_uncertain_create_is_not_replayed(self):
        self.state.pending("create")
        with self.assertRaisesRegex(tv.PublishingError, "already exist"):
            tv.run(self.release, self.state, None, "Bathroom")


if __name__ == "__main__":
    unittest.main()
