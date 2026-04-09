# はじめに (Getting started)

> 日本語翻訳 — 英語のマスター版 [`docs/getting-started.md`](../../getting-started.md) を正本とします
> 最終同期: v0.3.0 (2026-04-08)
> **v0.3 ドラフト** — この翻訳は初版で、英語の最新版よりも遅れている可能性があります。

5 分間のクイックスタート。終われば、実行したすべての Claude Code セッションが閲覧可能な Wiki として手に入ります。

## 前提条件

- Python ≥ 3.9（macOS には 3.9+ がデフォルトで搭載されています。多くの Linux ディストリビューションでも同様）
- `git`
- 既に Agent のデフォルトのセッションストアに保存された Claude Code または Codex CLI のセッションがあること

これだけです。`npm` も `brew` もデータベースもアカウントも不要です。

## インストール

### macOS / Linux

```bash
git clone https://github.com/Pratiyush/llm-wiki.git
cd llm-wiki
./setup.sh
```

### Windows

```cmd
git clone https://github.com/Pratiyush/llm-wiki.git
cd llm-wiki
setup.bat
```

`setup.sh` / `setup.bat` は次の手順を冪等に実行します:

1. `pip install --user` で `markdown`（必須）をインストール。シンタックスハイライトは CDN 経由の highlight.js を使用。
2. `raw/`、`wiki/`、`site/` ディレクトリを作成
3. `llmwiki adapters` を実行して検出された Agent を表示
4. 最初の同期の dry-run を実行し、何が変換されるかをプレビュー

## インストール後の 3 つのコマンド

```bash
./sync.sh        # Agent ストアから新しいセッションを取得 → raw/sessions/<project>/*.md
./build.sh       # raw/ + wiki/ を site/ にコンパイル
./serve.sh       # http://127.0.0.1:8765/ でローカルサーバーを起動
```

[http://127.0.0.1:8765/](http://127.0.0.1:8765/) を開いて試してみましょう:

- **⌘K** または **Ctrl+K** — コマンドパレット
- **/** — 検索バーにフォーカス
- **g h / g p / g s** — ホーム / プロジェクト / セッションへジャンプ
- **j / k** — セッションテーブルをナビゲート
- **?** — キーボードショートカットのヘルプ

## 次のステップ

- [アーキテクチャ (Architecture)](../../architecture.md) — Karpathy 3 層 + 8 層ビルドの内訳
- [設定 (Configuration)](../../configuration.md) — すべての調整可能な設定
- [プライバシー (Privacy)](../../privacy.md) — デフォルトの匿名化 + `.llmwikiignore` + ローカルホスト限定
- [Claude Code アダプター](../../adapters/claude-code.md)
- [Obsidian アダプター](../../adapters/obsidian.md)
