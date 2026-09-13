import contextlib
import copy
import io
import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from playwright.sync_api import sync_playwright

sys.path.insert(
    0, str(Path(__file__).resolve().parents[2] / "publish-3d-model-release" / "tests")
)
from publishing_fixture import make_manifest, module

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
tv = module("thingiverse")
CREATE_URL = "https://www.thingiverse.com/thing:create"
MAP = {
    "schema": 1,
    "platform": "thingiverse",
    "create_url": CREATE_URL,
    "editor_url": "https://www.thingiverse.com/thing:{id}/edit",
    "category": "Bathroom",
    "license": "CC-BY-4.0",
    "fields": {
        "title": {"label": "Title"},
        "description": {"label": "Description"},
        "tags": {"label": "Tags"},
    },
    "choices": [
        {
            "field": "category",
            "locator": {"label": "Category"},
            "option_label": "Bathroom",
            "verify": {"label": "Category"},
            "expected": "5",
        },
        {
            "field": "license",
            "locator": {"label": "License"},
            "option_label": "CC BY 4.0",
            "verify": {"label": "License"},
            "expected": "cc",
        },
    ],
    "uploads": {kind: {"css": "#" + kind} for kind in ("file", "image")},
    "uploaded_items": {
        kind: {"css": "#" + kind + "-items span"} for kind in ("file", "image")
    },
    "tag_items": {"css": "#tag-items span"},
    "save_draft": {"role": "button", "name": "Save draft"},
    "draft_marker": {"css": "#draft-marker"},
}


