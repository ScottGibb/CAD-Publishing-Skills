import copy
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from patchright.sync_api import TimeoutError as BrowserTimeout
from patchright.sync_api import sync_playwright

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
        self.assertEqual(self.page.locator("#file-items span").count(), 3)
        self.assertEqual(
            self.page.locator("#print_file-items span").inner_text(), "part.gcode"
        )
        self.assertEqual(
            self.page.locator("#tag-items span").all_text_contents(),
            ["towel", "rack", "bathroom"],
        )

    def test_manual_package_contains_copy_and_grouped_upload_files(self):
        output = self.folder / "printables-manual-upload"
        before = self.release.path.read_bytes()
        result = pp._manual_package(self.release, output)
        self.assertEqual(result["status"], "created")
        self.assertTrue((output / "UPLOAD.md").is_file())
        self.assertEqual(
            (output / "content" / "tags.txt").read_text(), "towel rack bathroom\n"
        )
        description = (output / "content" / "description.md").read_text()
        self.assertIn("A printable towel rack.", description)
        self.assertNotIn("## Licence", description)
        self.assertEqual(
            sorted(path.name for path in (output / "model-files").iterdir()),
            ["assembly.step", "assembly.stl", "part.stl"],
        )
        self.assertEqual(
            (output / "print-files" / "part.gcode").read_bytes(), b"G1 X1\n"
        )
        self.assertIn("file-descriptions.md", result["content"][-1])
        self.assertIn("model-files", (output / "UPLOAD.md").read_text())
        rendered = pp._manual_markdown(result)
        self.assertIn("| Field | File | Link |", rendered)
        self.assertIn("| Folder | Contents | Link |", rendered)
        self.assertTrue((output / "checksums.sha256").is_file())
        self.assertEqual(before, self.release.path.read_bytes())
        reused = pp._manual_package(self.release, output)
        self.assertEqual(reused["status"], "already-exists")
        self.assertIn("file-descriptions.md", reused["content"][-1])

    def test_inspection_uses_patchright_without_playwright(self):
        with patch.dict(sys.modules, {"playwright.sync_api": None}):
            with patch.object(pp, "emit") as report:
                self.assertEqual(pp.inspect_browser(self.page, pp.ORIGIN + "/"), 0)
            self.assertIn("controls", report.call_args.args[0])

    def test_inspection_reports_patchright_render_timeout(self):
        with (
            patch.object(
                self.page, "wait_for_function", side_effect=BrowserTimeout("timed out")
            ),
            self.assertRaisesRegex(pp.PublishingError, "did not finish rendering"),
        ):
            pp.inspect_browser(self.page, pp.ORIGIN + "/")

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

    def test_blocked_inspection_reports_before_waiting_and_does_not_retry(self):
        requests = []

        def blocked(route):
            requests.append(route.request.url)
            route.fulfill(
                status=403,
                content_type="text/html",
                body="<title>Just a moment...</title><p>Security checkpoint</p>",
            )

        self.page.route(pp.ORIGIN + "/", blocked)
        with patch.object(pp, "emit") as report:

            def user_finishes_review(_prompt):
                self.assertFalse(self.page.is_closed())
                self.assertEqual(self.page.title(), "Just a moment...")
                self.assertIn("HTTP 403", report.call_args.args[0]["error"])

            with patch("builtins.input", side_effect=user_finishes_review) as pause:
                status = pp.inspect_browser(self.page, pp.ORIGIN + "/", keep_open=True)
        self.assertEqual(status, 2)
        self.assertEqual(requests, [pp.ORIGIN + "/"])
        pause.assert_called_once()


if __name__ == "__main__":
    unittest.main()
