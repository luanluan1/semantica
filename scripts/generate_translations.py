# -*- coding: utf-8 -*-
"""
Generate (or regenerate) all translation files from README.md.

This script applies line-exact heading and prose replacements to README.md,
skipping content inside fenced code blocks, and writes the result to each
docs/i18n/<lang>/README.md.

It is the canonical way to rebuild translations after they have been
contaminated or when bootstrapping a new language from the English source.

Usage:
    python scripts/generate_translations.py
    python scripts/generate_translations.py --lang zh-CN   # single language

After running, always re-accept the baseline:
    python scripts/i18n_sync.py --accept
"""

import argparse
import re
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
README    = REPO_ROOT / "README.md"
I18N_DIR  = REPO_ROOT / "docs" / "i18n"

fence_re    = re.compile(r"^(`{3,}|~{3,})")
NAV_LINE_RE = re.compile(
    r"[^\n]*\[简体中文\]\(docs/i18n/zh-CN/README\.md\)[^\n]*"
)

NAVS = {
    "zh-CN": "[English](../../../README.md) · [简体中文](./README.md) · [日本語](../ja/README.md) · [한국어](../ko/README.md) · [Español](../es/README.md) · [Français](../fr/README.md)",
    "ja":    "[English](../../../README.md) · [简体中文](../zh-CN/README.md) · [日本語](./README.md) · [한국어](../ko/README.md) · [Español](../es/README.md) · [Français](../fr/README.md)",
    "ko":    "[English](../../../README.md) · [简体中文](../zh-CN/README.md) · [日本語](../ja/README.md) · [한국어](./README.md) · [Español](../es/README.md) · [Français](../fr/README.md)",
    "es":    "[English](../../../README.md) · [简体中文](../zh-CN/README.md) · [日本語](../ja/README.md) · [한국어](../ko/README.md) · [Español](./README.md) · [Français](../fr/README.md)",
    "fr":    "[English](../../../README.md) · [简体中文](../zh-CN/README.md) · [日本語](../ja/README.md) · [한국어](../ko/README.md) · [Español](../es/README.md) · [Français](./README.md)",
}

