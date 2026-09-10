#!/usr/bin/env python3
"""Thingiverse website drafts using a dedicated browser profile; no API tokens."""

import argparse
import re
import sys
import time
from pathlib import Path
from urllib.parse import urlparse

import tomllib

sys.path.insert(
    0, str(Path(__file__).resolve().parents[2] / "publish-3d-model-release" / "scripts")
)
from browser_support import (
    action_label,
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
from thingiverse_sections import fill_sections, load_sections, verify_sections

ORIGIN = "https://www.thingiverse.com"
LOGIN_URL = ORIGIN + "/"
SETTINGS = {
    "profile_dir",
    "ui_map",
    "category",
    "resume_url",
    "thing_id",
    "headed",
    "channel",
}


def thingiverse_url(url, saved=False):
    parsed = urlparse(str(url))
    pattern = (
        r"/thing:[1-9]\d*(?:/edit)?/?"
        if saved
        else r"/thing:(?:create|[1-9]\d*(?:/edit)?)/?"
    )
    if (
        parsed.scheme != "https"
        or parsed.netloc != "www.thingiverse.com"
        or parsed.query
        or parsed.fragment
        or not re.fullmatch(pattern, parsed.path)
    ):
        raise PublishingError(
            "Use a clean https://www.thingiverse.com/thing:<id> draft URL"
        )
    return str(url)


def draft_id(url):
    thingiverse_url(url, saved=True)
    return re.search(r"/thing:(\d+)", url).group(1)


def configured_settings(path):
    try:
        settings = tomllib.loads(private_path(path).read_text(encoding="utf-8"))[
            "thingiverse"
        ]
    except (OSError, ValueError, KeyError, TypeError):
        raise PublishingError(
            "Expected a private TOML file with a [thingiverse] browser-settings section"
        ) from None
    if not isinstance(settings, dict) or set(settings) - SETTINGS:
        raise PublishingError(
            "Thingiverse API credentials are no longer supported; configure profile_dir and ui_map instead"
        )
    for key, value in settings.items():
        if key == "headed":
            valid = isinstance(value, bool)
        elif key == "thing_id":
            valid = type(value) is int and value > 0
        else:
            valid = isinstance(value, str) and bool(value.strip())
        if not valid:
            raise PublishingError(f"Invalid Thingiverse browser setting: {key}")
    return settings


def validate_map(mapping, release, category=None):
    if mapping.get("schema") != 1 or mapping.get("platform") != "thingiverse":
        raise PublishingError(
            "Expected a schema 1 Thingiverse editor map from a signed-in inspection"
        )
    if mapping.get("license") != release.plan["thingiverse"][
        "license"
    ] or not mapping.get("category"):
        raise PublishingError(
            "Editor map must match the release licence and record its chosen category"
        )
    if category and category != mapping["category"]:
        raise PublishingError("Requested category differs from the editor map")
    if not {"title", "description", "tags"} <= mapping.get("fields", {}).keys():
        raise PublishingError("Editor map needs title, description and tags fields")
    if set(mapping["fields"]) - {"title", "description", "post_printing", "tags"}:
        raise PublishingError("Editor map contains an unsupported content field")
    for key in ("save_draft", "draft_marker", "choices", "uploads", "uploaded_items"):
        if key not in mapping:
            raise PublishingError(f"Editor map lacks {key}")
    if mapping.get("tag_mode", "chips") not in {
        "chips",
        "async-select",
        "comma-separated",
    }:
        raise PublishingError("Unsupported tag mode")
    if (
        mapping.get("tag_mode", "chips") != "comma-separated"
        and "tag_items" not in mapping
    ):
        raise PublishingError("Chip tags need a saved tag_items locator")
    if mapping.get("tag_mode") == "comma-separated" and any(
        "," in tag for tag in release.plan["thingiverse"]["tags"]
    ):
        raise PublishingError("Comma-separated tags cannot contain commas")
    choices = mapping["choices"]
    if {choice.get("field") for choice in choices} != {"category", "license"}:
        raise PublishingError(
            "Editor map needs verified category and licence selections"
        )
    for choice in choices:
        if (
            "locator" not in choice
            or "verify" not in choice
            or not ("expected" in choice or choice.get("checked"))
        ):
            raise PublishingError(
                "Each category/licence choice needs saved-value verification"
            )
    kinds = {asset["kind"] for asset in release.assets("thingiverse")}
    if (
        set(mapping["uploads"]) - {"file", "image"}
        or not kinds <= mapping["uploads"].keys()
        or not kinds <= mapping["uploaded_items"].keys()
    ):
        raise PublishingError(
            "Thingiverse needs file/gallery upload locators; G-code is Printables-only"
        )
    if not mapping.get("create_url") or not mapping.get("editor_url"):
        raise PublishingError(
            "Editor map needs create_url and editor_url observed on the live site; do not guess upload routes"
        )
    site_url(mapping["create_url"], ORIGIN)
    site_url(mapping["editor_url"].format(id="42"), ORIGIN)
    for action in (
        mapping["save_draft"],
        *[choice["locator"] for choice in choices],
        *mapping.get("open_editor", []),
    ):
        if re.search(
            r"\b(publish|delete|public|unlisted|purchase)\b", str(action), re.IGNORECASE
        ):
            raise PublishingError("Editor map contains a non-draft action")


def expected_fields(release, mapping):
    data = release.plan["thingiverse"]
    # The licence is selected and verified in Thingiverse's dedicated field.
    # Omit only the generated trailing licence block from legacy listing copy.
    result = {
        "title": data["title"],
        "description": data["description"].rsplit("\n\n## Licence\n\n", 1)[0],
    }
    if mapping.get("native_sections"):
        result["description"] = release.manifest["publication"]["description"]
        return result
    post_printing = data.get("post_printing", {}).get("description", "")
    if "post_printing" in mapping["fields"]:
        result["post_printing"] = post_printing
    elif post_printing:
        result["description"] += "\n\n## Post-Printing\n\n" + post_printing
    return result


def open_field(page, spec):
    for step in spec.get("open", []):
        safe_click(only(page, step))
    return only(page, spec)


def save_control(page, mapping, click=False):
    target = only(page, mapping["save_draft"])
    label = action_label(target)
    if re.search(
        r"\b(publish|delete|public|unlisted|purchase)\b", label, re.IGNORECASE
    ):
        raise PublishingError("The mapped action is not a draft operation")
    if not re.search(r"\bdraft\b", label, re.IGNORECASE):
        # Some editors use Save & View alongside a separate, unclicked Publish control.
        if "unpublished_marker" not in mapping:
            raise PublishingError(
                "A generic Save action needs an inspected unpublished_marker"
            )
        marker = only(page, mapping["unpublished_marker"])
        marker.wait_for(state="visible")
        text = action_label(marker)
        if not re.search(
            r"\b(draft|unpublished)\b|^Publish(?: Thing)?$", text, re.IGNORECASE
        ):
            raise PublishingError(
                "The editor does not prove that this is an unpublished draft"
            )
        if not re.search(r"\bsave\b", label, re.IGNORECASE):
            raise PublishingError(
                "Only a Save action can be used with an unpublished marker"
            )
    if click:
        target.wait_for(state="visible")
        if not target.is_enabled():
            raise PublishingError("The draft save control is disabled")
        # A floating site advert can cover the footer button. Activate the
        # verified button through its normal keyboard path, without force-clicks.
        target.press("Enter")


def fill_metadata(page, mapping, release):
    save_control(page, mapping)
    for name, value in expected_fields(release, mapping).items():
        open_field(page, mapping["fields"][name]).fill(value)
    for choice in mapping["choices"]:
        target = open_field(page, choice["locator"])
        if "option_label" in choice:
            target.select_option(label=choice["option_label"])
        elif choice.get("check"):
            target.check()
        else:
            safe_click(target)
    fill_tags(page, mapping, release)


def fill_tags(page, mapping, release):
    tags = open_field(page, mapping["fields"]["tags"])
    values = release.plan["thingiverse"]["tags"]
    if mapping.get("tag_mode") == "comma-separated":
        tags.fill(", ".join(values))
    else:
        existing = (
            {
                normalized(tag).casefold()
                for tag in item_names(page, mapping["tag_items"])
            }
            if "tag_items" in mapping
            else set()
        )
        for tag in values:
            if tag.casefold() in existing:
                continue
            tags.fill(tag)
            if mapping.get("tag_mode") == "async-select":
                option = page.get_by_role("option").filter(
                    has=page.get_by_text(
                        re.compile("^" + re.escape(tag) + "$", re.IGNORECASE)
                    )
                )
                option.wait_for(state="visible")
                safe_click(option)
            else:
                tags.press("Enter")
            if "tag_items" in mapping:
                deadline = time.monotonic() + 15
                while tag.casefold() not in {
                    normalized(item).casefold()
                    for item in item_names(page, mapping["tag_items"])
                }:
                    if time.monotonic() >= deadline:
                        raise PublishingError(
                            "A tag was not added; inspect the tag picker before saving"
                        )
                    page.wait_for_timeout(100)


def upload_assets(page, mapping, assets):
    for kind in ("file", "image"):
        group = [asset for asset in assets if asset["kind"] == kind]
        if group:
            target = open_field(page, mapping["uploads"][kind])
            if len(group) > 1 and target.get_attribute("multiple") is None:
                batches = [[asset] for asset in group]
            else:
                batches = [group]
            uploaded = []
            for batch in batches:
                target.set_input_files([asset["path"] for asset in batch])
                uploaded += [asset["name"] for asset in batch]
                wait_for_assets(page, mapping["uploaded_items"][kind], uploaded)
            emit(
                {"platform": "thingiverse", "uploaded_group": kind, "count": len(group)}
            )


def fill_editor(page, mapping, release):
    fill_metadata(page, mapping, release)
    upload_assets(page, mapping, release.assets("thingiverse"))


def wait_for_editor(page, mapping, release):
    # The editor renders empty controls before its saved model finishes loading.
    title = open_field(page, mapping["fields"]["title"])
    expected_title = normalized(release.plan["thingiverse"]["title"])
    deadline = time.monotonic() + 15
    while normalized(field_value(title)) != expected_title:
        if time.monotonic() >= deadline:
            raise PublishingError("Saved Thingiverse title differs from the release")
        page.wait_for_timeout(100)


def verify_editor(page, mapping, release):
    wait_for_editor(page, mapping, release)
    for name, value in expected_fields(release, mapping).items():
        if normalized(
            field_value(open_field(page, mapping["fields"][name]))
        ) != normalized(value):
            raise PublishingError(f"Saved Thingiverse {name} differs from the release")
    if mapping.get("tag_mode") == "comma-separated":
        saved_tags = field_value(open_field(page, mapping["fields"]["tags"])).split(",")
    else:
        saved_tags = item_names(page, mapping["tag_items"])
    if {normalized(tag).casefold() for tag in saved_tags if normalized(tag)} != {
        tag.casefold() for tag in release.plan["thingiverse"]["tags"]
    }:
        raise PublishingError("Saved Thingiverse tags differ from the release")
    for choice in mapping["choices"]:
        target = open_field(page, choice["verify"])
        if choice.get("checked"):
            matches = target.is_checked()
        else:
            matches = normalized(field_value(target)) == normalized(choice["expected"])
        if not matches:
            raise PublishingError(
                "Saved Thingiverse category/licence differs from the editor map"
            )
    assets = release.assets("thingiverse")
    for kind in {asset["kind"] for asset in assets}:
        wait_for_assets(
            page,
            mapping["uploaded_items"][kind],
            [asset["name"] for asset in assets if asset["kind"] == kind],
        )


def remember_url(page, state):
    try:
        model_id = draft_id(page.url)
    except PublishingError:
        return
    state.data.update({"id": model_id, "draft_url": ORIGIN + "/thing:" + model_id})
    state.save()


def run(
    release,
    state,
    page,
    mapping,
    resume_url=None,
    thing_id=None,
    interactive=False,
    accept_upload_terms=False,
    sections=None,
    update_sections=False,
):
    validate_map(mapping, release)
    if sections is not None:
        mapping = {**mapping, "native_sections": True}
    elif update_sections:
        raise PublishingError("--update-sections requires a section plan")
    recorded = state.existing_record().get("draft_url")
    candidates = [
        url for url in (resume_url, state.data.get("draft_url"), recorded) if url
    ]
    if thing_id:
        candidates.append(ORIGIN + f"/thing:{thing_id}")
    if state.data.get("id"):
        candidates.append(ORIGIN + f"/thing:{state.data['id']}")
    ids = {draft_id(url) for url in candidates}
    if len(ids) > 1:
        raise PublishingError(
            "Resume target conflicts with the recorded Thingiverse draft"
        )
    if not candidates:
        if state.data.get("pending") or state.data.get("assets"):
            raise PublishingError(
                "A draft may exist; retain the receipt and supply --resume-url after inspection"
            )
        response = page.goto(
            site_url(mapping["create_url"], ORIGIN), wait_until="domcontentloaded"
        )
        inspect_page(page, ORIGIN, response)
        for step in mapping.get("open_editor", []):
            safe_click(only(page, step))
        save_control(page, mapping)
        for spec in mapping.get("user_checkboxes", []):
            checkbox = only(page, spec)
            if (
                accept_upload_terms
                and spec == {"label": "Terms & Conditions"}
                and not checkbox.is_checked()
            ):
                if checkbox.is_visible():
                    checkbox.check()
                else:
                    page.locator("label").filter(
                        has_text=re.compile(r"^Terms & Conditions$")
                    ).click()
            if not checkbox.is_checked():
                if not interactive:
                    raise PublishingError(
                        "This draft needs the user's upload-terms acceptance; rerun with --headed before uploading"
                    )
                checkbox.scroll_into_view_if_needed()
                page.bring_to_front()
                input(
                    "Review and accept the upload terms in this draft form, then press Enter here (do not click Publish): "
                )
                if not checkbox.is_checked():
                    raise PublishingError(
                        "Upload terms were not accepted; no files uploaded"
                    )
        state.pending("editing-browser-draft")
        try:
            fill_editor(page, mapping, release)
            if sections is not None:
                fill_sections(page, sections, release)
                verify_sections(page, sections, persisted=False)
            state.pending("saving-browser-draft")
            save_control(page, mapping, click=True)
            page.wait_for_url(
                re.compile(r"https://www\.thingiverse\.com/thing:[1-9]\d*(?:/.*)?$"),
                timeout=60000,
            )
        finally:
            remember_url(page, state)
        if not state.data.get("draft_url"):
            raise PublishingError(
                "No saved draft URL was returned; reconcile the pending upload before retrying"
            )
        candidates = [state.data["draft_url"]]
    model_id = draft_id(candidates[0])
    draft_url = ORIGIN + "/thing:" + model_id
    state.data.update(
        {"id": model_id, "draft_url": draft_url, "adapter": "python-playwright"}
    )
    state.save()
    page.goto(draft_url, wait_until="domcontentloaded")
    if draft_id(page.url) != model_id:
        raise PublishingError("Unexpected draft redirect; no further actions")
    marker = only(page, mapping["draft_marker"])
    marker.wait_for(state="visible")
    if not re.search(
        r"\b(draft|unpublished)\b|has not been published",
        marker.inner_text(),
        re.IGNORECASE,
    ):
        raise PublishingError(
            "The saved Thing does not visibly identify itself as a draft"
        )
    editor_url = site_url(mapping["editor_url"].format(id=model_id), ORIGIN)
    response = page.goto(editor_url, wait_until="domcontentloaded")
    inspect_page(page, ORIGIN, response)
    if page.url.rstrip("/") != editor_url.rstrip("/"):
        raise PublishingError("Unexpected editor redirect; no further actions")
    if update_sections:
        wait_for_editor(page, mapping, release)
        save_control(page, mapping)
        state.pending("editing-requested-sections")
        fill_sections(page, sections, release)
        open_field(page, mapping["fields"]["description"]).fill(
            expected_fields(release, mapping)["description"]
        )
        verify_sections(page, sections, persisted=False)
        terms = page.get_by_label("Terms & Conditions", exact=True)
        # Existing drafts can show a disabled, unchecked terms control even
        # after acceptance at creation. Do not try to alter a disabled input.
        if terms.count() and terms.is_enabled() and not terms.is_checked():
            if not accept_upload_terms:
                raise PublishingError(
                    "Saving section changes needs explicit upload-terms authorization"
                )
            page.locator("label").filter(
                has_text=re.compile(r"^Terms & Conditions$")
            ).click()
            if not terms.is_checked():
                raise PublishingError("Upload terms could not be confirmed")
        state.pending("saving-requested-sections")
        save_control(page, mapping, click=True)
        page.wait_for_url(re.compile(re.escape(draft_url) + r"/?$"), timeout=45000)
        only(page, mapping["draft_marker"]).wait_for(state="visible")
        page.goto(editor_url, wait_until="domcontentloaded")
    verify_editor(page, mapping, release)
    section_result = verify_sections(page, sections) if sections is not None else {}
    state.data.update(section_result)
    state.done()
    result = {
        "id": model_id,
        "draft_url": draft_url,
        "visibility": "draft",
        "files_verified": len(release.assets("thingiverse")),
        "adapter": "python-playwright",
        **section_result,
    }
    state.record(result)
    emit({"platform": "thingiverse", "status": "verified", **result})


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "command", nargs="?", choices=("draft", "login", "inspect"), default="draft"
    )
    parser.add_argument("--manifest", type=Path)
    parser.add_argument(
        "--config", type=Path, help="Private TOML browser settings, not API credentials"
    )
    parser.add_argument("--profile-dir", type=Path)
    parser.add_argument("--ui-map", type=Path)
    parser.add_argument("--category")
    parser.add_argument("--resume-url")
    parser.add_argument("--thing-id", type=int)
    parser.add_argument("--state", type=Path)
    parser.add_argument(
        "--sections",
        type=Path,
        help="Native section content; otherwise read publication.thingiverse_sections from the manifest",
    )
    parser.add_argument(
        "--update-sections",
        action="store_true",
        help="Explicitly update sections on the recorded unpublished draft, without re-uploading model/gallery files",
    )
    parser.add_argument(
        "--url",
        default=LOGIN_URL,
        help="Observed site page to inspect; sign-in starts at the homepage",
    )
    parser.add_argument("--headed", action="store_true", default=None)
    parser.add_argument(
        "--pause",
        action="store_true",
        help="Pause a visible inspection for the user to handle a site checkpoint",
    )
    parser.add_argument("--channel", choices=("chrome", "chromium"))
    parser.add_argument("--execute", action="store_true")
    parser.add_argument(
        "--accept-upload-terms",
        action="store_true",
        help="Accept this Thingiverse draft's upload terms only when the user explicitly authorized it",
    )
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args(argv)
    if args.config:
        for key, value in configured_settings(args.config).items():
            if getattr(args, key) is None:
                setattr(args, key, value)
    args.channel = args.channel or "chrome"
    if args.channel not in {"chrome", "chromium"}:
        parser.error("--channel must be chrome or chromium")
    release, mapping, sections = None, None, None
    if args.command == "draft":
        if not args.manifest:
            parser.error("--manifest is required")
        release = Release(args.manifest)
        sections = load_sections(args.sections, release)
        if args.update_sections and sections is None:
            parser.error(
                "--update-sections needs --sections or publication.thingiverse_sections"
            )
        if args.ui_map:
            mapping = read_json(args.ui_map)
            validate_map(mapping, release, args.category)
        if not args.execute or args.dry_run:
            emit({**release.summary("thingiverse"), "adapter": "python-playwright"})
            return 0
        if mapping is None:
            parser.error(
                "--ui-map from a signed-in editor inspection is required; see references/browser.md"
            )
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
            manual_chrome_login(profile, site_url(args.url, ORIGIN), "thingiverse")
        return 0
    from playwright.sync_api import sync_playwright

    with file_lock(profile / ".publisher.lock"), sync_playwright() as playwright:
        context = playwright.chromium.launch_persistent_context(
            str(profile),
            channel=args.channel,
            headless=not (args.headed or args.pause or args.command == "login"),
            locale="en-GB",
        )
        context.set_default_timeout(15000)
        try:
            page = context.pages[0] if context.pages else context.new_page()
            if args.command in ("login", "inspect"):
                response = page.goto(
                    site_url(args.url, ORIGIN), wait_until="domcontentloaded"
                )
                if args.command == "login":
                    input(
                        "Complete Thingiverse sign-in and open the upload editor, then press Enter here: "
                    )
                    response = None
                elif args.pause:
                    input(
                        "Resolve any Thingiverse checkpoint in this window, then press Enter to inspect without uploading: "
                    )
                    response = None
                emit(
                    {"platform": "thingiverse", **inspect_page(page, ORIGIN, response)}
                )
                return 0
            path = (
                Path(args.state)
                if args.state
                else release.path.parent / ".publication-state" / "thingiverse.json"
            )
            with file_lock(path.with_suffix(".lock")):
                run(
                    release,
                    State(release, "thingiverse", path),
                    page,
                    mapping,
                    args.resume_url,
                    args.thing_id,
                    interactive=bool(args.headed),
                    accept_upload_terms=args.accept_upload_terms,
                    sections=sections,
                    update_sections=args.update_sections,
                )
        finally:
            context.close()
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as error:  # noqa: BLE001 - browser traces can contain credentials
        emit(
            {
                "platform": "thingiverse",
                "status": "error",
                "error": error_text(error),
                "next": "Retain publication state; use login or inspect to resolve the issue",
            }
        )
        raise SystemExit(2)
