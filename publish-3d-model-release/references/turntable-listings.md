# Turntable video handoff

Read this for releases containing a turntable that should appear in Thingiverse and Printables listings. Preparation, YouTube upload and listing edits are distinct steps; rendering does not upload or embed anything.

## Upload first, then prepare the listing sections

1. Build the model release with the turntable MP4 in the existing `video` slot, without a thumbnail. If that slot contains an assembly video, resolve the choice with the user; do not replace it silently. Existing uploaded assembly videos can still be embedded alongside the turntable.
2. For an authorized upload, run `publish-youtube` for this manifest first, independently or with the coordinator's `--platform youtube`. Reuse a matching recorded upload rather than uploading again. Read the verified ID/URL and processing status from the uploader result and `publication-record.json`. Confirm this receipt belongs to the turntable MP4 and current manifest, not an older assembly animation. Do not infer completion from an initiated transfer or unfinished processing.
3. Prepare a separate `turntable-listing.json` handoff beside the manifest containing `manifest_sha256`, `video_sha256`, `video_id` and `video_url`. Copy the hashes from the validated manifest/current manifest file and the ID/URL from the verified receipt. Use a canonical `https://www.youtube.com/watch?v=<11-character-ID>` URL. This local presentation handoff is not an asset upload or an edit to the immutable manifest. If a supplied existing video is used instead, verify its identity and association with the model before preparing the handoff.
4. Prepare Thingiverse's external section plan and the Printables presentation handoff below, then run the listing workflows. The coordinator's default platform order does not perform this dependency handoff automatically. Use selected platform runs; do not assume running all platforms once adds the video sections.

Never change the manifest to insert a newly returned YouTube URL. Receipts and external section plans hold post-upload URLs. Preserve existing manifest-bound upload state.

## Thingiverse

Add a custom native section to the external `thingiverse-sections.json` passed with `--sections` (or `thingiverse.sections` in coordinator settings):

```json
{
  "title": "Turntable",
  "video_url": "https://www.youtube.com/watch?v=VIDEO_ID_11",
  "video_caption": "360-degree CAD turntable"
}
```

The snippet is one entry in `custom_sections`, not a complete section plan. Replace the example ID with the verified turntable ID. Preserve Print Settings, Post Printing, Exploded View, Technical Drawing and Assembly Instructions. The native section adapter already supports this generic video card; no Summary-only substitute is sufficient. A requested update to an existing draft uses `--update-sections`, preserving the recorded draft and reconciling mismatches rather than creating a duplicate. Reopen and verify the **Turntable** card, its caption and exact video ID separately from Exploded View.

## Printables

Pass `turntable-listing.json` alongside the validated packet to `upload-printables-browser`. The packet generator does not automatically read YouTube receipts or add a video section. Use the handoff to prepare the small description addition before transferring it: a real `## Turntable` heading and the verified video URL, rendered as an embed through the editor's supported video control or paste behavior. Keep the remainder of the prepared description and any existing Exploded view embed intact. If a Turntable section already exists, reconcile its ID and reuse it; do not append a duplicate.

Do not edit the generated packet and retain its old checksums. Keep this addition as a separate presentation handoff. No new gallery image, thumbnail or downloadable MP4 is required. Save as a draft, reopen, and verify the rendered heading and exact embedded video ID. Remove temporary insertion markers. Record section title and video ID with the verified listing result; an uploaded video alone is not a verified listing section.

## Visibility

The YouTube uploader remains private-only. A private video can be embedded in a draft but is not playable by the general public. Verify embed persistence separately from playback permissions and report the limitation. Public or unlisted visibility is a separate explicitly authorized action outside this upload workflow; do not change it to make an embed work.
