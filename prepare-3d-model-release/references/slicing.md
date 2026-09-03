# PrusaSlicer workflow

Read this reference for an FDM release intended for Printables or whenever the user requests generated G-code.

## Required profile

The Publication JSON `slicing` object is the source of truth. When `enabled` is true it must declare:

- `output_folder` and `config_path`, absolute or relative to the release folder.
- `printer`, `material`, `nozzle_diameter_mm`, `layer_height_mm`, and `infill_percent`.
- Boolean `supports` and `brim` values.
- A short `goal` describing the intended balance, such as functional draft or display quality.

Do not infer a printer, nozzle or material from an unrelated prior release. Ask the user if a required value is missing.

## Generate the files

1. Identify only the printable component STLs in the release folder. Do not use a merged assembly STL.
2. Run the PrusaSlicer MCP mesh analysis and printability check for every component. Confirm the exported orientation is suitable; do not silently rotate a component without recording that change.
3. Generate one PrusaSlicer INI at `config_path` using the declared printer, material, nozzle and goal. Pass the declared layer height, infill, supports and brim settings as explicit custom settings, then verify the generated configuration reflects them. If the user supplied an existing INI, preserve it and use it directly.
4. Run the PrusaSlicer MCP slicing operation once per component STL, using the same verified configuration and the corresponding exact `printables_files` output path.
5. Check every operation succeeded and record the returned duration, filament usage and other available statistics. Confirm each output exists, is non-empty and belongs to exactly one component STL.
6. Run the release builder only after all declared outputs and the INI exist. It enforces one-to-one component coverage and records hashes and profile metadata in the manifest.

Generated G-code is machine-specific. Upload it only to Printables. This workflow creates local files; it never uploads to a printer and never starts a print.
