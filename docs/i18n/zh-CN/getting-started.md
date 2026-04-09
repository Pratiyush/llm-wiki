# 快速开始 (Getting started)

> 中文 (简体) 翻译 — 以英文主文档 [`docs/getting-started.md`](../../getting-started.md) 为准
> 上次同步：v0.3.0 (2026-04-08)
> **v0.3 初稿** — 本翻译为初版，可能落后于英文主文档。

5 分钟快速上手。完成后，你将拥有一个可浏览的 Wiki，包含你运行过的所有 Claude Code 会话。

## 前置要求

- Python ≥ 3.9（macOS 默认自带 3.9+；大多数 Linux 发行版也是）
- `git`
- 已有若干 Claude Code 或 Codex CLI 会话保存在 Agent 默认的会话存储目录

就这些。无需 `npm`、无需 `brew`、无需数据库、无需账号。

## 安装

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

`setup.sh` / `setup.bat` 会以幂等的方式完成以下步骤：

1. 通过 `pip install --user` 安装 `markdown`（必需）。语法高亮使用 highlight.js（通过 CDN 加载）。
2. 创建 `raw/`、`wiki/`、`site/` 目录结构
3. 运行 `llmwiki adapters` 显示检测到的 Agent
4. 首次同步的 dry-run 预览，你可以看到将要转换哪些内容

## 安装后的三个命令

```bash
./sync.sh        # 从 Agent 存储中拉取新会话 → raw/sessions/<project>/*.md
./build.sh       # 将 raw/ + wiki/ 编译为 site/
./serve.sh       # 在 http://127.0.0.1:8765/ 启动本地服务器
```

打开 [http://127.0.0.1:8765/](http://127.0.0.1:8765/) 并尝试：

- **⌘K** 或 **Ctrl+K** — 命令面板
- **/** — 聚焦搜索栏
- **g h / g p / g s** — 跳转到首页 / 项目 / 会话
- **j / k** — 浏览会话表
- **?** — 键盘快捷键帮助

## 下一步

- [架构 (Architecture)](../../architecture.md) — Karpathy 三层 + 8 层构建拆解
- [配置 (Configuration)](../../configuration.md) — 所有可调整的开关
- [隐私 (Privacy)](../../privacy.md) — 默认脱敏 + `.llmwikiignore` + 仅本机绑定
- [Claude Code 适配器](../../adapters/claude-code.md)
- [Obsidian 适配器](../../adapters/obsidian.md)
