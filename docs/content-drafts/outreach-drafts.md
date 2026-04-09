# Outreach Drafts and Templates

Ready-to-send emails, pitches, and operational guides for llm-wiki outreach.

**Project:** llm-wiki -- open-source Python CLI that converts AI coding session transcripts into a searchable static wiki
**GitHub:** https://github.com/Pratiyush/llm-wiki
**Demo:** https://pratiyush.github.io/llm-wiki/
**License:** MIT
**Karpathy spec:** https://gist.github.com/karpathy/442a6bf555914893e9891c11519de94f

---

## Email to Andrej Karpathy (#101)

**Subject:** Open-source implementation of your LLM Wiki spec -- llm-wiki

**Body:**

Hi Andrej,

I built an open-source implementation of your LLM Wiki gist. It follows your three-layer architecture (raw, wiki, site) and converts session transcripts from AI coding assistants into a searchable, interlinked knowledge base.

The core matches your spec. Where it extends beyond it:

- **8 agent adapters** -- Claude Code, Copilot, Cursor, Codex CLI, Gemini CLI, Aider, Windsurf, and Obsidian. Pluggable pattern: one ~50-line file per agent.
- **Pure-SVG visualizations** -- 365-day activity heatmap, tool-calling bar charts, token usage cards, pricing sparklines. No JavaScript charting library. CSS custom properties for dark mode.
- **Model directory** -- structured model profiles with benchmarks, auto-generated comparison pages, and an append-only changelog timeline.
- **AI-consumable exports** -- every page ships as .html, .txt, and .json. Site-level llms.txt, JSON-LD, sitemap, RSS.
- **MCP server** -- 7 tools so Claude Desktop, Cursor, or any MCP client can query the wiki programmatically.

Live demo (rebuilds on every push): https://pratiyush.github.io/llm-wiki/
GitHub: https://github.com/Pratiyush/llm-wiki

It is stdlib-only Python (one dep: `markdown`), MIT licensed, 472 tests. Setup is `git clone` + `./setup.sh` + `./build.sh`.

Thank you for publishing the spec. It was an excellent blueprint to build against.

Best,
[Your name]

---

## Anthropic DevRel Pitch (#102)

**Subject:** llm-wiki -- open-source project showcasing Claude Code session transcripts

**To:** Anthropic Developer Relations / Community team

**Body:**

Hi,

I am reaching out about llm-wiki, an open-source Python tool that converts Claude Code session transcripts into a searchable knowledge base. I think it could be a good fit for Anthropic's developer blog, community showcase, or Claude Code documentation.

**Why it is relevant to Anthropic:**

1. **Claude Code is the primary adapter.** The project was built around Claude Code's `.jsonl` transcript format. The `claude_code.py` adapter reads from `~/.claude/projects/`, parses conversation turns, extracts tool usage, and preserves the full session context including model, git branch, and token counts.

2. **It demonstrates the value of session transcripts.** Claude Code writes rich structured data to disk. llm-wiki shows what becomes possible when you treat that data as a first-class knowledge source: cross-project search, activity heatmaps, tool usage analytics, model comparison.

3. **MCP integration.** The project ships an MCP server with 7 tools, making the generated wiki queryable from Claude Desktop, Cursor, or any MCP client. This is a concrete example of the MCP protocol in practice.

4. **Dual-format output.** Every page ships as HTML for humans and as .txt/.json for LLMs. The site generates llms.txt and JSON-LD at the root. This aligns with the "AI-consumable web" direction.

**By the numbers:**

- 8 agent adapters (Claude Code, Copilot, Cursor, Codex CLI, Gemini CLI, Aider, Windsurf, Obsidian)
- 472 tests (unit + Playwright E2E with 62 Gherkin scenarios)
- Stdlib-only Python, one runtime dep (`markdown`), no npm, no database
- Pure-SVG visualizations, no JavaScript charting library
- MIT license, works offline, privacy-first with automatic redaction

