#!/usr/bin/env python3
"""Validate a generated Hermes Multiverse public repository and optional bundle."""

from __future__ import annotations

import argparse
import hashlib
import io
import json
import os
import re
import sys
import zipfile
from pathlib import Path, PurePosixPath
from urllib.parse import unquote

try:
    from PIL import Image
except ImportError as exc:  # pragma: no cover - dependency failure is environment-specific
    print("ERROR: Pillow is required to validate image decoding", file=sys.stderr)
    raise SystemExit(2) from exc

EXPECTED_SLUGS = [
    "123321",
    "123mikeyd",
    "adolan",
    "artsbro",
    "brooklyn-heartbreaker",
    "coffeeblender",
    "cthulhu",
    "doge-man",
    "don-piedro",
    "ee-dd",
    "emozilla",
    "fatcat",
    "fleety",
    "ggb",
    "gille",
    "gottz",
    "i-sneeze-kittens",
    "mgf-654",
    "noctis",
    "nousgirl",
    "quark2world",
    "realtimeuk",
    "sahil",
    "salt555",
    "shawncleta",
    "sidbin",
    "sudo-nightwing",
    "suzu",
    "tdamre",
    "teknium",
    "tinuviel",
    "tunacookie",
    "turbo-fit",
    "witcheer",
]
TARGET_STYLES = [
    "anime",
    "rick-and-morty",
    "disney",
    "mecha",
    "chibi",
    "gothic",
    "claymation-stop-motion",
    "hyper-realistic",
    "ink-pen-sketch",
]
EXPECTED_COUNTS = {
    "characters": 34,
    "profiles": 34,
    "style_sheets": 286,
    "target_styles": 9,
    "characters_with_all_target_styles": 30,
    "documentation_only_characters": 2,
    "source_only_characters": 0,
    "scene_documents": 4,
    "music_video_documents": 3,
    "reference_documents": 1,
}
DOCUMENTATION_ONLY = ["emozilla", "ggb"]
SOURCE_ONLY: dict[str, str] = {}
EXPECTED_IDENTITY_INVARIANTS = {"nousgirl": ["large-over-ear-headphones"]}
PROVISIONAL = ["gille", "quark2world", "suzu"]
PROVISIONAL_STATUS = "provisional-sheet-conflicts-with-legacy-unknown-status"
RIGHTS_PENDING = "sudo-nightwing"
RIGHTS_PENDING_STATUS = "approval-pending-per-profile"
RIGHTS_PENDING_STYLES = [
    "claymation-stop-motion",
    "hyper-realistic",
    "ink-pen-sketch",
]
ACCEPTED_OMISSIONS = {"witcheer": ["hyper-realistic"]}
ADDITIONAL_STYLES = {"sahil": ["samurai"], "teknium": ["punk"]}
SCENE_DOCUMENTS = ["ask-hermes", "beach-finale", "campfire", "carnival"]
MUSIC_VIDEO_DOCUMENTS = [
    "hermes-sr72",
    "tekpunk-one-more-prompt",
    "thank-you-nous-research-arts-bro",
]
REFERENCE_DOCUMENTS = ["3d-character-lineup"]
REQUIRED_ROOT_FILES = {
    ".gitattributes",
    ".gitignore",
    "ATTRIBUTION.md",
    "CONTRIBUTING.md",
    "GALLERY.md",
    "REFERENCE-GALLERY.md",
    "LICENSE-CODE",
    "NOTICE.md",
    "README.md",
    "SHA256SUMS",
    "STATUS.md",
    "manifests/export-manifest.json",
    "manifests/pending.json",
    "manifests/reference-index.json",
    "manifests/release-asset.sha256",
    "scripts/verify_repository.py",
    ".github/workflows/validate.yml",
}
PUBLIC_MANIFEST_KEYS = {
    "schema_version",
    "slug",
    "display_name",
    "aliases",
    "companions",
    "design_status",
    "rights_status",
    "target_styles",
    "published_styles",
    "accepted_omissions",
    "external_models",
    "identity_invariants",
}
EXTERNAL_MODEL_KEYS = {
    "name",
    "download_url",
    "release_url",
    "sha256",
    "bytes",
    "format",
    "rights_note",
}
EXPECTED_EXTERNAL_MODELS: dict[str, list[dict[str, object]]] = {
    "doge-man": [
        {
            "bytes": 28395018,
            "download_url": "https://github.com/123mikeyd/nrcu-vault/releases/download/rigged-models-v1/DogeMan-rigged.zip",
            "format": "ZIP containing GLB",
            "name": "DogeMan-rigged.zip",
            "release_url": "https://github.com/123mikeyd/nrcu-vault/releases/tag/rigged-models-v1",
            "rights_note": "No additional licence is asserted; the upstream content notice applies.",
            "sha256": "c543dd6a55d18263b6aa212220458a5d2e1a8e73619c3c5436d685335aa0c2ad",
        }
    ],
    "teknium": [
        {
            "bytes": 18623006,
            "download_url": "https://github.com/123mikeyd/nrcu-vault/releases/download/rigged-models-v1/Teknium-rigged.zip",
            "format": "ZIP containing GLB",
            "name": "Teknium-rigged.zip",
            "release_url": "https://github.com/123mikeyd/nrcu-vault/releases/tag/rigged-models-v1",
            "rights_note": "No additional licence is asserted; the upstream content notice applies.",
            "sha256": "bb08b497b5d682cf4176c16432e491e894e8c2fd151c40563487bb65d290994b",
        }
    ],
    "turbo-fit": [
        {
            "bytes": 41451999,
            "download_url": "https://github.com/123mikeyd/nrcu-vault/releases/download/rigged-models-v1/TurboFit-rigged.zip",
            "format": "ZIP containing GLB",
            "name": "TurboFit-rigged.zip",
            "release_url": "https://github.com/123mikeyd/nrcu-vault/releases/tag/rigged-models-v1",
            "rights_note": "No additional licence is asserted; the upstream content notice applies.",
            "sha256": "9b62d700d68c46dc8778d5cf088b3fbfc532c43d6843c49ee9e6bd6b79614cfe",
        }
    ],
    "witcheer": [
        {
            "bytes": 21751189,
            "download_url": "https://github.com/123mikeyd/nrcu-vault/releases/download/rigged-models-v1/Witcheer-rigged.zip",
            "format": "ZIP containing GLB",
            "name": "Witcheer-rigged.zip",
            "release_url": "https://github.com/123mikeyd/nrcu-vault/releases/tag/rigged-models-v1",
            "rights_note": "No additional licence is asserted; the upstream content notice applies.",
            "sha256": "b319cd50ab8c14f5bd96892b194d816213251691d291e155f1030bd605c5f61c",
        }
    ],
}
STYLE_RECORD_KEYS = {"style", "preview", "full_resolution"}
PREVIEW_KEYS = {"path", "sha256", "width", "height"}
FULL_RESOLUTION_KEYS = {"archive_path", "sha256", "bytes", "width", "height"}
REFERENCE_RECORD_KEYS = {
    "reference_id", "preview", "asset_type", "descriptor", "linked_characters",
    "candidate_characters", "mapping_status", "mapping_confidence", "rights_status",
}
TEXT_SUFFIXES = {"", ".md", ".json", ".py", ".yml", ".yaml", ".txt", ".sha256", ".gitignore", ".gitattributes"}
FORBIDDEN_PATH_COMPONENTS = {
    "_" + "registry",
    "_" + "source-archives",
    "_" + "shared-scenes",
    "_" + "unclassified",
    "archive",
    "source",
    "__pycache__",
}
FORBIDDEN_SUFFIXES = {".log", ".jsonl", ".pyc", ".marker", ".sh", ".bak", ".orig", ".swp"}
BLOCKED_METADATA_PARTS = {"exif", "gps", "xmp", "icc", "prompt", "workflow", "parameters", "comment"}
LINK_RE = re.compile(r"!?\[[^\]]*\]\(([^)]+)\)")
EMAIL_RE = re.compile(rb"[A-Z0-9._%+\-]+@[A-Z0-9.\-]+\.[A-Z]{2,}", re.IGNORECASE)
TOKEN_RES = [
    re.compile(rb"sk-[A-Za-z0-9]{16,}"),
    re.compile(rb"ghp_[A-Za-z0-9]{20,}"),
    re.compile(rb"AKIA[A-Z0-9]{16}"),
]
MAX_GIT_FILE_BYTES = 100 * 1024 * 1024


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def load_json(path: Path, errors: list[str]) -> object | None:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        errors.append(f"invalid JSON {path}: {exc}")
        return None


