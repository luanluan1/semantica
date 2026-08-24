"""Throwaway README i18n synchronization spike."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import urllib.parse
import urllib.request
from pathlib import Path


_TARGET_LANGUAGES = {
    "zh-CN": "ZH-HANS",
    "ja": "JA",
    "ko": "KO",
    "es": "ES",
    "fr": "FR",
}
_FENCE = re.compile(r"^\s*(```|~~~)")
_PURE_HTML = re.compile(r"^(?:\s*<[^>]+>\s*)+$")
_STRUCTURAL_PREFIX = re.compile(
    r"^(\s*(?:(?:#{1,6}|>|[-+*]|\d+[.)])\s+)+)"
)
_PROTECTED_INLINE = re.compile(
    r"`+[^`]*`+"
    r"|!\[[^\]]*\]\([^)]+\)"
    r"|(?<=\])\([^)]+\)"
    r"|<[^>]+>"
    r"|https?://[^\s)>]+"
    r"|&[A-Za-z0-9#]+;"
    r"|\*\*|__|~~|\||\[|\]"
)


class DeepLTranslator:
    """Small DeepL boundary used by the spike, with no SDK dependency."""

    def __init__(self, api_key, timeout=30):
        if not api_key:
            raise ValueError("DEEPL_AUTH_KEY is required")
        self.api_key = api_key
        self.timeout = timeout
        host = "api-free.deepl.com" if api_key.endswith(":fx") else "api.deepl.com"
        self.endpoint = f"https://{host}/v2/translate"

    def translate(self, text, locale):
        target = _TARGET_LANGUAGES.get(locale)
        if target is None:
            raise ValueError(f"Unsupported locale: {locale}")
        payload = urllib.parse.urlencode(
            {
                "text": text,
                "source_lang": "EN",
                "target_lang": target,
                "tag_handling": "xml",
                "ignore_tags": "keep",
                "preserve_formatting": "1",
            }
        ).encode("utf-8")
        request = urllib.request.Request(
            self.endpoint,
            data=payload,
            headers={
                "Authorization": f"DeepL-Auth-Key {self.api_key}",
                "Content-Type": "application/x-www-form-urlencoded",
                "User-Agent": "semantica-readme-i18n-spike/1",
            },
            method="POST",
        )
        with urllib.request.urlopen(request, timeout=self.timeout) as response:
            body = json.loads(response.read().decode("utf-8"))
        return body["translations"][0]["text"]


class MarkerTranslator:
    """Visible, deterministic provider for testing without an external API."""

    def translate(self, text, locale):
        parts = re.split(
            r'(<keep id="p\d+">codex_keep_\d+</keep>)', text
        )
        for index, part in enumerate(parts):
            if not part.startswith("<keep ") and re.search(r"[A-Za-z]", part):
                parts[index] = re.sub(
                    r"(?=[A-Za-z])", f"[{locale}] ", part, count=1
                )
                break
        return "".join(parts)


def _cache_key(locale, source_line):
    value = f"{locale}\0{source_line}".encode("utf-8")
    return hashlib.sha256(value).hexdigest()


def _protect_inline(text):
    protected = []

    def replace(match):
        index = len(protected)
        marker = f"codex_keep_{index}"
        token = f'<keep id="p{index}">{marker}</keep>'
        protected.append((marker, match.group(0)))
        return token

    return _PROTECTED_INLINE.sub(replace, text), protected


def _restore_inline(text, protected):
    keep_tag = (
        r'<keep\b[^>]*>\s*codex_keep_\d+\s*</keep\s*>'
    )
    text = re.sub(rf'`+(?P<tag>{keep_tag})`+', r'\g<tag>', text)
    for marker, original in protected:
        tag = re.compile(
            rf'<keep\b[^>]*>\s*{re.escape(marker)}\s*</keep\s*>',
            re.IGNORECASE,
        )
        text = tag.sub(lambda _match: original, text, count=1)
    text = re.sub(r'\]\s+\(', '](', text)
    return text


def _translate_line(line, locale, translator):
    newline = ""
    if line.endswith("\r\n"):
        line, newline = line[:-2], "\r\n"
    elif line.endswith("\n"):
        line, newline = line[:-1], "\n"

    prefix = ""
    prefix_match = _STRUCTURAL_PREFIX.match(line)
    if prefix_match:
        prefix = prefix_match.group(1)
        line = line[len(prefix) :]

    leading = line[: len(line) - len(line.lstrip())]
    trailing = line[len(line.rstrip()) :]
    content = line.strip()
    protected_text, protected = _protect_inline(content)
    translated = translator.translate(protected_text, locale)
    restored = _restore_inline(translated, protected)
    return f"{prefix}{leading}{restored}{trailing}{newline}"


def synchronize(source, locale, translator, cache):
    """Translate prose lines while reusing translations keyed by source content."""

    if locale not in _TARGET_LANGUAGES:
        raise ValueError(f"Unsupported locale: {locale}")

    updated_cache = dict(cache)
    output = []
    fence_marker = None
    html_tag_open = False

    for line in source.splitlines(keepends=True):
        fence_match = _FENCE.match(line)
        if fence_match:
            marker = fence_match.group(1)
            if fence_marker is None:
                fence_marker = marker
            elif marker == fence_marker:
                fence_marker = None
            output.append(line)
            continue

        stripped = line.strip()
        if fence_marker is not None:
            output.append(line)
            continue
        if html_tag_open:
            output.append(line)
            if ">" in line:
                html_tag_open = False
            continue
        if stripped.startswith("<") and ">" not in stripped:
            html_tag_open = True
            output.append(line)
            continue

        should_translate = (
            bool(stripped)
            and not stripped.startswith("<!--")
            and not re.fullmatch(r"[-*_]{3,}", stripped)
            and not _PURE_HTML.fullmatch(stripped)
            and bool(re.search(r"[A-Za-z]", stripped))
        )
        if not should_translate:
            output.append(line)
            continue

        key = _cache_key(locale, line)
        translated = updated_cache.get(key)
        if translated is None:
            translated = _translate_line(line, locale, translator)
            updated_cache[key] = translated
        output.append(translated)

    return "".join(output), updated_cache


def _fenced_blocks(markdown):
    blocks = []
    current = []
    marker = None
    for line in markdown.splitlines(keepends=True):
        fence_match = _FENCE.match(line)
        if marker is None:
            if fence_match:
                marker = fence_match.group(1)
                current = [line]
        else:
            current.append(line)
            if fence_match and fence_match.group(1) == marker:
                blocks.append("".join(current))
                current = []
                marker = None
    if current:
        blocks.append("".join(current))
    return blocks


def assert_protected_structure(source, translated):
    """Reject translations that alter non-prose Markdown structures."""

    checks = (
        ("fenced code blocks", _fenced_blocks(source), _fenced_blocks(translated)),
        (
            "inline code",
            re.findall(r"`+[^`\n]*`+", source),
            re.findall(r"`+[^`\n]*`+", translated),
        ),
        (
            "link targets",
            re.findall(r"\]\(([^)]+)\)", source),
            re.findall(r"\]\(([^)]+)\)", translated),
        ),
        (
            "HTML tags",
            re.findall(r"<[^>]+>", source),
            re.findall(r"<[^>]+>", translated),
        ),
        (
            "URLs",
            re.findall(r"https?://[^\s)>]+", source),
            re.findall(r"https?://[^\s)>]+", translated),
        ),
        (
            "line prefixes",
            [
                match.group(1) if (match := _STRUCTURAL_PREFIX.match(line)) else ""
                for line in source.splitlines()
            ],
            [
                match.group(1) if (match := _STRUCTURAL_PREFIX.match(line)) else ""
                for line in translated.splitlines()
            ],
        ),
        (
            "table delimiters",
            [line.count("|") for line in source.splitlines()],
            [line.count("|") for line in translated.splitlines()],
        ),
    )
    if len(source.splitlines()) != len(translated.splitlines()):
        raise ValueError("Protected Markdown changed: line count")
    for label, before, after in checks:
        if before != after:
            raise ValueError(f"Protected Markdown changed: {label}")


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--cache-dir", type=Path, required=True)
    parser.add_argument("--provider", choices=("marker", "deepl"), required=True)
    parser.add_argument(
        "--locales",
        nargs="+",
        choices=tuple(_TARGET_LANGUAGES),
        default=tuple(_TARGET_LANGUAGES),
    )
    args = parser.parse_args(argv)

    source = args.source.read_text(encoding="utf-8")
    source_hash = hashlib.sha256(source.encode("utf-8")).hexdigest()
    args.output_dir.mkdir(parents=True, exist_ok=True)
    args.cache_dir.mkdir(parents=True, exist_ok=True)

    if args.provider == "marker":
        translator = MarkerTranslator()
    else:
        translator = DeepLTranslator(os.environ.get("DEEPL_AUTH_KEY", ""))

    header = (
        "<!-- This file is generated from README.md. Do not edit directly. "
        f"source-sha256: {source_hash} -->\n\n"
    )
    for locale in args.locales:
        cache_path = args.cache_dir / f"{locale}.json"
        if cache_path.exists():
            cache = json.loads(cache_path.read_text(encoding="utf-8"))
        else:
            cache = {}
        translated, updated_cache = synchronize(source, locale, translator, cache)
        output_path = args.output_dir / f"README.{locale}.md"
        output_path.write_text(header + translated, encoding="utf-8", newline="")
        assert_protected_structure(source, translated)
        cache_path.write_text(
            json.dumps(updated_cache, ensure_ascii=False, indent=2, sort_keys=True)
            + "\n",
            encoding="utf-8",
            newline="",
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
