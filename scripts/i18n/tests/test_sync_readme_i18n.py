import json
import os
import sys
import tempfile
import unittest
from pathlib import Path


sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from sync_readme_i18n import (
    DeepLTranslator,
    assert_protected_structure,
    main,
    synchronize,
)


SAMPLE_README = """<div align="center">

# Semantica

    Build a context graph with **traceable decisions** and `pip install semantica`.
    Support RDF & LPG data models.

[Read the guide](docs/guide.md) or visit https://example.com/docs.

<img
  src="docs/demo.gif"
  alt="Semantica demo"
  width="900"
/>

```python
message = "Do not translate this string"
```

| Feature | Description |
| --- | --- |
| Provenance | Trace every decision |

</div>
"""


class RecordingTranslator:
    def __init__(self, transform=lambda text, locale: text):
        self.calls = []
        self.transform = transform

    def translate(self, text, locale):
        self.calls.append((text, locale))
        return self.transform(text, locale)


class XmlExpandingTranslator(RecordingTranslator):
    def translate(self, text, locale):
        translated = super().translate(text, locale)
        return translated.replace(
            '<keep id="p0">codex_keep_0</keep>',
            '<keep id="p0">codex_keep_0</keep>',
        )


class MarkdownFormattingTranslator(RecordingTranslator):
    def translate(self, text, locale):
        translated = super().translate(text, locale)
        return translated.replace(
            '<keep id="p0">codex_keep_0</keep>',
            '`<keep id="p0">codex_keep_0</keep>`',
        ).replace("](", "] (")


class SynchronizeTests(unittest.TestCase):
    def test_identity_translation_round_trips_markdown_byte_for_byte(self):
        translator = RecordingTranslator()

        result, cache = synchronize(SAMPLE_README, "zh-CN", translator, {})

        self.assertEqual(SAMPLE_README, result)
        self.assertGreater(len(cache), 0)

    def test_translation_preserves_code_links_html_and_markdown_markers(self):
        translator = RecordingTranslator(
            lambda text, locale: text.replace("Build a context graph", "构建上下文图")
            .replace("traceable decisions", "可追溯决策")
            .replace("Read the guide", "阅读指南")
            .replace("Feature", "功能")
            .replace("Description", "说明")
            .replace("Provenance", "溯源")
            .replace("Trace every decision", "追踪每项决策")
            .replace("img", "图像")
            .replace("src", "来源")
            .replace("alt", "替代")
        )

        result, _ = synchronize(SAMPLE_README, "zh-CN", translator, {})

        self.assertIn("构建上下文图", result)
        self.assertIn("**可追溯决策**", result)
        self.assertIn("Support RDF & LPG data models.", result)
        self.assertIn("`pip install semantica`", result)
        self.assertIn("[阅读指南](docs/guide.md)", result)
        self.assertIn("https://example.com/docs", result)
        self.assertIn('<div align="center">', result)
        self.assertIn(
            '<img\n  src="docs/demo.gif"\n  alt="Semantica demo"\n  width="900"\n/>',
            result,
        )
        self.assertIn('message = "Do not translate this string"', result)
        self.assertIn("| 功能 | 说明 |", result)

    def test_dense_badge_rows_are_kept_verbatim(self):
        dense = "[One](one) [Two](two) [Three](three) [Four](four)"
        translator = RecordingTranslator(lambda text, locale: "translated")
        result, _ = synchronize(dense, "zh-CN", translator, {})
        self.assertEqual(dense, result)
        self.assertEqual([], translator.calls)

    def test_external_link_rows_are_kept_verbatim(self):
        linked = "Read the [online guide](https://example.com/guide)."
        translator = RecordingTranslator(lambda text, locale: "translated")
        result, _ = synchronize(linked, "zh-CN", translator, {})
        self.assertEqual(linked, result)
        self.assertEqual([], translator.calls)

    def test_protection_tokens_have_content_for_xml_translation(self):
        translator = XmlExpandingTranslator()

        result, _ = synchronize(SAMPLE_README, "zh-CN", translator, {})

        self.assertNotIn("<keep", result)
        self.assertIn("`pip install semantica`", result)
        self.assertIn('message = "Do not translate this string"', result)

    def test_removes_provider_markdown_formatting_around_protected_tokens(self):
        translator = MarkdownFormattingTranslator()

        result, _ = synchronize(SAMPLE_README, "fr", translator, {})

        self.assertIn("`pip install semantica`", result)
        self.assertIn("[Read the guide](docs/guide.md)", result)

    def test_reuses_cached_lines_and_translates_only_changed_prose(self):
        first = RecordingTranslator()
        _, cache = synchronize(SAMPLE_README, "fr", first, {})
        changed = SAMPLE_README.replace(
            "Trace every decision", "Trace every important decision"
        )
        second = RecordingTranslator()

        result, updated_cache = synchronize(changed, "fr", second, cache)

        self.assertEqual(changed, result)
        self.assertEqual(1, len(second.calls))
        self.assertGreaterEqual(len(updated_cache), len(cache))

    def test_serialized_cache_can_be_reused(self):
        first = RecordingTranslator()
        expected, cache = synchronize(SAMPLE_README, "ja", first, {})
        restored_cache = json.loads(json.dumps(cache))
        second = RecordingTranslator()

        actual, _ = synchronize(SAMPLE_README, "ja", second, restored_cache)

        self.assertEqual(expected, actual)
        self.assertEqual([], second.calls)

    def test_structure_validator_accepts_translation_with_protected_markdown(self):
        translator = RecordingTranslator(lambda text, locale: f"Translated {text}")
        translated, _ = synchronize(SAMPLE_README, "es", translator, {})

        assert_protected_structure(SAMPLE_README, translated)

    def test_structure_validator_rejects_changed_link_destination(self):
        changed = SAMPLE_README.replace("docs/guide.md", "docs/other.md")

        with self.assertRaisesRegex(ValueError, "link targets"):
            assert_protected_structure(SAMPLE_README, changed)

    def test_deepl_requires_an_api_key(self):
        with self.assertRaisesRegex(ValueError, "DEEPL_AUTH_KEY"):
            DeepLTranslator("")

    def test_cli_generates_all_requested_locales_and_persistent_caches(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / "README.md"
            output = root / "generated"
            cache = root / "cache"
            source.write_text(SAMPLE_README, encoding="utf-8", newline="")

            exit_code = main(
                [
                    "--source",
                    str(source),
                    "--output-dir",
                    str(output),
                    "--cache-dir",
                    str(cache),
                    "--provider",
                    "marker",
                    "--locales",
                    "zh-CN",
                    "ja",
                    "ko",
                    "es",
                    "fr",
                ]
            )

            self.assertEqual(0, exit_code)
            for locale in ("zh-CN", "ja", "ko", "es", "fr"):
                generated = output / f"README.{locale}.md"
                manifest = cache / f"{locale}.json"
                self.assertTrue(generated.is_file())
                self.assertTrue(manifest.is_file())
                content = generated.read_text(encoding="utf-8")
                self.assertIn("This file is generated from README.md", content)
                self.assertIn(f"[{locale}]", content)
                self.assertIn("`pip install semantica`", content)
                self.assertIn('message = "Do not translate this string"', content)


if __name__ == "__main__":
    unittest.main()
