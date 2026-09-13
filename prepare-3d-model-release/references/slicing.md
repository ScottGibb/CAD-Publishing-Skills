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
6. Complete the user review gate below before running the release builder or handing the release to a publishing skill. The builder's checks do not establish that the user approved the print orientation.

## User review gate

Apply this gate to newly sliced and reused G-code. Before continuing release preparation, packaging or upload:

1. Present a toolpath/layer preview of each actual G-code file, with its filename and a link for the user to inspect it. State the orientation in plain language (which face touches the bed and which direction the part points), build height, printer, material, nozzle, layer height, infill, supports and brim. Highlight any overhang, adhesion or other slicing warnings. Do not substitute a CAD render or an orientation score for a G-code preview. If a preview cannot be produced, provide the file for the user to open in their G-code viewer and state that you could not visually verify it.
2. Ask explicitly: "Please review these sliced G-code files. Are the orientation and print settings correct, and may I continue preparing and uploading this release?" Wait for an affirmative answer covering the displayed files. General permission to slice, a request to use the slicer's recommendation, silence or a previous release's approval does not satisfy this gate.
3. Record the user's confirmation in a separate `gcode-review.json` beside the release, with the reviewed component STL, slicer configuration and G-code paths and SHA-256 hashes, the displayed orientation/profile, and the confirmation text and date. Record only confirmation actually received; never fabricate approval or edit an immutable manifest to add it. This is a workflow handoff record, not a claim that the existing Python validators enforce approval.
4. An existing confirmation may be reused for the exact unchanged reviewed files; do not ask again unnecessarily. If the G-code, component STL or slicer configuration changes, or the user rejects the orientation, correct and re-slice as authorized, show the new result and obtain fresh confirmation. When resuming without evidence of approval for the current hashes, pause for review, even if the old manifest validates.

After approval, run the release builder. It enforces one-to-one component coverage and records hashes and profile metadata in the manifest. User review does not mean the G-code has been physically test-printed.

Generated G-code is machine-specific. Upload it only to Printables. This workflow creates local files; it never uploads to a printer and never starts a print.
