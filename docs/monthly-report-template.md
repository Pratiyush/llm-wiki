# Monthly Project Health Report Template

Copy this template at the start of each month. Fill in the numbers from
GitHub Insights, the issue tracker, and PyPI stats.

---

## llmwiki Monthly Report -- YYYY-MM

**Reporting period:** YYYY-MM-01 to YYYY-MM-DD
**Prepared by:** ___

### Adoption

| Metric | This month | Last month | Delta |
|---|---|---|---|
| GitHub stars | ___ | ___ | +___ |
| GitHub forks | ___ | ___ | +___ |
| Unique cloners | ___ | ___ | ___ |
| Unique visitors | ___ | ___ | ___ |
| PyPI downloads (monthly) | ___ | ___ | +___ |
| npm/Homebrew installs | ___ | ___ | +___ |

**Data sources:**
- Stars/forks: GitHub repo page
- Cloners/visitors: GitHub Insights > Traffic
- PyPI downloads: [pepy.tech/projects/llmwiki](https://pepy.tech/projects/llmwiki)

### Issues

| Metric | Count |
|---|---|
| Issues opened | ___ |
| Issues closed | ___ |
| Open issues (end of month) | ___ |
| Oldest open issue (age in days) | ___ |
| Bugs opened | ___ |
| Bugs closed | ___ |
| Feature requests opened | ___ |

**Top 3 issues by upvotes:**
1. #___ -- ___
2. #___ -- ___
3. #___ -- ___

### Pull requests

| Metric | Count |
|---|---|
| PRs opened | ___ |
| PRs merged | ___ |
| PRs closed (not merged) | ___ |
| Open PRs (end of month) | ___ |
| Average time to merge (days) | ___ |

### Contributors

| Metric | Count |
|---|---|
| Total contributors (all time) | ___ |
| New contributors this month | ___ |
| Commits to main | ___ |

**New contributors:**
- @___ -- PR #___ (description)
- @___ -- PR #___ (description)

### Releases

| Version | Date | Highlights |
|---|---|---|
| v___ | YYYY-MM-DD | ___ |

### Test suite

| Metric | Value |
|---|---|
| Total tests | ___ |
| Tests added this month | ___ |
| Test pass rate | ___% |
| E2E scenarios | ___ |
| Build time (CI) | ___ s |

### Demo site

| Metric | Value |
|---|---|
| Uptime (%) | ___ |
| Lighthouse score (avg) | ___ |
| Pages deployed | ___ |
| Unique visitors (site analytics) | ___ |

### Top feature requests

Ranked by upvotes on open issues:

1. ___ (__ upvotes)
2. ___ (__ upvotes)
3. ___ (__ upvotes)
4. ___ (__ upvotes)
5. ___ (__ upvotes)

### Next month priorities

1. ___
2. ___
3. ___

### Retrospective notes

**What went well:**
- ___

**What could improve:**
- ___

**Risks / blockers:**
- ___

---

## How to fill this out

1. **GitHub Insights:** repo page > Insights > Traffic, Contributors,
   Community
2. **Issues/PRs:** use `gh` CLI:
   ```bash
   # Issues opened this month
   gh issue list --state all --search "created:2026-MM-01..2026-MM-31" | wc -l

   # PRs merged this month
   gh pr list --state merged --search "merged:2026-MM-01..2026-MM-31" | wc -l

   # New contributors
   gh pr list --state merged --search "merged:2026-MM-01..2026-MM-31" \
     --json author --jq '.[].author.login' | sort -u
   ```
3. **PyPI downloads:** [pepy.tech](https://pepy.tech/projects/llmwiki)
   or `pip install pypistats && pypistats overall llmwiki --last-month`
4. **Lighthouse:** run `npx lighthouse https://pratiyush.github.io/llm-wiki/ --output=json`
   or check the Chrome DevTools Lighthouse tab
5. **Stars:** `gh api repos/Pratiyush/llm-wiki --jq '.stargazers_count'`

## Where to publish

- **GitHub Discussions:** create a "Monthly Reports" category for
  public transparency
- **Internal doc:** if the project has private stakeholders
- **Blog post:** quarterly or on major milestones (100 stars, v1.0,
  first external contributor)
