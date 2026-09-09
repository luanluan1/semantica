# README Internationalisation (i18n)

This directory contains repository-managed translations of the canonical
[`README.md`](../../README.md) at the repository root.

---

## 1. Source of truth

**`README.md` in the repository root is the one and only canonical source.**

- Do not edit translation files to introduce new content that does not exist in
  the canonical README.
- Do not move the English README out of the repository root.
- Do not put complete translations inside README.md itself.

---

## 2. Where translations live

```
docs/i18n/
├── README.md                ← this file (workflow documentation)
├── .section-hashes          ← JSON map of section-id → SHA-256; committed to git
├── zh-CN/
│   └── README.md            ← Simplified Chinese
├── ja/
│   └── README.md            ← Japanese
├── ko/
│   └── README.md            ← Korean
├── es/
│   └── README.md            ← Spanish
└── fr/
    └── README.md            ← French
```

Language codes follow [BCP 47](https://www.ietf.org/rfc/bcp/bcp47.txt) conventions
(e.g. `zh-CN` for Simplified Chinese, `pt-BR` for Brazilian Portuguese).

---

## 3. How to synchronise translations after changing README.md

The sync tool (`scripts/i18n_sync.py`) works at the **section** level.
It parses README.md into its Markdown headings, hashes each section, and compares
those hashes against the baseline stored in `docs/i18n/.section-hashes`.
When a section changes, only that section needs re-translation — unchanged
sections in every translation file are left exactly as they are.

### Step-by-step

```bash
# 1. Check what changed
python scripts/i18n_sync.py

# 2. Inject the changed English sections into all translation files.
#    Each changed section is wrapped with <!-- NEEDS-TRANSLATION --> markers
#    so translators can find them instantly.
python scripts/i18n_sync.py --propagate

# 3. Open each docs/i18n/<lang>/README.md and translate the marked blocks.
#    Rules:
#      • Translate prose, headings, table labels, <details>/<summary> text.
#      • NEVER translate: code blocks, shell commands, URLs, env var names,
#        package/import paths, class names, API paths, version numbers,
#        badge URLs, HTML tags.
#      • Remove the <!-- NEEDS-TRANSLATION: begin/end --> marker lines
#        once you have translated the content inside them.

# 4. Record the updated sections as the accepted baseline.
#    This command aborts if any translation file still has markers.
python scripts/i18n_sync.py --accept

# 5. Commit everything together.
git add README.md docs/i18n/
git commit -m "docs(i18n): synchronise translations with README.md"
```

### What requires human review

The tool propagates changed sections as English text with markers.
**A human translator must translate the content inside those markers.**
The tool does not call any external translation API — translation quality is
entirely under human control. This ensures:

- Technical identifiers, commands, and URLs are never accidentally translated.
- Context-sensitive prose is translated accurately.
- No credentials or external services are required to run the workflow.

---

## 4. How to add a new language

```bash
# 1. Create the translation directory and file
mkdir -p docs/i18n/<lang-code>
cp README.md docs/i18n/<lang-code>/README.md
# Translate the prose in docs/i18n/<lang-code>/README.md manually.

# 2. Add the language to LANGUAGES in scripts/i18n_sync.py:
#    LANGUAGES: list[tuple[str, str]] = [
#        ...existing entries...
#        ("<lang-code>", "<Language Name>"),   # ← add here
#    ]

# 3. Add a link to the language selector in README.md (top nav + footer).

# 4. Record the baseline
python scripts/i18n_sync.py --accept

# 5. Commit
git add docs/i18n/<lang-code>/README.md \
        docs/i18n/.section-hashes \
        scripts/i18n_sync.py \
        README.md
git commit -m "docs(i18n): add <Language Name> translation"
```

No other files need to change.

---

## 5. How CI validates synchronisation

The CI workflow (`.github/workflows/i18n-check.yml`) runs on any PR that
touches `README.md`, `docs/i18n/**`, or `scripts/i18n_sync.py`:

```bash
python scripts/i18n_sync.py --check
```

This exits 1 (blocking the PR) when:

- A language listed in `LANGUAGES` is missing its `README.md` file.
- Any section in README.md has changed since the last `--accept`
  (section hash mismatch in `.section-hashes`).
- Any translation file still contains `<!-- NEEDS-TRANSLATION -->` markers.

The error message prints the exact commands needed to fix the failure.

---

## 6. Translation rules (reference)

| ✅ Translate | ❌ Never translate |
|---|---|
| Prose paragraphs | Shell commands |
| Headings | Code block contents |
| Table row/column labels | URLs and hyperlinks |
| `<details>`/`<summary>` text | Environment variable names |
| Badge alt text (prose only) | Python package/import paths |
| UI description text | Class and function names |
| Comparison table cells (prose) | API endpoint paths |
| Release notes prose | Configuration keys |
| | Version numbers |
| | Badge image `src=` URLs |
| | HTML tags and attributes |

Preserve all Markdown structure exactly: headings, tables, fenced code blocks
(with language tags), `<details>`, `<summary>`, `<div>`, horizontal rules, and
blank lines. Markdown structure in translation files must mirror the canonical
README exactly so the sync tool can match sections reliably.
