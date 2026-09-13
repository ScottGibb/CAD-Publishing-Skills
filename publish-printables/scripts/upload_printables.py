#!/usr/bin/env python3
"""Scripted Printables drafts with a reusable, inspected editor map. No screenshots."""

import argparse
import re
import sys
from pathlib import Path
from urllib.parse import urlparse

sys.path.insert(
    0, str(Path(__file__).resolve().parents[2] / "publish-3d-model-release" / "scripts")
)
from browser_support import (
    field_value,
    inspect_page,
    item_names,
    manual_chrome_login,
    normalized,
    only,
    safe_click,
    site_url,
    wait_for_assets,
)
from publisher_support import (
    PublishingError,
    Release,
    State,
    emit,
    error_text,
    file_lock,
    private_path,
    read_json,
)
from publisher_support import (
    printables_tags as platform_tags,
)

ORIGIN = "https://www.printables.com"
CREATE_URL = ORIGIN + "/model/create"


def printables_url(url):
    parsed = urlparse(url)
    if (
        parsed.scheme != "https"
        or parsed.netloc != "www.printables.com"
        or not parsed.path.startswith("/model/")
    ):
        raise PublishingError(
            "Editor URLs must be on https://www.printables.com/model/"
        )
    return url


def validate_map(mapping, release):
    if mapping.get("schema") != 1:
        raise PublishingError("Unsupported editor map; see references/browser.md")
    for name in ("title", "summary", "description", "tags"):
        if name not in mapping.get("fields", {}):
            raise PublishingError(f"Editor map lacks the {name} field")
    for name in ("save_draft", "draft_marker", "tag_items", "choices"):
        if name not in mapping:
            raise PublishingError(f"Editor map lacks {name}")
    license_id = release.plan["printables"]["license"]
    if mapping.get("license") != license_id or not mapping.get("category"):
        raise PublishingError(
            "Editor map must record the chosen category and match the release licence"
        )
    if {choice.get("field") for choice in mapping["choices"]} != {
        "category",
        "license",
    }:
        raise PublishingError(
            "Editor map needs verified category and licence selections"
        )
    for choice in mapping["choices"]:
        if "verify" not in choice or not (
            "expected" in choice or choice.get("checked")
        ):
            raise PublishingError(
                "Every selection needs a saved-value verification locator"
            )
    for kind in {asset["kind"] for asset in release.assets("printables")}:
        if kind not in mapping.get("uploads", {}) or kind not in mapping.get(
            "uploaded_items", {}
        ):
            raise PublishingError(
                f"Editor map lacks upload/verification locators for {kind}"
            )
    if release.plan["printables"].get("slicing"):
        required = {"printer", "material", "nozzle_diameter_mm", "layer_height_mm"}
        if not required <= {
            check["profile_key"] for check in mapping.get("slicing_checks", [])
        }:
            raise PublishingError(
                "slicing_checks must verify printer, material, nozzle and layer height"
            )
    for spec in (mapping["save_draft"], *[x["locator"] for x in mapping["choices"]]):
        if re.search(r"\b(publish|delete|public|unlisted)\b", str(spec), re.IGNORECASE):
            raise PublishingError("Editor map contains a non-draft action")


def expected_fields(release):
    data = release.plan["printables"]
    return {name: data[name] for name in ("title", "summary", "description")}


def verify_editor(page, mapping, release):
    for name, value in expected_fields(release).items():
        if normalized(field_value(only(page, mapping["fields"][name]))) != normalized(
            value
        ):
            raise PublishingError(f"Saved Printables {name} differs from the release")
    tags = {normalized(x).lower() for x in item_names(page, mapping["tag_items"])}
    if tags != set(platform_tags(release.plan["printables"]["tags"])):
        raise PublishingError("Saved Printables tags differ from the release")
    for choice in mapping["choices"]:
        target = only(page, choice["verify"])
        if choice.get("checked"):
            if not target.is_checked():
                raise PublishingError(
                    "Saved Printables category/licence selection was not confirmed"
                )
        elif normalized(field_value(target)) != normalized(choice["expected"]):
            raise PublishingError(
                "Saved Printables category/licence differs from the editor map"
            )
    assets = release.assets("printables")
    for kind in {a["kind"] for a in assets}:
        wait_for_assets(
            page,
            mapping["uploaded_items"][kind],
            [a["name"] for a in assets if a["kind"] == kind],
        )
    profile = release.plan["printables"].get("slicing", {}).get("profile", {})
    for check in mapping.get("slicing_checks", []):
        expected = str(profile[check["profile_key"]])
        if expected not in only(page, check["locator"]).inner_text():
            raise PublishingError(
                f"Detected slicing value differs: {check['profile_key']}"
            )


