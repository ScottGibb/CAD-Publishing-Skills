import hashlib
import importlib.util
import tempfile
import unittest
from pathlib import Path


SCRIPT = Path(__file__).parents[1] / "scripts" / "create_publish_plan.py"
SPEC = importlib.util.spec_from_file_location("create_publish_plan", SCRIPT)
MODULE = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(MODULE)


class SlicingMetadataTests(unittest.TestCase):
    def make_manifest(self, config: Path) -> dict:
        digest = hashlib.sha256(config.read_bytes()).hexdigest()
        return {
            "printables_files": [{"path": "example-v1-part.gcode"}],
            "slicing": {
                "profile": {"printer": "Original Prusa i3 MK3S+", "material": "PLA"},
                "config": {"source_path": str(config), "sha256": digest},
                "component_outputs": [
                    {"stl": "example-v1-part.stl", "print_file": "example-v1-part.gcode"}
                ],
            },
        }

    def test_accepts_matching_slicing_metadata(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            config = Path(directory) / "profile.ini"
            config.write_text("layer_height = 0.3\n", encoding="utf-8")
            slicing = MODULE.verify_slicing(self.make_manifest(config))
            self.assertEqual(slicing["profile"]["material"], "PLA")

    def test_rejects_changed_slicer_configuration(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            config = Path(directory) / "profile.ini"
            config.write_text("layer_height = 0.3\n", encoding="utf-8")
            manifest = self.make_manifest(config)
            config.write_text("layer_height = 0.2\n", encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "configuration changed"):
                MODULE.verify_slicing(manifest)

    def test_requires_assembly_stl_alongside_component_stls(self) -> None:
        MODULE.verify_model_files(
            [
                {"path": "part.stl", "role": "stl"},
                {"path": "assembly.stl", "role": "assembly-stl"},
            ]
        )
        with self.assertRaisesRegex(ValueError, "exactly one assembly STL"):
            MODULE.verify_model_files([{"path": "part.stl", "role": "stl"}])


if __name__ == "__main__":
    unittest.main()
