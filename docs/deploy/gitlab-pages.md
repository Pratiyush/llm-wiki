# Deploying to GitLab Pages

Host your llmwiki site on GitLab Pages for free, with automatic builds
on every push to the default branch.

## Quick start

1. Copy the template to your repo root:

```bash
cp .gitlab-ci.yml.example .gitlab-ci.yml
```

2. Enable GitLab Pages for your project:
   - Go to **Settings > Pages**
   - Ensure Pages is enabled (it is by default on gitlab.com)

3. Commit and push:

```bash
git add .gitlab-ci.yml
git commit -m "ci: enable GitLab Pages deployment"
git push
```

4. Your site will be available at:

```
https://<namespace>.gitlab.io/<project>/
```

Where `<namespace>` is your GitLab username or group, and `<project>`
is the repository name.

## How it works

The pipeline has three stages:

| Stage | What it does |
|---|---|
| `build_site` | Installs llmwiki, runs `llmwiki build`, moves output to `public/` |
| `privacy_check` | Greps build output for PII patterns (usernames, API keys) |
| `pages` | Deploys `public/` to GitLab Pages (default branch only) |

The `privacy_check` stage runs the same pattern matching as the GitHub
Actions workflow to prevent accidental PII leaks. Customize the regex
patterns in the `grep -rE` line to match your setup.

## Configuration

### CI/CD variables

No secrets or CI variables are required. GitLab Pages deployment uses
the built-in `pages` job which requires no authentication.

### Custom domain

To use a custom domain instead of `*.gitlab.io`:

1. Go to **Settings > Pages > New Domain**
2. Add your domain and verify DNS
3. GitLab will provision a TLS certificate automatically

### Private projects

GitLab Pages on private projects are accessible only to project members
by default. To make the site public:

1. Go to **Settings > General > Visibility**
2. Under "Pages", select "Everyone" or "Everyone with access"

### Python version

The template uses `python:3.12-slim`. To use a different version, change
the `image` field in the `build_site` job.

## Differences from GitHub Pages

| Feature | GitHub Pages | GitLab Pages |
|---|---|---|
| Workflow file | `.github/workflows/pages.yml` | `.gitlab-ci.yml` |
| Output directory | Configured via action | Must be `public/` |
| Branch restriction | Configurable | Uses `rules:` in CI |
| Custom domain | Settings > Pages | Settings > Pages > New Domain |
| HTTPS | Automatic | Automatic |
| Private site | GitHub Pro required | Available on free tier |

## Troubleshooting

**Pipeline passes but site not visible:**
- Check that the `pages` job ran (not just `build_site`)
- Verify Pages is enabled in Settings > Pages
- Wait 5-10 minutes for DNS propagation on first deploy

**Privacy check fails:**
- The `privacy_check` stage found potential PII in the build output
- Check your `config.json` redaction rules
- Run `llmwiki build` locally and grep for the flagged patterns

**Build fails with "no sources found":**
- Run `llmwiki init` and `llmwiki sync` locally first
- Commit the `raw/sessions/` directory (or configure the CI to run sync)
