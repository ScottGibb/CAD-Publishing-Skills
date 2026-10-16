---
name: publish-3d-model-release
description: Coordinate Thingiverse drafts, Printables manual upload packages and private YouTube uploads from one validated CAD release manifest.
---

# Publish 3D Model Release

Use a `release-manifest.json` produced by `$prepare-3d-model-release`. Run the Python commands with `uv`; use the platform skills independently for single-platform requests.

The shared manifest must include the merged assembly STL with role `assembly-stl`. Send it to both Printables and Thingiverse with the component STLs and source CAD files. Never include it in slicing component mappings or generate G-code from it.

## Workflow

For releases containing G-code, check the [user review gate](../prepare-3d-model-release/references/slicing.md#user-review-gate) before continuing to packaging or uploads. Require actual user approval for the current STL, configuration and G-code hashes, including reused releases. If approval is missing or the files changed, show the G-code review and pause. An offline preflight may diagnose the release while awaiting approval, but passing validation is not approval. Preserve existing remote uploads while a revised slice awaits review.

For releases with technical drawings, confirm each sheet preview is a declared gallery image for both platforms and is referenced in the Thingiverse Technical Drawing section plan. A successful preflight or verified text-only section does not establish these image placements. Resolve missing declarations before uploads; the drawing PDF remains a separate downloadable file.

1. From this directory run `uv run --locked scripts/publish_release.py --manifest <manifest>` for a compact offline preflight. Do not print full plans or load script source during normal use.
2. Read only the needed platform skill: [Thingiverse](../publish-thingiverse/SKILL.md), [Printables packet preparation](../prepare-printables-upload/SKILL.md) and [browser upload](../upload-printables-browser/SKILL.md), or [YouTube](../publish-youtube/SKILL.md). See [account setup](references/account-setup.md) for credentials and the coordinator configuration.
3. Run `uv run --locked scripts/publish_release.py --manifest <manifest> --config <settings.json> --execute` to invoke the platform scripts. Use `--platform thingiverse`, `--platform printables`, or `--platform youtube` to narrow a run. Credentials are file paths or environment values, never pasted into chat.
4. Read the compact results and `publication-record.json`. The Printables branch creates a browser-free packet and reports `ready-for-manual-upload` with `next_skill: upload-printables-browser`; continue with that skill for an authorized upload. The CLI does not drive the interactive browser; Thingiverse and YouTube retain their remote verification and receipt behavior. Resolve an actionable error without restarting completed uploads.

Thingiverse uses a Python Playwright adapter with a reusable inspected editor map. Printables content generation remains in `prepare-printables-upload`; remote draft creation uses `upload-printables-browser` through the interactive browser. YouTube uses its Data API. Read only the selected workflow. Account login and checkpoints can require user action; a successful local packet is not proof of a saved remote draft.

For Thingiverse native print settings, post-printing photos and custom assembly/drawing/video sections, pass a `thingiverse.sections` content-plan path in coordinator settings or prepare `publication.thingiverse_sections` in the manifest. Read the Thingiverse skill's section reference for the schema. Changes to an existing draft use its direct `--update-sections` command only when requested; default reruns verify without editing.

Optional Obsidian project notes remain an output through the Obsidian MCP tools when requested; the Python publishers do not write to the vault. The existing `create_publish_plan.py` remains available with `--summary` for compact validation, or without it when a full plan file is needed.

## Safety

- Never publish a Thingiverse or Printables listing; leave both as drafts.
- Never make a YouTube upload public or unlisted.
- Validate the manifest and asset hashes before any upload.
- Do not store passwords, OAuth client secrets, or access tokens in the vault.