# Line-exact replacements (including trailing \n).
# Only heading lines and short prose-only lines are listed here.
# Everything inside code blocks is left verbatim by the fence tracker.
REPLACEMENTS: dict[str, dict[str, str]] = {
    "zh-CN": {
        "### Graph-Native Infrastructure for Context and Accountable AI Systems\n": "### 面向上下文感知与可问责 AI 系统的图原生基础设施\n",
        "#### *Developer-first, knowledge infrastructure for AI, alternative to expensive enterprise platforms.*\n": "#### *以开发者为先，面向 AI 的知识基础设施，可替代昂贵的企业级平台。*\n",
        "#### Built for High-Stakes, Regulated Domains\n": "#### 专为高风险受监管场景而生\n",
        "## What Semantica Gives You\n": "## Semantica 能为您提供什么\n",
        "## Why Semantica\n": "## 为什么选择 Semantica\n",
        "## Quick Start\n": "## 快速开始\n",
        "## Architecture\n": "## 架构\n",
        "## Decision Intelligence\n": "## 决策智能\n",
        "## Context Graphs\n": "## 上下文图\n",
        "## Recipe: Audit Trail for a Regulated Decision\n": "## 实践：受监管决策的审计链\n",
        "## Explore the Platform\n": "## 探索平台\n",
        "## Module Reference\n": "## 模块参考\n",
        "## More Recipes\n": "## 更多实践\n",
        "## Features at a Glance\n": "## 功能概览\n",
        "## Performance\n": "## 性能\n",
        "## CLI\n": "## 命令行接口\n",
        "## Integrations\n": "## 集成\n",
        "### Agentic Frameworks\n": "### 智能体框架\n",
        "### MCP Server\n": "### MCP 服务器\n",
        "### REST API\n": "### REST API\n",
        "### Plugin Bundles\n": "### 插件包\n",
        "## Knowledge Explorer\n": "## 知识浏览器\n",
        "## What's New in v0.7.0\n": "## v0.7.0 新特性\n",
        "## What's New in v0.6.8\n": "## v0.6.8 新特性\n",
        "## Built for High-Stakes Domains\n": "## 为高风险场景而生\n",
        "## Installation\n": "## 安装\n",
        "### CI & Deployment\n": "### CI 与部署\n",
        "## Enterprise\n": "## 企业版\n",
        "## Community & Support\n": "## 社区与支持\n",
        "## Star History\n": "## Star 历史\n",
        "## Contributors\n": "## 贡献者\n",
        "## Contributing\n": "## 贡献指南\n",
        "## Cite Us\n": "## 引用\n",
        "**[▶ Watch the full platform walkthrough](https://www.youtube.com/watch?v=QfnNZg4-dZA)**\n": "**[▶ 观看完整平台演示](https://www.youtube.com/watch?v=QfnNZg4-dZA)**\n",
        "**[⭐ Star on GitHub](https://github.com/semantica-agi/semantica)** &nbsp;·&nbsp; **[Join Discord](https://discord.gg/sV34vps5hH)**\n": "**[⭐ 在 GitHub 上 Star](https://github.com/semantica-agi/semantica)** &nbsp;·&nbsp; **[加入 Discord](https://discord.gg/sV34vps5hH)**\n",
        "**[⭐ Star on GitHub →](https://github.com/semantica-agi/semantica)**\n": "**[⭐ 在 GitHub 上 Star →](https://github.com/semantica-agi/semantica)**\n",
        "MIT License · Built by [Semantica](https://github.com/semantica-agi)\n": "MIT 许可证 · 由 [Semantica](https://github.com/semantica-agi) 构建\n",
        "If this project helps you build better AI, a star means a lot.\n": "如果这个项目帮助您构建了更好的 AI，一颗 Star 对我们意义重大。\n",
        "If Semantica solves a real problem for you, a star helps others find it.\n": "如果 Semantica 为您解决了实际问题，点个 Star 有助于让更多人发现它。\n",
        "**Verify your install in 5 seconds:**\n": "**5 秒内验证安装：**\n",
    },
    "ja": {
        "### Graph-Native Infrastructure for Context and Accountable AI Systems\n": "### コンテキストと説明責任ある AI システムのためのグラフネイティブインフラ\n",
        "#### *Developer-first, knowledge infrastructure for AI, alternative to expensive enterprise platforms.*\n": "#### *開発者ファースト、AI のためのナレッジインフラ。高額なエンタープライズプラットフォームの代替。*\n",
        "#### Built for High-Stakes, Regulated Domains\n": "#### 高リスク・規制対象ドメイン向けに構築\n",
        "## What Semantica Gives You\n": "## Semantica が提供するもの\n",
        "## Why Semantica\n": "## なぜ Semantica なのか\n",
        "## Quick Start\n": "## クイックスタート\n",
        "## Architecture\n": "## アーキテクチャ\n",
        "## Decision Intelligence\n": "## 意思決定インテリジェンス\n",
        "## Context Graphs\n": "## コンテキストグラフ\n",
        "## Recipe: Audit Trail for a Regulated Decision\n": "## レシピ：規制対象の意思決定における監査証跡\n",
        "## Explore the Platform\n": "## プラットフォームを探索する\n",
        "## Module Reference\n": "## モジュールリファレンス\n",
        "## More Recipes\n": "## さらなるレシピ\n",
        "## Features at a Glance\n": "## 機能一覧\n",
        "## Performance\n": "## パフォーマンス\n",
        "## CLI\n": "## CLI\n",
        "## Integrations\n": "## インテグレーション\n",
        "### Agentic Frameworks\n": "### エージェントフレームワーク\n",
        "### MCP Server\n": "### MCP サーバー\n",
        "### REST API\n": "### REST API\n",
        "### Plugin Bundles\n": "### プラグインバンドル\n",
        "## Knowledge Explorer\n": "## ナレッジエクスプローラー\n",
        "## What's New in v0.7.0\n": "## v0.7.0 の新機能\n",
        "## What's New in v0.6.8\n": "## v0.6.8 の新機能\n",
        "## Built for High-Stakes Domains\n": "## 高リスクドメイン向けに構築\n",
        "## Installation\n": "## インストール\n",
        "### CI & Deployment\n": "### CI とデプロイメント\n",
        "## Enterprise\n": "## エンタープライズ\n",
        "## Community & Support\n": "## コミュニティとサポート\n",
        "## Star History\n": "## スター履歴\n",
        "## Contributors\n": "## コントリビューター\n",
        "## Contributing\n": "## コントリビューション\n",
        "## Cite Us\n": "## 引用\n",
        "*Knowledge Explorer · Context Graphs · Reasoning Engine · Decision Intelligence · Ontology Hub*\n": "*ナレッジエクスプローラー · コンテキストグラフ · 推論エンジン · 意思決定インテリジェンス · オントロジーハブ*\n",
        "**[▶ Watch the full platform walkthrough](https://www.youtube.com/watch?v=QfnNZg4-dZA)**\n": "**[▶ プラットフォーム全体のウォークスルーを見る](https://www.youtube.com/watch?v=QfnNZg4-dZA)**\n",
        "**[⭐ Star on GitHub](https://github.com/semantica-agi/semantica)** &nbsp;·&nbsp; **[Join Discord](https://discord.gg/sV34vps5hH)**\n": "**[⭐ GitHub でスター](https://github.com/semantica-agi/semantica)** &nbsp;·&nbsp; **[Discord に参加](https://discord.gg/sV34vps5hH)**\n",
        "**[⭐ Star on GitHub →](https://github.com/semantica-agi/semantica)**\n": "**[⭐ GitHub でスター →](https://github.com/semantica-agi/semantica)**\n",
        "MIT License · Built by [Semantica](https://github.com/semantica-agi)\n": "MIT ライセンス · [Semantica](https://github.com/semantica-agi) によって構築\n",
        "If this project helps you build better AI, a star means a lot.\n": "このプロジェクトがより良い AI を構築するのに役立つなら、スターはとても大きな意味を持ちます。\n",
        "If Semantica solves a real problem for you, a star helps others find it.\n": "Semantica が実際の問題を解決するなら、スターで他の人に見つけてもらえます。\n",
        "**Verify your install in 5 seconds:**\n": "**5 秒でインストールを確認：**\n",
    },
    "ko": {
        "### Graph-Native Infrastructure for Context and Accountable AI Systems\n": "### 컨텍스트 및 설명 가능한 AI 시스템을 위한 그래프 네이티브 인프라\n",
        "#### *Developer-first, knowledge infrastructure for AI, alternative to expensive enterprise platforms.*\n": "#### *개발자 우선, AI를 위한 지식 인프라. 비싼 엔터프라이즈 플랫폼의 대안.*\n",
        "#### Built for High-Stakes, Regulated Domains\n": "#### 고위험, 규제 도메인을 위해 구축\n",
        "## What Semantica Gives You\n": "## Semantica가 제공하는 것\n",
        "## Why Semantica\n": "## 왜 Semantica인가\n",
        "## Quick Start\n": "## 빠른 시작\n",
        "## Architecture\n": "## 아키텍처\n",
        "## Decision Intelligence\n": "## 의사결정 인텔리전스\n",
        "## Context Graphs\n": "## 컨텍스트 그래프\n",
        "## Recipe: Audit Trail for a Regulated Decision\n": "## 레시피: 규제 대상 의사결정의 감사 추적\n",
        "## Explore the Platform\n": "## 플랫폼 탐색\n",
        "## Module Reference\n": "## 모듈 레퍼런스\n",
        "## More Recipes\n": "## 추가 레시피\n",
        "## Features at a Glance\n": "## 기능 개요\n",
        "## Performance\n": "## 성능\n",
        "## CLI\n": "## CLI\n",
        "## Integrations\n": "## 통합\n",
        "### Agentic Frameworks\n": "### 에이전트 프레임워크\n",
        "### MCP Server\n": "### MCP 서버\n",
        "### REST API\n": "### REST API\n",
        "### Plugin Bundles\n": "### 플러그인 번들\n",
        "## Knowledge Explorer\n": "## 지식 탐색기\n",
        "## What's New in v0.7.0\n": "## v0.7.0의 새로운 기능\n",
        "## What's New in v0.6.8\n": "## v0.6.8의 새로운 기능\n",
        "## Built for High-Stakes Domains\n": "## 고위험 도메인을 위해 구축\n",
        "## Installation\n": "## 설치\n",
        "### CI & Deployment\n": "### CI 및 배포\n",
        "## Enterprise\n": "## 엔터프라이즈\n",
        "## Community & Support\n": "## 커뮤니티 및 지원\n",
        "## Star History\n": "## 스타 히스토리\n",
        "## Contributors\n": "## 기여자\n",
        "## Contributing\n": "## 기여하기\n",
        "## Cite Us\n": "## 인용하기\n",
        "*Knowledge Explorer · Context Graphs · Reasoning Engine · Decision Intelligence · Ontology Hub*\n": "*지식 탐색기 · 컨텍스트 그래프 · 추론 엔진 · 의사결정 인텔리전스 · 온톨로지 허브*\n",
        "**[▶ Watch the full platform walkthrough](https://www.youtube.com/watch?v=QfnNZg4-dZA)**\n": "**[▶ 전체 플랫폼 둘러보기 시청](https://www.youtube.com/watch?v=QfnNZg4-dZA)**\n",
        "**[⭐ Star on GitHub](https://github.com/semantica-agi/semantica)** &nbsp;·&nbsp; **[Join Discord](https://discord.gg/sV34vps5hH)**\n": "**[⭐ GitHub에서 스타 남기기](https://github.com/semantica-agi/semantica)** &nbsp;·&nbsp; **[Discord 참가](https://discord.gg/sV34vps5hH)**\n",
        "**[⭐ Star on GitHub →](https://github.com/semantica-agi/semantica)**\n": "**[⭐ GitHub에서 스타 남기기 →](https://github.com/semantica-agi/semantica)**\n",
        "MIT License · Built by [Semantica](https://github.com/semantica-agi)\n": "MIT 라이선스 · [Semantica](https://github.com/semantica-agi)가 구축\n",
        "If this project helps you build better AI, a star means a lot.\n": "이 프로젝트가 더 나은 AI를 구축하는 데 도움이 된다면, 스타 하나가 큰 의미가 됩니다.\n",
        "If Semantica solves a real problem for you, a star helps others find it.\n": "Semantica가 실제 문제를 해결해 드린다면, 스타를 남겨 다른 사람들이 찾을 수 있도록 도와주세요.\n",
        "**Verify your install in 5 seconds:**\n": "**5초 안에 설치 확인:**\n",
    },
    "es": {
        "### Graph-Native Infrastructure for Context and Accountable AI Systems\n": "### Infraestructura nativa de grafos para sistemas de contexto e IA responsable\n",
        "#### *Developer-first, knowledge infrastructure for AI, alternative to expensive enterprise platforms.*\n": "#### *Primero el desarrollador: infraestructura de conocimiento para IA, alternativa a las costosas plataformas empresariales.*\n",
        "#### Built for High-Stakes, Regulated Domains\n": "#### Construido para dominios regulados de alto riesgo\n",
        "## What Semantica Gives You\n": "## Lo que Semantica te ofrece\n",
        "## Why Semantica\n": "## ¿Por qué Semantica?\n",
        "## Quick Start\n": "## Inicio rápido\n",
        "## Architecture\n": "## Arquitectura\n",
        "## Decision Intelligence\n": "## Inteligencia de Decisiones\n",
        "## Context Graphs\n": "## Grafos de Contexto\n",
        "## Recipe: Audit Trail for a Regulated Decision\n": "## Receta: Pista de auditoría para una decisión regulada\n",
        "## Explore the Platform\n": "## Explora la plataforma\n",
        "## Module Reference\n": "## Referencia de módulos\n",
        "## More Recipes\n": "## Más recetas\n",
        "## Features at a Glance\n": "## Características de un vistazo\n",
        "## Performance\n": "## Rendimiento\n",
        "## CLI\n": "## CLI\n",
        "## Integrations\n": "## Integraciones\n",
        "### Agentic Frameworks\n": "### Frameworks de agentes\n",
        "### MCP Server\n": "### Servidor MCP\n",
        "### REST API\n": "### API REST\n",
        "### Plugin Bundles\n": "### Bundles de plugins\n",
        "## Knowledge Explorer\n": "## Explorador de conocimiento\n",
        "## What's New in v0.7.0\n": "## Novedades en v0.7.0\n",
        "## What's New in v0.6.8\n": "## Novedades en v0.6.8\n",
        "## Built for High-Stakes Domains\n": "## Construido para dominios de alto riesgo\n",
        "## Installation\n": "## Instalación\n",
        "### CI & Deployment\n": "### CI y despliegue\n",
        "## Enterprise\n": "## Empresas\n",
        "## Community & Support\n": "## Comunidad y soporte\n",
        "## Star History\n": "## Historial de estrellas\n",
        "## Contributors\n": "## Colaboradores\n",
        "## Contributing\n": "## Contribuir\n",
        "## Cite Us\n": "## Cítanos\n",
        "*Knowledge Explorer · Context Graphs · Reasoning Engine · Decision Intelligence · Ontology Hub*\n": "*Explorador de conocimiento · Grafos de contexto · Motor de razonamiento · Inteligencia de decisiones · Hub de ontologías*\n",
        "**[▶ Watch the full platform walkthrough](https://www.youtube.com/watch?v=QfnNZg4-dZA)**\n": "**[▶ Ver el recorrido completo de la plataforma](https://www.youtube.com/watch?v=QfnNZg4-dZA)**\n",
        "**[⭐ Star on GitHub](https://github.com/semantica-agi/semantica)** &nbsp;·&nbsp; **[Join Discord](https://discord.gg/sV34vps5hH)**\n": "**[⭐ Dale una estrella en GitHub](https://github.com/semantica-agi/semantica)** &nbsp;·&nbsp; **[Únete a Discord](https://discord.gg/sV34vps5hH)**\n",
        "**[⭐ Star on GitHub →](https://github.com/semantica-agi/semantica)**\n": "**[⭐ Dale una estrella en GitHub →](https://github.com/semantica-agi/semantica)**\n",
        "MIT License · Built by [Semantica](https://github.com/semantica-agi)\n": "Licencia MIT · Construido por [Semantica](https://github.com/semantica-agi)\n",
        "If this project helps you build better AI, a star means a lot.\n": "Si este proyecto te ayuda a construir mejor IA, una estrella significa mucho.\n",
        "If Semantica solves a real problem for you, a star helps others find it.\n": "Si Semantica resuelve un problema real para ti, una estrella ayuda a que otros lo encuentren.\n",
        "**Verify your install in 5 seconds:**\n": "**Verifica tu instalación en 5 segundos:**\n",
    },
    "fr": {
        "### Graph-Native Infrastructure for Context and Accountable AI Systems\n": "### Infrastructure native aux graphes pour les systèmes de contexte et d'IA responsable\n",
        "#### *Developer-first, knowledge infrastructure for AI, alternative to expensive enterprise platforms.*\n": "#### *Orientée développeur, infrastructure de connaissance pour l'IA, alternative aux plateformes d'entreprise coûteuses.*\n",
        "#### Built for High-Stakes, Regulated Domains\n": "#### Conçu pour les domaines à enjeux élevés et réglementés\n",
        "## What Semantica Gives You\n": "## Ce que Semantica vous offre\n",
        "## Why Semantica\n": "## Pourquoi Semantica ?\n",
        "## Quick Start\n": "## Démarrage rapide\n",
        "## Architecture\n": "## Architecture\n",
        "## Decision Intelligence\n": "## Intelligence décisionnelle\n",
        "## Context Graphs\n": "## Graphes de contexte\n",
        "## Recipe: Audit Trail for a Regulated Decision\n": "## Recette : Piste d'audit pour une décision réglementée\n",
        "## Explore the Platform\n": "## Explorer la plateforme\n",
        "## Module Reference\n": "## Référence des modules\n",
        "## More Recipes\n": "## Plus de recettes\n",
        "## Features at a Glance\n": "## Fonctionnalités en un coup d'œil\n",
        "## Performance\n": "## Performance\n",
        "## CLI\n": "## CLI\n",
        "## Integrations\n": "## Intégrations\n",
        "### Agentic Frameworks\n": "### Frameworks agentiques\n",
        "### MCP Server\n": "### Serveur MCP\n",
        "### REST API\n": "### API REST\n",
        "### Plugin Bundles\n": "### Bundles de plugins\n",
        "## Knowledge Explorer\n": "## Explorateur de connaissances\n",
        "## What's New in v0.7.0\n": "## Nouveautés de v0.7.0\n",
        "## What's New in v0.6.8\n": "## Nouveautés de v0.6.8\n",
        "## Built for High-Stakes Domains\n": "## Conçu pour les domaines à enjeux élevés\n",
        "## Installation\n": "## Installation\n",
        "### CI & Deployment\n": "### CI et déploiement\n",
        "## Enterprise\n": "## Entreprise\n",
        "## Community & Support\n": "## Communauté et support\n",
        "## Star History\n": "## Historique des étoiles\n",
        "## Contributors\n": "## Contributeurs\n",
        "## Contributing\n": "## Contribuer\n",
        "## Cite Us\n": "## Nous citer\n",
        "*Knowledge Explorer · Context Graphs · Reasoning Engine · Decision Intelligence · Ontology Hub*\n": "*Explorateur de connaissances · Graphes de contexte · Moteur de raisonnement · Intelligence décisionnelle · Hub d'ontologies*\n",
        "**[▶ Watch the full platform walkthrough](https://www.youtube.com/watch?v=QfnNZg4-dZA)**\n": "**[▶ Voir le parcours complet de la plateforme](https://www.youtube.com/watch?v=QfnNZg4-dZA)**\n",
        "**[⭐ Star on GitHub](https://github.com/semantica-agi/semantica)** &nbsp;·&nbsp; **[Join Discord](https://discord.gg/sV34vps5hH)**\n": "**[⭐ Étoile sur GitHub](https://github.com/semantica-agi/semantica)** &nbsp;·&nbsp; **[Rejoindre Discord](https://discord.gg/sV34vps5hH)**\n",
        "**[⭐ Star on GitHub →](https://github.com/semantica-agi/semantica)**\n": "**[⭐ Étoile sur GitHub →](https://github.com/semantica-agi/semantica)**\n",
        "MIT License · Built by [Semantica](https://github.com/semantica-agi)\n": "Licence MIT · Construit par [Semantica](https://github.com/semantica-agi)\n",
        "If this project helps you build better AI, a star means a lot.\n": "Si ce projet vous aide à construire une meilleure IA, une étoile compte beaucoup.\n",
        "If Semantica solves a real problem for you, a star helps others find it.\n": "Si Semantica résout un vrai problème pour vous, une étoile aide les autres à le trouver.\n",
        "**Verify your install in 5 seconds:**\n": "**Vérifiez votre installation en 5 secondes :**\n",
    },
}


