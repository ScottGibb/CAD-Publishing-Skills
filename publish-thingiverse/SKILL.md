---
name: publish-thingiverse
description: Create, update native sections on, or verify Thingiverse drafts with a uv-managed Python browser script. Use for model files, galleries, print settings, assembly content and tags without API tokens.
---

# Publish Thingiverse

Use this Python browser uploader with the sibling `publish-3d-model-release` validator. Keep the skills together. Commands below run from this skill directory.

1. Run `uv run --locked scripts/upload_thingiverse.py --manifest <manifest>` for compact offline preflight.
2. Read [browser setup](references/browser.md) for first-time login and editor mapping. `login --profile-dir <private-profile>` opens normal Chrome at the **homepage**, not an assumed upload route. The user completes sign-in and security checkpoints.
3. Reuse an inspected editor map when it matches the category and licence. A live-tested [Bathroom / CC-BY-4.0 map](references/bathroom-cc-by-map.json) is bundled. For another category, licence or changed site, run `inspect --profile-dir <private-profile>` and inspect the observed upload URL with `--url`; repair only the affected mapping. Never substitute the local test fixture or guess a create/edit URL.
4. For native Print Settings, Post Printing, Exploded View, Technical Drawing and Assembly Instructions, read [section content](references/sections.md). Pass `--sections <sections.json>` or prepare `publication.thingiverse_sections` in the manifest. Reuse verified release text, checksummed images and an existing video URL; do not invent settings or upload a new video.
5. Add `--execute --profile-dir <private-profile> --ui-map <map.json>` for an authorized draft upload. Reuse the same manifest, section plan and receipt. `--thing-id <id>` or `--resume-url <url>` verifies a known draft without uploading again; add `--update-sections` only when the user requests changes to that exact draft. An uncertain write requires reconciliation, not a new draft.
6. Report the actual verified draft URL or the specific blocker. Login-window closure, offline preflight and fixture tests are not proof of a live upload.

Routine use runs the script without loading its source, screenshots or model-directed clicking. Stop at CAPTCHA or access denial for the user; do not add stealth flags or copy cookies from other profiles. If the user explicitly authorizes accepting this draft's upload terms, use `--accept-upload-terms`; otherwise pause for that acceptance. This does not authorize unrelated consent or public publication. Upload images and built photos to the gallery; G-code is Printables-only. Native sections are saved, reopened and checked, including image captions and video ID. Without a section plan, the legacy Post-Printing text falls back to the mapped field or summary; that fallback is not a native section.

Keep the licence in Thingiverse's dedicated licence field; do not repeat generated licence text in the main description. The Thingiverse API path has been removed. Existing token files are not used or deleted. Browser settings can be supplied through flags or a separate private TOML file described in the reference; do not overwrite another platform's credentials.

Prioritize a signed-in inspection and one authorized draft happy path before expanding tests. Local regression checks remain available with `uv run --locked python -m unittest discover -s tests`.
