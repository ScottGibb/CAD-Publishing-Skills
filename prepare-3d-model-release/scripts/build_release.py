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
SLICING_REQUIRED_KEYS = {
    "output_folder", "config_path", "printer", "material", "nozzle_diameter_mm",
    "layer_height_mm", "infill_percent", "supports", "brim", "goal",
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
    slicing = data.get("slicing")
    if slicing is not None:
        if not isinstance(slicing, dict):
            raise ValueError("slicing must be an object")
        if not isinstance(slicing.get("enabled"), bool):
            raise ValueError("slicing.enabled must be true or false")
        if slicing["enabled"]:
            missing_slicing = SLICING_REQUIRED_KEYS - slicing.keys()
            if missing_slicing:
                raise ValueError(
                    "slicing metadata is missing: " + ", ".join(sorted(missing_slicing))
                )
            for key in ("output_folder", "config_path", "printer", "material", "goal"):
                if not isinstance(slicing[key], str) or not slicing[key].strip():
                    raise ValueError(f"slicing.{key} must be a non-empty string")
            for key in ("nozzle_diameter_mm", "layer_height_mm"):
                value = slicing[key]
                if isinstance(value, bool) or not isinstance(value, (int, float)) or value <= 0:
                    raise ValueError(f"slicing.{key} must be a positive number")
            infill = slicing["infill_percent"]
            if isinstance(infill, bool) or not isinstance(infill, (int, float)) or not 0 <= infill <= 100:
                raise ValueError("slicing.infill_percent must be between 0 and 100")
            for key in ("supports", "brim"):
                if not isinstance(slicing[key], bool):
                    raise ValueError(f"slicing.{key} must be true or false")
            if not printables_files:
                raise ValueError("slicing is enabled but printables_files is empty")
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


def resolve_declared_path(value: str, folder: Path) -> Path:
    path = Path(value).expanduser()
    if not path.is_absolute():
        path = folder / path
    return path.resolve()


def match_sliced_outputs(stls: list[Path], outputs: list[Path]) -> list[dict]:
    if len(outputs) != len(stls):
        raise ValueError("Slicing must produce exactly one print file per component STL")
    unmatched = set(outputs)
    mappings = []
    for stl in stls:
        matches = [
            path for path in unmatched
            if path.stem == stl.stem
            or path.stem.startswith(f"{stl.stem}_")
            or path.stem.startswith(f"{stl.stem}-")
        ]
        if len(matches) != 1:
            raise ValueError(f"Expected exactly one sliced output matching {stl.name}")
        output = matches[0]
        unmatched.remove(output)
        mappings.append({"stl": stl.name, "print_file": output.name})
    if unmatched:
        raise ValueError("Sliced outputs contain files that do not match a component STL")
    return mappings


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
    slicing_record = None
    slicing = data.get("slicing")
    if slicing and slicing["enabled"]:
        output_folder = resolve_declared_path(slicing["output_folder"], folder)
        config_path = resolve_declared_path(slicing["config_path"], folder)
        if not output_folder.is_dir():
            raise ValueError(f"Slicing output folder does not exist: {output_folder}")
        if config_path.suffix.lower() != ".ini" or not config_path.is_file():
            raise ValueError(f"Missing PrusaSlicer INI configuration: {config_path}")
        if not config_path.is_relative_to(output_folder):
            raise ValueError("slicing.config_path must be inside slicing.output_folder")
        if any(not path.is_relative_to(output_folder) for path in print_file_paths):
            raise ValueError("Generated print files must be inside slicing.output_folder")
        component_outputs = match_sliced_outputs(stls, print_file_paths)
        slicing_record = {
            "profile": {
                key: slicing[key]
                for key in (
                    "printer", "material", "nozzle_diameter_mm", "layer_height_mm",
                    "infill_percent", "supports", "brim", "goal",
                )
            },
            "output_folder": str(output_folder),
            "config": external_artifact(config_path, "prusaslicer-config"),
            "component_outputs": component_outputs,
        }
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
    if slicing_record:
        manifest["slicing"] = slicing_record
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
