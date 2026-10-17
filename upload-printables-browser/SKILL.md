---
name: upload-printables-browser
description: Upload prepared CAD release content and files to Printables through the interactive web browser, save an unpublished draft, and verify it after reopening. Use for Printables uploads or explicitly requested updates to an existing draft. Content generation and slicing belong to prepare-printables-upload and prepare-3d-model-release.
---

# Upload Printables in the Browser

Consume the validated manifest and content/file packet from [prepare-printables-upload](../prepare-printables-upload/SKILL.md). This skill only transfers prepared content, applies Printables presentation choices, and verifies the saved draft. Do not export CAD, slice, rewrite the project documentation, or replace the preparation workflow.

Use the available interactive browser tools, normally `mcp__cua_repl`, and their documented APIs. Do not run the retired Printables scripted browser adapter. Read [browser workflow](references/browser-workflow.md) for upload mechanics and verified recovery paths.

## Inputs and authorization

- Use the intended release manifest, packet guide, file inventory and checksums. Keep model/source files, gallery images, drawing PDFs and G-code in their correct upload areas. Include the merged assembly STL as a reference model, never as a slicing input.
- For G-code, reuse approval only for the exact reviewed STL, configuration and G-code hashes; follow the preparation skill's [review gate](../prepare-3d-model-release/references/slicing.md#user-review-gate) if approval is missing. Do not infer approval from successful validation.
- Inspect the existing publication record and any open editor first. Reuse a known draft ID and preserve the user's existing edits. Update only the requested content; reconcile uncertain uploads or saves before creating anything new.
- User authorization to upload covers preparing and saving this draft. Leave it unpublished. Login, checkpoints and terms prompts follow the browser tool's confirmation rules. Do not invent account credentials, design provenance, printer settings or a replacement video upload.

## Upload and presentation

1. Reuse an appropriate browser tab. If no draft exists, navigate through the visible Create → Model action. Retain the draft URL as soon as the site assigns it, even before the explicit save completes.
2. Fill the prepared title and summary, respecting the displayed length limits. Select the best fitting category and exact prepared licence, and add the prepared space-separated tags. Select original/remix/reupload and AI provenance from verified user information; AI-assisted slicing or uploading alone does not establish AI-created geometry.
3. Upload the validated files using the documented file chooser. A ZIP containing only the intended assets is a useful one-step handoff when the site's current form supports ZIP extraction. Verify the unpacked categories and filenames; do not leave the ZIP as the only downloadable model asset.
4. Order the gallery explicitly: CAD render first, built-model photos in the middle, technical drawing sheets last. ZIP extraction order is not reliable. Verify the saved first and last images rather than assuming filename order.
5. Transfer the prepared description as Markdown with real headings such as `## Assembly`, `## Technical drawing` and `## Exploded view`. If the form uses a rich-text editor, use its supported heading formatting or a Markdown conversion path and verify that the resulting headings are actual headings. Plain paragraphs that look like titles, or literal unrendered `##` text, are insufficient.
6. When this upload includes G-code, omit the print-settings section from the Printables description; retain required per-file printer/material/nozzle/layer/time/weight metadata and select the main printer. This does not change Thingiverse, whose description/native settings still need print settings. If G-code is absent, use the prepared print instructions.
7. Put each technical drawing in both the gallery and the description's Technical drawing section at readable resolution, with the downloadable PDF retained. Embed the already-authorized video URL through the editor's video control or supported paste behavior; verify the intended video ID. Do not change its privacy. Before saving, remove any temporary insertion markers (for example `VIDEOINSERT` or `VIDEOSINERT`) from the description, and verify their absence again after reopening the saved draft. An existing video embed does not prove its placeholder text was removed.
8. Keep DRAFT selected and save. Reopen or reload that exact editor after the save completes. Verify title, summary, category, licence, tags, provenance, gallery order, all expected files, G-code profile metadata, rendered headings, inline drawing and video. A populated form or assigned ID alone is not a completed upload.
9. Preserve other platforms' publication records. Record the verified Printables draft ID/URL, visibility, verification time and any user-assisted upload step. Return the draft link, a saved screenshot of the result and any precise unresolved item.

## Keep context small

Read the packet summary once. Batch deterministic field actions and inspect a focused state afterward; use small accessibility diffs or bounded snapshots rather than full-page dumps. Use semantic locators for repeated fields, and current accessibility indices for one-off controls. Take screenshots for visual verification or a concrete blocker, not after every click. Do not loop through failed selectors or repeatedly reopen the same unsaved upload.
