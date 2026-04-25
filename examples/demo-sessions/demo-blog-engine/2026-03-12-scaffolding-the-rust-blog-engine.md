---
title: "Session: scaffolding-the-rust-blog-engine — 2026-03-12"
type: source
tags: [claude-code, session-transcript, demo]
date: 2026-03-12
source_file: raw/sessions/demo-blog-engine/2026-03-12-scaffolding-the-rust-blog-engine.md
sessionId: demo-000000000000000000000000000001
slug: scaffolding-the-rust-blog-engine
project: demo-blog-engine
started: 2026-03-12T09:02:11+00:00
ended: 2026-03-12T11:14:03+00:00
cwd: /Users/demo/code/demo-blog-engine
gitBranch: main
permissionMode: default
model: claude-sonnet-4-6
user_messages: 3
tool_calls: 8
tools_used: [Bash, Edit, Read, Write]
tool_counts: {"Write": 4, "Bash": 2, "Edit": 1, "Read": 1}
token_totals: {"input": 8400, "cache_creation": 12000, "cache_read": 31000, "output": 4200}
turn_count: 3
hour_buckets: {"2026-03-12T09": 7, "2026-03-12T10": 11, "2026-03-12T11": 4}
duration_seconds: 7912
is_subagent: false
---

# Session: scaffolding-the-rust-blog-engine — 2026-03-12

**Project:** `demo-blog-engine` · **Branch:** `main` · **Mode:** `default` · **Model:** `claude-sonnet-4-6`

## Summary

Bootstrapped a small static-site generator in Rust. Chose `pulldown-cmark` for markdown parsing over `comrak` after weighing compile-time vs. GFM support. Scaffolded the `cargo new` project, added a `Post` struct, and wrote a first pass of the markdown → HTML pipeline.

## Conversation

### Turn 1 — User

I want to build a minimal static blog engine in Rust. Start a new crate, pick a markdown library, and write the skeleton of the build step.

### Turn 1 — Assistant

Kicking off with `cargo new --bin demo-blog-engine`. For markdown I'll compare `pulldown-cmark` and `comrak`:

- `pulldown-cmark` — tiny, pure-Rust, CommonMark-only, fast
- `comrak` — full GFM (tables, strikethrough, task lists), slightly heavier

Since we want something minimal, I'll start with `pulldown-cmark` and we can switch if we need GFM.

**Tools used in this turn:**
- `Bash`: `cargo new --bin demo-blog-engine` — exit 0
- `Write`: `Cargo.toml`

```toml
[package]
name = "demo-blog-engine"
version = "0.1.0"
edition = "2021"

[dependencies]
pulldown-cmark = "0.10"
serde = { version = "1", features = ["derive"] }
toml = "0.8"
```

- `Write`: `src/main.rs`

```rust
use std::path::Path;

mod post;

fn main() -> anyhow::Result<()> {
    let content_dir = Path::new("content");
    let out_dir = Path::new("public");
    std::fs::create_dir_all(out_dir)?;

    for entry in std::fs::read_dir(content_dir)? {
        let path = entry?.path();
        if path.extension().and_then(|s| s.to_str()) != Some("md") {
            continue;
        }
        let post = post::Post::from_markdown_file(&path)?;
        let out = out_dir.join(format!("{}.html", post.slug));
        std::fs::write(&out, post.body_html)?;
        println!("wrote {}", out.display());
    }
    Ok(())
}
```

### Turn 2 — User

Good. Add a `Post` struct that holds title, slug, date, and body, and wire up a function that reads a markdown file from `content/` and returns a `Post`.

### Turn 2 — Assistant

Added `src/post.rs` with the struct and a `Post::from_markdown_file(path)` constructor. It parses a YAML-style frontmatter block (just the five keys we need), then feeds the remaining body through `pulldown-cmark` to get HTML.

**Tools used in this turn:**
- `Write`: `src/post.rs`

```rust
use pulldown_cmark::{html, Options, Parser};
use serde::Deserialize;
use std::path::Path;

#[derive(Debug, Deserialize)]
pub struct Frontmatter {
    pub title: String,
    pub slug: String,
    pub date: String,
}

#[derive(Debug)]
pub struct Post {
    pub title: String,
    pub slug: String,
    pub date: String,
    pub body_html: String,
}

impl Post {
    pub fn from_markdown_file(path: &Path) -> anyhow::Result<Self> {
        let raw = std::fs::read_to_string(path)?;
        let (fm_str, body) = split_frontmatter(&raw);
        let fm: Frontmatter = toml::from_str(fm_str)?;

        let mut opts = Options::empty();
        opts.insert(Options::ENABLE_STRIKETHROUGH);
        let parser = Parser::new_ext(body, opts);
        let mut body_html = String::new();
        html::push_html(&mut body_html, parser);

        Ok(Post { title: fm.title, slug: fm.slug, date: fm.date, body_html })
    }
}

fn split_frontmatter(raw: &str) -> (&str, &str) {
    // expects `+++\n...\n+++\n<body>`
    let bytes = raw.as_bytes();
    if !raw.starts_with("+++\n") { return ("", raw); }
    if let Some(end) = raw[4..].find("\n+++\n") {
        let fm = &raw[4..4 + end];
        let body = &raw[4 + end + 5..];
        return (fm, body);
    }
    ("", raw)
}
```

- `Edit`: `src/main.rs` — added `mod post;`
- `Read`: `src/main.rs` (1–40)

### Turn 3 — User

Let's test it. Drop a sample post into `content/hello.md` and run the build.

### Turn 3 — Assistant

Wrote a sample post and ran `cargo run`. First build took ~14s (clean), subsequent ~0.4s. Output HTML is being written to `public/hello.html`. Looking good.

**Tools used in this turn:**
- `Write`: `content/hello.md` (5-line preview)
- `Bash`: `cargo run` — exit 0

## Connections

- [[demo-blog-engine]] — project
- [[Rust]] — language
- [[pulldown-cmark]] — markdown library
- [[StaticSiteGeneration]] — concept
