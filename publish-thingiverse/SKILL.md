---
name: publish-thingiverse
description: Create or resume a Thingiverse draft from a validated CAD release manifest using a uv-managed Python API uploader. Use for Thingiverse files, gallery images, metadata and tags.
---

# Publish Thingiverse

Use the sibling `publish-3d-model-release` validator and this Python uploader. Keep these skills together in the CAD Skills repository. Commands below run from this skill directory.

1. Run `uv run --locked scripts/upload_thingiverse.py --manifest <manifest> --category <full-category-name>` for a compact, offline preflight. Obtain the category from the release context or `--list-categories`; do not silently assign one.
2. Add `--execute --token-file <private-token-file>` to create the authorized draft. Alternatively use `THINGIVERSE_TOKEN` supplied by the user environment. Read [API setup](references/api.md) for first-time credentials or API failures.
3. Reuse the same manifest and state on later runs. Use `--thing-id <id>` to adopt a known existing draft; the script refuses published Things. It records completed files and stops on uncertain writes instead of blindly repeating them.
4. Report the returned draft URL and any verification gaps. `publication-record.json` is updated only after remote verification.

Run commands without reading the Python source into context. Full JSON is for debugging only. The script uses the official upload-guide flow, preserves multipart field order, keeps API authorization off storage requests, and never calls a publish endpoint. Upload images and built photos to the gallery; G-code belongs only on Printables. API `is_wip` describes design maturity, not draft visibility. Assembly instructions are included in the API instructions field; do not claim a dedicated Post-Printing layout was verified.

Tests: `uv run --locked python -m unittest discover -s tests`.
