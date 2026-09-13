---
name: prepare-3d-model-release
description: Prepare a versioned 3D-printable model release from an Obsidian project note, Fusion 360's enabled CAD Exporter, and PrusaSlicer. Use when exporting STL, STEP, F3D and drawing assets, creating printer-specific G-code from component STLs for Printables, adding optional built-model photos, validating a release folder, or generating shared Thingiverse and Printables listing copy and an immutable release manifest.
---

# Prepare 3D Model Release

Use the Obsidian project note as the source of truth. Do not access excluded vault areas.

## Workflow

1. Add the [publication template](assets/publication-template.md) to the project note and complete its JSON values.
2. Create the versioned release folder specified by `release_folder`. Keep it outside the vault when it contains binary assets.
3. In Fusion 360, activate and save the intended design, then run the already-enabled **Export 3D Model Release** CAD Exporter. Choose an empty staging folder. The exporter writes an assembly F3D, STEP and STL, one STL per visible solid body, a transparent preview PNG, and `fusion-export.json`.
4. Copy only the intended printable body STLs, assembly STEP, F3D archive, preview image, and `fusion-export.json` into `release_folder`, normalising their names to the `<release-name>-v<version>` convention. Do not treat the merged assembly STL as a printable component. Export the drawing PDF/PNG and any animation from Fusion separately, using the filenames declared in the Publication JSON.
5. For an FDM release intended for Printables, complete the Publication JSON's `slicing` object and read [the PrusaSlicer workflow](references/slicing.md). Use the PrusaSlicer MCP to analyse every intended component STL, generate or load the declared slicer configuration, and slice each component separately to the exact paths declared in `printables_files`. Never slice the merged assembly STL.
6. Verify that every intended component STL has exactly one generated G-code file, that the slicer reports success, and that the output uses the declared printer, material, nozzle, layer height, infill, support and adhesion settings. Keep the generated slicer configuration beside the G-code for reproducibility.
7. Pause for the user's explicit confirmation of the actual sliced G-code before continuing release preparation. Show each component's toolpath preview, orientation and bed-contact face, build height, print profile and warnings; provide the G-code for inspection. Follow the [G-code review gate](references/slicing.md#user-review-gate), including for reused files. A slicer recommendation, successful slice or checksum validation is not user approval.
8. Optionally list physical-print JPEG or PNG files in the ordered `built_model_photos` array. These may also use absolute paths or paths relative to `release_folder` and may be supplied after the CAD release assets are ready.
9. After G-code approval, run `uv run scripts/build_release.py --note <project-note>`. It checks required assets, the declared slicing profile, one-to-one STL/G-code coverage, optional built-model photos, and then writes `release-manifest.json`, `listing-copy.md`, and `release-summary.md` into the release folder.
10. Do not edit a generated manifest. Re-run preparation after changing note content or files.

## Required output

- At least one STL, one assembly STEP, one F3D archive, and one drawing PDF.
- A `fusion-export.json` produced by the enabled CAD Exporter, identifying the saved source design and its exported bodies or selected components.
- Asset names begin with `<release-name>-v<version>`.
- Use `license: "CC-BY-4.0"` with an explicit attribution name when reuse is allowed but creator credit is required. Keep `CC-BY-SA-4.0` supported only for releases that also require adaptations to use the same licence.
- For FDM releases destined for Printables, create one printer-specific G-code file per printable component STL. Record the exact slicer profile and generated configuration; checksum the G-code as Printables-only assets and never include it in the Thingiverse upload set. A release may omit slicing only when the user explicitly does not want Printables print files or when G-code is not applicable.
- Built-model photos are optional. When listed, they are checksummed supplemental assets for both Printables and Thingiverse, in the order supplied.

## Safety

- Treat `release-manifest.json` as immutable hand-off material for `$publish-3d-model-release`.
- Do not overwrite a versioned folder without the explicit Fusion confirmation.
- Do not guess the printer, material or nozzle. Ask when those values are not already declared in the project note.
- Generate files locally only. Never upload G-code to a printer or start a print as part of release preparation.
- Keep credentials and tokens out of the note, release folder, and vault.
