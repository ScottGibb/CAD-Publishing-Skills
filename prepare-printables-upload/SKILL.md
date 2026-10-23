---
name: prepare-printables-upload
description: Prepare a validated Printables manual-upload package with paste-ready Markdown, tags, model files, gallery images and printer-ready G-code.
---

# Prepare Printables Upload

Use this skill after a release manifest has been prepared. It creates the browser-free content and file packet for [upload-printables-browser](../upload-printables-browser/SKILL.md). It does not upload content or save a remote listing.

This replaces the deprecated `publish-printables` packet skill; existing package commands now run from `prepare-printables-upload`.

Before packaging a release containing G-code, follow the [user review gate](../prepare-3d-model-release/references/slicing.md#user-review-gate). Confirm that the user reviewed and approved the actual G-code and its orientation for the current file hashes. This also applies to reused G-code and existing packets. If approval is missing or invalidated by changed files, show the review and pause before continuing. Do not infer approval from a valid manifest or a general upload request.

Run from this skill directory:

```bash
uv run --locked --no-dev scripts/upload_printables.py package \
  --manifest /absolute/release/release-manifest.json \
  --format markdown
```

The command validates the immutable manifest and every declared asset, including the merged assembly STL, then creates `printables-manual-upload/` beside the manifest. The assembly STL belongs in `model-files/` alongside the component STLs and source CAD files; it does not belong in `print-files/` and must not have generated G-code. The packet contains:

- `UPLOAD.md`, with the upload order, links and descriptions.
- `content/`, with `title.md`, `summary.md`, `description.md`, print and assembly instructions, a licence selection reference and `tags.txt`.
- `model-files/`, `images/` and `print-files/`, containing the files for each Printables upload area when that group exists.
- `content/file-descriptions.md`, `release-manifest.json`, `checksums.sha256` and `package-record.json`.

Written fields are Markdown. Write tags as one lowercase, space-separated line in `tags.txt` for direct copy/paste into Printables. Split phrases and hyphenated values into individual words and remove duplicate tags, preserving their first occurrence. Do not use hyphens or one tag per line. The command prints a Markdown table with absolute links to the folders and each file. Return that table to the user after the command completes.

Use `--output-dir` to choose another destination. An existing packet for the same manifest is reused; a packet for a different manifest is rejected rather than overwritten. The source release and manifest are never modified.

The former scripted `login`, `inspect` and `draft` commands remain only as recorded diagnostics. Do not use them for uploads. After preparing the packet, use [upload-printables-browser](../upload-printables-browser/SKILL.md) for the interactive upload, presentation choices and saved-draft verification. The historical HTTP 403 applies to the scripted route; it does not establish that the interactive browser is blocked.

Do not make a listing public. The separate browser skill transfers the generated copy and files and saves an unpublished draft, with user assistance only when required.

Tests: `uv run --locked python -m unittest discover -s tests`.

## Turntable presentation handoff

For a requested turntable section, follow [the video handoff](../publish-3d-model-release/references/turntable-listings.md). Supply the verified `turntable-listing.json` beside the packet to `upload-printables-browser`; it provides the URL for a real `## Turntable` heading and video embed. The package script does not fetch YouTube receipts or automatically insert this section. Prepare this small addition separately from the checksummed packet, preserving existing copy and any Exploded view section. Do not modify packet content while retaining stale checksums. No saved still or thumbnail is needed.