def generate(lang: str, readme_text: str) -> str:
    """Apply line-exact replacements to readme_text for the given language."""
    reps = REPLACEMENTS[lang]
    lines = readme_text.splitlines(keepends=True)
    in_fence = False
    out: list[str] = []
    for line in lines:
        if fence_re.match(line.strip()):
            in_fence = not in_fence
            out.append(line)
            continue
        out.append(line if in_fence else reps.get(line, line))
    result = "".join(out)
    # Replace root-relative nav bar with language-relative paths
    result = NAV_LINE_RE.sub(NAVS[lang], result)
    # Fix internal hrefs: translation files live in docs/i18n/<lang>/, so
    # root-relative hrefs like href="plugins/..." must become ../../../plugins/...
    # and must point to README (not the directory) so docs_check.py resolves them.
    HREF_FIXES = [
        ('href="plugins/.windsurf-plugin/"', 'href="../../../plugins/.windsurf-plugin/README"'),
        ('href="plugins/.cline-plugin/"',    'href="../../../plugins/.cline-plugin/README"'),
        ('href="plugins/.continue-plugin/"', 'href="../../../plugins/.continue-plugin/README"'),
        ('href="plugins/.vscode-plugin/"',   'href="../../../plugins/.vscode-plugin/README"'),
        ('href="integrations/openclaw/"',    'href="../../../integrations/openclaw/README"'),
    ]
    for old, new in HREF_FIXES:
        result = result.replace(old, new)
    return result


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate translation files from README.md.")
    parser.add_argument("--lang", choices=list(REPLACEMENTS), help="Generate only this language.")
    args = parser.parse_args()

    if not README.exists():
        print(f"ERROR: {README} not found", file=sys.stderr)
        sys.exit(1)

    readme_text = README.read_text(encoding="utf-8")
    langs = [args.lang] if args.lang else list(REPLACEMENTS)

    for lang in langs:
        result = generate(lang, readme_text)
        out_path = I18N_DIR / lang / "README.md"
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(result, encoding="utf-8")
        fences = sum(1 for l in result.splitlines() if l.strip().startswith("```"))
        status = "OK" if fences % 2 == 0 else "ODD-FENCES"
        print(f"  {lang}: {len(result.splitlines())} lines, {fences} fences ({status})")

    print(
        "\nDone. Now run:\n"
        "    python scripts/i18n_sync.py --accept\n"
        "to record the new baseline, then commit everything."
    )


if __name__ == "__main__":
    main()
