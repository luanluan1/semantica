#!/usr/bin/env python3
"""
README i18n synchronisation tool.

PURPOSE
-------
README.md is the single canonical English source of truth.
This script bridges the gap between "README.md changed" and "translations updated":
it does NOT just detect staleness — it actively propagates changes into every
translation file by replacing changed sections with the updated English text,
clearly marked for human translation review.

HOW IT WORKS
------------
1.  Parses README.md into Markdown sections (by heading level).
2.  Compares each section's content against the version recorded in
    docs/i18n/.section-hashes (a JSON map of section-id → SHA-256).
3.  For each translation file, any section whose content changed is replaced
    with the current English text wrapped in a NEEDS-TRANSLATION block.
4.  Unchanged sections in translation files are left exactly as they are.
5.  After a human translates the marked sections, they remove the markers
    and run `python scripts/i18n_sync.py --accept` to update the hash store.

COMMANDS
--------
  python scripts/i18n_sync.py                  # show status: which sections are stale
  python scripts/i18n_sync.py --propagate       # inject changed English sections into
                                                # all translation files (marked for review)
  python scripts/i18n_sync.py --accept          # record current README.md sections as
                                                # accepted baseline; clear stale markers
  python scripts/i18n_sync.py --check           # CI mode: exit 1 if stale or markers remain

ADDING A NEW LANGUAGE
---------------------
1.  Copy README.md to docs/i18n/<lang-code>/README.md and translate the prose.
2.  Add the language code + name to LANGUAGES below.
3.  Add a link to the language selector in README.md (top + footer).
4.  Run:  python scripts/i18n_sync.py --accept
5.  Commit everything.

NO EXTERNAL DEPENDENCIES.  Pure Python 3.8+, stdlib only.
No credentials required for local use or CI validation.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import sys
from pathlib import Path
from typing import Optional

# ---------------------------------------------------------------------------
# Configuration — update LANGUAGES when adding a new locale
# ---------------------------------------------------------------------------

REPO_ROOT   = Path(__file__).resolve().parent.parent
CANONICAL   = REPO_ROOT / "README.md"
I18N_DIR    = REPO_ROOT / "docs" / "i18n"
HASHES_FILE = I18N_DIR / ".section-hashes"

# Add an entry here when adding a new language.
# Format: (BCP-47 code, human-readable name)
LANGUAGES: list[tuple[str, str]] = [
    ("zh-CN", "Simplified Chinese"),
    ("ja",    "Japanese"),
    ("ko",    "Korean"),
    ("es",    "Spanish"),
    ("fr",    "French"),
]

# Marker injected around sections that need translation after a README.md change.
# Human translators: replace the English text between the markers, then remove
# the marker lines themselves, and run `python scripts/i18n_sync.py --accept`.
MARKER_BEGIN = "<!-- NEEDS-TRANSLATION: begin -->"
MARKER_END   = "<!-- NEEDS-TRANSLATION: end -->"


# ---------------------------------------------------------------------------
# Section parsing
# ---------------------------------------------------------------------------

def _heading_id(heading_text: str) -> str:
    """Derive a stable, slug-style ID from a heading line (without the leading #s)."""
    text = heading_text.strip().lstrip("#").strip()
    text = re.sub(r"[^\w\s-]", "", text.lower())
    text = re.sub(r"[\s_]+", "-", text).strip("-")
    return text


def parse_sections(text: str) -> list[dict]:
    """
    Split *text* into sections, each a dict with keys:
      - id:      stable slug derived from the first heading
      - heading: the raw heading line (e.g. "## Quick Start")
      - body:    everything after the heading until the next same-or-higher heading
      - level:   heading level (1–6), or 0 for the preamble before the first heading
      - raw:     heading + body (the full section text as it appears in the file)
    The preamble (content before the first heading) is always section[0] with id="__preamble__".
    """
    lines = text.splitlines(keepends=True)
    sections: list[dict] = []
    current_lines: list[str] = []
    current_heading = ""
    current_level   = 0

    def flush(heading: str, level: int, body_lines: list[str]) -> None:
        raw  = heading + "".join(body_lines) if heading else "".join(body_lines)
        body = "".join(body_lines)
        sid  = _heading_id(heading) if heading else "__preamble__"
        # Make IDs unique by appending a count if necessary
        base = sid
        n    = sum(1 for s in sections if s["id"] == sid or s["id"].startswith(sid + "-"))
        if n:
            sid = f"{base}-{n}"
        sections.append({"id": sid, "heading": heading, "body": body, "level": level, "raw": raw})

    heading_re = re.compile(r"^(#{1,6})\s")
    in_fence   = False
    fence_pat  = re.compile(r"^(`{3,}|~{3,})")
    for line in lines:
        # Track fenced code blocks so we don't parse # inside them as headings
        if fence_pat.match(line.strip()):
            in_fence = not in_fence
        m = heading_re.match(line)
        if m and not in_fence:
            flush(current_heading, current_level, current_lines)
            current_heading = line
            current_level   = len(m.group(1))
            current_lines   = []
        else:
            current_lines.append(line)
    flush(current_heading, current_level, current_lines)
    return sections


def section_hash(section: dict) -> str:
    """Return the SHA-256 of a section's raw content."""
    return hashlib.sha256(section["raw"].encode("utf-8")).hexdigest()


# ---------------------------------------------------------------------------
# Hash store (docs/i18n/.section-hashes)
# ---------------------------------------------------------------------------

def load_hashes() -> dict[str, str]:
    if not HASHES_FILE.exists():
        return {}
    with HASHES_FILE.open(encoding="utf-8") as fh:
        return json.load(fh)


def save_hashes(hashes: dict[str, str]) -> None:
    I18N_DIR.mkdir(parents=True, exist_ok=True)
    with HASHES_FILE.open("w", encoding="utf-8") as fh:
        json.dump(hashes, fh, indent=2, sort_keys=True)
        fh.write("\n")


# ---------------------------------------------------------------------------
# Translation file helpers
# ---------------------------------------------------------------------------

def translation_path(lang_code: str) -> Path:
    return I18N_DIR / lang_code / "README.md"


def stale_sections(canonical_sections: list[dict], stored_hashes: dict[str, str]) -> list[dict]:
    """Return sections whose content has changed since the last --accept."""
    changed = []
    for sec in canonical_sections:
        if sec["id"] == "__preamble__":
            continue  # preamble changes are tracked separately; rarely need re-translation
        current = section_hash(sec)
        if stored_hashes.get(sec["id"]) != current:
            changed.append(sec)
    return changed


def has_pending_markers(path: Path) -> bool:
    """Return True if the translation file still contains NEEDS-TRANSLATION markers."""
    if not path.exists():
        return False
    return MARKER_BEGIN in path.read_text(encoding="utf-8")


def inject_stale_sections(canonical_sections: list[dict],
                           translation_path: Path,
                           changed_ids: set[str]) -> bool:
    """
    Update *translation_path* so that every section in *changed_ids* is
    replaced with the current English text wrapped in NEEDS-TRANSLATION markers.
    Sections not in *changed_ids* are left exactly as they are.

    Matches sections by position (index) rather than by ID, since translated
    headings produce different slugs than the English originals.

    Returns True if the file was modified.
    """
    if not translation_path.exists():
        # No translation exists yet: seed the whole file with English + markers
        lines = []
        for sec in canonical_sections:
            if sec["id"] in changed_ids:
                lines.append(MARKER_BEGIN + "\n")
                lines.append(sec["raw"])
                if not sec["raw"].endswith("\n"):
                    lines.append("\n")
                lines.append(MARKER_END + "\n")
            else:
                lines.append(sec["raw"])
        translation_path.parent.mkdir(parents=True, exist_ok=True)
        translation_path.write_text("".join(lines), encoding="utf-8")
        return True

    orig = translation_path.read_text(encoding="utf-8")
    tr_sections = parse_sections(orig)

    # Match by position: canonical section i ↔ translation section i.
    # If the counts differ, fall back to id-based matching for the excess.
    output_parts: list[str] = []

    for i, sec in enumerate(canonical_sections):
        is_changed = sec["id"] in changed_ids

        if is_changed:
            output_parts.append(MARKER_BEGIN + "\n")
            output_parts.append(sec["raw"])
            if not sec["raw"].endswith("\n"):
                output_parts.append("\n")
            output_parts.append(MARKER_END + "\n")
        else:
            # Keep the existing translation at this position
            if i < len(tr_sections):
                raw = tr_sections[i]["raw"]
                # Strip any previously injected stale markers (idempotent)
                raw = raw.replace(MARKER_BEGIN + "\n", "").replace(MARKER_END + "\n", "")
                output_parts.append(raw)
            else:
                # Brand-new section not in translation yet: mark for translation
                output_parts.append(MARKER_BEGIN + "\n")
                output_parts.append(sec["raw"])
                if not sec["raw"].endswith("\n"):
                    output_parts.append("\n")
                output_parts.append(MARKER_END + "\n")

    new_content = "".join(output_parts)
    if new_content == orig:
        return False
    translation_path.write_text(new_content, encoding="utf-8")
    return True


# ---------------------------------------------------------------------------
# Commands
# ---------------------------------------------------------------------------

def cmd_status(canonical_sections: list[dict], stored_hashes: dict[str, str]) -> None:
    """Print a status table of all sections and translation files."""
    changed = stale_sections(canonical_sections, stored_hashes)
    changed_ids = {s["id"] for s in changed}

    if not changed_ids:
        print("✓  README.md sections are in sync with the stored baseline.")
    else:
        print(f"⚠  {len(changed_ids)} section(s) changed in README.md since last sync:\n")
        for s in changed:
            print(f"   {s['level'] * '#'}  {s['heading'].strip()!r}  (id: {s['id']})")
        print()

    print("Translation file status:")
    for code, name in LANGUAGES:
        path = translation_path(code)
        if not path.exists():
            print(f"   ✗  {code:8s}  ({name}) — file missing")
        elif has_pending_markers(path):
            print(f"   ⏳  {code:8s}  ({name}) — has NEEDS-TRANSLATION markers (review required)")
        elif changed_ids:
            print(f"   ⚠  {code:8s}  ({name}) — stale (run --propagate)")
        else:
            print(f"   ✓  {code:8s}  ({name})")
    print()
    if changed_ids:
        print("Run:  python scripts/i18n_sync.py --propagate")
        print("      … translate the marked sections …")
        print("      python scripts/i18n_sync.py --accept")


def cmd_propagate(canonical_sections: list[dict], stored_hashes: dict[str, str]) -> None:
    """
    For every stale section, replace the corresponding section in each
    translation file with the current English text wrapped in NEEDS-TRANSLATION
    markers.  Unchanged sections are untouched.
    """
    if not stored_hashes:
        print(
            "ERROR: no baseline recorded yet.\n"
            "Run --accept first (after verifying all translations are complete),\n"
            "then use --propagate only when README.md subsequently changes.",
            file=sys.stderr,
        )
        sys.exit(1)

    changed = stale_sections(canonical_sections, stored_hashes)
    changed_ids = {s["id"] for s in changed}

    if not changed_ids:
        print("Nothing to propagate — README.md is in sync with the stored baseline.")
        return

    print(f"Propagating {len(changed_ids)} changed section(s) into translation files:\n")
    for s in changed:
        print(f"  • {s['heading'].strip()} (id: {s['id']})")
    print()

    for code, name in LANGUAGES:
        path = translation_path(code)
        modified = inject_stale_sections(canonical_sections, path, changed_ids)
        if modified:
            print(f"  ✓  Updated {path.relative_to(REPO_ROOT)}")
        else:
            print(f"  –  {path.relative_to(REPO_ROOT)} already up to date")

    print()
    print("Next steps:")
    print("  1. Open each docs/i18n/<lang>/README.md file.")
    print("  2. Find every <!-- NEEDS-TRANSLATION: begin --> block.")
    print("  3. Translate the English text inside the block into the target language.")
    print("  4. Remove the <!-- NEEDS-TRANSLATION: begin/end --> marker lines.")
    print("  5. Run:  python scripts/i18n_sync.py --accept")
    print("  6. Commit all changed files.")


def cmd_accept(canonical_sections: list[dict]) -> None:
    """
    Record the current README.md section hashes as the accepted baseline.
    Aborts if any translation file still has NEEDS-TRANSLATION markers.
    """
    pending = []
    for code, name in LANGUAGES:
        path = translation_path(code)
        if has_pending_markers(path):
            pending.append((code, name, path))

    if pending:
        print("ERROR: the following translation files still have NEEDS-TRANSLATION markers:\n",
              file=sys.stderr)
        for code, name, path in pending:
            print(f"  {path.relative_to(REPO_ROOT)}  ({name})", file=sys.stderr)
        print(
            "\nTranslate and remove all markers before running --accept.",
            file=sys.stderr,
        )
        sys.exit(1)

    hashes = {sec["id"]: section_hash(sec) for sec in canonical_sections}
    save_hashes(hashes)
    print(f"Accepted — recorded hashes for {len(hashes)} sections in {HASHES_FILE.relative_to(REPO_ROOT)}")
    print("Commit docs/i18n/.section-hashes together with the updated translation files.")


def cmd_check() -> None:
    """
    CI validation mode.  Exits 1 if:
      - any language is missing its README.md file, OR
      - README.md has sections not in the stored baseline (stale), OR
      - any translation file still contains NEEDS-TRANSLATION markers.
    """
    if not CANONICAL.exists():
        print(f"ERROR: {CANONICAL} not found", file=sys.stderr)
        sys.exit(1)

    canonical_text     = CANONICAL.read_text(encoding="utf-8")
    canonical_sections = parse_sections(canonical_text)
    stored_hashes      = load_hashes()
    failures: list[str] = []

    # 1. Missing files
    for code, name in LANGUAGES:
        path = translation_path(code)
        if not path.exists():
            failures.append(f"Missing: {path.relative_to(REPO_ROOT)}  ({name})")

    # 2. Stale sections
    changed = stale_sections(canonical_sections, stored_hashes)
    if changed:
        for s in changed:
            failures.append(
                f"Stale: section '{s['heading'].strip()}' (id: {s['id']}) changed in README.md"
            )

    # 3. Pending markers
    for code, name in LANGUAGES:
        path = translation_path(code)
        if has_pending_markers(path):
            failures.append(
                f"Pending: {path.relative_to(REPO_ROOT)} still has NEEDS-TRANSLATION markers"
            )

    if failures:
        print("i18n check FAILED:\n", file=sys.stderr)
        for f in failures:
            print(f"  ✗  {f}", file=sys.stderr)
        print(
            "\nTo fix:\n"
            "  python scripts/i18n_sync.py --propagate   # inject changed sections\n"
            "  # translate the marked sections in each docs/i18n/<lang>/README.md\n"
            "  python scripts/i18n_sync.py --accept      # record acceptance\n"
            "  git add docs/i18n && git commit -m 'docs(i18n): sync translations'\n",
            file=sys.stderr,
        )
        sys.exit(1)

    n = len(canonical_sections) - 1  # exclude preamble
    print(f"i18n check passed — {n} sections, "
          f"{len(LANGUAGES)} translations, no pending markers.")


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def main() -> None:
    parser = argparse.ArgumentParser(
        description="README i18n synchronisation tool.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    group = parser.add_mutually_exclusive_group()
    group.add_argument(
        "--propagate",
        action="store_true",
        help="Inject changed English sections (with NEEDS-TRANSLATION markers) "
             "into all translation files.",
    )
    group.add_argument(
        "--accept",
        action="store_true",
        help="Record the current README.md sections as the accepted baseline "
             "(run after translating all marked sections).",
    )
    group.add_argument(
        "--check",
        action="store_true",
        help="CI mode: exit 1 if sections are stale or markers remain.",
    )
    args = parser.parse_args()

    if args.check:
        cmd_check()
        return

    if not CANONICAL.exists():
        print(f"ERROR: {CANONICAL} not found", file=sys.stderr)
        sys.exit(1)

    canonical_text     = CANONICAL.read_text(encoding="utf-8")
    canonical_sections = parse_sections(canonical_text)
    stored_hashes      = load_hashes()

    if args.propagate:
        cmd_propagate(canonical_sections, stored_hashes)
    elif args.accept:
        cmd_accept(canonical_sections)
    else:
        cmd_status(canonical_sections, stored_hashes)


if __name__ == "__main__":
    main()
