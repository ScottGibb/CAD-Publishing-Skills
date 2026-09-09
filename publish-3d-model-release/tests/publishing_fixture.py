"""Small synthetic release; never reaches a publishing service."""

import hashlib
import importlib.util
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "publish-3d-model-release" / "scripts"))


def module(platform):
    path = ROOT / f"publish-{platform}" / "scripts" / f"upload_{platform}.py"
    spec = importlib.util.spec_from_file_location(f"test_{platform}_module", path)
    result = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(result)
    return result


def make_manifest(folder):
    folder = Path(folder)
    files = []
    for name, role in (
        ("part.stl", "stl"),
        ("assembly.step", "assembly-step"),
        ("preview.png", "image"),
    ):
        path = folder / name
        path.write_bytes(b"synthetic upload fixture " + name.encode())
        files.append(
            {
                "path": name,
                "role": role,
                "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
            }
        )
    note = folder / "release-note.md"
    note.write_text("Synthetic release input.")
    gcode = folder / "part.gcode"
    gcode.write_bytes(b"G1 X1\n")
    video = folder / "video.mp4"
    video.write_bytes(b"synthetic video bytes")
    manifest = {
        "schema": 1,
        "source_note": {
            "path": str(note),
            "sha256": hashlib.sha256(note.read_bytes()).hexdigest(),
        },
        "publication": {
            "title": "Towel Rack",
            "summary": "A towel rack.",
            "description": "A printable towel rack.",
            "print_instructions": "PLA, 0.2 mm",
            "assembly_instructions": "Slide parts together.",
            "license": "CC-BY-4.0",
            "tags": ["towel rack", "bathroom"],
            "attribution": "Fixture Author",
        },
        "files": files,
        "printables_files": [
            {
                "path": gcode.name,
                "source_path": str(gcode),
                "sha256": hashlib.sha256(gcode.read_bytes()).hexdigest(),
            }
        ],
        "video": {
            "path": video.name,
            "title": "Towel Rack exploded view",
            "description": "Assembly animation.",
            "sha256": hashlib.sha256(video.read_bytes()).hexdigest(),
        },
    }
    path = folder / "release-manifest.json"
    path.write_text(json.dumps(manifest))
    return path
