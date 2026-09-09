# Browser draft checklist

This is a manual troubleshooting reference, not the default publishing route. Prefer the separate Python platform skills and their saved verification receipts. Use this checklist only when the user requests a manual review or an adapter issue specifically needs it.

Use `publish-plan.json` as the only upload source. In both Thingiverse and Printables:

1. Start a new model listing and keep its visibility as draft.
2. Paste the title, description, tags, attribution, and licence from the matching plan section. For `CC-BY-4.0`, select **Creative Commons Attribution** / **CC BY 4.0** in the current editor and verify the named creator receives credit.
3. Upload every shared non-image file in `files` to both services and upload images in the plan order, with the first image as the hero image.
4. If `built_model_photos` is non-empty, append them to both galleries in their listed order.
5. If `thingiverse.post_printing` is present, use its description in Thingiverse's **Post-Printing** section and verify its photos are present there or in the listing gallery, according to the current editor.
6. If `printables_files` is non-empty, upload those files only to Printables' **Print Files** area. Do not upload them to Thingiverse. When the plan includes `slicing`, use its profile as the authority and confirm the detected printer, material, nozzle and layer height agree with it; also review the detected duration and weight before saving. The recorded PrusaSlicer INI is provenance material and is not a Thingiverse upload.
7. Save the draft. Re-open it and check every attachment, the licence, tags, full description, built-model photos, and the Thingiverse Post-Printing section when present.
8. Record the resulting draft URL and verification time in `publication-record.json`, using the asset template.

Do not click Publish. If a site lacks a draft state, stop before its final publication button and record that final review is still required.