def fill_editor(page, mapping, release):
    # Resolve every field and upload input before the first content mutation.
    for spec in mapping["fields"].values():
        only(page, spec)
    for spec in mapping["uploads"].values():
        only(page, spec)
    only(page, mapping["save_draft"])
    for name, value in expected_fields(release).items():
        only(page, mapping["fields"][name]).fill(value)
    for choice in mapping["choices"]:
        target = only(page, choice["locator"])
        if "option_label" in choice:
            target.select_option(label=choice["option_label"])
        elif choice.get("check"):
            target.check()
        else:
            safe_click(target)
    tags = only(page, mapping["fields"]["tags"])
    for tag in platform_tags(release.plan["printables"]["tags"]):
        tags.fill(tag)
        tags.press("Enter")
    assets = release.assets("printables")
    for kind in ("file", "image", "print_file"):
        group = [asset for asset in assets if asset["kind"] == kind]
        if group:
            only(page, mapping["uploads"][kind]).set_input_files(
                [a["path"] for a in group]
            )
            wait_for_assets(
                page, mapping["uploaded_items"][kind], [a["name"] for a in group]
            )
            emit(
                {"platform": "printables", "uploaded_group": kind, "count": len(group)}
            )


def run(release, state, page, mapping, resume_url=None):
    validate_map(mapping, release)
    url = resume_url or state.data.get("draft_url")
    if (
        state.data.get("pending") or state.existing_record().get("draft_url")
    ) and not url:
        raise PublishingError(
            "A draft may exist; inspect it and pass --resume-url to verify it without reuploading"
        )
    if not url:
        page.goto(CREATE_URL, wait_until="domcontentloaded")
        if urlparse(page.url).netloc != "www.printables.com":
            raise PublishingError("Sign in with the login command before uploading")
        state.pending("editing")
        fill_editor(page, mapping, release)
        state.pending("saving-draft")
        safe_click(only(page, mapping["save_draft"]), draft=True)
        try:
            page.wait_for_url(
                re.compile(r"https://www\.printables\.com/model/\d+.*"), timeout=60000
            )
        finally:
            if re.match(r"https://www\.printables\.com/model/\d+", page.url):
                state.data["draft_url"] = page.url
                state.save()
        url = state.data.get("draft_url")
        if not url:
            raise PublishingError(
                "No saved draft URL was returned; inspect the draft before trying again"
            )
    url = printables_url(url)
    match = re.match(r"https://www\.printables\.com/model/(\d+)", url)
    if not match:
        raise PublishingError(
            "A saved Printables draft URL must include a numeric model ID"
        )
    model_id = match.group(1)
    draft_url = f"https://www.printables.com/model/{model_id}"
    page.goto(draft_url, wait_until="domcontentloaded")
    marker = only(page, mapping["draft_marker"])
    marker.wait_for(state="visible", timeout=30000)
    if not re.search(r"\bdraft\b", marker.inner_text(), re.IGNORECASE):
        raise PublishingError(
            "The saved model does not visibly identify itself as a draft"
        )
    editor_url = printables_url(
        mapping.get(
            "reopen_editor_url", "https://www.printables.com/model/{id}/edit"
        ).format(id=model_id)
    )
    page.goto(editor_url, wait_until="domcontentloaded")
    verify_editor(page, mapping, release)
    state.data.update({"id": model_id, "draft_url": draft_url})
    state.done()
    result = {"id": model_id, "draft_url": draft_url, "visibility": "draft"}
    state.record(result)
    emit({"platform": "printables", "status": "verified", **result})


