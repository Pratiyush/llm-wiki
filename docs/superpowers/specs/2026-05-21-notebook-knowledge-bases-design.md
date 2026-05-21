# Notebook Knowledge Bases Design

## Status

Approved design direction from user discussion on 2026-05-21.

## Goal

Extend the current enterprise internal-control Q&A system into a notebook-based knowledge platform. The existing enterprise management content becomes the default notebook named "企业管理制度". Admin users can create additional private notebooks, such as "人工智能", upload PDF, Word, Markdown, or text materials into them, generate wiki pages and graphs, and ask questions strictly grounded in the selected notebook's uploaded knowledge.

The intended product behavior is similar to NotebookLM, but built on top of the existing llmwiki wiki, graph, upload, and Q&A capabilities.

## Decisions

- Notebooks are first-class knowledge-base boundaries.
- Each notebook has an independent directory tree with its own raw files, wiki pages, and graph data.
- Normal operation is notebook-isolated. Q&A, search, wiki browsing, graph browsing, and saved syntheses use only the selected notebook.
- Admin users may explicitly enable cross-notebook search. Cross-notebook answers must identify which notebook each source came from.
- Non-admin users can only see and use the default "企业管理制度" notebook.
- Admin-created notebooks are private in the first version.
- The data model reserves a `visibility` field for future publishing or sharing, but the first version does not expose publish controls.
- The existing enterprise internal-control content will be migrated into `notebooks/enterprise-management/`.
- The first notebook version targets the Web UI. Full CLI, MCP, static-site, and export support can follow later.

## Directory Model

Each notebook owns its own data tree:

```text
notebooks/
  enterprise-management/
    notebook.json
    raw/
      company-docs/
      uploads/
    wiki/
      index.md
      overview.md
      log.md
      sources/
      entities/
      concepts/
      syntheses/
    graph/
      graph.json
  ai/
    notebook.json
    raw/
      uploads/
    wiki/
      index.md
      overview.md
      log.md
      sources/
      entities/
      concepts/
      syntheses/
    graph/
      graph.json
```

`notebook.json` stores lightweight metadata for portability:

```json
{
  "slug": "enterprise-management",
  "name": "企业管理制度",
  "description": "企业内控制度、合同采购、工程签证、造价咨询、预结算等制度知识库",
  "visibility": "public",
  "is_default": true
}
```

The database remains authoritative for permissions and ownership. `notebook.json` is a filesystem companion for inspection, backups, and future portability.

## Database Model

Add a `Notebook` table:

```text
id
slug
name
description
owner_id
visibility      # private / public; first version uses private for admin notebooks
is_default
created_at
updated_at
```

Add `notebook_id` to existing scoped tables:

- `UploadedFile`
- `KnowledgeLineage`
- `Conversation`
- `ChatHistory`
- `PendingWiki`
- `OutdatedFlag`

Migration behavior:

- Create the default notebook row if it does not exist.
- Backfill existing records with the default notebook id.
- Keep old rows usable so existing enterprise-management chat history remains visible under the default notebook.

## Access Rules

Notebook access is enforced in the backend, not only hidden in the frontend.

Rules:

- Anonymous or unauthenticated use should resolve to the default notebook only, if the current route allows anonymous access.
- Non-admin authenticated users only receive and access the default notebook.
- Admin users receive the default notebook plus notebooks they own.
- Admin-created notebooks default to `visibility = private`.
- If a non-admin requests any private notebook slug, the API returns 403.
- Unknown notebook slugs return 404.
- Invalid notebook slugs are rejected before path resolution.

Slug constraints:

- Lowercase ASCII.
- Allowed characters: `a-z`, `0-9`, `-`.
- Must not contain path separators, dot segments, or URL-encoded traversal.

## Backend Architecture

Create a notebook service responsible for all notebook resolution:

- Validate notebook slugs.
- Resolve default notebook.
- Resolve current user's accessible notebooks.
- Resolve filesystem roots:
  - `notebook_root`
  - `raw_dir`
  - `wiki_dir`
  - `graph_dir`
- Create notebook directory skeletons.
- Create or read `notebook.json`.
- Reject unauthorized access.

Existing Web services and routes must stop reading global `REPO_ROOT / "wiki"` directly. They should accept a notebook context or resolved `wiki_dir`.

Affected areas:

- `llmwiki/web/services/wiki_reader.py`
- `llmwiki/web/services/ingester.py`
- `llmwiki/web/services/glm_client.py`
- `llmwiki/web/routes/pages.py`
- `llmwiki/web/routes/query.py`
- `llmwiki/web/routes/upload.py`
- `llmwiki/web/routes/graph.py`
- `llmwiki/web/routes/manage.py`
- `llmwiki/graph.py`

The graph module should accept `wiki_dir` and `graph_dir` parameters so notebooks do not share graph state.

## Upload Flow

Admin uploads into the currently selected notebook:

1. Frontend sends `notebook_slug` with the upload request.
2. Backend resolves and authorizes that notebook.
3. Original file is saved under:

```text
notebooks/<slug>/raw/uploads/<safe-filename>
```

4. The document converter extracts Markdown.
5. Source page is written under:

```text
notebooks/<slug>/wiki/sources/<source-slug>.md
```

6. LLM extraction creates or updates entity and concept pages in that same notebook:

```text
notebooks/<slug>/wiki/entities/*.md
notebooks/<slug>/wiki/concepts/*.md
```

7. The notebook's `index.md`, `overview.md`, `log.md`, and graph are updated.
8. `UploadedFile` and `KnowledgeLineage` rows include `notebook_id`.

Non-admin upload behavior remains restricted to the default notebook unless a later permission design allows more.

## Q&A Flow

Default Q&A:

- Frontend includes current `notebook_slug`.
- Backend resolves the notebook for the current user.
- Context building searches only `notebooks/<slug>/wiki/`.
- Tool-calling search and read operations are bound to that same `wiki_dir`.
- Saved syntheses are written to:

```text
notebooks/<slug>/wiki/syntheses/<slug>.md
```

Cross-notebook search:

- Admin only.
- Must be explicitly enabled in the request.
- Searches only notebooks the admin may access.
- Context sections include notebook name and page path.
- The final answer should identify source notebook names in citations or source labels.

Conversation history:

- `Conversation` and `ChatHistory` rows include `notebook_id`.
- Thread lists are scoped to the selected notebook.
- A user switching notebooks should see different chat histories.

## Frontend Design

Normal users:

- No notebook switcher.
- No notebook management UI.
- Default experience remains the current "企业管理制度" Q&A, wiki, upload, graph, and management surface as permitted by role.
- Attempts to access private notebooks are rejected and redirected to the default notebook.

Admin users:

- Top navigation adds a notebook selector:

```text
当前知识库：企业管理制度 v
```

- The selector lists:
  - 企业管理制度
  - Admin-created private notebooks
- Current notebook selection controls:
  - Wiki tree
  - Q&A
  - Upload destination
  - Graph
  - File and wiki management lists
- Management page adds a Notebook Management section:
  - Create notebook
  - Edit name and description
  - Archive or delete empty notebook
  - View page, file, and update counts

Notebook creation fields:

- Name, for example `人工智能`.
- Slug, auto-generated from name but editable.
- Description, optional.

Deletion policy:

- First version only allows deleting empty notebooks.
- Non-empty notebooks can be archived or hidden from the selector.
- The default notebook cannot be deleted.

Q&A page:

- Admin sees a "跨知识库搜索" checkbox.
- It is off by default.
- Non-admin users do not see it.

## Migration Design

Target migration:

```text
raw/company-docs/        -> notebooks/enterprise-management/raw/company-docs/
wiki/                    -> notebooks/enterprise-management/wiki/
graph/                   -> notebooks/enterprise-management/graph/
```