**Links:**
- GitHub: https://github.com/Pratiyush/llm-wiki
- Live demo: https://pratiyush.github.io/llm-wiki/
- Based on: Andrej Karpathy's LLM Wiki spec

I would be glad to write a guest blog post, do a walkthrough, or provide anything else that would be useful.

Best,
[Your name]

---

## tobi (qmd author) Collaboration Note (#103)

**Subject:** llm-wiki already exports to qmd -- interested in collaborating?

**Body:**

Hi tobi,

I maintain llm-wiki, an open-source tool that converts AI coding session transcripts into a static knowledge base. While building out export formats, I added qmd (Quarto markdown) as a first-class output target.

The integration is already working: each session page can be exported as a `.qmd` file with YAML frontmatter that Quarto understands, so users can pipe their AI session archive straight into a Quarto site for academic-style rendering, PDF export, or integration with R/Python notebooks.

I thought you might be interested since qmd is your format. A few ways we could collaborate:

- **Review the qmd output.** If the frontmatter or body structure could be improved for Quarto compatibility, I would like to know.
- **Cross-link projects.** If it makes sense, a mention in Quarto's ecosystem page or a link from our docs to Quarto as a downstream consumer.
- **Joint example.** A tutorial showing "AI coding session -> llm-wiki -> Quarto site -> PDF report" could be useful to both communities.

Project: https://github.com/Pratiyush/llm-wiki
Demo: https://pratiyush.github.io/llm-wiki/

Happy to jump on a call or keep it async -- whatever works for you.

Best,
[Your name]

---

## Podcast Pitch -- Talk Python / Python Bytes (#104)

**Subject:** Pitch: stdlib-only Python project that turns AI coding sessions into a wiki

**Body:**

Hi Michael [Kennedy] / Brian [Okken],

I have a project that I think fits the show well. It is a pure-Python story with some unusual technical choices.

**llm-wiki** is an open-source CLI that converts AI coding session transcripts (Claude Code, Copilot, Cursor, Codex CLI, Gemini CLI) into a searchable static knowledge base. The Python angle:

**Stdlib-only by design.** One runtime dependency: the `markdown` library. No npm, no template engine, no database. HTML is generated with f-string templates in a single `build.py` file. The conscious choice to avoid Jinja, Flask, and Django is a story in itself -- when your input is structured data (not blog posts), a template language fights the pipeline.

**Pure-SVG visualizations from stdlib Python.** Four modules generate GitHub-style activity heatmaps, tool-calling bar charts, token usage cards, and pricing sparklines as raw SVG strings. No Matplotlib, no D3, no Chart.js. CSS custom properties handle dark mode. The SVGs print cleanly and work in RSS readers.

**472 tests.** Unit tests, a Playwright E2E suite with 62 Gherkin scenarios, and snapshot tests. The testing story is as much a topic as the code itself.

**Pluggable adapter pattern.** Each AI agent is supported via a single ~50-line Python file that implements a base class. Adding a new agent means writing one file, one fixture, and one test. Eight adapters ship today.

**f-string templates over Jinja.** The entire HTML generation layer uses Python f-strings. No template inheritance, no filters, no custom tags. It sounds like it should not work, but it does -- and the result is a single-file build pipeline that anyone can read top to bottom.

**Other talking points:**
- Karpathy's LLM Wiki spec and what it means to build against someone else's architecture
- Privacy-first design: auto-redaction of secrets, localhost-only, `.llmwikiignore`
- MCP server: 7 tools for querying the wiki from Claude Desktop or Cursor
- Dual-format pages: every .html has a .txt and .json sibling for AI consumption

GitHub: https://github.com/Pratiyush/llm-wiki
Demo: https://pratiyush.github.io/llm-wiki/
MIT license. Python 3.9+. Works offline.

Happy to come on whenever works. I can do a live demo or keep it conversational.

