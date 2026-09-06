# Deploying to Vercel or Netlify

llmwiki produces a plain static site under `site/`. Any static hosting platform can serve it. This guide covers Vercel and Netlify.

## General approach

Both platforms need:

1. A Python runtime to run `llmwiki build`
2. Session data committed to the repo (or seeded from examples)
3. The output directory pointed at `site/`

## Vercel

### Quick setup

1. Push your llm-wiki repo to GitHub/GitLab/Bitbucket.
2. Go to [vercel.com](https://vercel.com), import the repo.
3. Configure the build:

| Setting | Value |
|---|---|
| Framework Preset | Other |
| Build Command | `pip install markdown && python3 -m llmwiki init && python3 -m llmwiki build --out ./site` |
| Output Directory | `site` |
| Install Command | (leave empty) |

4. Deploy.

### vercel.json (optional)

Drop this in the repo root for explicit configuration:

```json
{
  "buildCommand": "pip install markdown && python3 -m llmwiki init && python3 -m llmwiki build --out ./site",
  "outputDirectory": "site",
  "framework": null
}
```

### Python runtime on Vercel

Vercel's build environment includes Python 3. If you need a specific version, add a `runtime.txt`:

```
python-3.12
```

### Seeding session data

If your sessions are not committed, seed from the demo data in the build command:

```
pip install markdown && python3 -m llmwiki init && cp -r examples/demo-sessions/* raw/sessions/ 2>/dev/null; python3 -m llmwiki build --out ./site
```

## Netlify

### Quick setup

1. Push your repo to GitHub/GitLab/Bitbucket.
2. Go to [netlify.com](https://www.netlify.com/), import the repo.
3. Configure the build:

| Setting | Value |
|---|---|
| Build command | `pip install markdown && python3 -m llmwiki init && python3 -m llmwiki build --out ./site` |
| Publish directory | `site` |

4. Deploy.

### netlify.toml

Drop this in the repo root for reproducible configuration:

```toml
[build]
  command = "pip install markdown && python3 -m llmwiki init && python3 -m llmwiki build --out ./site"
  publish = "site"

[build.environment]
  PYTHON_VERSION = "3.12"

# SPA-style fallback for command palette deep links
[[redirects]]
  from = "/*"
  to = "/index.html"
  status = 200
  conditions = {Role = ["admin"]}
```

### Python runtime on Netlify

Set the `PYTHON_VERSION` environment variable in the Netlify dashboard or in `netlify.toml` (shown above). Netlify supports Python 3.8+.

Alternatively, add a `runtime.txt` at the repo root:

```
3.12
```

## Custom domain

Both platforms support custom domains:

### Vercel

1. Go to **Project Settings > Domains**
2. Add your domain
3. Add the DNS records Vercel provides (CNAME or A record)
4. HTTPS is automatic

### Netlify

1. Go to **Site Settings > Domain Management > Add custom domain**
2. Add your domain
3. Add the DNS records Netlify provides
4. HTTPS via Let's Encrypt is automatic

## Troubleshooting

### Build fails with "No module named 'llmwiki'"

Make sure the build command includes `pip install markdown` (not `pip install -e .`, which requires the repo to be a proper Python package). The `python3 -m llmwiki` invocation works from the repo root without a pip install of the package itself, as long as `markdown` is available.

Alternatively, use:

```
pip install -e . && python3 -m llmwiki init && python3 -m llmwiki build --out ./site
```

### Build fails with "no sources found"

Session data needs to be present at build time. Either:
- Commit `raw/sessions/` to the repo
- Seed from `examples/demo-sessions/` in the build command
- Run `llmwiki sync` as part of the build (requires agent session stores, unlikely in CI)

### Site loads but styles are missing

Ensure the output directory setting matches exactly: `site` (not `site/` or `./site/`).

### Slow builds

The build is CPU-bound (markdown rendering). For large session stores (1000+ sessions), builds take 30-60 seconds. This is within Vercel's and Netlify's free-tier build time limits.