def safe_relative_path(value: object, label: str, errors: list[str]) -> str | None:
    if not isinstance(value, str) or not value:
        errors.append(f"{label} must be a non-empty relative path")
        return None
    path = PurePosixPath(value)
    if path.is_absolute() or ".." in path.parts or "\\" in value or "\x00" in value:
        errors.append(f"unsafe relative path in {label}: {value!r}")
        return None
    return value


def expected_styles_for_slug(slug: str) -> set[str]:
    target = set(TARGET_STYLES)
    if slug in DOCUMENTATION_ONLY or slug in SOURCE_ONLY:
        return set()
    if slug == RIGHTS_PENDING:
        return target - set(RIGHTS_PENDING_STYLES)
    if slug == "witcheer":
        return target - {"hyper-realistic"}
    return target | set(ADDITIONAL_STYLES.get(slug, []))


def expected_repository_paths(reference_ids: list[str]) -> set[str]:
    paths = set(REQUIRED_ROOT_FILES)
    for slug in EXPECTED_SLUGS:
        paths.update(
            {
                f"characters/{slug}/README.md",
                f"characters/{slug}/manifest.json",
                f"characters/{slug}/references.md",
                f"docs/characters/{slug}.md",
            }
        )
        paths.update(f"previews/{slug}/{style}.webp" for style in expected_styles_for_slug(slug))
    paths.update(f"docs/scenes/{name}.md" for name in SCENE_DOCUMENTS)
    paths.update(f"docs/music-videos/{name}.md" for name in MUSIC_VIDEO_DOCUMENTS)
    paths.update(f"docs/references/{name}.md" for name in REFERENCE_DOCUMENTS)
    paths.update(f"previews/references/{reference_id}.webp" for reference_id in reference_ids)
    return paths


def expected_counts(reference_count: int) -> dict[str, int]:
    return {
        **EXPECTED_COUNTS,
        "repository_files": 447 + reference_count,
        "supporting_references": reference_count,
        "character_reference_pages": len(EXPECTED_SLUGS),
    }


def reference_title(record: dict[str, object]) -> str:
    descriptor = record.get("descriptor")
    if isinstance(descriptor, str) and descriptor:
        return descriptor.replace("-", " ").title()
    return str(record.get("asset_type", "reference")).replace("-", " ").title()


def expected_reference_gallery(records: list[dict[str, object]]) -> str:
    lines = [
        "# Supporting-reference gallery", "",
        "These are metadata-stripped previews of canonical non-style references. Candidate identity links are explicitly non-canonical.", "",
    ]
    for record in records:
        preview = record["preview"]
        assert isinstance(preview, dict)
        lines.extend([
            f"## {reference_title(record)}", "", f"![{reference_title(record)}]({preview['path']})", "",
            f"- Reference ID: `{record['reference_id']}`", f"- Type: `{record['asset_type']}`",
            f"- Mapping: `{record['mapping_status']}` (`{record['mapping_confidence']}`)",
            f"- Rights: `{record['rights_status']}`",
            f"- Canonical character links: {', '.join(f'[`{slug}`](characters/{slug}/references.md)' for slug in record['linked_characters']) or 'none'}",
            f"- Candidate character links — **not canonical**: {', '.join(f'[`{slug}`](characters/{slug}/references.md)' for slug in record['candidate_characters']) or 'none'}", "",
        ])
    return "\n".join(lines).rstrip() + "\n"


