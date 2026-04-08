---
title: "Session: adding-oauth-login — 2026-02-15"
type: source
tags: [claude-code, session-transcript, demo]
date: 2026-02-15
source_file: raw/sessions/demo-todo-api/2026-02-15-adding-oauth-login.md
sessionId: demo-000000000000000000000000000012
slug: adding-oauth-login
project: demo-todo-api
started: 2026-02-15T13:00:00+00:00
ended: 2026-02-15T15:40:00+00:00
cwd: /Users/demo/code/demo-todo-api
gitBranch: feat/oauth
permissionMode: default
model: claude-sonnet-4-6
user_messages: 8
tool_calls: 22
tools_used: [Read, Write, Edit, Bash, WebFetch, Grep]
tool_counts: {"Edit": 8, "Read": 6, "Write": 3, "Bash": 3, "WebFetch": 1, "Grep": 1}
token_totals: {"input": 12000, "cache_creation": 18000, "cache_read": 45000, "output": 5600}
turn_count: 8
hour_buckets: {"2026-02-15T13": 8, "2026-02-15T14": 10, "2026-02-15T15": 4}
duration_seconds: 9600
is_subagent: false
---

# Session: adding-oauth-login — 2026-02-15

**Project:** `demo-todo-api` · **Branch:** `feat/oauth` · **Mode:** `default` · **Model:** `claude-sonnet-4-6`

## Summary

Added GitHub OAuth login via `authlib`. Sessions are cookie-backed, signed with `itsdangerous`. Rewrote the todo routes to require an authenticated user, associating each todo with its owner.

## Conversation

### Turn 1 — User

Add GitHub OAuth. Each todo should belong to a user.

### Turn 1 — Assistant

Plan:

1. Add `authlib` + `itsdangerous` deps
2. New `app/auth.py` with the OAuth client setup
3. Two routes: `/auth/login` (redirect) and `/auth/callback`
4. Signed-cookie session middleware
5. Add a `user_id` column to `Todo`, make it an FK to `User`
6. Gate every `/todos` route behind `Depends(current_user)`

### Turn 2 — User

Do it.

### Turn 2 — Assistant

All wired up. Migration is an Alembic revision (`0002_add_user_table`). Tests updated to seed a fake user and include the session cookie. 12 tests pass.

**Tools used in this turn:**
- `Write`: `app/auth.py` (5-line preview)
- `Edit`: `app/models.py` — added `User` + FK
- `Edit`: `app/routes/todos.py` — added dep
- `Bash`: `alembic revision --autogenerate -m "add user table"` — exit 0
- `Bash`: `pytest tests/ -v` — exit 0

## Connections

- [[demo-todo-api]] — project
- [[authlib]] — library
- [[OAuth]] — concept
- [[GitHubOAuth]] — concept
