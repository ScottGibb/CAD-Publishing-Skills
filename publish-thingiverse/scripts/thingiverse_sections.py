"""Native Thingiverse sections using controls inspected in the live editor."""

import json
import re
import time
from urllib.parse import parse_qs, urlparse

from browser_support import normalized, safe_click
from publisher_support import PublishingError, fingerprint, read_json


def youtube_id(url):
    parsed = urlparse(url)
    value = parse_qs(parsed.query).get("v", [""])[0]
    if (
        parsed.scheme != "https"
        or parsed.netloc not in {"www.youtube.com", "youtube.com"}
        or parsed.path != "/watch"
        or set(parse_qs(parsed.query)) != {"v"}
        or not re.fullmatch(r"[A-Za-z0-9_-]{11}", value)
    ):
        raise PublishingError("Exploded View needs an existing clean YouTube watch URL")
    return value


def load_sections(path, release):
    data = (
        read_json(path)
        if path
        else release.manifest["publication"].get("thingiverse_sections")
    )
    if data is None:
        return None
    if (
        data.get("schema") != 1
        or not isinstance(data.get("print_settings"), dict)
        or not isinstance(data.get("post_printing"), dict)
    ):
        raise PublishingError(
            "Sections need schema 1, print_settings and post_printing"
        )
    custom = data.get("custom_sections", [])
    titles = [item.get("title") for item in custom]
    if any(not isinstance(title, str) or not title.strip() for title in titles) or len(
        set(titles)
    ) != len(titles):
        raise PublishingError("Custom section titles must be nonempty and unique")
    assets = {
        item["name"]: item
        for item in release.assets("thingiverse")
        if item["kind"] == "image"
    }
    for section in [data["post_printing"], *custom]:
        if (
            not section.get("text")
            and not section.get("images")
            and not section.get("video_url")
        ):
            raise PublishingError("Each requested section must have content")
        if section.get("images") and section.get("video_url"):
            raise PublishingError("Use separate image and video sections")
        for item in section.get("images", []):
            if item.get("file") not in assets or not item.get("caption"):
                raise PublishingError(
                    "Section images need a checksummed release image and a caption"
                )
        if section.get("video_url"):
            youtube_id(section["video_url"])
    for name in ("rafts", "supports"):
        if name in data["print_settings"] and not isinstance(
            data["print_settings"][name], bool
        ):
            raise PublishingError(
                f"print_settings.{name} must be a boolean when specified"
            )
    return data


def wait_for(page, condition, message, timeout=30):
    deadline = time.monotonic() + timeout
    while not condition():
        if time.monotonic() >= deadline:
            raise PublishingError(message)
        page.wait_for_timeout(100)


def card_for(page, title, kind, create=False):
    if kind in {"print-settings", "post-printing"}:
        card = page.locator("#" + kind)
        if not card.count() and create:
            name = (
                "Add Print Settings section"
                if kind == "print-settings"
                else "Add Post Printing section"
            )
            safe_click(page.get_by_role("button", name=name, exact=True))
        card.wait_for(state="attached")
    else:
        cards = page.locator('[id^="custom-"]')
        matches = [
            card
            for card in cards.all()
            if card.get_by_placeholder("Enter a title", exact=True).count() == 1
            and card.get_by_placeholder("Enter a title", exact=True).input_value()
            == title
        ]
        if len(matches) > 1:
            raise PublishingError(f"Duplicate custom section: {title}")
        if matches:
            card = matches[0]
        elif create:
            before = cards.count()
            safe_click(
                page.get_by_role("button", name="Add Custom Section", exact=True)
            )
            wait_for(
                page,
                lambda: cards.count() == before + 1,
                "Custom section was not added",
            )
            card = cards.last
            card.get_by_placeholder("Enter a title", exact=True).fill(title)
        else:
            raise PublishingError(f"Saved section is missing: {title}")
    show = card.get_by_role("button", name="Show content", exact=True)
    if show.count() == 1 and show.is_visible():
        safe_click(show)
    return card