Best,
[Your name]

---

## Podcast Pitch -- Latent Space / Practical AI (#105)

**Subject:** Pitch: multi-agent knowledge base implementing Karpathy's LLM Wiki spec

**Body:**

Hi [Swyx / Alessio] or [Daniel / Chris],

I built an open-source tool that sits at the intersection of several trends your listeners care about: multi-agent tooling, the Karpathy LLM Wiki pattern, AI-consumable web formats, and MCP.

**llm-wiki** converts session transcripts from 8 AI coding assistants into a unified, searchable knowledge base. The AI tooling story:

**The multi-agent problem is real.** Developers use Claude Code, Copilot, Cursor, Codex CLI, and Gemini CLI -- often in the same week. Each writes transcripts to a different location in a different format. llm-wiki unifies them through a pluggable adapter pattern: one ~50-line Python file per agent, shared parsing/rendering/redaction core. The result is a single knowledge base across all your AI coding tools.

**Karpathy's spec as a blueprint.** The project implements Andrej Karpathy's three-layer LLM Wiki architecture: immutable raw transcripts, LLM-maintained wiki pages with wikilinks, and a generated static site. Building against someone else's spec -- what it constrains, where it liberates, and where you have to extend beyond it -- is a useful discussion topic.

**Dual-format pages.** Every page ships as .html (with Schema.org microdata), .txt (plain text for LLMs), and .json (structured metadata + body). The site generates llms.txt, JSON-LD, sitemap, and RSS at the root. This is a concrete implementation of the "AI-consumable web" idea.

**MCP server.** 7 tools that let Claude Desktop, Cursor, or any MCP client query the wiki: search sessions, get project stats, list models, retrieve specific pages. A working example of MCP beyond "hello world."

**Model directory with changelog.** Structured model profiles, auto-generated comparison pages, and an append-only changelog timeline with pricing sparklines. Useful for anyone tracking the model landscape.

**Other angles:**
- Pure-SVG visualization pipeline (no JS charting library)
- Privacy-first: automatic redaction, localhost-only, no telemetry, no API key required
- 472 tests, stdlib-only Python (one dep), MIT license
- The "write-once, read-never" problem with AI session transcripts

GitHub: https://github.com/Pratiyush/llm-wiki
Demo: https://pratiyush.github.io/llm-wiki/
Karpathy's spec: https://gist.github.com/karpathy/442a6bf555914893e9891c11519de94f

I can go deep on architecture or keep it high-level -- whatever fits the episode format.

Best,
[Your name]

---

## Conference Talk Abstract (#106)

### Lightning Talk (5 minutes)

**Title:** From /dev/null to Knowledge Base: What Your AI Coding Sessions Are Hiding

**Abstract (200 words):**

Every AI coding assistant writes full session transcripts to disk. Claude Code writes JSONL to `~/.claude/projects/`. Copilot, Cursor, Codex CLI, and Gemini CLI each have their own store. Most developers have hundreds of these files and have never opened one.

Those transcripts contain architecture decisions, debugging sessions with dead ends, library evaluations, and code snippets you will want again. They are valuable. They are just inaccessible.

llm-wiki is an open-source Python CLI that converts these transcripts into a searchable, interlinked static wiki. It implements Andrej Karpathy's three-layer LLM Wiki architecture: immutable raw transcripts, LLM-maintained wiki pages, and a generated HTML site with global search and pure-SVG visualizations.

In five minutes I will show the three-layer pipeline in action, demonstrate how a pluggable adapter pattern supports 8 AI agents in ~50 lines each, and explain why the entire build pipeline uses f-string templates instead of Jinja. You will see a 365-day activity heatmap, tool-calling charts, and a model directory -- all generated from session data you already have on disk.

Walk away knowing how to set up your own AI coding knowledge base in under 5 minutes.

### Full Talk (20 minutes)