def expected_character_references(slug: str, display_name: str, records: list[dict[str, object]]) -> str:
    linked = [record for record in records if slug in record["linked_characters"]]
    candidates = [record for record in records if slug in record["candidate_characters"]]
    lines = [
        f"# {display_name} — supporting references", "",
        "Shared references remain single-copy previews in the central reference gallery.", "",
        f"- Canonical reference links: {len(linked)}", f"- Candidate links (not canonical): {len(candidates)}", "",
        "## Canonical references", "",
    ]
    if not linked:
        lines.extend(["No canonical reference links.", ""])
    for record in linked:
        lines.extend([
            f"### {reference_title(record)}", "", f"![{reference_title(record)}](../../{record['preview']['path']})", "",
            f"- Reference ID: `{record['reference_id']}`", f"- Type: `{record['asset_type']}`",
            f"- Mapping confidence: `{record['mapping_confidence']}`", f"- Rights: `{record['rights_status']}`", "",
        ])
    lines.extend(["## Candidate references — not canonical", ""])
    if not candidates:
        lines.extend(["No candidate reference links.", ""])
    for record in candidates:
        lines.extend([
            f"### {reference_title(record)}", "", "**NOT CANONICAL — candidate identity link only.**", "",
            f"![{reference_title(record)}](../../{record['preview']['path']})", "",
            f"- Reference ID: `{record['reference_id']}`", f"- Type: `{record['asset_type']}`",
            f"- Mapping confidence: `{record['mapping_confidence']}`", f"- Rights: `{record['rights_status']}`", "",
        ])
    return "\n".join(lines).rstrip() + "\n"


def validate_references(root: Path, errors: list[str]) -> list[dict[str, object]]:
    raw = load_json(root / "manifests" / "reference-index.json", errors)
    if not isinstance(raw, dict):
        return []
    if set(raw) != {"schema_version", "release", "summary", "references"}:
        errors.append("reference index has unexpected fields")
    if raw.get("schema_version") != 1 or raw.get("release") != "v0.2.0-wip":
        errors.append("reference index schema/release mismatch")
    records = raw.get("references")
    if not isinstance(records, list):
        errors.append("reference index records must be a list")
        return []
    seen_ids: set[str] = set()
    allowed_slugs = set(EXPECTED_SLUGS)
    valid: list[dict[str, object]] = []
    for index, record in enumerate(records):
        label = f"references[{index}]"
        if not isinstance(record, dict) or set(record) != REFERENCE_RECORD_KEYS:
            errors.append(f"public reference fields are not allowlisted in {label}")
            continue
        reference_id = record.get("reference_id")
        if not isinstance(reference_id, str) or re.fullmatch(r"ref-[0-9a-f]{16}", reference_id) is None or reference_id in seen_ids:
            errors.append(f"invalid or duplicate reference ID in {label}")
            continue
        seen_ids.add(reference_id)
        preview = record.get("preview")
        if not isinstance(preview, dict) or set(preview) != PREVIEW_KEYS:
            errors.append(f"invalid reference preview fields in {label}")
            continue
        expected_path = f"previews/references/{reference_id}.webp"
        if safe_relative_path(preview.get("path"), f"{label}.preview.path", errors) != expected_path:
            errors.append(f"reference preview path mismatch for {reference_id}")
        linked = record.get("linked_characters")
        candidates = record.get("candidate_characters")
        if not isinstance(linked, list) or not all(isinstance(item, str) for item in linked) or linked != sorted(set(linked)):
            errors.append(f"invalid canonical character links for {reference_id}")
            linked = []
        if not isinstance(candidates, list) or not all(isinstance(item, str) for item in candidates) or candidates != sorted(set(candidates)):
            errors.append(f"invalid candidate character links for {reference_id}")
            candidates = []
        if (set(linked) | set(candidates)) - allowed_slugs or set(linked) & set(candidates):
            errors.append(f"invalid or overlapping reference character links for {reference_id}")
        status = record.get("mapping_status")
        if status not in {"character-mapped", "candidate-only", "scene-classified-cast-unresolved"}:
            errors.append(f"invalid mapping status for {reference_id}")
        if status == "candidate-only" and (linked or not candidates):
            errors.append(f"candidate-only reference is presented canonically: {reference_id}")
        if not all(isinstance(record.get(key), str) and record.get(key) for key in ("asset_type", "mapping_confidence", "rights_status")):
            errors.append(f"invalid public descriptor field for {reference_id}")
        if record.get("descriptor") is not None and (not isinstance(record.get("descriptor"), str) or not record.get("descriptor")):
            errors.append(f"invalid reference descriptor for {reference_id}")
        preview_file = root / expected_path
        if preview_file.is_file():
            if preview.get("sha256") != sha256_file(preview_file):
                errors.append(f"reference preview hash mismatch for {reference_id}")
            try:
                with Image.open(preview_file) as image:
                    image.load()
                    if image.format != "WEBP": errors.append(f"reference preview is not WebP: {reference_id}")
                    if [image.width, image.height] != [preview.get("width"), preview.get("height")]: errors.append(f"reference preview dimensions mismatch for {reference_id}")
                    blocked = {key for key in image.info if any(part in key.lower() for part in BLOCKED_METADATA_PARTS)}
                    if blocked: errors.append(f"blocked reference preview metadata for {reference_id}: {sorted(blocked)}")
            except Exception as exc:
                errors.append(f"reference preview decode failed for {reference_id}: {exc}")
        valid.append(record)
    if [record["reference_id"] for record in valid] != sorted(seen_ids):
        errors.append("reference records are not sorted by stable ID")
    summary = {
        "reference_assets": len(valid),
        "character_mapped": sum(record["mapping_status"] == "character-mapped" for record in valid),
        "candidate_only": sum(record["mapping_status"] == "candidate-only" for record in valid),
        "scene_classified_cast_unresolved": sum(record["mapping_status"] == "scene-classified-cast-unresolved" for record in valid),
        "canonical_character_links": sum(len(record["linked_characters"]) for record in valid),
        "candidate_character_links": sum(len(record["candidate_characters"]) for record in valid),
    }
    if raw.get("summary") != summary:
        errors.append("reference index summary is inaccurate")
    gallery = root / "REFERENCE-GALLERY.md"
    if gallery.is_file() and gallery.read_text(encoding="utf-8") != expected_reference_gallery(valid):
        errors.append("reference gallery does not match reference index")
    return valid


