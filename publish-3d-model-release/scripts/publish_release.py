#!/usr/bin/env python3
"""Coordinate the separate uv-managed publishing skills with compact output."""

import argparse
import subprocess
from pathlib import Path

from publisher_support import (
    PublishingError,
    Release,
    child_environment,
    emit,
    read_json,
)

SETTINGS = {
    "thingiverse": ("category", "config", "profile_dir", "ui_map", "sections", "resume_url", "thing_id", "state", "headed", "channel"),
    "printables": ("profile_dir", "ui_map", "resume_url", "state", "headed", "channel"),
    "youtube": ("config", "client_secrets", "token_path", "session_path", "video_id", "state"),
}


def command(platform, release, settings, execute=False):
    skill = Path(__file__).resolve().parents[2] / f"publish-{platform}"
    args = [
        "uv",
        "run",
        "--locked",
        "--project",
        str(skill),
        str(skill / "scripts" / f"upload_{platform}.py"),
        "--manifest",
        str(release.path),
    ]
    if set(settings) - set(SETTINGS[platform]):
        raise PublishingError(
            f"Unknown {platform} setting; see references/account-setup.md"
        )
    for key, value in settings.items():
        if value is None or value is False:
            continue
        args.append("--" + key.replace("_", "-"))
        if value is not True:
            args.append(str(value))
    if execute:
        args.append("--execute")
    return args


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", required=True, type=Path)
    parser.add_argument("--config", type=Path)
    parser.add_argument("--platform", nargs="+", choices=tuple(SETTINGS))
    parser.add_argument("--execute", action="store_true")
    args = parser.parse_args(argv)
    release = Release(args.manifest)
    platforms = args.platform or ["thingiverse", "printables"] + (
        ["youtube"] if release.plan.get("video") else []
    )
    platforms = list(dict.fromkeys(platforms))
    if not args.config:
        if args.execute:
            parser.error(
                "--config is required to execute; see references/account-setup.md"
            )
        for platform in platforms:
            emit(release.summary(platform))
        return 0
    config = read_json(args.config)
    for platform in platforms:
        if platform not in config:
            raise PublishingError(f"Configuration lacks {platform}")
    # Validate every configured command before the first external write.
    failed = []
    for platform in platforms:
        result = subprocess.run(
            command(platform, release, config[platform]),
            check=False,
            env=child_environment(),
        )
        if result.returncode:
            failed.append(platform)
    if failed or not args.execute:
        return 2 if failed else 0
    for platform in platforms:
        result = subprocess.run(
            command(platform, release, config[platform], execute=True),
            check=False,
            env=child_environment(),
        )
        if result.returncode:
            failed.append(platform)
    record_path = release.path.parent / "publication-record.json"
    record = read_json(record_path) if record_path.exists() else {}
    pending = (
        ["youtube"]
        if "youtube" in platforms
        and (record.get("youtube") or {}).get("processing") != "succeeded"
        else []
    )
    emit(
        {
            "status": "needs-attention"
            if failed
            else "processing"
            if pending
            else "completed",
            "failed_platforms": failed,
            "pending_platforms": pending,
            "record": str(record_path),
        }
    )
    return 2 if failed else 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (PublishingError, ValueError, OSError, KeyError) as error:
        emit({"status": "error", "error": str(error)})
        raise SystemExit(2)
