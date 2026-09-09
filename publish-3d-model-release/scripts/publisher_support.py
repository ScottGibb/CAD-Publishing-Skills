"""Shared release validation, compact output and resumable publication records."""

import fcntl
import hashlib
import json
import os
import re
import tempfile
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path

from create_publish_plan import build_plan, sha256


class PublishingError(RuntimeError):
    pass


def emit(value):
    print(json.dumps(value, ensure_ascii=False, separators=(",", ":")), flush=True)


def error_text(error):
    """Network exceptions can include credentials or signed URLs in their message."""
    return str(error) if isinstance(error, PublishingError) else type(error).__name__


def child_environment():
    """Each uv child selects its own locked project environment."""
    return {key: value for key, value in os.environ.items() if key != "VIRTUAL_ENV"}


def printables_tags(tags):
    return list(dict.fromkeys(re.sub(r"\s+", "-", tag.strip().lower()) for tag in tags))


def read_json(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def atomic_json(path, data):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temporary = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as stream:
            json.dump(data, stream, ensure_ascii=False, indent=2)
            stream.write("\n")
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


@contextmanager
def file_lock(path):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a") as stream:
        try:
            fcntl.flock(stream, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError as error:
            raise PublishingError(
                "Another publisher is using this release; rerun after it finishes"
            ) from error
        try:
            yield
        finally:
            fcntl.flock(stream, fcntl.LOCK_UN)


def private_path(path):
    path = Path(path).expanduser().resolve()
    repo = Path(__file__).resolve().parents[2]
    if path.is_relative_to(repo) or any(
        p.name.lower() == "obsidian" or (p / ".obsidian").is_dir() for p in path.parents
    ):
        raise PublishingError(
            "Keep credentials, browser profiles and session URLs outside the repository and vault"
        )
    return path


def token_value(path, env_name):
    value = (
        private_path(path).read_text().strip()
        if path
        else os.environ.get(env_name, "").strip()
    )
    if not value or any(char.isspace() for char in value):
        raise PublishingError(
            f"Supply a token file or {env_name}; never paste credentials into chat"
        )
    return value


class Release:
    def __init__(self, manifest):
        self.path = Path(manifest).resolve()
        try:
            self.plan = build_plan(self.path)
        except (ValueError, KeyError, OSError) as error:
            raise PublishingError(f"Release validation failed: {error}") from error
        self.manifest = read_json(self.path)
        self.digest = sha256(self.path)

    def assets(self, platform):
        result = []
        for item in self.plan[platform]["files"]:
            path = (self.path.parent / item["path"]).resolve()
            if not path.is_relative_to(self.path.parent):
                raise PublishingError(
                    "Shared asset paths must stay inside the release folder"
                )
            if path.suffix.lower() in {".gcode", ".gco", ".bgcode"}:
                raise PublishingError(
                    "G-code must be declared in printables_files, not shared files"
                )
            result.append(
                self.asset(item, path, "image" if item["role"] == "image" else "file")
            )
        for item in self.plan[platform].get("built_model_photos", []):
            result.append(self.asset(item, Path(item["source_path"]), "image"))
        if platform == "printables":
            for item in self.plan[platform].get("print_files", []):
                result.append(self.asset(item, Path(item["source_path"]), "print_file"))
        names = [item["name"].casefold() for item in result]
        if len(names) != len(set(names)):
            raise PublishingError("Upload filenames must be unique across the release")
        return result

    @staticmethod
    def asset(item, path, kind):
        return {
            "path": str(path.resolve()),
            "name": path.name,
            "sha256": item["sha256"],
            "kind": kind,
            "bytes": path.stat().st_size,
        }

    def summary(self, platform):
        if platform == "youtube":
            video = self.plan.get("video")
            if not video:
                raise PublishingError("This release has no video")
            return {
                "platform": platform,
                "mode": "dry-run",
                "privacy": "private",
                "title": video["title"],
                "tags": self.manifest["publication"]["tags"],
            }
        assets = self.assets(platform)
        return {
            "platform": platform,
            "mode": "dry-run",
            "title": self.plan[platform]["title"],
            "files": sum(a["kind"] == "file" for a in assets),
            "images": sum(a["kind"] == "image" for a in assets),
            "print_files": sum(a["kind"] == "print_file" for a in assets),
            "tags": printables_tags(self.plan[platform]["tags"])
            if platform == "printables"
            else self.plan[platform]["tags"],
        }


class State:
    def __init__(self, release, platform, path=None):
        self.path = (
            Path(path)
            if path
            else release.path.parent / ".publication-state" / f"{platform}.json"
        )
        self.release = release
        self.platform = platform
        self.data = (
            read_json(self.path)
            if self.path.exists()
            else {
                "schema": 1,
                "platform": platform,
                "manifest_sha256": release.digest,
                "assets": {},
            }
        )
        if (
            self.data.get("schema") != 1
            or self.data.get("platform") != platform
            or self.data.get("manifest_sha256") != release.digest
        ):
            raise PublishingError(
                "Publication state belongs to another manifest or platform"
            )

    def save(self):
        atomic_json(self.path, self.data)

    def pending(self, action):
        self.data["pending"] = action
        self.save()

    def done(self):
        self.data.pop("pending", None)
        self.save()

    def record(self, values):
        path = self.release.path.parent / "publication-record.json"
        with file_lock(path.with_suffix(".lock")):
            record = read_json(path) if path.exists() else {"schema": 1}
            previous = record.get(self.platform) or {}
            record[self.platform] = {
                **previous,
                **values,
                "verified_at": datetime.now(timezone.utc).isoformat(),
            }
            atomic_json(path, record)

    def existing_record(self):
        path = self.release.path.parent / "publication-record.json"
        return (read_json(path).get(self.platform) or {}) if path.exists() else {}


def fingerprint(data):
    return hashlib.sha256(json.dumps(data, sort_keys=True).encode()).hexdigest()