def expected_pending(manifests: dict[str, dict[str, object]]) -> dict[str, object]:
    return {
        "schema_version": 1,
        "release": "v0.2.0-wip",
        "documentation_only": [
            {
                "slug": "emozilla",
                "reason": "documentation-only; associated third-party reference is not reusable",
            },
            {
                "slug": "ggb",
                "reason": "documentation-only; excluded from style generation in this release",
            },
        ],
        "source_only": [],
        "rights_pending": [
            {
                "slug": RIGHTS_PENDING,
                "rights_status": RIGHTS_PENDING_STATUS,
                "missing_styles": RIGHTS_PENDING_STYLES,
            }
        ],
        "accepted_omissions": [
            {
                "slug": "witcheer",
                "styles": ["hyper-realistic"],
                "reason": "accepted target-style omission",
            }
        ],
        "provisional_designs": [
            {"slug": slug, "design_status": manifests.get(slug, {}).get("design_status")}
            for slug in PROVISIONAL
        ],
        "summary": {
            "documentation_only": 2,
            "source_only": 0,
            "rights_pending_characters": 1,
            "rights_pending_styles": 3,
            "accepted_omissions": 1,
            "provisional_designs": 3,
        },
    }


def validate_inventory(root: Path, reference_ids: list[str], errors: list[str]) -> list[Path]:
    files: list[Path] = []
    for path in sorted(root.rglob("*")):
        relative = path.relative_to(root)
        if ".git" in relative.parts:
            continue
        relative_posix = relative.as_posix()
        if path.is_symlink():
            errors.append(f"symlink is forbidden: {relative_posix}")
            continue
        if path.is_dir():
            continue
        if not path.is_file():
            errors.append(f"non-regular file is forbidden: {relative_posix}")
            continue
        files.append(path)
        lower_parts = {part.lower() for part in relative.parts}
        if lower_parts & FORBIDDEN_PATH_COMPONENTS:
            errors.append(f"forbidden path component: {relative_posix}")
        lower_name = path.name.lower()
        if any(lower_name.endswith(suffix) for suffix in FORBIDDEN_SUFFIXES) or lower_name.endswith("~"):
            errors.append(f"forbidden filename or extension: {relative_posix}")
        if path.stat().st_size > MAX_GIT_FILE_BYTES:
            errors.append(f"file exceeds 100 MiB Git limit: {relative_posix}")
        if len(relative.parts) >= 2 and relative.parts[0] == "characters":
            if len(relative.parts) != 3 or relative.parts[2] not in {"README.md", "manifest.json", "references.md"}:
                errors.append(f"forbidden character asset path: {relative_posix}")
        if path.suffix.lower() == ".png":
            errors.append(f"full-resolution image committed to repository: {relative_posix}")

        if path.suffix.lower() in TEXT_SUFFIXES or path.name in {"LICENSE-CODE", ".gitignore", ".gitattributes", "SHA256SUMS"}:
            try:
                data = path.read_bytes()
            except OSError as exc:
                errors.append(f"cannot read {relative_posix}: {exc}")
                continue
            private_roots = [b"/" + b"home" + b"/", b"/" + b"tmp" + b"/"]
            if any(marker in data for marker in private_roots):
                errors.append(f"forbidden absolute path in {relative_posix}")
            private_references = [
                ("_" + "registry" + "/").encode(),
                ("_" + "source-archives" + "/").encode(),
                ("_" + "shared-scenes" + "/").encode(),
                ("_" + "unclassified" + "/").encode(),
                ("review" + "-batches" + "/").encode(),
            ]
            if any(marker in data for marker in private_references):
                errors.append(f"forbidden private path reference in {relative_posix}")
            if EMAIL_RE.search(data):
                errors.append(f"email address is forbidden in {relative_posix}")
            sensitive_fragments = [
                b"o" + b"auth",
                b"api" + b"_key",
                b"access" + b"_token",
                b"refresh" + b"_token",
                b"client" + b"_secret",
                b"account" + b"_id",
                b"credential" + b" fingerprint",
            ]
            lowered = data.lower()
            if any(fragment in lowered for fragment in sensitive_fragments):
                errors.append(f"credential or account identifier pattern in {relative_posix}")
            if any(pattern.search(data) for pattern in TOKEN_RES):
                errors.append(f"credential-shaped token in {relative_posix}")
    actual_paths = {path.relative_to(root).as_posix() for path in files}
    expected_paths = expected_repository_paths(reference_ids)
    if len(actual_paths) != len(expected_paths):
        errors.append(
            f"repository file count: expected {len(expected_paths)}, found {len(actual_paths)}"
        )
    for relative in sorted(expected_paths - actual_paths):
        errors.append(f"missing repository file: {relative}")
    for relative in sorted(actual_paths - expected_paths):
        errors.append(f"unexpected repository file: {relative}")
    return files


def validate_markdown_links(root: Path, files: list[Path], errors: list[str]) -> None:
    resolved_root = root.resolve()
    for path in files:
        if path.suffix.lower() != ".md":
            continue
        try:
            text = path.read_text(encoding="utf-8")
        except (OSError, UnicodeError) as exc:
            errors.append(f"cannot read Markdown {path.relative_to(root).as_posix()}: {exc}")
            continue
        for raw_target in LINK_RE.findall(text):
            target = raw_target.strip().strip("<>")
            if not target or target.startswith("#") or target.startswith(("http://", "https://")):
                continue
            target = target.split(maxsplit=1)[0]
            target = target.split("#", 1)[0].split("?", 1)[0]
            target = unquote(target)
            if not target:
                continue
            if ":" in target.split("/", 1)[0] or Path(target).is_absolute():
                errors.append(
                    f"unsafe Markdown link in {path.relative_to(root).as_posix()}: {raw_target}"
                )
                continue
            resolved = (path.parent / target).resolve()
            if not resolved.is_relative_to(resolved_root):
                errors.append(
                    f"Markdown link escapes repository in {path.relative_to(root).as_posix()}: {raw_target}"
                )
            elif not resolved.exists():
                errors.append(
                    f"broken Markdown link in {path.relative_to(root).as_posix()}: {raw_target}"
                )


