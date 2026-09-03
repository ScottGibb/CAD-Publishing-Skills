#!/usr/bin/env python3
# /// script
# requires-python = ">=3.11"
# dependencies = []
# ///
"""Validate a 3D model release described by an Obsidian project note."""

import argparse
import hashlib
import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

BEGIN = "<!-- 3d-model-release:begin -->"
END = "<!-- 3d-model-release:end -->"
REQUIRED_KEYS = {"release_name", "version", "release_folder", "title", "description",
                 "print_instructions", "tags", "license", "images", "video"}
PRINT_FILE_SUFFIXES = {".gcode", ".bgcode", ".sl1", ".sl1s"}
PHOTO_SUFFIXES = {".jpg", ".jpeg", ".png"}
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


def publication(note: Path) -> dict:
    text = note.read_text(encoding="utf-8")
    try:
        block = text.split(BEGIN, 1)[1].split(END, 1)[0]
        payload = re.search(r"```json\s*(.*?)\s*```", block, re.DOTALL).group(1)
        data = json.loads(payload)
    except (IndexError, AttributeError, json.JSONDecodeError) as error:
        raise ValueError("Add a valid Publication JSON block from assets/publication-template.md") from error
    missing = REQUIRED_KEYS - data.keys()
    if missing:
        raise ValueError(f"Publication metadata is missing: {', '.join(sorted(missing))}")
    if data["license"] not in LICENSE_LABELS:
        allowed = ", ".join(sorted(LICENSE_LABELS))
        raise ValueError(f"Unsupported license; allowed: {allowed}")
    attribution = data.get("attribution")
    if attribution is not None and (not isinstance(attribution, str) or not attribution.strip()):
        raise ValueError("attribution must be a non-empty creator name when supplied")
    if not isinstance(data["tags"], list) or not data["tags"]:
        raise ValueError("Provide at least one tag")
    printables_files = data.get("printables_files", [])
    if not isinstance(printables_files, list) or not all(isinstance(item, str) and item for item in printables_files):
        raise ValueError("printables_files must be a list of non-empty file paths")
    built_model_photos = data.get("built_model_photos", [])
    if not isinstance(built_model_photos, list) or not all(isinstance(item, str) and item for item in built_model_photos):
        raise ValueError("built_model_photos must be a list of non-empty file paths")
    return data


def artifact(path: Path, role: str) -> dict:
    return {"role": role, "path": path.name, "bytes": path.stat().st_size, "sha256": sha256(path)}


def external_artifact(path: Path, role: str) -> dict:
    return {"role": role, "path": path.name, "source_path": str(path),
            "bytes": path.stat().st_size, "sha256": sha256(path)}


