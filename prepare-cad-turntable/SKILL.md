---
name: prepare-cad-turntable
description: Prepare a looping Blender turntable video from exported CAD geometry for a versioned model release. Use for CAD publishing turntables; design changes and exploded assembly animations stay in the CAD workflow.
---

# Prepare CAD Turntable

Create an optional presentation video before `prepare-3d-model-release` builds the immutable manifest. Use Blender for rendering and the saved CAD export as the geometry source. Do not create a saved still or thumbnail.

## Geometry and scene

- Read the intended Publication JSON and `fusion-export.json`. Import the assembly STL for a single material, or the matching component STLs when separate materials are needed. Never import both and duplicate the geometry. Preserve component alignment; verify dimensions and orientation because STL does not encode units.
- Use available Blender tools or a local Blender Python script. Inspect the current scene first and save to a new release-specific file; preserve unrelated open scenes and existing source files.
- Reuse a turntable scene when available, with a fixed camera, neutral background, soft lighting and restrained materials. Fit the camera to the whole assembly throughout rotation. Keep its base grounded, use a shared pivot at the assembly centre and rotate all components together around the vertical axis. Materials must not imply physical features absent from the model.
- Suggested defaults: 1920 × 1080, 30 fps, 10 seconds per revolution. Adjust for model proportions and an explicitly requested destination. Record Blender version, render engine, frame range, resolution and frame rate in the scene. Use a quick preview before a full render.

## Loop and verification

Use linear rotation interpolation. For a 300-frame loop, key 0 degrees at frame 1 and 360 degrees at frame 301, rendering frames 1–300 to avoid a duplicated endpoint. Keep the camera and lights fixed.

Render a silent H.264 MP4 with a broadly compatible pixel format such as yuv420p. Rendering intermediate frames in a scratch folder is fine; do not add them to the release or gallery. Inspect representative angles, play the completed video and check the loop boundary, clipping, shadows, materials, duration and frame size. A render-start response is not proof of completion. Report any verification that could not be performed.

## Release handoff

- Save `<release-name>-v<version>-turntable.mp4` in the declared release folder. Save the reusable scene as `<release-name>-v<version>-turntable.blend` alongside it; this is local source material and is not automatically checksummed or uploaded by the current manifest builder.
- Set Publication JSON `video` to an object with `file`, `title` and `description`, using the MP4 filename. Omit `thumbnail`; leave `images` unchanged. Use verified project copy and identify the video as a CAD render.
- The current publishing schema supports one video per model release. If an assembly video is already declared, preserve it and ask which video should occupy that slot. Do not silently replace it or claim both will upload. Multi-video publishing requires a separate schema/publisher change.
- Continue `prepare-3d-model-release` to validate and checksum the MP4. Rebuild the manifest after changing a declared video; never patch an existing manifest hash. Keep any Blender source outside the shared upload list.
- Hand off authorized private video uploads to `publish-youtube` through the existing publishing coordinator. Preparing a turntable does not authorize an upload, public publication, printer upload or print start.

## YouTube and listing sections

When the user requests publishing as well as preparation, continue with [publish-youtube](../publish-youtube/SKILL.md) for the authorized private upload, then follow [the turntable listing handoff](../publish-3d-model-release/references/turntable-listings.md). This skill does not itself implement YouTube transfer. Add a native **Turntable** section to Thingiverse and a real **Turntable** heading with an embed to Printables, using the same verified turntable video ID. Keep an existing Exploded View section and its video intact. Do not generate a still or thumbnail for either listing.