def validate_manifests(
    root: Path, errors: list[str]
) -> tuple[dict[str, dict[str, object]], list[str], list[str], dict[str, dict[str, object]]]:
    manifest_paths = sorted((root / "characters").glob("*/manifest.json"))
    profile_paths = sorted((root / "docs" / "characters").glob("*.md"))
    readme_paths = sorted((root / "characters").glob("*/README.md"))
    preview_paths = sorted(
        path
        for slug in EXPECTED_SLUGS
        for path in (root / "previews" / slug).glob("*.webp")
    )
    if len(manifest_paths) != EXPECTED_COUNTS["characters"]:
        errors.append(
            f"character manifest count: expected {EXPECTED_COUNTS['characters']}, found {len(manifest_paths)}"
        )
    if len(profile_paths) != EXPECTED_COUNTS["profiles"]:
        errors.append(f"profile count: expected {EXPECTED_COUNTS['profiles']}, found {len(profile_paths)}")
    if len(readme_paths) != EXPECTED_COUNTS["characters"]:
        errors.append(
            f"character README count: expected {EXPECTED_COUNTS['characters']}, found {len(readme_paths)}"
        )
    if len(preview_paths) != EXPECTED_COUNTS["style_sheets"]:
        errors.append(
            f"preview count: expected {EXPECTED_COUNTS['style_sheets']}, found {len(preview_paths)}"
        )
    scene_count = len(list((root / "docs" / "scenes").glob("*.md")))
    music_count = len(list((root / "docs" / "music-videos").glob("*.md")))
    reference_count = len(list((root / "docs" / "references").glob("*.md")))
    if scene_count != EXPECTED_COUNTS["scene_documents"]:
        errors.append(f"scene document count: expected 4, found {scene_count}")
    if music_count != EXPECTED_COUNTS["music_video_documents"]:
        errors.append(f"music-video document count: expected 3, found {music_count}")
    if reference_count != EXPECTED_COUNTS["reference_documents"]:
        errors.append(f"reference document count: expected 1, found {reference_count}")

    manifest_slugs = [path.parent.name for path in manifest_paths]
    profile_slugs = [path.stem for path in profile_paths]
    readme_slugs = [path.parent.name for path in readme_paths]
    preview_relative = [path.relative_to(root).as_posix() for path in preview_paths]
    if manifest_slugs != EXPECTED_SLUGS:
        errors.append("character manifest slugs do not match the frozen 34-character set")
    if profile_slugs != EXPECTED_SLUGS:
        errors.append("profile slugs do not match the frozen 34-character set")
    if readme_slugs != EXPECTED_SLUGS:
        errors.append("character README slugs do not match the frozen 34-character set")

    manifests: dict[str, dict[str, object]] = {}
    source_hashes: list[str] = []
    declared_previews: list[str] = []
    archive_records: dict[str, dict[str, object]] = {}
    full_target_count = 0
    published_total = 0
    for path in manifest_paths:
        raw = load_json(path, errors)
        if not isinstance(raw, dict):
            continue
        manifest = raw
        slug = manifest.get("slug")
        if not isinstance(slug, str):
            errors.append(f"manifest has invalid slug: {path.relative_to(root).as_posix()}")
            continue
        manifests[slug] = manifest
        actual_keys = set(manifest)
        required_keys = PUBLIC_MANIFEST_KEYS - {"companions", "external_models", "identity_invariants"}
        if not required_keys.issubset(actual_keys) or not actual_keys.issubset(PUBLIC_MANIFEST_KEYS):
            errors.append(f"public manifest fields are not allowlisted for {slug}: {sorted(actual_keys)}")
        if manifest.get("schema_version") != 1:
            errors.append(f"unsupported public manifest schema for {slug}")
        if path.parent.name != slug:
            errors.append(f"manifest slug/path mismatch for {slug}")
        if manifest.get("target_styles") != TARGET_STYLES:
            errors.append(f"target styles mismatch for {slug}")
        if not isinstance(manifest.get("display_name"), str) or not manifest.get("display_name"):
            errors.append(f"display name must be a non-empty string for {slug}")
        if not isinstance(manifest.get("design_status"), str) or not manifest.get("design_status"):
            errors.append(f"design status must be a non-empty string for {slug}")
        if not isinstance(manifest.get("rights_status"), str) or not manifest.get("rights_status"):
            errors.append(f"rights status must be a non-empty string for {slug}")
        aliases = manifest.get("aliases")
        if not isinstance(aliases, list) or not all(isinstance(item, str) and item for item in aliases):
            errors.append(f"aliases must be a string list for {slug}")
        companions = manifest.get("companions")
        if "companions" in manifest and (
            not isinstance(companions, list)
            or not all(isinstance(item, str) and item for item in companions)
        ):
            errors.append(f"companions must be a string list for {slug}")
        external_models = manifest.get("external_models")
        if "external_models" in manifest:
            if not isinstance(external_models, list):
                errors.append(f"external_models must be a list for {slug}")
            else:
                seen_model_names: set[str] = set()
                release_prefix = "https://github.com/123mikeyd/nrcu-vault/releases/"
                for index, model in enumerate(external_models):
                    label = f"{slug}.external_models[{index}]"
                    if not isinstance(model, dict) or set(model) != EXTERNAL_MODEL_KEYS:
                        errors.append(f"invalid external model fields in {label}")
                        continue
                    name = model.get("name")
                    if (
                        not isinstance(name, str)
                        or not name.endswith(".zip")
                        or "/" in name
                        or "\\" in name
                        or name in seen_model_names
                    ):
                        errors.append(f"invalid external model name in {label}")
                    else:
                        seen_model_names.add(name)
                    for field in ("download_url", "release_url"):
                        value = model.get(field)
                        if not isinstance(value, str) or not value.startswith(release_prefix):
                            errors.append(f"invalid external model {field} in {label}")
                    digest = model.get("sha256")
                    if not isinstance(digest, str) or re.fullmatch(r"[0-9a-f]{64}", digest) is None:
                        errors.append(f"invalid external model sha256 in {label}")
                    byte_size = model.get("bytes")
                    if not isinstance(byte_size, int) or isinstance(byte_size, bool) or byte_size <= 0:
                        errors.append(f"invalid external model byte size in {label}")
                    for field in ("format", "rights_note"):
                        value = model.get(field)
                        if not isinstance(value, str) or not value.strip():
                            errors.append(f"invalid external model {field} in {label}")
        if manifest.get("external_models", []) != EXPECTED_EXTERNAL_MODELS.get(slug, []):
            errors.append(f"approved external model metadata mismatch for {slug}")
        identity_invariants = manifest.get("identity_invariants", [])
        if not isinstance(identity_invariants, list) or not all(
            isinstance(item, str) and item for item in identity_invariants
        ):
            errors.append(f"identity invariants must be a string list for {slug}")
        if identity_invariants != EXPECTED_IDENTITY_INVARIANTS.get(slug, []):
            errors.append(f"approved identity invariants mismatch for {slug}")
        expected_omissions = ACCEPTED_OMISSIONS.get(slug, [])
        if manifest.get("accepted_omissions") != expected_omissions:
            errors.append(f"accepted omissions mismatch for {slug}")
        styles = manifest.get("published_styles")
        if not isinstance(styles, list):
            errors.append(f"published styles must be a list for {slug}")
            continue
        declared_style_order = [record.get("style") for record in styles if isinstance(record, dict)]
        if all(isinstance(style, str) for style in declared_style_order) and declared_style_order != sorted(declared_style_order):
            errors.append(f"published styles are not sorted for {slug}")
        published_total += len(styles)
        seen_styles: set[str] = set()
        for index, record in enumerate(styles):
            label = f"{slug}.published_styles[{index}]"
            if not isinstance(record, dict) or set(record) != STYLE_RECORD_KEYS:
                errors.append(f"invalid style record fields in {label}")
                continue
            style = record.get("style")
            if not isinstance(style, str) or style in seen_styles:
                errors.append(f"invalid or duplicate style in {label}")
                continue
            seen_styles.add(style)
            preview = record.get("preview")
            full = record.get("full_resolution")
            if not isinstance(preview, dict) or set(preview) != PREVIEW_KEYS:
                errors.append(f"invalid preview fields in {label}")
                continue
            if not isinstance(full, dict) or set(full) != FULL_RESOLUTION_KEYS:
                errors.append(f"invalid full-resolution fields in {label}")
                continue
            expected_preview = f"previews/{slug}/{style}.webp"
            preview_path = safe_relative_path(preview.get("path"), f"{label}.preview.path", errors)
            archive_path = safe_relative_path(full.get("archive_path"), f"{label}.full_resolution.archive_path", errors)
            if preview_path != expected_preview:
                errors.append(f"preview path mismatch for {slug}/{style}")
            if archive_path is not None:
                archive = PurePosixPath(archive_path)
                if len(archive.parts) != 5 or archive.parts[:3] != ("characters", slug, "styles") or archive.parts[3] != style:
                    errors.append(f"full-resolution archive path mismatch for {slug}/{style}")
                if archive_path in archive_records:
                    errors.append(f"duplicate full-resolution archive path: {archive_path}")
                else:
                    archive_records[archive_path] = full
            preview_file = root / expected_preview
            if preview_file.is_file():
                actual_hash = sha256_file(preview_file)
                if preview.get("sha256") != actual_hash:
                    errors.append(f"preview hash mismatch for {slug}/{style}")
                try:
                    with Image.open(preview_file) as image:
                        image.load()
                        if [image.width, image.height] != [preview.get("width"), preview.get("height")]:
                            errors.append(f"preview dimensions mismatch for {slug}/{style}")
                except Exception as exc:  # Pillow raises several format-specific exceptions
                    errors.append(f"preview decode failed for {slug}/{style}: {exc}")
            declared_previews.append(expected_preview)
            source_hash = full.get("sha256")
            if not isinstance(source_hash, str) or not re.fullmatch(r"[0-9a-f]{64}", source_hash):
                errors.append(f"invalid source hash for {slug}/{style}")
            else:
                source_hashes.append(source_hash)
            if not all(isinstance(full.get(key), int) and full.get(key) > 0 for key in ("bytes", "width", "height")):
                errors.append(f"invalid full-resolution size/dimensions for {slug}/{style}")
        target_set = set(TARGET_STYLES)
        if target_set.issubset(seen_styles):
            full_target_count += 1
        expected_additional = set(ADDITIONAL_STYLES.get(slug, []))
        actual_additional = seen_styles - target_set
        if actual_additional != expected_additional:
            errors.append(f"additional styles mismatch for {slug}")
        expected_styles = expected_styles_for_slug(slug)
        if seen_styles != expected_styles:
            errors.append(f"published style set is inaccurate for {slug}")

    if published_total != EXPECTED_COUNTS["style_sheets"]:
        errors.append(
            f"published style total: expected {EXPECTED_COUNTS['style_sheets']}, found {published_total}"
        )
    if full_target_count != EXPECTED_COUNTS["characters_with_all_target_styles"]:
        errors.append(
            "all-target-style character count: expected "
            f"{EXPECTED_COUNTS['characters_with_all_target_styles']}, found {full_target_count}"
        )
    if sorted(declared_previews) != preview_relative:
        errors.append("manifest-declared previews do not exactly match repository previews")
    if len(source_hashes) != len(set(source_hashes)):
        errors.append("duplicate full-resolution source hashes detected")
    if manifests.get(RIGHTS_PENDING, {}).get("rights_status") != RIGHTS_PENDING_STATUS:
        errors.append("sudo-nightwing rights-pending status is inaccurate")
    for slug in PROVISIONAL:
        if manifests.get(slug, {}).get("design_status") != PROVISIONAL_STATUS:
            errors.append(f"provisional design status is inaccurate for {slug}")
    for slug in DOCUMENTATION_ONLY:
        if manifests.get(slug, {}).get("published_styles") != []:
            errors.append(f"documentation-only character has published styles: {slug}")
    for slug, status in SOURCE_ONLY.items():
        manifest = manifests.get(slug, {})
        if manifest.get("design_status") != status:
            errors.append(f"source-only design status is inaccurate for {slug}")
        if manifest.get("published_styles") != []:
            errors.append(f"source-only character has published styles: {slug}")
    return manifests, source_hashes, declared_previews, archive_records


