---
name: publish-3d-model-release
description: Create Thingiverse and Printables drafts, route optional sliced files only to Printables, route optional built-model photos to both platforms, and upload an optional 3D-model video privately to YouTube from a validated release manifest. Use when publishing a prepared 3D-model release while keeping model listings as drafts and videos private for final human review.
---

# Publish 3D Model Release

Use only a `release-manifest.json` produced by `$prepare-3d-model-release`. Do not access excluded vault areas.

## Workflow

1. From this skill directory, run `uv run scripts/create_publish_plan.py --manifest <release-manifest.json>` before opening any publishing site. It rejects changed or missing assets and writes a dry-run publication plan.
2. Use the connected browser in the existing signed-in Thingiverse and Printables sessions to create completed drafts from the plan. Upload shared `files` to both services, append optional `built_model_photos` to both galleries in their listed order, populate Thingiverse's Post-Printing section when the plan supplies it, upload optional `printables_files` only to Printables' Print Files area, and verify the saved draft URLs.
3. From this skill directory, run `uv run scripts/upload_youtube.py` with a Google OAuth desktop-client secret held outside the vault. The script uploads **private** only and records the result in a separate publication record.
4. Create or update `publication-record.json` beside the manifest with the two draft URLs and optional YouTube URL. Do not alter the manifest.

## Safety

- Never publish a Thingiverse or Printables listing; leave both as drafts.
- Never make a YouTube upload public or unlisted.
- Never use browser automation until the dry-run plan succeeds.
- Do not store passwords, OAuth client secrets, or access tokens in the vault.