**Title:** Building a Multi-Agent Knowledge Base: Architecture Decisions Behind llm-wiki

**Abstract (300 words):**

AI coding assistants are the most-used, least-archived tools in a developer's workflow. Claude Code, Copilot, Cursor, Codex CLI, and Gemini CLI each write session transcripts to disk in different formats and locations. The result is a fragmented, unsearchable archive of architecture decisions, debugging sessions, and code reviews that evaporates after each session ends.

llm-wiki is an open-source Python tool that unifies these transcripts into a searchable knowledge base following Andrej Karpathy's three-layer LLM Wiki pattern. In this talk, I will walk through the architecture decisions that shaped the project and the trade-offs behind each:

**The adapter pattern:** How a single base class and 8 adapters (~50 lines each) support every major AI coding assistant. What the base class enforces, what it leaves open, and how to add a new agent in one file.

**f-strings over Jinja:** Why the entire HTML generation layer uses Python f-strings instead of a template engine. When structured-data pipelines and template inheritance collide, and why one file beats twenty.

**Pure-SVG from stdlib Python:** Generating GitHub-style activity heatmaps, tool-calling bar charts, token usage cards, and pricing sparklines as raw SVG strings. No Matplotlib, no D3. CSS custom properties for dark mode. Why this approach produces better output for this use case.

**Dual-format output:** Every page ships as .html, .txt, and .json. Site-level llms.txt, JSON-LD, and an MCP server with 7 tools. Designing for human and machine readers simultaneously.

**Testing at 472:** Unit tests, Playwright E2E with 62 Gherkin scenarios, snapshot tests. How to test a pipeline that generates HTML from session transcripts.

Attendees will understand the architecture patterns behind a real-world multi-agent data pipeline and leave with a working knowledge base of their own.

**Target venues:** PyCon (US, EU), local Python meetups, developer tooling conferences, AI/ML meetups

**Requirements:** Projector for live demo. Internet not required (demo runs locally).

---

## Testimonial Request Template (#120)

### Email version

**Subject:** Quick favor -- would you share your experience with llm-wiki?

**Body:**

Hi [Name],

Thank you for trying llm-wiki. I noticed you [starred the repo / opened an issue / mentioned it on Twitter / contributed a PR -- customize]. I am collecting early user feedback for the project page and README, and your perspective would be valuable.

If you have 5 minutes, would you be willing to share a short testimonial? It can be as short as two sentences. Here are some prompts to make it easier:

1. **What problem did llm-wiki solve for you?** (e.g., "I had 200+ Claude Code sessions and no way to search them.")
2. **What surprised you about the tool?** (e.g., setup speed, visualization quality, a feature you did not expect)
3. **How has it changed your workflow?** (e.g., "I now check the wiki before starting a new session to see if I already solved this.")
4. **What would you tell another developer considering it?**

You can reply to this email, DM me, or open a comment on the GitHub discussion thread: [link to discussion].

I will share the draft with you before publishing anything, and you can request edits or removal at any time.

Thanks again for being an early user.

Best,
[Your name]

### Twitter/X DM version

Hey [Name] -- thanks for [starring / trying / mentioning] llm-wiki. I am collecting short testimonials for the project page. Would you be open to sharing 1-2 sentences about your experience? Totally fine if not. If yes, here is a quick prompt: What problem did it solve for you, or what surprised you about it?

### GitHub Discussion post (for collecting multiple testimonials)

**Title:** Share your experience with llm-wiki

**Body:**

If you have used llm-wiki on your own session transcripts, I would love to hear about your experience. Short or long, positive or constructive -- all feedback is useful.

Some prompts:

- What agent(s) do you use it with? (Claude Code, Copilot, Cursor, etc.)
- How many sessions are in your wiki?
- What was the setup experience like?
- What feature do you use most?
- What is missing or could be improved?
- Would you recommend it to other developers? Why or why not?

