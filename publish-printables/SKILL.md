---
name: publish-printables
description: Prepare a validated Printables manual-upload package with paste-ready Markdown, tags, model files, gallery images and printer-ready G-code.
---

# Publish Printables

Use this skill after a release manifest has been prepared. It creates a browser-free upload packet so the user can complete the final Printables form manually.

Run from this skill directory:

```bash
uv run --locked --no-dev scripts/upload_printables.py package \
  --manifest /absolute/release/release-manifest.json \
  --format markdown
```

The command validates the immutable manifest and every declared asset, then creates `printables-manual-upload/` beside the manifest. The packet contains:

- `UPLOAD.md`, with the upload order, links and descriptions.
- `content/`, with `title.md`, `summary.md`, `description.md`, print and assembly instructions, a licence selection reference and `tags.txt`.
- `model-files/`, `images/` and `print-files/`, containing the files for each Printables upload area when that group exists.
- `content/file-descriptions.md`, `release-manifest.json`, `checksums.sha256` and `package-record.json`.

Written fields are Markdown. Tags are newline-separated in `tags.txt`, with Printables' lowercase and hyphenated tag values already applied. The command prints a Markdown table with absolute links to the folders and each file. Return that table to the user after the command completes.

Use `--output-dir` to choose another destination. An existing packet for the same manifest is reused; a packet for a different manifest is rejected rather than overwritten. The source release and manifest are never modified.

The former `login`, `inspect` and `draft` browser commands remain only as recorded diagnostics. Printables' automated browser route is not live-verified: the site returned HTTP 403 at its security checkpoint even though the dedicated normal Chrome profile retained the sign-in. Do not retry the checkpoint, change browser fingerprints, extract tokens or present the browser adapter as a working upload path. Read [browser status](references/browser.md) when that history is relevant.

Do not make a listing public. The user reviews the generated copy, selects the appropriate category and licence, uploads the folders, and saves the model as a draft manually.

Tests: `uv run --locked python -m unittest discover -s tests`.
