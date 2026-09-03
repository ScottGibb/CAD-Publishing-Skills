---
name: prepare-3d-model-release
description: Prepare a versioned 3D-printable model release from an Obsidian project note and Fusion 360's enabled CAD Exporter. Use when exporting STL, STEP, F3D, required drawing assets, optional Printables-only sliced files, optional built-model photos, validating a release folder, or generating shared Thingiverse and Printables listing copy and an immutable release manifest.
---

# Prepare 3D Model Release

Use the Obsidian project note as the source of truth. Do not access excluded vault areas.

## Workflow

1. Add the [publication template](assets/publication-template.md) to the project note and complete its JSON values.
2. Create the versioned release folder specified by `release_folder`. Keep it outside the vault when it contains binary assets.
3. In Fusion 360, activate and save the intended design, then run the already-enabled **Export 3D Model Release** CAD Exporter. Choose an empty staging folder. The exporter writes an assembly F3D, STEP and STL, one STL per visible solid body, a transparent preview PNG, and `fusion-export.json`.
4. Copy only the intended printable body STLs, assembly STEP, F3D archive, preview image, and `fusion-export.json` into `release_folder`, normalising their names to the `<release-name>-v<version>` convention. Do not treat the merged assembly STL as a printable component. Export the drawing PDF/PNG and any animation from Fusion separately, using the filenames declared in the Publication JSON.
5. Optionally list printer-specific `.gcode`, `.bgcode`, `.sl1`, or `.sl1s` files in the Publication JSON's `printables_files` array. Paths may be absolute or relative to `release_folder`; these files may live in a separate sliced-output folder.
6. Optionally list physical-print JPEG or PNG files in the ordered `built_model_photos` array. These may also use absolute paths or paths relative to `release_folder` and may be supplied after the CAD release assets are ready.
7. Run `uv run scripts/build_release.py --note <project-note>`. It checks required assets and optional sliced files and built-model photos, then writes `release-manifest.json`, `listing-copy.md`, and `release-summary.md` into the release folder.
8. Do not edit a generated manifest. Re-run preparation after changing note content or files.

## Required output

- At least one STL, one assembly STEP, one F3D archive, and one drawing PDF.
- A `fusion-export.json` produced by the enabled CAD Exporter, identifying the saved source design and its exported bodies or selected components.
- Asset names begin with `<release-name>-v<version>`.
- Use `license: "CC-BY-4.0"` with an explicit attribution name when reuse is allowed but creator credit is required. Keep `CC-BY-SA-4.0` supported only for releases that also require adaptations to use the same licence.
- Sliced print files are optional. When listed, they are checksummed as Printables-only assets and must never be included in the Thingiverse upload set.
- Built-model photos are optional. When listed, they are checksummed supplemental assets for both Printables and Thingiverse, in the order supplied.

## Safety

- Treat `release-manifest.json` as immutable hand-off material for `$publish-3d-model-release`.
- Do not overwrite a versioned folder without the explicit Fusion confirmation.
- Keep credentials and tokens out of the note, release folder, and vault.