def validate_previews(root: Path, errors: list[str]) -> None:
    hashes: dict[str, str] = {}
    for path in sorted((root / "previews").glob("*/*.webp")):
        relative = path.relative_to(root).as_posix()
        digest = sha256_file(path)
        is_reference_preview = relative.startswith("previews/references/")
        if not is_reference_preview and digest in hashes:
            errors.append(f"duplicate preview hash: {relative} and {hashes[digest]}")
        elif not is_reference_preview:
            hashes[digest] = relative
        try:
            with Image.open(path) as image:
                image.verify()
            with Image.open(path) as image:
                image.load()
                if image.format != "WEBP":
                    errors.append(f"preview is not WebP: {relative}")
                if max(image.size) > 960:
                    errors.append(f"preview long edge exceeds 960px: {relative}")
                blocked = {
                    key
                    for key in image.info
                    if any(part in key.lower() for part in BLOCKED_METADATA_PARTS)
                }
                if blocked:
                    errors.append(f"blocked preview metadata in {relative}: {sorted(blocked)}")
        except Exception as exc:
            errors.append(f"preview decode failed for {relative}: {exc}")


def parse_checksum_file(path: Path, errors: list[str]) -> dict[str, str]:
    result: dict[str, str] = {}
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except (OSError, UnicodeError) as exc:
        errors.append(f"cannot read checksum file {path}: {exc}")
        return result
    entry_order: list[str] = []
    for line in lines:
        match = re.fullmatch(r"([0-9a-f]{64})  (.+)", line)
        if not match:
            errors.append(f"invalid checksum line in {path.name}: {line!r}")
            continue
        digest, relative = match.groups()
        entry_order.append(relative)
        if relative in result:
            errors.append(f"duplicate checksum path in {path.name}: {relative}")
        if safe_relative_path(relative, f"{path.name} entry", errors) is not None:
            result[relative] = digest
    if entry_order != sorted(entry_order):
        errors.append(f"checksum entries are not sorted by path: {path.name}")
    return result


