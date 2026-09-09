import copy
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

pp = module("printables")
MAP = {
    "schema": 1,
    "category": "Bathroom",
    "license": "CC-BY-4.0",
    "fields": {
        name: {"label": name.capitalize()}
        for name in ("title", "summary", "description", "tags")
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
    "uploads": {kind: {"css": "#" + kind} for kind in ("file", "image", "print_file")},
    "uploaded_items": {
        kind: {"css": "#" + kind + "-items span"}
        for kind in ("file", "image", "print_file")
    },
    "tag_items": {"css": "#tag-items span"},
    "save_draft": {"role": "button", "name": "Save draft"},
    "draft_marker": {"text": "This model is a draft"},
}


class PrintablesTests(unittest.TestCase):
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
        self.release = pp.Release(make_manifest(self.folder))
        self.context = self.browser.new_context()
        self.addCleanup(self.context.close)
        html = Path(__file__).with_name("editor_fixture.html").read_text()
        # Every request is intercepted. These tests never contact Printables.
        self.context.route(
            "**/*",
            lambda route: route.fulfill(
                status=200, content_type="text/html", body=html
            ),
        )
        self.page = self.context.new_page()

    def test_draft_save_reopens_and_verifies_without_duplicate_upload(self):
        state = pp.State(self.release, "printables")
        with patch.object(pp, "emit"):
            pp.run(self.release, state, self.page, MAP)
            pp.run(self.release, pp.State(self.release, "printables"), self.page, MAP)
        self.assertEqual(self.page.evaluate("localStorage.getItem('save-count')"), "1")
        self.assertEqual(self.page.locator("#file-items span").count(), 2)
        self.assertEqual(
            self.page.locator("#print_file-items span").inner_text(), "part.gcode"
        )
        self.assertEqual(
            self.page.locator("#tag-items span").all_text_contents(),
            ["towel-rack", "bathroom"],
        )

    def test_wrong_save_mapping_cannot_publish(self):
        self.page.goto(pp.CREATE_URL)
        with self.assertRaisesRegex(pp.PublishingError, "not a draft operation"):
            pp.safe_click(
                self.page.get_by_role("button", name="Publish", exact=True), draft=True
            )
        self.assertIsNone(self.page.evaluate("window.unwantedPublish"))

    def test_ambiguous_field_is_rejected_before_filling(self):
        self.page.goto(pp.CREATE_URL)
        mapping = copy.deepcopy(MAP)
        mapping["fields"]["title"] = {"css": "input"}
        with self.assertRaisesRegex(pp.PublishingError, "exactly one"):
            pp.fill_editor(self.page, mapping, self.release)
        self.assertEqual(self.page.get_by_label("Title").input_value(), "")

    def test_incorrect_saved_metadata_fails_verification(self):
        self.page.goto(pp.CREATE_URL)
        pp.fill_editor(self.page, MAP, self.release)
        self.page.get_by_label("Title").fill("Wrong title")
        with self.assertRaisesRegex(pp.PublishingError, "title differs"):
            pp.verify_editor(self.page, MAP, self.release)

    def test_uncertain_save_requires_an_existing_draft(self):
        state = pp.State(self.release, "printables")
        state.pending("saving-draft")
        with self.assertRaisesRegex(pp.PublishingError, "draft may exist"):
            pp.run(self.release, state, self.page, MAP)

    def test_category_and_license_verification_cannot_be_omitted(self):
        mapping = copy.deepcopy(MAP)
        mapping["choices"] = []
        with self.assertRaisesRegex(pp.PublishingError, "verified category"):
            pp.validate_map(mapping, self.release)


if __name__ == "__main__":
    unittest.main()