def inspect_browser(page, url, pause=False, keep_open=False):
    """Report the inspection before waiting, including a site access failure."""
    from patchright.sync_api import TimeoutError as BrowserTimeout

    status = 0
    try:
        response = page.goto(site_url(url, ORIGIN), wait_until="domcontentloaded")
        if pause:
            input(
                "Resolve any Printables checkpoint in this window, then press Enter to inspect without uploading: "
            )
            response = None
        result = {
            "platform": "printables",
            **inspect_page(page, ORIGIN, response, timeout_error=BrowserTimeout),
        }
    except Exception as error:  # Keep browser diagnostics credential-safe.
        if not keep_open:
            raise
        status = 2
        result = {
            "platform": "printables",
            "status": "error",
            "error": error_text(error),
            "next": "The browser remains open for review; no automatic retries or uploads",
        }
    emit(result)
    if keep_open:
        page.bring_to_front()
        input(
            "Inspection finished. Chrome will remain open for you. Press Enter here only when you want to close it; this does not retry or upload: "
        )
    return status


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "command", nargs="?", choices=("draft", "login", "inspect"), default="draft"
    )
    parser.add_argument("--manifest", type=Path)
    parser.add_argument("--profile-dir", type=Path)
    parser.add_argument("--ui-map", type=Path)
    parser.add_argument(
        "--url",
        default=ORIGIN + "/",
        help="Observed site page to inspect; sign-in starts at the homepage",
    )
    parser.add_argument("--resume-url")
    parser.add_argument("--state", type=Path)
    parser.add_argument("--headed", action="store_true")
    parser.add_argument(
        "--pause",
        action="store_true",
        help="Pause a visible inspection for the user to handle a site checkpoint",
    )
    parser.add_argument(
        "--keep-open",
        action="store_true",
        help="Show the inspection result, then keep Chrome open for review even when access is blocked",
    )
    parser.add_argument("--channel", choices=("chrome", "chromium"), default="chrome")
    parser.add_argument("--execute", action="store_true")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args(argv)
    if args.keep_open and (args.command != "inspect" or not sys.stdin.isatty()):
        parser.error("--keep-open requires inspect in an interactive terminal")
    release = None
    if args.command == "draft":
        if not args.manifest:
            parser.error("--manifest is required")
        release = Release(args.manifest)
        if args.ui_map:
            mapping = read_json(args.ui_map)
            validate_map(mapping, release)
        if not args.execute or args.dry_run:
            result = release.summary("printables")
            result["tags"] = platform_tags(result["tags"])
            result["adapter"] = "python-patchright"
            emit(result)
            return 0
        if not args.ui_map:
            parser.error(
                "--ui-map from an inspected editor is required; see references/browser.md"
            )
        mapping = read_json(args.ui_map)
        validate_map(mapping, release)
    if not args.profile_dir:
        parser.error("--profile-dir is required for login, inspection and execution")
    profile = private_path(args.profile_dir)
    profile.mkdir(parents=True, exist_ok=True, mode=0o700)
    if profile.stat().st_mode & 0o077:
        raise PublishingError(
            "The browser profile must have owner-only permissions (chmod 700)"
        )
    if args.command == "login" and args.channel == "chrome":
        with file_lock(profile / ".publisher.lock"):
            manual_chrome_login(profile, site_url(args.url, ORIGIN), "printables")
        return 0
    from patchright.sync_api import TimeoutError as BrowserTimeout
    from patchright.sync_api import sync_playwright

    with file_lock(profile / ".publisher.lock"), sync_playwright() as playwright:
        context = playwright.chromium.launch_persistent_context(
            str(profile),
            channel=args.channel,
            headless=not (
                args.headed or args.pause or args.keep_open or args.command == "login"
            ),
            locale="en-GB",
        )
        context.set_default_timeout(15000)
        try:
            page = context.pages[0] if context.pages else context.new_page()
            if args.command == "inspect":
                return inspect_browser(page, args.url, args.pause, args.keep_open)
            if args.command == "login":
                response = page.goto(
                    site_url(args.url, ORIGIN), wait_until="domcontentloaded"
                )
                input(
                    "Complete Printables sign-in in the opened browser, then press Enter here: "
                )
                response = None
                emit(
                    {
                        "platform": "printables",
                        **inspect_page(
                            page, ORIGIN, response, timeout_error=BrowserTimeout
                        ),
                    }
                )
                return 0
            path = (
                args.state
                or release.path.parent / ".publication-state" / "printables.json"
            )
            with file_lock(path.with_suffix(".lock")):
                run(
                    release,
                    State(release, "printables", path),
                    page,
                    mapping,
                    args.resume_url,
                )
        finally:
            context.close()
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as error:  # noqa: BLE001 - do not expose browser traces or credentials
        # Browser tracebacks can expose page content. Return one compact diagnostic.
        emit(
            {
                "platform": "printables",
                "status": "error",
                "error": error_text(error),
                "next": "Use inspect for a focused form check; retain publication state",
            }
        )
        raise SystemExit(2)