Migration should be explicit, with dry-run support:

```bash
llmwiki notebooks migrate-default --dry-run
llmwiki notebooks migrate-default
```

Behavior:

- Create default `Notebook` row.
- Create `notebooks/enterprise-management/`.
- Copy existing enterprise files into the default notebook tree.
- Do not silently overwrite existing notebook files.
- Backfill existing database rows with default `notebook_id`.
- Write `notebook.json`.
- Print a migration summary.

Compatibility:

- Web UI should not mix old global `wiki/` with notebook `wiki/`.
- If the default notebook wiki does not exist but old global `wiki/` exists, admin routes should show a migration-required message.
- Old global files should not be deleted automatically in the first version.

## Necessary Project Fixes

The notebook work depends on several existing project issues being fixed or contained.

Must fix in the notebook implementation:

- Replace global `wiki/` hardcoding in Web services and graph code with notebook-scoped roots.
- Add `notebook_id` to scoped database records.
- Enforce notebook permissions in backend routes.
- Bind upload, search, graph, Q&A, saved syntheses, and chat history to the selected notebook.
- Migrate the existing enterprise content into the default notebook.
- Fix mojibake Chinese UI and backend strings that currently display as corrupted text.

Should fix with the same release if possible:

- Add runtime files to `.gitignore`, including `llmwiki.db`, `.jwt_secret`, and `.env`.
- Update docs to distinguish the original static llmwiki mode from the current Web notebook mode.
- Keep Web notebook scope separate from first-version CLI/MCP/static export scope.

Can defer:

- Per-notebook static site generation.
- Per-notebook MCP tools.
- Publishing private admin notebooks to normal users.
- Department-level or role-level notebook sharing.

## Testing Plan

Backend tests:

- Default notebook creation.
- Slug validation.
- Admin can access own private notebooks.
- Normal users only access the default notebook.
- Unauthorized notebook access returns 403.
- Missing notebook returns 404.
- `wiki_reader` reads tree, list, page, and search results from the selected notebook only.
- Graph generation accepts notebook paths and does not merge notebooks.
- Upload writes raw and wiki files under the selected notebook.
- Q&A context builder only uses the selected notebook by default.
- Cross-notebook search only works for admin and only includes accessible notebooks.
- Database migration backfills `notebook_id`.

Permission tests:

- `/api/notebooks` returns only the default notebook for normal users.
- Normal users cannot request private notebook pages, graph, upload, or Q&A.
- Admin can create, switch to, upload into, and query a private notebook.

Manual acceptance:

1. Normal user opens the system and sees only "企业管理制度".
2. Normal user cannot see a notebook switcher.
3. Admin creates an "人工智能" notebook.
4. Admin uploads an AI-related document.
5. The AI notebook shows source, entity, and concept wiki pages.
6. The AI notebook graph only displays AI notebook content.
7. Asking inside the AI notebook uses only AI notebook content.
8. Switching back to "企业管理制度" hides AI notebook content from search, graph, and Q&A.
9. Admin enables cross-notebook search and receives answers with source notebook labels.
10. Chinese UI and backend messages render correctly.

## Out of Scope for First Version

- Letting normal users create notebooks.
- Letting normal users see admin private notebooks.
- Publishing or sharing notebooks.
- Department-level notebook ACLs.
- Per-notebook static site build/export parity.
- Per-notebook MCP parity.
- Full rewrite of the original open-source llmwiki documentation.

## Open Follow-Up

After this design is accepted, the implementation plan should split the work into small tasks:

1. Notebook model and service.
2. Migration command.
3. Scoped wiki reader and graph.
4. Scoped upload and ingester.
5. Scoped Q&A and chat history.
6. Notebook API and frontend selector.
7. Admin notebook management UI.
8. Permission tests and regression tests.
9. Mojibake cleanup and docs updates.