If you are comfortable with your response being quoted on the README or project page, please say so explicitly. I will always share the draft before publishing and you can request edits.

---

## README A/B Test Plan (#121)

### Goal

Measure which README variation converts more GitHub visitors into stars and clones.

### What to vary

| Element | Variant A (current) | Variant B |
|---|---|---|
| Hero text | Current tagline | "Your AI sessions are write-once, read-never. Fix that." |
| Visual | Static screenshot | Animated GIF showing: Cmd+K search -> session detail -> heatmap (15s loop) |
| Badge placement | Top of README | After the hero image/GIF |
| Install section | Shell commands inline | Tabbed block: Quick Start / Docker / Manual |
| Feature list | Bullet points | 2-column table with icons |
| Social proof | None | Star count badge + "Used by X developers" (once testimonials exist) |

### How to measure

**Primary metric:** Star velocity (stars per day over the measurement window).

**Secondary metrics:**
- Unique clones per day (GitHub Traffic tab, Settings > Traffic)
- README scroll depth (not directly measurable on GitHub, but measurable on the docs site if mirrored)
- Issue/discussion creation rate

**Measurement window:** 2 weeks per variant (14 days minimum to smooth out daily variance).

**Baseline:** Record the current star velocity for 2 weeks before making any changes.

### Implementation steps

1. **Week -2 to 0: Baseline.** Do not change the README. Record daily star count and clone count from GitHub Traffic. Note any external events (HN post, newsletter mention) that could skew data.

2. **Week 0: Prepare Variant B.** Create the GIF using the demo site (screen record with Kap or asciinema, convert to GIF with ffmpeg, optimize with gifsicle to < 2 MB). Write the alternate hero text, badge layout, and install section. Stage in a branch.

3. **Week 0, Day 1: Deploy Variant A measurement.** Confirm Variant A (current README) metrics are being tracked. Start the 2-week timer.

4. **Week 2, Day 1: Switch to Variant B.** Merge the README branch. Start the 2-week timer. Avoid launching any other promotional activity during this window.

5. **Week 4, Day 1: Analyze.** Compare star velocity, clone velocity, and issue creation rate between the two periods. Account for confounding factors (was there a viral tweet in one window but not the other?).

6. **Decision.** If Variant B shows >= 20% improvement in star velocity with no obvious confound, keep it. Otherwise, revert to Variant A or iterate on a Variant C.

### GIF creation guide

```bash
# Record with asciinema (terminal) or Kap (browser)
# If browser demo, record at 1280x720

# Convert to GIF
ffmpeg -i recording.mov -vf "fps=10,scale=800:-1:flags=lanczos" -c:v gif raw.gif

# Optimize
gifsicle -O3 --lossy=80 --colors=128 raw.gif -o demo.gif

# Target: < 2 MB, 15-second loop, 10 fps
```

### Risks

- GitHub Traffic data has a 14-day retention window. Export daily.
- External events (HN post, newsletter) during one window but not the other will invalidate the comparison. Note all external promotion in a log.
- Star count is public and cumulative. Use daily deltas, not totals.

---

## Discord Server Setup Checklist (#57)

### Step 1: Create the server

1. Open Discord. Click the "+" button in the server sidebar.
2. Select "Create My Own" > "For a club or community."
3. Server name: **llm-wiki**
4. Upload server icon: use the project logo or a placeholder.
5. Click "Create."

### Step 2: Configure server settings

1. **Settings > Overview:**
   - Description: "Community for llm-wiki -- an open-source tool that converts AI coding session transcripts into a searchable knowledge base."
   - Enable Community Server (Settings > Enable Community). This unlocks: welcome screen, server insights, announcement channels.

2. **Settings > Safety Setup:**
   - Verification level: Medium (must be registered on Discord for 5+ minutes)
   - Explicit content filter: Scan messages from all members
   - Enable DM spam filter