def validate_checksums(root: Path, files: list[Path], errors: list[str]) -> None:
    checksum_path = root / "SHA256SUMS"
    checksums = parse_checksum_file(checksum_path, errors)
    expected_paths = sorted(
        path.relative_to(root).as_posix() for path in files if path != checksum_path
    )
    if sorted(checksums) != expected_paths:
        errors.append("SHA256SUMS does not exactly cover every repository file except itself")
    for relative, expected in checksums.items():
        target = root / relative
        if target.is_file() and sha256_file(target) != expected:
            errors.append(f"repository checksum mismatch: {relative}")


def validate_export_manifest(root: Path, files: list[Path], reference_count: int, errors: list[str]) -> dict[str, object] | None:
    path = root / "manifests" / "export-manifest.json"
    raw = load_json(path, errors)
    if not isinstance(raw, dict):
        return None
    if set(raw) != {"schema_version", "release", "counts", "target_styles", "release_bundle", "files"}:
        errors.append("export manifest has unexpected fields")
    if raw.get("schema_version") != 1 or raw.get("release") != "v0.2.0-wip":
        errors.append("export manifest schema/release mismatch")
    if raw.get("counts") != expected_counts(reference_count):
        errors.append("export manifest frozen counts mismatch")
    if raw.get("target_styles") != TARGET_STYLES:
        errors.append("export manifest target styles mismatch")
    inventory = raw.get("files")
    expected_files = [
        candidate
        for candidate in files
        if candidate.relative_to(root).as_posix()
        not in {"SHA256SUMS", "manifests/export-manifest.json"}
    ]
    expected_records = [
        {
            "path": candidate.relative_to(root).as_posix(),
            "sha256": sha256_file(candidate),
            "bytes": candidate.stat().st_size,
        }
        for candidate in sorted(expected_files)
    ]
    if inventory != expected_records:
        errors.append("export manifest file inventory mismatch")
    bundle = raw.get("release_bundle")
    if not isinstance(bundle, dict) or set(bundle) != {"filename", "sha256", "bytes", "image_count", "checksum_file"}:
        errors.append("export manifest release bundle record is invalid")
    else:
        if bundle.get("image_count") != EXPECTED_COUNTS["style_sheets"]:
            errors.append("release bundle image count mismatch")
        checksum_text_path = root / "manifests" / "release-asset.sha256"
        try:
            checksum_text = checksum_text_path.read_text(encoding="utf-8").strip()
        except (OSError, UnicodeError) as exc:
            errors.append(f"cannot read release asset checksum: {exc}")
        else:
            expected_line = f"{bundle.get('sha256')}  {bundle.get('filename')}"
            if checksum_text != expected_line:
                errors.append("release asset checksum record mismatch")
        if bundle.get("checksum_file") != "manifests/release-asset.sha256":
            errors.append("release bundle checksum path mismatch")
    return raw


def validate_pending(root: Path, manifests: dict[str, dict[str, object]], errors: list[str]) -> None:
    raw = load_json(root / "manifests" / "pending.json", errors)
    expected = expected_pending(manifests)
    if raw != expected:
        errors.append("pending-status manifest is inaccurate")