def choose_dropdown(page, card, index, value):
    selected = card.locator(".react-select__single-value")
    control = card.get_by_role("combobox").nth(index)
    # The second dropdown is enabled only after the printer brand has loaded.
    control.wait_for(state="visible")
    safe_click(control)
    option = page.get_by_role("option", name=value, exact=True)
    option.wait_for(state="visible")
    safe_click(option)
    wait_for(
        page,
        lambda: value in selected.all_text_contents(),
        "Printer selection was not confirmed",
    )


def radio_for(card, group, label):
    for radio in card.locator(f'input[type=radio][name="{group}"]').all():
        labels = radio.evaluate(
            "e=>Array.from(e.labels||[]).map(l=>l.textContent.trim())"
        )
        if label in labels:
            return radio
    raise PublishingError(f"No inspected {group} radio for {label}")


def radio_selected(radio):
    # The saved editor marks the label selected but can leave input.checked
    # false. This matches the native value displayed on the saved detail page.
    return radio.is_checked() or radio.evaluate(
        "e=>Array.from(e.labels||[]).some(l=>l.className.includes('RadioButtonGroup__selected--'))"
    )


def fill_print_settings(page, settings):
    card = card_for(page, "Print Settings", "print-settings", create=True)
    for index, key in enumerate(("printer_brand", "printer")):
        if settings.get(key):
            choose_dropdown(page, card, index, settings[key])
    for key in ("rafts", "supports"):
        if key in settings:
            radio = radio_for(card, key, "Yes" if settings[key] else "No")
            if not radio_selected(radio):
                label = card.locator(
                    f"label[for={json.dumps(radio.get_attribute('id'))}]"
                )
                safe_click(label)
    for key, placeholder in (
        ("resolution", "Enter a recommended resolution"),
        ("infill", "Enter a recommended infill value"),
    ):
        if settings.get(key):
            card.get_by_placeholder(placeholder, exact=True).fill(str(settings[key]))
    if settings.get("material"):
        material = card.locator('input[name="filament-material"]')
        if not material.count():
            safe_click(card.get_by_role("button", name="Add Filament", exact=True))
        if material.count() != 1:
            raise PublishingError(
                "Multiple filament entries need targeted reconciliation"
            )
        button = card.get_by_role(
            "button", name="Material " + settings["material"], exact=True
        )
        if "PrintSettingsForm__selected--" not in (button.get_attribute("class") or ""):
            safe_click(button)
    if settings.get("notes"):
        notes = card.get_by_placeholder(
            "Share more information and instructions", exact=True
        )
        if not notes.count():
            safe_click(card.get_by_role("button", name="Add Notes", exact=True))
        notes.fill(settings["notes"])


def fill_content(page, card, section, release):
    if section.get("text"):
        text = card.get_by_placeholder("Tell us more...", exact=True)
        if not text.count():
            safe_click(
                card.get_by_role("button", name="Add section with text", exact=True)
            )
        if text.count() != 1:
            raise PublishingError("Multiple text blocks need targeted reconciliation")
        text.fill(section["text"])
    assets = {item["name"]: item for item in release.assets("thingiverse")}
    images = card.locator('img[class*="ContentSectionImage__contentSectionImage--"]')
    requested = section.get("images", [])
    if requested and images.count() > len(requested):
        raise PublishingError("Existing section has extra images; nothing was removed")
    for index, item in enumerate(requested):
        if images.count() <= index:
            card.locator('input[type="file"]').set_input_files(
                assets[item["file"]]["path"]
            )
            wait_for(
                page,
                lambda expected=index + 1: images.count() == expected,
                "Section image upload was not confirmed",
            )
        caption = card.get_by_placeholder("Add a caption", exact=True).nth(index)
        alt = images.nth(index).get_attribute("alt") or ""
        if caption.input_value() != item["caption"] and item["file"] not in alt:
            raise PublishingError(
                "An existing image does not match this section plan; inspect it before changing captions"
            )
        caption.fill(item["caption"])
    if section.get("video_url"):
        video_id = youtube_id(section["video_url"])
        frames = card.locator("iframe")
        if not frames.count():
            field = card.get_by_label("Enter YouTube or Vimeo URL", exact=True)
            if not field.count():
                safe_click(
                    card.get_by_role(
                        "button", name="Add section with video", exact=True
                    )
                )
            field.fill(section["video_url"])
            safe_click(card.get_by_role("button", name="Add video", exact=True))
            wait_for(page, lambda: frames.count() == 1, "Video block was not added")
        if (
            frames.count() != 1
            or f"/embed/{video_id}" != urlparse(frames.first.get_attribute("src")).path
        ):
            raise PublishingError(
                "The section contains a different video; it was not replaced"
            )
        card.get_by_placeholder("Add a caption", exact=True).fill(
            section.get("video_caption", "Exploded-view animation")
        )


