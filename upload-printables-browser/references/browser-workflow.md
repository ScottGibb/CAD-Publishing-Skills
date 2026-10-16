# Interactive Printables workflow

## Evidence and limits

On 16 October 2026 the Codex in-app browser passed Printables' security check, the user signed in to Prusa Account, and an authorized model draft was saved and reopened successfully. The user selected one prepared ZIP manually; automatic file selection was not verified. The unpacked release contained model/CAD assets, a PDF, G-code and gallery images. A full-resolution drawing pasted through the browser clipboard persisted inside the description, and the existing YouTube URL became a video embed.

The older headless/scripted browser route returned HTTP 403. That history does not prove the interactive browser is blocked. Conversely, one successful interactive draft does not guarantee future login, chooser behavior, gallery ordering or site controls. Inspect the current UI and report the actual outcome.

## File chooser and one-step handoff

Read the selected browser's file-upload documentation before the first upload. Register its file-chooser event before clicking the observed upload input or Browse control, then set only the validated absolute asset paths. Catch event failures so an unhandled rejection does not reset the browser session.

If selection times out, inspect the resulting UI once, follow the documented troubleshooting route, and use a supported native picker if available. Do not copy cookies, alter browser fingerprints, inspect hidden app state, or retry browser variants. If the picker cannot be controlled, ask the user to select a single prepared upload ZIP through Browse and continue with the rest of the draft afterward. Clearly report this assistance; do not claim fully automatic uploading.

Build a temporary ZIP from only the manifest's validated upload assets, with unique basenames: component STLs, reference assembly STL, source CAD, drawing PDF, declared gallery images/build photos and approved G-code. Exclude OAuth files, browser profiles, receipts, upload-session URLs and unrelated folder contents. Use existing packaging tools rather than building another browser-upload script. A ZIP is transport convenience, not a replacement for the release manifest or approval record.

After extraction, check the individual model files, Other Files PDF, gallery images and Print Files. Distinct box/lid or other actual components should contribute to time and weight totals; only genuine variants should be excluded. Do not invent brand, colour, duration or weight when the site cannot parse them. Reorder the gallery using the current UI: render first, physical photos next, drawings last.

## Markdown and inline drawing

Assemble the upload description from the prepared Markdown fields without changing engineering claims. Use Markdown headings and confirm their rendered semantics in the editor and saved draft. In a rich editor, apply heading styles when pasted Markdown/HTML becomes plain paragraphs. When G-code is present, omit the descriptive print-settings section while keeping assembly, drawing and video content.

Insert the drawing at the Technical drawing heading using the editor's supported image insertion. If its file chooser fails but browser clipboard APIs support PNG data, copy the validated local drawing image to the browser clipboard, position the cursor in that section, and paste through normal keyboard input. This succeeded in the live workflow. Wait for the upload placeholder to disappear and verify a persisted image source with readable dimensions after saving. Do not substitute the gallery thumbnail for the full drawing. Avoid duplicating an existing image on a resumed draft.

An existing authorized YouTube watch URL may auto-embed when pasted; otherwise use the visible Insert Video control. Verify the saved iframe/video ID. Never assume that an empty paragraph or a heading proves an embed exists.

## Save, reopen, reconcile

Use the visible Save Draft control with DRAFT selected. The form may assign a model ID during file or inline-image upload; record that URL and continue with the same draft. Wait for saving to finish, then reopen/reload the known editor and verify persisted content and draft status. Preserve a screenshot and a compact record of asset counts, gallery order and content checks. If saving is uncertain, inspect that draft before attempting another create action.

If the user takes over or asks to stop, stop browser mutations and report the last confirmed save and any transferred assets. Do not restart the upload or overwrite the user's manual changes.