3. **Settings > Roles:**

   | Role | Color | Permissions | Assignment |
   |---|---|---|---|
   | @Maintainer | Blue | Admin, manage channels, manage roles, pin messages | Manual (project maintainers) |
   | @Contributor | Green | Send messages, attach files, add reactions, use slash commands | Manual (anyone who has merged a PR) |
   | @Member | Gray | Send messages, add reactions | Auto (on join, after verification) |
   | @Bot | Purple | Send messages, embed links, manage messages | Manual (assigned to bots) |

### Step 3: Create channels

**Category: WELCOME**
- `#welcome` (read-only) -- server rules + links
- `#introductions` -- new members introduce themselves
- `#announcements` (read-only, @Maintainer can post) -- releases, blog posts, milestones

**Category: GENERAL**
- `#general` -- main discussion
- `#show-your-wiki` -- screenshots and demos of personal wikis
- `#help` -- setup questions and troubleshooting

**Category: DEVELOPMENT**
- `#contributions` -- PR discussion, review requests
- `#feature-ideas` -- proposals and discussion before opening a GitHub issue
- `#bugs` -- bug reports (with template: OS, Python version, agent, steps to reproduce)

**Category: AGENTS**
- `#claude-code` -- Claude Code adapter discussion
- `#copilot` -- Copilot adapter discussion
- `#cursor` -- Cursor adapter discussion
- `#other-agents` -- Codex CLI, Gemini CLI, Aider, Windsurf, Obsidian

**Category: META**
- `#feedback` -- feedback on the Discord itself
- `#off-topic` -- non-project discussion

### Step 4: Welcome message

Set up in Settings > Enable Community > Welcome Screen.

**Description:** Welcome to the llm-wiki community. Here is how to get started:

| Channel | Purpose |
|---|---|
| #welcome | Read the rules and find project links |
| #general | Start chatting |
| #help | Ask setup or usage questions |
| #show-your-wiki | Share screenshots of your wiki |
| #contributions | Discuss PRs and development |

### Step 5: Welcome channel content (#welcome)

Post the following pinned message:

```
**Welcome to the llm-wiki Discord**

llm-wiki is an open-source Python CLI that converts AI coding session transcripts into a searchable static wiki.

**Links:**
- GitHub: https://github.com/Pratiyush/llm-wiki
- Live demo: https://pratiyush.github.io/llm-wiki/
- Getting started: https://github.com/Pratiyush/llm-wiki#quickstart

**Rules:**
1. Be respectful. No harassment, spam, or self-promotion unrelated to the project.
2. Search before asking. Check #help history and GitHub Issues first.
3. Use the right channel. Agent-specific questions go in the agent channels.
4. No sharing of session transcripts that contain secrets, API keys, or personal data.
5. Bug reports should include: OS, Python version, agent name, and steps to reproduce.

**Roles:**
- @Maintainer -- project maintainers
- @Contributor -- anyone who has merged a PR (ask in #general to be assigned)
- @Member -- everyone (auto-assigned)
```

### Step 6: Bots and integrations

1. **GitHub bot:** Add the official GitHub Discord integration. Configure to post in `#announcements`:
   - New releases
   - Merged PRs (optional -- can be noisy)

2. **MEE6 or Carl-bot (optional):** Auto-role assignment on join, moderation (anti-spam, word filter).

3. **Webhook for CI (optional):** Post build status to `#contributions` via GitHub Actions webhook.

### Step 7: Invite link

1. Settings > Invites > Create a permanent invite link.
2. Set to never expire, no max uses.
3. Add to: README, GitHub repo description, docs site footer, social bios.

---

## Custom Domain Deployment Guide (#62)

### Option A: GitHub Pages with custom domain

This is the simplest path if you are already using GitHub Pages for the demo site.

**Step 1: Buy a domain.**
Recommended registrars: Cloudflare Registrar (cheapest renewals), Namecheap, Google Domains (now Squarespace Domains), Porkbun.

