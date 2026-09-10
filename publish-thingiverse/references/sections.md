# Native Thingiverse sections

The Python adapter uses the real **Add Print Settings**, **Add Post Printing** and **Add Section** controls. It fills native cards rather than adding headings to the Summary. A section plan can be supplied with `--sections /absolute/release/thingiverse-sections.json`, or included as `publication.thingiverse_sections` before preparing the immutable manifest. Do not edit an existing manifest in place.

## Content plan

Use verified release instructions and assets. Omit unknown print settings; do not infer rafts, filament brand or colour. Printer brand and printer must exactly match Thingiverse's dropdown labels, which can differ from the release's prose (for example, `Prusa` and `I3 MK3S`). Image `file` values must be filenames of checksummed images already declared for Thingiverse. The drawing PDF stays in Thing Files; its PNG preview goes in Technical Drawing.

This example illustrates the schema, not default settings for other projects. Replace the settings, text, filenames and existing video URL with the actual release content:

```json
{
  "schema": 1,
  "print_settings": {
    "printer_brand": "Prusa",
    "printer": "I3 MK3S",
    "supports": false,
    "resolution": "0.30 mm",
    "infill": "15%",
    "material": "PLA",
    "notes": "Release-specific nozzle, brim and component instructions."
  },
  "post_printing": {
    "text": "Release-specific finishing and assembly notes.",
    "images": [{"file": "built-01.jpeg", "caption": "Completed physical print"}]
  },
  "custom_sections": [
    {
      "title": "Exploded View",
      "video_url": "https://www.youtube.com/watch?v=VIDEO_ID_11",
      "video_caption": "Exploded-view animation"
    },
    {
      "title": "Technical Drawing",
      "text": "See drawing.pdf in Thing Files for the downloadable drawing.",
      "images": [{"file": "drawing-preview.png", "caption": "Technical drawing"}]
    },
    {"title": "Assembly Instructions", "text": "The verified assembly instructions."}
  ]
}
```

`rafts` and `supports` accept booleans when known. Material uses an existing Thingiverse material button such as `PLA`; arbitrary custom materials and multiple filament entries are not implemented. Each content card supports one text block and either captioned images or one YouTube video. Use a clean `https://www.youtube.com/watch?v=<11-character-ID>` URL. This adapter embeds the existing video only: it does not upload to YouTube or change its visibility. A private video remains private and will not become publicly playable through embedding.

## Create, verify or update

From the repository root, first run offline preflight with the section plan:

```bash
uv run --locked --project publish-thingiverse \
  publish-thingiverse/scripts/upload_thingiverse.py \
  --manifest "/absolute/release/release-manifest.json" \
  --ui-map publish-thingiverse/references/bathroom-cc-by-map.json \
  --sections "/absolute/release/thingiverse-sections.json"
```

For an authorized new draft, add `--profile-dir /absolute/private/thingiverse-profile --headed --execute`. Add `--accept-upload-terms` only when the user has explicitly authorized that acceptance for this draft. Otherwise the visible run pauses for the user before uploading.

Rerunning the same command with `--execute` and the same receipt is read-only remote verification. Keep supplying the same section plan. To change sections on the recorded unpublished draft, the user must request that edit; then add `--update-sections`. This operation reuses matching cards, updates the Summary to avoid duplicate inline sections, and does not re-upload model or gallery files. Unexpected extra blocks/images or a different video stop for targeted reconciliation; nothing is deleted automatically.

Verification reopens the saved editor and checks print settings, section titles/text, image captions and persisted image URLs, and the embedded video ID. The receipt and publication record include `sections_verified` and `sections_sha256`. Changing a separate section plan does not silently change a remote draft: a verification mismatch requires an explicit update.

The coordinator accepts `thingiverse.sections` as a file path. Edit authorization and terms acceptance remain per-run flags on the direct Thingiverse command, not stored standing permissions in coordinator settings.
