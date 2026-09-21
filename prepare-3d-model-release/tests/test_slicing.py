import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


SCRIPT = Path(__file__).parents[1] / "scripts" / "build_release.py"


class SlicingWorkflowTests(unittest.TestCase):
    def make_release(self, root: Path, include_gcode: bool = True) -> Path:
        release = root / "example-v1"
        sliced = root / "example-v1-sliced"
        release.mkdir()
        sliced.mkdir()
        prefix = "example-v1"
        for name, content in {
            f"{prefix}-part.stl": b"solid part\nendsolid part\n",
            f"{prefix}-assembly.stl": b"solid assembly\nendsolid assembly\n",
            f"{prefix}-assembly.step": b"STEP",
            f"{prefix}.f3d": b"F3D",
            f"{prefix}-drawing.pdf": b"%PDF-1.4",
            f"{prefix}-01-hero.png": b"PNG",
        }.items():
            (release / name).write_bytes(content)
        (release / "fusion-export.json").write_text(
            json.dumps({"source_design": "Example", "exported_bodies": ["Part"]}),
            encoding="utf-8",
        )
        (sliced / f"{prefix}-prusaslicer.ini").write_text("layer_height = 0.3\n", encoding="utf-8")
        if include_gcode:
            (sliced / f"{prefix}-part.gcode").write_text("G28\nG1 X1 Y1\n", encoding="utf-8")
        publication = {
            "release_name": "example",
            "version": "1",
            "release_folder": str(release),
            "title": "Example",
            "description": "Example model",
            "print_instructions": "Print flat",
            "tags": ["example"],
            "license": "CC-BY-4.0",
            "images": [f"{prefix}-01-hero.png"],
            "slicing": {
                "enabled": True,
                "output_folder": str(sliced),
                "config_path": str(sliced / f"{prefix}-prusaslicer.ini"),
                "printer": "Original Prusa i3 MK3S+",
                "material": "PLA",
                "nozzle_diameter_mm": 0.4,
                "layer_height_mm": 0.3,
                "infill_percent": 10,
                "supports": False,
                "brim": False,
                "goal": "functional draft",
            },
            "printables_files": [str(sliced / f"{prefix}-part.gcode")],
            "built_model_photos": [],
            "video": None,
        }
        note = root / "project.md"
        note.write_text(
            "<!-- 3d-model-release:begin -->\n```json\n"
            + json.dumps(publication)
            + "\n```\n<!-- 3d-model-release:end -->\n",
            encoding="utf-8",
        )
        return note

    def run_builder(self, note: Path) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            [sys.executable, str(SCRIPT), "--note", str(note), "--dry-run"],
            text=True,
            capture_output=True,
            check=False,
        )

    def test_records_one_sliced_output_per_component(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            result = self.run_builder(self.make_release(Path(directory)))
            self.assertEqual(result.returncode, 0, result.stderr)
            manifest = json.loads(result.stdout)
            self.assertEqual(
                manifest["slicing"]["component_outputs"],
                [{"stl": "example-v1-part.stl", "print_file": "example-v1-part.gcode"}],
            )
            self.assertIn(
                {"role": "assembly-stl", "path": "example-v1-assembly.stl"},
                [
                    {"role": item["role"], "path": item["path"]}
                    for item in manifest["files"]
                ],
            )
            self.assertEqual(manifest["slicing"]["profile"]["layer_height_mm"], 0.3)

    def test_rejects_release_without_assembly_stl(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            note = self.make_release(Path(directory))
            (Path(directory) / "example-v1" / "example-v1-assembly.stl").unlink()
            result = self.run_builder(note)
            self.assertEqual(result.returncode, 2)
            self.assertIn("exactly one assembly STL", result.stderr)

    def test_rejects_missing_generated_gcode(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            result = self.run_builder(self.make_release(Path(directory), include_gcode=False))
            self.assertEqual(result.returncode, 2)
            self.assertIn("Missing Printables print file", result.stderr)


if __name__ == "__main__":
    unittest.main()