Suggested domains: `llmwiki.dev`, `llmwiki.org`, `llm-wiki.dev`

**Step 2: Configure DNS.**

For an apex domain (e.g., `llmwiki.dev`):

| Type | Name | Value | TTL |
|---|---|---|---|
| A | @ | 185.199.108.153 | 300 |
| A | @ | 185.199.109.153 | 300 |
| A | @ | 185.199.110.153 | 300 |
| A | @ | 185.199.111.153 | 300 |

For a `www` subdomain:

| Type | Name | Value | TTL |
|---|---|---|---|
| CNAME | www | pratiyush.github.io | 300 |

**Step 3: Configure GitHub Pages.**

1. Go to GitHub repo > Settings > Pages.
2. Under "Custom domain," enter your domain (e.g., `llmwiki.dev`).
3. Check "Enforce HTTPS" (will be available after DNS propagates, usually 10-30 minutes).
4. GitHub will create a `CNAME` file in the repo root. Make sure your build pipeline does not delete it, or add `CNAME` to the build output directory.

**Step 4: Update build pipeline.**

If your GitHub Actions workflow runs `./build.sh`, ensure the `CNAME` file is preserved in `site/`:

```bash
# In your build script or GitHub Actions workflow:
echo "llmwiki.dev" > site/CNAME
```

**Step 5: Verify.**

```bash
dig llmwiki.dev +short
# Should return GitHub Pages IPs

curl -I https://llmwiki.dev
# Should return 200 with GitHub Pages headers
```

DNS propagation can take up to 48 hours but usually completes in 10-30 minutes.

### Option B: Vercel

**Step 1: Import project.**

1. Go to https://vercel.com/new
2. Import the GitHub repo.
3. Set the build command to `./build.sh` and the output directory to `site/`.
4. Deploy.

**Step 2: Add custom domain.**

1. In the Vercel dashboard, go to Project > Settings > Domains.
2. Add your domain.
3. Vercel will display the required DNS records. Add them at your registrar.

**Step 3: DNS records (Vercel).**

| Type | Name | Value |
|---|---|---|
| A | @ | 76.76.21.21 |
| CNAME | www | cname.vercel-dns.com |

**Step 4: Verify.** Vercel provisions an SSL certificate automatically. Check the domain in the dashboard for status.

### Option C: Netlify

**Step 1: Import project.**

1. Go to https://app.netlify.com/start
2. Connect the GitHub repo.
3. Build command: `./build.sh`
4. Publish directory: `site/`
5. Deploy.

**Step 2: Add custom domain.**

1. In Netlify dashboard, go to Site Settings > Domain Management > Add custom domain.
2. Add your domain and follow the DNS setup instructions.

**Step 3: DNS records (Netlify).**

| Type | Name | Value |
|---|---|---|
| A | @ | 75.2.60.5 |
| CNAME | www | [your-site-name].netlify.app |

Or use Netlify DNS for automatic configuration.

**Step 4: Verify.** Netlify provisions an SSL certificate via Let's Encrypt automatically.

### Post-deployment checklist

- [ ] HTTPS works (no mixed content warnings)
- [ ] `www` subdomain redirects to apex (or vice versa)
- [ ] Update the demo link in the README, package metadata, social profiles, and all outreach materials
- [ ] Update `sitemap.xml` base URL if hardcoded
- [ ] Update `robots.txt` if it references the old domain
- [ ] Set up redirect from `pratiyush.github.io/llm-wiki` to the new domain (GitHub Pages supports this via a meta redirect in `index.html` or a 301 in the old CNAME config)
- [ ] Test the RSS feed URL
- [ ] Test the llms.txt URL

---

## HN/Reddit Monitoring Setup (#117)

### Goal

Get notified whenever "llm-wiki" or "llm wiki" is mentioned on Hacker News, Reddit, or the broader web.

