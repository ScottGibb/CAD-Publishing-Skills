#!/usr/bin/env python3
# /// script
# requires-python = ">=3.11"
# dependencies = []
# ///
"""Verify a prepared release and generate a draft-only publication plan."""

import argparse
import hashlib
import json
import sys
from datetime import datetime, timezone
from pathlib import Path


LICENSE_LABELS = {
    "CC-BY-4.0": "CC BY 4.0",
    "CC-BY-SA-4.0": "CC BY-SA 4.0",
}


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def verify_shared_file(folder: Path, item: dict) -> None:
    path = folder / item["path"]
    if not path.is_file() or sha256(path) != item["sha256"]:
        raise ValueError(f"Release asset changed or is missing: {item['path']}")


def verify_printables_file(item: dict) -> None:
    path = Path(item["source_path"])
    if not path.is_file() or sha256(path) != item["sha256"]:
        raise ValueError(f"Printables print file changed or is missing: {item['path']}")


def verify_built_model_photo(item: dict) -> None:
    path = Path(item["source_path"])
    if not path.is_file() or sha256(path) != item["sha256"]:
        raise ValueError(f"Built-model photo changed or is missing: {item['path']}")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--manifest", required=True, type=Path)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    manifest_path = args.manifest.resolve()
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    if manifest.get("schema") != 1:
        raise ValueError("Unsupported release manifest")
    note = Path(manifest["source_note"]["path"])
    if not note.is_file() or sha256(note) != manifest["source_note"]["sha256"]:
        raise ValueError("Project note changed since release preparation; prepare a new manifest")
    folder = manifest_path.parent
    for item in manifest["files"]:
        verify_shared_file(folder, item)
    printables_files = manifest.get("printables_files", [])
    if not isinstance(printables_files, list):
        raise ValueError("Invalid printables_files in release manifest")
    for item in printables_files:
        verify_printables_file(item)
    built_model_photos = manifest.get("built_model_photos", [])
    if not isinstance(built_model_photos, list):
        raise ValueError("Invalid built_model_photos in release manifest")
    for item in built_model_photos:
        verify_built_model_photo(item)
    video = manifest.get("video")
    if video and (not (folder / video["path"]).is_file() or sha256(folder / video["path"]) != video["sha256"]):
        raise ValueError("Release video changed or is missing")
    data = manifest["publication"]
    if data["license"] not in LICENSE_LABELS:
        raise ValueError(f"Unsupported release license: {data['license']}")
    licence_copy = LICENSE_LABELS[data["license"]]
    attribution = data.get("attribution", "").strip()
    if attribution:
        licence_copy += f" — credit {attribution}."
    assembly_instructions = data.get("assembly_instructions", "").strip()
    thingiverse_print_settings = data["print_instructions"].strip()
    if assembly_instructions and thingiverse_print_settings.endswith(assembly_instructions):
        thingiverse_print_settings = thingiverse_print_settings[:-len(assembly_instructions)].strip()
    thingiverse_description = (f"{data['description']}\n\n## Print Settings\n\n"
                               f"{thingiverse_print_settings}\n\n## Licence\n\n{licence_copy}")
    printables_description = data["description"]
    if data.get("assembly_instructions"):
        printables_description += ("\n\n## Post-Printing / Assembly\n\n"
                                   f"{data['assembly_instructions']}")
    printables_description += f"\n\n## Licence\n\n{licence_copy}"
    thingiverse = {"title": data["title"], "description": thingiverse_description,
                   "tags": data["tags"], "license": data["license"],
                   "attribution": attribution,
                   "files": manifest["files"], "built_model_photos": built_model_photos}
    if assembly_instructions or built_model_photos:
        post_printing_copy = assembly_instructions
        if built_model_photos:
            photo_note = "Photos of the completed print are included in the gallery."
            post_printing_copy = f"{post_printing_copy}\n\n{photo_note}".strip()
        thingiverse["post_printing"] = {
            "description": post_printing_copy,
            "photos": built_model_photos,
        }
    printables = {"title": data["title"], "description": printables_description,
                  "tags": data["tags"], "license": data["license"],
                  "attribution": attribution,
                  "files": manifest["files"], "print_files": printables_files,
                  "built_model_photos": built_model_photos}
    plan = {"schema": 1, "created_at": datetime.now(timezone.utc).isoformat(),
            "manifest": str(manifest_path), "mode": "draft-only",
            "thingiverse": thingiverse, "printables": printables,
            "files": manifest["files"], "printables_files": printables_files,
            "built_model_photos": built_model_photos, "video": video}
    if args.dry_run:
        print(json.dumps(plan, indent=2))
        return 0
    output = folder / "publish-plan.json"
    output.write_text(json.dumps(plan, indent=2) + "\n", encoding="utf-8")
    print(f"Draft-only publish plan written to {output}")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (ValueError, KeyError, json.JSONDecodeError) as error:
        print(f"publish plan failed: {error}", file=sys.stderr)
        raise SystemExit(2)