def fill_sections(page, data, release):
    fill_print_settings(page, data["print_settings"])
    fill_content(
        page,
        card_for(page, "Post Printing", "post-printing", create=True),
        data["post_printing"],
        release,
    )
    for section in data.get("custom_sections", []):
        fill_content(
            page,
            card_for(page, section["title"], "custom", create=True),
            section,
            release,
        )


def verify_sections(page, data, persisted=True):
    settings = data["print_settings"]
    card = card_for(page, "Print Settings", "print-settings")
    selected = card.locator(".react-select__single-value").all_text_contents()
    for key in ("printer_brand", "printer"):
        if settings.get(key) and settings[key] not in selected:
            raise PublishingError(f"Saved print setting differs: {key}")
    for key in ("rafts", "supports"):
        if (
            key in settings
            and not radio_selected(
                radio_for(card, key, "Yes" if settings[key] else "No")
            )
        ):
            raise PublishingError(f"Saved print setting differs: {key}")
    if settings.get("material"):
        button = card.get_by_role(
            "button", name="Material " + settings["material"], exact=True
        )
        if "PrintSettingsForm__selected--" not in (button.get_attribute("class") or ""):
            raise PublishingError("Saved print material differs")
    for key, selector in (
        ("resolution", '[placeholder="Enter a recommended resolution"]'),
        ("infill", '[placeholder="Enter a recommended infill value"]'),
        ("notes", '[placeholder="Share more information and instructions"]'),
    ):
        if settings.get(key) and normalized(
            card.locator(selector).input_value()
        ) != normalized(settings[key]):
            raise PublishingError(f"Saved print setting differs: {key}")
    sections = [("Post Printing", "post-printing", data["post_printing"])] + [
        (s["title"], "custom", s) for s in data.get("custom_sections", [])
    ]
    for title, kind, section in sections:
        card = card_for(page, title, kind)
        if section.get("text") and normalized(
            card.get_by_placeholder("Tell us more...", exact=True).input_value()
        ) != normalized(section["text"]):
            raise PublishingError(f"Saved text differs: {title}")
        images = card.locator(
            'img[class*="ContentSectionImage__contentSectionImage--"]'
        )
        if images.count() != len(section.get("images", [])):
            raise PublishingError(f"Saved image count differs: {title}")
        for index, item in enumerate(section.get("images", [])):
            if (
                card.get_by_placeholder("Add a caption", exact=True)
                .nth(index)
                .input_value()
                != item["caption"]
            ):
                raise PublishingError(f"Saved image caption differs: {title}")
            source = images.nth(index).get_attribute("src") or ""
            if not source or (persisted and source.startswith("blob:")):
                raise PublishingError(f"Section image has not been persisted: {title}")
        if section.get("video_url"):
            frames = card.locator("iframe")
            if frames.count() != 1 or urlparse(
                frames.first.get_attribute("src")
            ).path != "/embed/" + youtube_id(section["video_url"]):
                raise PublishingError(f"Saved video differs: {title}")
            if card.get_by_placeholder(
                "Add a caption", exact=True
            ).input_value() != section.get("video_caption", "Exploded-view animation"):
                raise PublishingError(f"Saved video caption differs: {title}")
    return {
        "sections_verified": ["Print Settings", *[s[0] for s in sections]],
        "sections_sha256": fingerprint(data),
    }