class ThingiverseTests(unittest.TestCase):
    def test_async_tags_accept_exact_create_option_and_verify_chip(self):
        self.page.set_content("""
            <label>Tags<input id="tags"></label><div id="tag-items"></div>
            <div id="options"></div>
            <script>
            document.querySelector('#tags').oninput = e => {
                const value = e.target.value;
                const option = document.createElement('div');
                option.setAttribute('role', 'option');
                option.textContent = 'Create "' + value + '"';
                option.onclick = () => {
                    const chip = document.createElement('span');
                    chip.textContent = value;
                    document.querySelector('#tag-items').append(chip);
                    document.querySelector('#options').replaceChildren();
                };
                document.querySelector('#options').replaceChildren(option);
            };
            </script>
        """)
        mapping = {**MAP, "tag_mode": "async-select"}
        tv.fill_tags(self.page, mapping, self.release)
        self.assertEqual(
            self.page.locator("#tag-items span").all_text_contents(),
            self.release.plan["thingiverse"]["tags"],
        )

    @classmethod
    def setUpClass(cls):
        cls.playwright = sync_playwright().start()
        cls.browser = cls.playwright.chromium.launch(headless=True)

    @classmethod
    def tearDownClass(cls):
        cls.browser.close()
        cls.playwright.stop()

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.folder = Path(self.temp.name)
        self.release = tv.Release(make_manifest(self.folder))
        self.context = self.browser.new_context()
        self.addCleanup(self.context.close)
        html = Path(__file__).with_name("editor_fixture.html").read_text()
        self.requests = []

        def intercept(route):
            self.requests.append(route.request.url)
            route.fulfill(status=200, content_type="text/html", body=html)

        # Every request is intercepted; these tests never access an account.
        self.context.route("**/*", intercept)
        self.page = self.context.new_page()
        self.page.set_default_timeout(500)
        self.state = tv.State(self.release, "thingiverse")

    def run_draft(self, mapping=MAP, state=None, **kwargs):
        with patch.object(tv, "emit"):
            tv.run(self.release, state or self.state, self.page, mapping, **kwargs)

    def test_saved_draft_is_verified_and_rerun_does_not_duplicate_uploads(self):
        self.run_draft()
        uploads = self.page.evaluate("localStorage.getItem('upload-count')")
        self.run_draft(state=tv.State(self.release, "thingiverse"))
        self.assertEqual(self.page.evaluate("localStorage.getItem('save-count')"), "1")
        self.assertEqual(
            self.page.evaluate("localStorage.getItem('upload-count')"), uploads
        )
        self.assertEqual(
            self.page.locator("#tag-items span").all_text_contents(),
            ["towel rack", "bathroom"],
        )
        self.assertEqual(
            self.page.locator("#file-items span").all_text_contents(),
            ["part.stl", "assembly.step"],
        )
        self.assertEqual(
            self.page.locator("#image-items span").inner_text(), "preview.png"
        )
        self.assertIn(
            "Slide parts together", self.page.get_by_label("Description").input_value()
        )
        description = self.page.get_by_label("Description").input_value()
        self.assertNotIn("## Licence", description)
        self.assertNotIn("CC BY 4.0", description)
        self.assertEqual(self.page.get_by_label("License").input_value(), "cc")
        self.assertEqual(
            tv.expected_fields(self.release, {**MAP, "native_sections": True})[
                "description"
            ],
            self.release.manifest["publication"]["description"],
        )
        record = json.loads((self.folder / "publication-record.json").read_text())
        self.assertEqual(record["thingiverse"]["visibility"], "draft")
        self.assertFalse(any("api.thingiverse.com" in url for url in self.requests))

    def test_publish_action_is_rejected_before_content_changes(self):
        mapping = copy.deepcopy(MAP)
        mapping["save_draft"] = {"role": "button", "name": "Publish Thing"}
        with self.assertRaisesRegex(tv.PublishingError, "non-draft"):
            self.run_draft(mapping)
        self.assertEqual(self.page.url, "about:blank")

    def test_generic_save_requires_a_visible_unpublished_marker(self):
        self.page.goto(CREATE_URL)
        self.page.locator("#save").evaluate("e => e.textContent='Save & View'")
        mapping = copy.deepcopy(MAP)
        mapping["save_draft"] = {"role": "button", "name": "Save & View"}
        with self.assertRaisesRegex(tv.PublishingError, "unpublished_marker"):
            tv.save_control(self.page, mapping, click=True)
        mapping["unpublished_marker"] = {"css": "#unpublished-marker"}
        tv.save_control(self.page, mapping)
        self.page.locator("#unpublished-marker").evaluate("e => e.textContent='Public'")
        with self.assertRaisesRegex(tv.PublishingError, "unpublished draft"):
            tv.save_control(self.page, mapping)

    def test_uncertain_write_is_not_repeated(self):
        self.state.pending("saving-browser-draft")
        with self.assertRaisesRegex(tv.PublishingError, "draft may exist"):
            self.run_draft()
        self.assertEqual(self.page.url, "about:blank")

    def test_lost_save_response_retains_id_and_verifies_without_reupload(self):
        save = tv.save_control

        def lose_response(page, mapping, click=False):
            save(page, mapping, click)
            if click:
                raise ConnectionError("simulated lost acknowledgement")

        with (
            patch.object(tv, "save_control", side_effect=lose_response),
            self.assertRaises(ConnectionError),
        ):
            self.run_draft()
        saved = tv.State(self.release, "thingiverse")
        self.assertEqual(saved.data["id"], "42")
        self.assertIn("pending", saved.data)
        self.run_draft(state=saved)
        self.assertEqual(self.page.evaluate("localStorage.getItem('save-count')"), "1")

    def test_existing_api_receipt_is_reused_and_other_platforms_are_preserved(self):
        self.run_draft()
        record = self.folder / "publication-record.json"
        data = json.loads(record.read_text())
        data["youtube"] = {"id": "existing-video"}
        record.write_text(json.dumps(data))
        self.state.data = {
            "schema": 1,
            "platform": "thingiverse",
            "manifest_sha256": self.release.digest,
            "id": 42,
            "assets": {"old-api-asset": 91},
            "pending": "upload",
        }
        self.state.save()
        self.run_draft(state=tv.State(self.release, "thingiverse"))
        self.assertEqual(self.page.evaluate("localStorage.getItem('save-count')"), "1")
        self.assertEqual(
            json.loads(record.read_text())["youtube"]["id"], "existing-video"
        )

    def test_conflicting_resume_id_is_rejected_before_navigation(self):
        self.state.data["id"] = 42
        with self.assertRaisesRegex(tv.PublishingError, "conflicts"):
            self.run_draft(thing_id=43)
        self.assertEqual(self.page.url, "about:blank")

    def test_published_thing_is_not_modified_or_reported_as_a_draft(self):
        self.run_draft()
        self.page.evaluate("localStorage.setItem('published', 'true')")
        with self.assertRaisesRegex(tv.PublishingError, "identify itself as a draft"):
            self.run_draft()
        self.assertEqual(self.page.evaluate("localStorage.getItem('save-count')"), "1")

    def test_post_printing_and_comma_separated_tags_are_verified(self):
        mapping = copy.deepcopy(MAP)
        mapping["fields"]["post_printing"] = {"label": "Post-Printing"}
        mapping["tag_mode"] = "comma-separated"
        self.run_draft(mapping)
        self.assertIn(
            "Slide parts together",
            self.page.get_by_label("Post-Printing").input_value(),
        )
        self.assertEqual(
            self.page.get_by_label("Tags").input_value(), "towel rack, bathroom"
        )

    def test_gcode_cannot_be_added_to_the_thingiverse_upload_map(self):
        mapping = copy.deepcopy(MAP)
        mapping["uploads"]["print_file"] = {"css": "#file"}
        with self.assertRaisesRegex(tv.PublishingError, "Printables-only"):
            self.run_draft(mapping)

    def test_credentials_are_not_read_from_legacy_flags_or_config(self):
        config = self.folder / "config.toml"
        config.write_text('[thingiverse]\ntoken = "private-fixture-token"\n')
        with self.assertRaisesRegex(tv.PublishingError, "no longer supported"):
            tv.configured_settings(config)
        config.write_text(
            '[thingiverse]\nprofile_dir = "/private/profile"\nui_map = "/private/map.json"\n'
        )
        self.assertEqual(
            tv.configured_settings(config)["profile_dir"], "/private/profile"
        )
        with contextlib.redirect_stderr(io.StringIO()), self.assertRaises(SystemExit):
            tv.main(["--token-file", str(config)])

    def test_non_thingiverse_urls_and_unverified_choices_are_rejected(self):
        for url in (
            "https://example.com/thing:42",
            "https://www.thingiverse.com/thing:42?token=x",
            "https://www.thingiverse.com/thing:42/publish",
        ):
            with self.subTest(url=url), self.assertRaises(tv.PublishingError):
                tv.thingiverse_url(url)
        mapping = copy.deepcopy(MAP)
        mapping["choices"] = []
        with self.assertRaisesRegex(tv.PublishingError, "verified category"):
            tv.validate_map(mapping, self.release)

    def test_saved_metadata_mismatch_is_not_recorded_as_success(self):
        self.page.goto(CREATE_URL)
        with patch.object(tv, "emit"):
            tv.fill_editor(self.page, MAP, self.release)
        self.page.get_by_label("Title").fill("Wrong title")
        with self.assertRaisesRegex(tv.PublishingError, "title differs"):
            tv.verify_editor(self.page, MAP, self.release)
        self.assertFalse((self.folder / "publication-record.json").exists())


if __name__ == "__main__":
    unittest.main()