### 1. Google Alerts

Go to https://www.google.com/alerts

Create alerts for each of these queries:

| Query | Frequency | Sources | Deliver to |
|---|---|---|---|
| `"llm-wiki"` | As-it-happens | Automatic | Email |
| `"llm wiki"` | As-it-happens | Automatic | Email |
| `"llm-wiki" github` | As-it-happens | Automatic | Email |
| `pratiyush llm-wiki` | As-it-happens | Automatic | Email |

Settings for each:
- How often: As-it-happens
- Sources: Automatic
- Language: English
- Region: Any region
- How many: All results
- Deliver to: your email (or an RSS reader via the RSS icon)

### 2. F5Bot (Reddit monitoring)

Go to https://f5bot.com

1. Create an account (free).
2. Add these keywords:

| Keyword | Subreddits (optional filter) |
|---|---|
| `llm-wiki` | (all) |
| `llm wiki` | (all) |
| `llmwiki` | (all) |

F5Bot will email you whenever these terms appear in a Reddit post title, post body, or comment. Response time is typically under 15 minutes.

### 3. Hacker News (hn.algolia.com RSS)

HN's Algolia search API supports RSS feeds for saved searches.

**Step 1:** Go to https://hn.algolia.com

**Step 2:** Search for each term and grab the RSS URL:

| Search term | RSS URL |
|---|---|
| `llm-wiki` | `https://hn.algolia.com/api/v1/search?query=%22llm-wiki%22&tags=story` (add `&format=rss` or use a wrapper) |
| `llm wiki` | `https://hn.algolia.com/api/v1/search?query=%22llm+wiki%22&tags=story` |
| `llmwiki` | `https://hn.algolia.com/api/v1/search?query=llmwiki&tags=story` |

**Step 3:** Add these RSS feeds to your reader (Feedly, Inoreader, NetNewsWire, or any RSS client).

Alternative: Use https://hnrss.github.io for a cleaner RSS interface:

```
https://hnrss.org/newest?q=%22llm-wiki%22
https://hnrss.org/newest?q=%22llm+wiki%22
```

These can also be filtered by points threshold:

```
https://hnrss.org/newest?q=%22llm-wiki%22&points=5
```

### 4. GitHub notifications

You should already get these, but verify:

1. Go to https://github.com/Pratiyush/llm-wiki
2. Click Watch > Custom > check: Issues, Pull Requests, Releases, Discussions
3. In GitHub Settings > Notifications, confirm email delivery is enabled.

### 5. Twitter/X monitoring (optional)

Use TweetDeck (or a third-party tool like Nuzzel/Tweeten) to create a saved search column for:

- `llm-wiki`
- `"llm wiki"`
- `github.com/Pratiyush/llm-wiki`

Twitter's search API is unreliable for low-volume terms. Consider supplementing with a weekly manual search.

### 6. Automation with IFTTT or Zapier (optional)

If you want all alerts in one place (e.g., a Slack channel or Discord channel):

1. Create an IFTTT applet: RSS Feed (hn.algolia.com) -> Slack/Discord webhook
2. Create an IFTTT applet: Email (Google Alerts) -> Slack/Discord webhook (filter by subject line)
3. Or use Zapier with the same triggers for more control over formatting.

### Response playbook

When a mention is detected:

1. **Read the full context** before responding. Is it positive, negative, a question, or a comparison?
2. **If it is a question or issue:** respond helpfully. Link to the relevant docs or GitHub issue.
3. **If it is positive:** thank them. Ask if they would be willing to share a testimonial (see Testimonial Request Template above).
4. **If it is negative or a bug report:** acknowledge, ask for details, open a GitHub issue if warranted.
5. **If it is a comparison with a competing tool:** respond factually. Do not disparage the other tool. Highlight differentiation without marketing language.
6. **Log all mentions** in a simple spreadsheet or GitHub Discussion thread for tracking over time.