def validate_release_bundle(
    bundle_path: Path,
    detached_checksum: Path | None,
    export_manifest: dict[str, object] | None,
    archive_records: dict[str, dict[str, object]],
    errors: list[str],
) -> None:
    if export_manifest is None:
        return
    bundle_record = export_manifest.get("release_bundle")
    if not isinstance(bundle_record, dict):
        return
    if not bundle_path.is_file() or bundle_path.is_symlink():
        errors.append(f"release bundle is not a regular file: {bundle_path}")
        return
    bundle_hash = sha256_file(bundle_path)
    if bundle_hash != bundle_record.get("sha256"):
        errors.append("release bundle SHA-256 mismatch")
    if bundle_path.stat().st_size != bundle_record.get("bytes"):
        errors.append("release bundle byte-size mismatch")

    checksum_path = detached_checksum or bundle_path.with_suffix(bundle_path.suffix + ".sha256")
    if not checksum_path.is_file() or checksum_path.is_symlink():
        errors.append(f"detached release checksum is missing or unsafe: {checksum_path}")
    else:
        try:
            checksum_text = checksum_path.read_text(encoding="utf-8").strip()
        except (OSError, UnicodeError) as exc:
            errors.append(f"cannot read detached release checksum: {exc}")
        else:
            expected_line = f"{bundle_record.get('sha256')}  {bundle_record.get('filename')}"
            if checksum_text != expected_line:
                errors.append("detached release checksum mismatch")

    try:
        with zipfile.ZipFile(bundle_path) as archive:
            bad = archive.testzip()
            if bad is not None:
                errors.append(f"release ZIP CRC failure: {bad}")
            names = archive.namelist()
            if names != sorted(names):
                errors.append("release ZIP entries are not sorted")
            if len(names) != len(set(names)):
                errors.append("release ZIP has duplicate entry names")
            image_names = [name for name in names if name != "SHA256SUMS"]
            if len(image_names) != EXPECTED_COUNTS["style_sheets"] or "SHA256SUMS" not in names:
                errors.append(
                    "release ZIP must contain exactly "
                    f"{EXPECTED_COUNTS['style_sheets']} images plus SHA256SUMS"
                )
            if sorted(image_names) != sorted(archive_records):
                errors.append("release ZIP images do not exactly match public manifest archive paths")
            for info in archive.infolist():
                pure = PurePosixPath(info.filename)
                if pure.is_absolute() or ".." in pure.parts or info.is_dir():
                    errors.append(f"unsafe release ZIP entry: {info.filename}")
                if info.date_time != (1980, 1, 1, 0, 0, 0):
                    errors.append(f"non-deterministic ZIP timestamp: {info.filename}")
                if info.compress_type != zipfile.ZIP_STORED:
                    errors.append(f"release ZIP entry is not stored byte-for-byte: {info.filename}")
                if ((info.external_attr >> 16) & 0o777) != 0o644:
                    errors.append(f"non-deterministic ZIP permissions: {info.filename}")
            internal_data = archive.read("SHA256SUMS") if "SHA256SUMS" in names else b""
            try:
                internal_lines = internal_data.decode("utf-8").splitlines()
            except UnicodeDecodeError as exc:
                errors.append(f"release ZIP SHA256SUMS is not UTF-8: {exc}")
                internal_lines = []
            internal: dict[str, str] = {}
            internal_order: list[str] = []
            for line in internal_lines:
                match = re.fullmatch(r"([0-9a-f]{64})  (.+)", line)
                if not match:
                    errors.append(f"invalid release ZIP checksum line: {line!r}")
                    continue
                digest, name = match.groups()
                internal_order.append(name)
                if name in internal:
                    errors.append(f"duplicate release ZIP checksum path: {name}")
                internal[name] = digest
            if internal_order != sorted(internal_order):
                errors.append("release ZIP SHA256SUMS entries are not sorted by path")
            if sorted(internal) != sorted(image_names):
                errors.append("release ZIP SHA256SUMS does not exactly cover images")
            seen_hashes: dict[str, str] = {}
            for name in image_names:
                data = archive.read(name)
                digest = sha256_bytes(data)
                if internal.get(name) != digest:
                    errors.append(f"release ZIP checksum mismatch: {name}")
                record = archive_records.get(name)
                if record is not None:
                    if record.get("sha256") != digest:
                        errors.append(f"release ZIP/public manifest hash mismatch: {name}")
                    if record.get("bytes") != len(data):
                        errors.append(f"release ZIP/public manifest byte-size mismatch: {name}")
                    try:
                        with Image.open(io.BytesIO(data)) as image:
                            image.verify()
                        with Image.open(io.BytesIO(data)) as image:
                            image.load()
                            if [image.width, image.height] != [record.get("width"), record.get("height")]:
                                errors.append(f"release ZIP/public manifest dimensions mismatch: {name}")
                    except Exception as exc:
                        errors.append(f"release ZIP image decode failed for {name}: {exc}")
                if digest in seen_hashes:
                    errors.append(f"duplicate release image hash: {name} and {seen_hashes[digest]}")
                else:
                    seen_hashes[digest] = name
    except (OSError, zipfile.BadZipFile, KeyError) as exc:
        errors.append(f"invalid release ZIP: {exc}")


def validate(
    root: Path,
    release_bundle: Path | None = None,
    detached_checksum: Path | None = None,
) -> list[str]:
    errors: list[str] = []
    if detached_checksum is not None and release_bundle is None:
        errors.append("detached checksum requires --release-bundle")
    if not root.is_dir() or root.is_symlink():
        return [f"repository root is not a regular directory: {root}"]
    references = validate_references(root, errors)
    reference_ids = [str(record["reference_id"]) for record in references]
    files = validate_inventory(root, reference_ids, errors)
    relative_files = {path.relative_to(root).as_posix() for path in files}
    missing = sorted(REQUIRED_ROOT_FILES - relative_files)
    if missing:
        errors.append(f"missing required repository files: {missing}")
    validate_markdown_links(root, files, errors)
    manifests, _source_hashes, _declared_previews, archive_records = validate_manifests(root, errors)
    for slug in EXPECTED_SLUGS:
        page = root / "characters" / slug / "references.md"
        display_name = manifests.get(slug, {}).get("display_name")
        if page.is_file() and isinstance(display_name, str):
            try:
                actual_page = page.read_text(encoding="utf-8")
            except (OSError, UnicodeError) as exc:
                errors.append(f"cannot read character reference page for {slug}: {exc}")
            else:
                if actual_page != expected_character_references(slug, display_name, references):
                    errors.append(f"character reference page does not match reference index: {slug}")
    validate_previews(root, errors)
    validate_pending(root, manifests, errors)
    export_manifest = validate_export_manifest(root, files, len(references), errors)
    validate_checksums(root, files, errors)
    if release_bundle is not None:
        validate_release_bundle(
            release_bundle,
            detached_checksum,
            export_manifest,
            archive_records,
            errors,
        )
    return errors


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path("."))
    parser.add_argument("--release-bundle", type=Path)
    parser.add_argument("--detached-checksum", type=Path)
    return parser.parse_args()


def absolute_unresolved(path: Path) -> Path:
    return Path(os.path.abspath(os.fspath(path.expanduser())))


def main() -> int:
    args = parse_args()
    errors = validate(
        absolute_unresolved(args.root),
        absolute_unresolved(args.release_bundle) if args.release_bundle else None,
        absolute_unresolved(args.detached_checksum) if args.detached_checksum else None,
    )
    if errors:
        for error in errors:
            print(f"ERROR: {error}", file=sys.stderr)
        print(f"FAIL: {len(errors)} validation error(s)", file=sys.stderr)
        return 1
    print("PASS: Hermes Multiverse public repository validation complete")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
