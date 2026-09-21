## Publication

<!-- 3d-model-release:begin -->
```json
{
  "release_name": "example-bracket",
  "version": "1",
  "release_folder": "/absolute/path/to/example-bracket-v1",
  "title": "Example Bracket",
  "summary": "A short one-line summary.",
  "description": "Describe what the model is for, how it works, and any limitations.",
  "print_instructions": "State material, orientation, supports, and assembly steps.",
  "assembly_instructions": "Optional assembly-only copy for a platform that stores print settings separately.",
  "tags": ["3D-Printing", "Bracket"],
  "license": "CC-BY-4.0",
  "attribution": "Creator name",
  "images": ["example-bracket-v1-01-hero.jpg"],
  "slicing": {
    "enabled": true,
    "output_folder": "../example-bracket-v1-sliced",
    "config_path": "../example-bracket-v1-sliced/example-bracket-v1-prusaslicer.ini",
    "printer": "Original Prusa i3 MK3S+",
    "material": "PLA",
    "nozzle_diameter_mm": 0.4,
    "layer_height_mm": 0.3,
    "infill_percent": 10,
    "supports": false,
    "brim": false,
    "goal": "functional draft"
  },
  "printables_files": [
    "../example-bracket-v1-sliced/example-bracket-v1-part.gcode"
  ],
  "built_model_photos": [],
  "video": null
}
```
<!-- 3d-model-release:end -->

<!-- `CC-BY-4.0` permits sharing and adaptation while requiring credit; set `attribution` to the creator name that both listings should display. `CC-BY-SA-4.0` remains supported when adaptations must also use the same licence. `assembly_instructions` is optional and lets the Printables description omit duplicated print settings while retaining assembly guidance. `printables_files` is optional. List absolute paths or paths relative to `release_folder` for `.gcode`, `.bgcode`, `.sl1`, or `.sl1s` files; they are validated and routed only to Printables. `built_model_photos` is an optional ordered list of absolute or release-folder-relative `.jpg`, `.jpeg`, or `.png` paths. They are validated and routed to both platform galleries; when present, the publishing plan also creates a Thingiverse Post-Printing block. `video`, when used, is an object with `file`, `title`, `description`, and optional `thumbnail`. -->

<!-- Include `<release-name>-v<version>-assembly.stl` in the release folder for upload to both Printables and Thingiverse, but never slice it. For an FDM release going to Printables, keep `slicing.enabled` true and replace every example profile value. Generate the config at `config_path`, slice each printable component STL separately to the corresponding ordered `printables_files` path, and keep those machine-specific files out of Thingiverse. Set `slicing.enabled` false only when the user explicitly opts out or G-code is not applicable. -->
