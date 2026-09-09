---
name: publish-3d-model-release
description: Coordinate separate Thingiverse, Printables and YouTube Python publishing skills from one validated CAD release manifest. Use for a complete release with draft model listings, Printables-only G-code and an optional private video.
---

# Publish 3D Model Release

Use a `release-manifest.json` produced by `$prepare-3d-model-release`. Run the Python commands with `uv`; use the three platform skills independently for single-platform requests.

## Workflow

1. From this directory run `uv run --locked scripts/publish_release.py --manifest <manifest>` for a compact offline preflight. Do not print full plans or load script source during normal use.
2. Read only the needed platform skill: [Thingiverse](../publish-thingiverse/SKILL.md), [Printables](../publish-printables/SKILL.md), or [YouTube](../publish-youtube/SKILL.md). See [account setup](references/account-setup.md) for credentials and the coordinator configuration.
3. Run `uv run --locked scripts/publish_release.py --manifest <manifest> --config <settings.json> --execute` to invoke the platform scripts. Use `--platform thingiverse`, `--platform printables`, or `--platform youtube` to narrow a run. Credentials are file paths or environment values, never pasted into chat.
4. Read the compact results and `publication-record.json`. The scripts verify remote state, preserve other platforms' records and reuse local receipts. Resolve an actionable error without restarting completed uploads. A missing login or editor map is not a verified publication.

Thingiverse uses its documented REST upload flow. YouTube uses its Data API. Printables uses a Python Playwright adapter with a reusable inspected editor map; initial login and mapping remain required. Routine publishing does not use the Computer Use skill or screenshots. If the Python adapter fails, inspect only the affected form controls and repair the mapping. Do not silently start a manual browser workflow.

Optional Obsidian project notes remain an output through the Obsidian MCP tools when requested; the Python publishers do not write to the vault. The existing `create_publish_plan.py` remains available with `--summary` for compact validation, or without it when a full plan file is needed.

## Safety

- Never publish a Thingiverse or Printables listing; leave both as drafts.
- Never make a YouTube upload public or unlisted.
- Validate the manifest and asset hashes before any upload.
- Do not store passwords, OAuth client secrets, or access tokens in the vault.
