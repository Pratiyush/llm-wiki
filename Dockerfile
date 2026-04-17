# ── build stage ──────────────────────────────────────────────
FROM python:3.12-slim AS builder

WORKDIR /app

# Copy only what pip needs to install the package.
COPY pyproject.toml README.md CHANGELOG.md LICENSE ./
COPY llmwiki/ llmwiki/

# Install the package (and its sole runtime dep: markdown>=3.4).
RUN pip install --no-cache-dir .

# ── runtime stage ────────────────────────────────────────────
FROM python:3.12-slim

# OCI-standard labels — registries + security scanners use these.
LABEL org.opencontainers.image.title="llmwiki" \
      org.opencontainers.image.description="Karpathy-style LLM wiki from Claude Code, Codex, Cursor, Gemini, Copilot, and Obsidian sessions" \
      org.opencontainers.image.source="https://github.com/Pratiyush/llm-wiki" \
      org.opencontainers.image.licenses="MIT" \
      org.opencontainers.image.authors="Pratiyush <pratiyush1@gmail.com>"

# Non-root user for runtime safety. UID 1000 matches the default Linux
# host user so mounted volumes don't end up root-owned.
RUN groupadd --gid 1000 app && \
    useradd  --uid 1000 --gid app --shell /bin/bash --create-home app

# Bring over installed packages and the CLI entry-point script.
COPY --from=builder /usr/local/lib/python3.12/site-packages/ \
                    /usr/local/lib/python3.12/site-packages/
COPY --from=builder /usr/local/bin/llmwiki /usr/local/bin/llmwiki

WORKDIR /wiki

# Seed the example sessions so `llmwiki init` has something to demo.
COPY --chown=app:app examples/ examples/

# Fix ownership on the mount point so bind-mounts work as the app user.
RUN chown -R app:app /wiki

USER app

# The serve command defaults to port 8765.
EXPOSE 8765

ENTRYPOINT ["llmwiki"]
CMD ["serve", "--host", "0.0.0.0", "--port", "8765", "--dir", "site"]