def resolve_external_files(data: dict, field: str, folder: Path,
                           suffixes: set[str], label: str) -> list[Path]:
    paths = []
    for value in data.get(field, []):
        candidate = Path(value).expanduser()
        if not candidate.is_absolute():
            candidate = folder / candidate
        candidate = candidate.resolve()
        if candidate.suffix.lower() not in suffixes:
            allowed = ", ".join(sorted(suffixes))
            raise ValueError(f"Unsupported {label}: {candidate.name}; allowed: {allowed}")
        if not candidate.is_file():
            raise ValueError(f"Missing {label}: {candidate}")
        paths.append(candidate)
    if len(paths) != len(set(paths)):
        raise ValueError(f"{field} contains duplicate paths")
    names = [path.name for path in paths]
    if len(names) != len(set(names)):
        raise ValueError(f"{field} contains duplicate filenames")
    return paths


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--note", required=True, type=Path)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    note = args.note.resolve()
    data = publication(note)
    folder = Path(data["release_folder"]).expanduser().resolve()
    prefix = f"{data['release_name']}-v{data['version']}"
    if not folder.is_dir():
        raise ValueError(f"Release folder does not exist: {folder}")
    print_file_paths = resolve_external_files(
        data, "printables_files", folder, PRINT_FILE_SUFFIXES, "Printables print file"
    )
    built_photo_paths = resolve_external_files(
        data, "built_model_photos", folder, PHOTO_SUFFIXES, "built-model photo"
    )
    listed_print_files = set(print_file_paths)
    unlisted_print_files = sorted(
        path.resolve() for suffix in PRINT_FILE_SUFFIXES for path in folder.glob(f"*{suffix}")
        if path.resolve() not in listed_print_files
    )
    if unlisted_print_files:
        raise ValueError("Print files in the release folder must be listed in printables_files: "
                         + ", ".join(path.name for path in unlisted_print_files))
    stls = sorted(folder.glob(f"{prefix}-*.stl"))
    steps = sorted(folder.glob(f"{prefix}-assembly.stp")) + sorted(folder.glob(f"{prefix}-assembly.step"))
    archives = sorted(folder.glob(f"{prefix}.f3d"))
    drawings = sorted(folder.glob(f"{prefix}-drawing.pdf"))
    if not stls or len(steps) != 1 or len(archives) != 1 or len(drawings) != 1:
        raise ValueError("Required files: one or more component STL, exactly one assembly STEP, one F3D, and one drawing PDF")
    images = []
    for name in data["images"]:
        image = folder / name
        if not image.is_file():
            raise ValueError(f"Missing listed image: {name}")
        images.append(artifact(image, "image"))
    video = data["video"]
    if video:
        video_path = folder / video["file"]
        if not video_path.is_file():
            raise ValueError(f"Missing listed video: {video['file']}")
    files = ([artifact(path, "stl") for path in stls] + [artifact(steps[0], "assembly-step"),
             artifact(archives[0], "fusion-archive"), artifact(drawings[0], "drawing-pdf")] + images)
    printables_files = [external_artifact(path, "print-file") for path in print_file_paths]
    built_model_photos = [external_artifact(path, "built-model-photo") for path in built_photo_paths]
    duplicate_photo_names = ({item["path"] for item in files}
                             & {item["path"] for item in built_model_photos})
    if duplicate_photo_names:
        raise ValueError("Built-model photo filenames duplicate release assets: "
                         + ", ".join(sorted(duplicate_photo_names)))
    fusion_record = folder / "fusion-export.json"
    if not fusion_record.is_file():
        raise ValueError("Missing fusion-export.json; run the Fusion release command before preparing")
    try:
        fusion_export = json.loads(fusion_record.read_text(encoding="utf-8"))
    except json.JSONDecodeError as error:
        raise ValueError("fusion-export.json is invalid") from error
    exported_items = fusion_export.get("exported_bodies") or fusion_export.get("selected_components")
    if not fusion_export.get("source_design") or not isinstance(exported_items, list) or not exported_items:
        raise ValueError(
            "fusion-export.json lacks a source design or exported bodies/components"
        )
    manifest = {"schema": 1, "created_at": datetime.now(timezone.utc).isoformat(),
                "source_note": {"path": str(note), "sha256": sha256(note)},
                "fusion_export": fusion_export, "publication": data, "files": files}
    if printables_files:
        manifest["printables_files"] = printables_files
    if "built_model_photos" in data:
        manifest["built_model_photos"] = built_model_photos
    if video:
        manifest["video"] = {"path": video["file"], "sha256": sha256(folder / video["file"]),
                             "title": video["title"], "description": video["description"],
                             "thumbnail": video.get("thumbnail")}
    if args.dry_run:
        print(json.dumps(manifest, indent=2))
        return 0
    (folder / "release-manifest.json").write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    licence_copy = LICENSE_LABELS[data["license"]]
    if data.get("attribution"):
        licence_copy += f" — credit {data['attribution']}."
    copy = f"# {data['title']}\n\n{data.get('summary', '')}\n\n{data['description']}\n\n## Printing and assembly\n\n{data['print_instructions']}\n\n## Licence\n\n{licence_copy}\n\n## Tags\n\n" + ", ".join(data["tags"]) + "\n"
    (folder / "listing-copy.md").write_text(copy, encoding="utf-8")
    (folder / "release-summary.md").write_text(f"# {prefix}\n\nPrepared successfully. Use `release-manifest.json` with `$publish-3d-model-release`.\n", encoding="utf-8")
    counts = [f"{len(files)} shared release files"]
    if printables_files:
        counts.append(f"{len(printables_files)} Printables-only files")
    if built_model_photos:
        counts.append(f"{len(built_model_photos)} built-model photos for both platforms")
    print(f"Prepared {prefix}: {', '.join(counts)} validated in {folder}")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except ValueError as error:
        print(f"release validation failed: {error}", file=sys.stderr)
        raise SystemExit(2)
