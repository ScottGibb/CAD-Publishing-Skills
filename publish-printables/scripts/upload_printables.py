#!/usr/bin/env python3
"""Prepare Printables manual-upload packets and retain browser diagnostics."""

import argparse
import hashlib
import json
import re
import shutil
import sys
import tempfile
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

PACKAGE_SCHEMA = 1
PACKAGE_FOLDERS = {
    "file": "model-files",
    "image": "images",
    "print_file": "print-files",
}
ROLE_DESCRIPTIONS = {
    "stl": "Printable model part",
    "assembly-stl": "Printable assembly model",
    "assembly-step": "Complete assembly CAD file",
    "f3d": "Fusion 360 source design",
    "drawing-pdf": "Technical drawing",
    "image": "Gallery image",
    "built-model-photo": "Photo of the completed print",
    "print_file": "Printer-ready G-code",
}


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


def _file_hash(path):
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _markdown_cell(value):
    return str(value).replace("|", "\\|").replace("\n", " ").strip()


def _manual_asset_rows(release):
    """Return validated Printables assets with human-readable upload guidance."""
    source_items = {}
    for item in release.plan["printables"]["files"]:
        source_items[str((release.path.parent / item["path"]).resolve())] = item
    for item in release.plan["printables"].get("print_files", []):
        source_items[str(Path(item["source_path"]).resolve())] = item
    for item in release.plan["printables"].get("built_model_photos", []):
        source_items[str(Path(item["source_path"]).resolve())] = item

    rows = []
    for asset in release.assets("printables"):
        source_item = source_items.get(asset["path"], {})
        role = source_item.get("role", asset["kind"])
        description = source_item.get("description") or ROLE_DESCRIPTIONS.get(
            role, "File for Printables upload"
        )
        rows.append(
            {
                "name": asset["name"],
                "kind": asset["kind"],
                "role": role,
                "description": description,
                "source": asset["path"],
                "sha256": asset["sha256"],
                "bytes": asset["bytes"],
                "folder": PACKAGE_FOLDERS[asset["kind"]],
                "target": f"{PACKAGE_FOLDERS[asset['kind']]}/{asset['name']}",
            }
        )
    return rows


def _manual_content(release):
    data = release.plan["printables"]
    publication = release.manifest["publication"]
    content = {
        "title.md": data["title"].strip(),
        "summary.md": data["summary"].strip(),
        "description.md": publication["description"].strip(),
        "tags.txt": "\n".join(platform_tags(data["tags"])),
        "print-settings.md": publication["print_instructions"].strip(),
    }
    assembly = publication.get("assembly_instructions", "").strip()
    if assembly:
        content["assembly-instructions.md"] = assembly
    license_text = publication["license"]
    attribution = publication.get("attribution", "").strip()
    if attribution:
        license_text += f"\n\nAttribution: {attribution}"
    content["license.md"] = license_text
    return content


def _folder_rows(asset_rows):
    folders = [
        {
            "name": "Listing copy",
            "folder": "content",
            "description": "Paste-ready Markdown fields and newline-separated tags.",
        }
    ]
    descriptions = {
        "model-files": "Model and source files for the Printables Files section.",
        "images": "Gallery images for the Printables model page.",
        "print-files": "Printer-ready G-code for the Printables Print Files section.",
    }
    for folder in ("model-files", "images", "print-files"):
        if any(row["folder"] == folder for row in asset_rows):
            folders.append(
                {
                    "name": folder.replace("-", " ").title(),
                    "folder": folder,
                    "description": descriptions[folder],
                }
            )
    return folders


def _write_manual_guide(root, content, asset_rows, folders):
    field_rows = [
        ("Title", "content/title.md"),
        ("Summary", "content/summary.md"),
        ("Description", "content/description.md"),
        ("Tags", "content/tags.txt"),
        ("Print settings", "content/print-settings.md"),
    ]
    if "assembly-instructions.md" in content:
        field_rows.append(("Assembly instructions", "content/assembly-instructions.md"))
    field_rows.append(("Licence selection reference", "content/license.md"))
    field_rows.append(("File descriptions", "content/file-descriptions.md"))
    lines = [
        f"# {content['title.md'].strip()}",
        "",
        "This packet was generated from a validated release manifest.",
        "Use the Markdown files for Printables' written fields. Add each line in "
        "tags.txt as one tag.",
        "",
        "## Listing copy",
        "",
        "| Printables field | Copy file |",
        "| --- | --- |",
    ]
    lines.extend(f"| {label} | [{path}]({path}) |" for label, path in field_rows)
    lines.extend(
        [
            "",
            "## Upload folders",
            "",
            "| Folder | Contents | Location |",
            "| --- | --- | --- |",
        ]
    )
    lines.extend(
        f"| {folder['name']} | {folder['description']} | "
        f"[{folder['folder']}/]({folder['folder']}/) |"
        for folder in folders
    )
    lines.extend(
        [
            "",
            "## File descriptions",
            "",
            "| Filename | Type | Description | Upload folder |",
            "| --- | --- | --- | --- |",
        ]
    )
    lines.extend(
        f"| `{_markdown_cell(row['name'])}` | {_markdown_cell(row['role'])} | "
        f"{_markdown_cell(row['description'])} | [{row['folder']}/]({row['folder']}/) |"
        for row in asset_rows
    )
    lines.extend(
        [
            "",
            "Keep G-code in Printables' Print Files section. Review the title, "
            "description, tags, licence and draft visibility before saving.",
            "",
        ]
    )
    (root / "UPLOAD.md").write_text("\n".join(lines), encoding="utf-8")


