"""Small DOM helpers shared by the browser-backed publishing skills."""

import re
import shutil
import subprocess
import sys
import time
from pathlib import Path
from urllib.parse import urlparse

from publisher_support import PublishingError, emit


def site_url(url, origin):
    parsed = urlparse(str(url))
    if (
        parsed.scheme != "https"
        or parsed.netloc != urlparse(origin).netloc
        or parsed.query
        or parsed.fragment
    ):
        raise PublishingError(f"Use a clean page URL on {origin}")
    return str(url)


def manual_chrome_login(profile, url, platform):
    """User-owned sign-in in ordinary Chrome, without automation/debugging flags."""
    executable = (
        "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"
        if sys.platform == "darwin"
        else shutil.which("google-chrome")
    )
    if not executable or not Path(executable).is_file():
        raise PublishingError("Google Chrome is required for manual Chrome sign-in")
    process = subprocess.Popen(
        [executable, f"--user-data-dir={profile}", "--no-first-run", url],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    try:
        input(
            f"Sign in to {platform} in this dedicated Chrome window, return to the site, then press Enter here: "
        )
    finally:
        if process.poll() is None:
            process.terminate()
            try:
                process.wait(timeout=15)
            except subprocess.TimeoutExpired:
                raise PublishingError(
                    "Close the dedicated Chrome window before running inspect"
                ) from None
    emit(
        {
            "platform": platform,
            "status": "login-window-closed",
            "next": "Run inspect to verify the saved session",
        }
    )


def inspect_page(page, origin, response, *, timeout_error=None):
    """Report access failures using the caller's browser timeout exception."""
    if timeout_error is None:
        from playwright.sync_api import TimeoutError as timeout_error

    if response and response.status >= 400:
        raise PublishingError(
            f"Site returned HTTP {response.status}; complete any checkpoint in normal Chrome before retrying"
        )
    if re.search(
        r"just a moment|access denied|attention required", page.title(), re.IGNORECASE
    ):
        raise PublishingError(
            "Browser security checkpoint; complete it in normal Chrome before retrying"
        )
    if urlparse(page.url).netloc != urlparse(origin).netloc:
        raise PublishingError(
            "Sign-in is required; use login and return to the site before inspection"
        )
    page.locator("body").wait_for(state="visible")
    try:
        page.wait_for_function(
            "() => Array.from(document.querySelectorAll('a,button,input,textarea,select')).some(e => e.getClientRects().length)",
            timeout=15000,
        )
    except timeout_error:
        raise PublishingError(
            "The page did not finish rendering its controls; inspect in a visible browser"
        ) from None
    return {
        "url": page.url.split("?")[0].split("#")[0],
        "title": page.title(),
        "controls": control_inventory(page),
        "navigation": page.locator("a[href]").evaluate_all(
            """els => els.filter(e => e.getClientRects().length).map(e => ({text:e.innerText.trim().slice(0,100),href:e.getAttribute('href').split(/[?#]/)[0]})).filter(e => /log.?in|sign.?in|upload|create|new thing|add model|draft|edit/i.test(e.text+' '+e.href)).slice(0,30)"""
        ),
    }


def locator(page, spec):
    modes = [
        key for key in ("label", "role", "placeholder", "text", "css") if key in spec
    ]
    if len(modes) != 1:
        raise PublishingError("Each editor locator must have exactly one selector")
    if spec.get("frame"):
        page = page.frame_locator(spec["frame"])
    if "label" in spec:
        return page.get_by_label(spec["label"], exact=True)
    if "role" in spec and "name" in spec:
        return page.get_by_role(spec["role"], name=spec["name"], exact=True)
    if "placeholder" in spec:
        return page.get_by_placeholder(spec["placeholder"], exact=True)
    if "text" in spec:
        return page.get_by_text(spec["text"], exact=True)
    if "css" in spec:
        return page.locator(spec["css"])
    raise PublishingError("A role locator requires an accessible name")


def only(page, spec):
    result = locator(page, spec)
    if result.count() == 0:
        result.wait_for(state="attached")
    if result.count() != 1:
        raise PublishingError(
            "Editor map no longer matches exactly one control; run inspect"
        )
    return result


def action_label(target):
    return " ".join(
        (
            target.get_attribute("aria-label") or "",
            target.inner_text(),
            target.get_attribute("value") or "",
        )
    ).strip()


def safe_click(target, draft=False):
    label = action_label(target)
    if re.search(
        r"\b(publish|delete|public|unlisted|purchase)\b", label, re.IGNORECASE
    ):
        raise PublishingError("The mapped action is not a draft operation")
    if draft and not re.search(r"\bdraft\b", label, re.IGNORECASE):
        raise PublishingError("The save control does not explicitly say draft")
    target.click()


def normalized(text):
    return " ".join(str(text).split())


def field_value(target):
    return target.evaluate(
        "e => /^(INPUT|TEXTAREA|SELECT)$/.test(e.tagName) ? e.value : e.innerText"
    )


def item_names(page, spec):
    items = locator(page, spec)
    attribute = spec.get("name_attribute")
    if attribute:
        return items.evaluate_all(
            "(els, attr) => els.map(e => e.getAttribute(attr) || '')", attribute
        )
    return items.all_text_contents()


def wait_for_assets(page, spec, names, timeout=60):
    deadline = time.monotonic() + timeout
    while True:
        if set(names) <= {normalized(x) for x in item_names(page, spec)}:
            return
        if time.monotonic() >= deadline:
            raise PublishingError(
                "Uploaded filenames were not confirmed; inspect the draft and retain the state file"
            )
        page.wait_for_timeout(500)


def control_inventory(page):
    """Inspect visible form controls, never input values, cookies or page scripts."""
    return page.locator(
        "input:not([type=password]):not([type=hidden]),textarea,select,[contenteditable=true],button,[role=tab]"
    ).evaluate_all(
        """els => els.filter(e => e.type==='file' || e.getClientRects().length).slice(0,100).map(e => ({
          tag:e.tagName.toLowerCase(),type:e.getAttribute('type'),id:e.id,
          name:e.getAttribute('name'),accept:e.getAttribute('accept'),multiple:e.multiple,
          role:e.getAttribute('role'),maxlength:e.getAttribute('maxlength'),
          label:e.labels ? Array.from(e.labels).map(l=>l.innerText.trim()).join(' ') : null,
          aria_label:e.getAttribute('aria-label'),placeholder:e.getAttribute('placeholder'),
          text:e.tagName==='BUTTON' || e.getAttribute('role')==='tab' ? e.innerText.trim().slice(0,120) : null,
          options:e.tagName==='SELECT' ? Array.from(e.options).map(o=>({label:o.text,value:o.value})).slice(0,80) : undefined
        }))"""
    )