def _write_file_descriptions(root, asset_rows):
    lines = [
        "# Printables file descriptions",
        "",
        "| Filename | Type | Description | Upload folder |",
        "| --- | --- | --- | --- |",
    ]
    lines.extend(
        f"| `{_markdown_cell(row['name'])}` | {_markdown_cell(row['role'])} | "
        f"{_markdown_cell(row['description'])} | `{row['folder']}/` |"
        for row in asset_rows
    )
    lines.append("")
    (root / "content" / "file-descriptions.md").write_text(
        "\n".join(lines), encoding="utf-8"
    )


def _manual_result(output, content, asset_rows, folders, status):
    return {
        "platform": "printables",
        "status": status,
        "mode": "manual-upload-package",
        "output_dir": str(output),
        "guide": str(output / "UPLOAD.md"),
        "content": [str(output / "content" / name) for name in content],
        "folders": [
            {
                **folder,
                "path": str(output / folder["folder"]),
            }
            for folder in folders
        ],
        "files": [
            {
                **row,
                "path": str(output / row["target"]),
            }
            for row in asset_rows
        ],
    }


def _manual_package(release, output):
    output = Path(output).expanduser().resolve()
    if output == release.path.parent or release.path.is_relative_to(output):
        raise PublishingError("Manual package output must be separate from the release manifest")
    output.parent.mkdir(parents=True, exist_ok=True)
    record_path = output / "package-record.json"
    if output.exists() or output.is_symlink():
        if record_path.is_file():
            try:
                record = json.loads(record_path.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError):
                record = {}
            if (
                record.get("schema") == PACKAGE_SCHEMA
                and record.get("manifest_sha256") == release.digest
            ):
                return _manual_result(
                    output,
                    record["content"],
                    record["files"],
                    record["folders"],
                    "already-exists",
                )
        raise PublishingError(
            f"Manual package directory already exists: {output}; choose another --output-dir"
        )

    content = _manual_content(release)
    content_files = [*content, "file-descriptions.md"]
    asset_rows = _manual_asset_rows(release)
    folders = _folder_rows(asset_rows)
    with tempfile.TemporaryDirectory(prefix=f".{output.name}.", dir=output.parent) as temporary:
        root = Path(temporary)
        (root / "content").mkdir()
        for folder in folders:
            (root / folder["folder"]).mkdir(exist_ok=True)
        for name, value in content.items():
            (root / "content" / name).write_text(value.rstrip() + "\n", encoding="utf-8")
        _write_file_descriptions(root, asset_rows)
        for row in asset_rows:
            target = root / row["target"]
            shutil.copy2(row["source"], target)
        shutil.copy2(release.path, root / "release-manifest.json")
        _write_manual_guide(root, content, asset_rows, folders)
        checksum_lines = []
        for path in sorted(root.rglob("*")):
            if path.is_file():
                checksum_lines.append(
                    f"{_file_hash(path)}  {path.relative_to(root)}"
                )
        (root / "checksums.sha256").write_text(
            "\n".join(checksum_lines) + "\n", encoding="utf-8"
        )
        record = {
            "schema": PACKAGE_SCHEMA,
            "manifest_sha256": release.digest,
            "content": content_files,
            "folders": folders,
            "files": asset_rows,
        }
        (root / "package-record.json").write_text(
            json.dumps(record, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
        )
        root.rename(output)
    return _manual_result(
        output,
        content_files,
        asset_rows,
        folders,
        "created",
    )


def _manual_markdown(result):
    lines = [
        "## Printables manual upload package",
        "",
        f"Guide: [{Path(result['guide']).name}](<{result['guide']}>)",
        "",
        "### Listing copy",
        "",
        "| Field | File | Link |",
        "| --- | --- | --- |",
    ]
    lines.extend(
        f"| {_markdown_cell(Path(path).stem.replace('-', ' ').title())} | "
        f"`{Path(path).name}` | [{Path(path).name}](<{path}>) |"
        for path in result["content"]
    )
    lines.extend(
        [
            "",
            "### Upload folders",
            "",
            "| Folder | Contents | Link |",
            "| --- | --- | --- |",
        ]
    )
    lines.extend(
        f"| {folder['name']} | {folder['description']} | "
        f"[{folder['folder']}/](<{folder['path']}>) |"
        for folder in result["folders"]
    )
    lines.extend(
        [
            "",
            "### Uploaded files",
            "",
            "| File | Description | Upload folder | Link |",
            "| --- | --- | --- | --- |",
        ]
    )
    lines.extend(
        f"| `{_markdown_cell(row['name'])}` | {_markdown_cell(row['description'])} | "
        f"{row['folder']}/ | [{row['name']}](<{row['path']}>) |"
        for row in result["files"]
    )
    return "\n".join(lines) + "\n"


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
        "command",
        nargs="?",
        choices=("package", "draft", "login", "inspect"),
        default="draft",
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
    parser.add_argument(
        "--output-dir",
        type=Path,
        help="Destination for the browser-free manual upload package",
    )
    parser.add_argument(
        "--format",
        choices=("json", "markdown"),
        default="json",
        help="Output format for the manual package result",
    )
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
    if args.command == "package":
        if not args.manifest:
            parser.error("--manifest is required")
        if args.execute:
            parser.error("--execute is not valid for a manual package")
        release = Release(args.manifest)
        output = args.output_dir or release.path.parent / "printables-manual-upload"
        result = _manual_package(release, output)
        if args.format == "markdown":
            print(_manual_markdown(result), end="")
        else:
            emit(result)
        return 0
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
