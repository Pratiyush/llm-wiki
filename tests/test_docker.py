"""Tests for Docker setup (v1.1.0, #123)."""

from __future__ import annotations

import pytest

from llmwiki import REPO_ROOT


DOCKERFILE = REPO_ROOT / "Dockerfile"
COMPOSE = REPO_ROOT / "docker-compose.yml"
PUBLISH_WORKFLOW = REPO_ROOT / ".github" / "workflows" / "docker-publish.yml"
DOCS = REPO_ROOT / "docs" / "deploy" / "docker.md"


# ─── Dockerfile ───────────────────────────────────────────────────────


def test_dockerfile_exists():
    assert DOCKERFILE.is_file()


def test_dockerfile_uses_python_slim_base():
    text = DOCKERFILE.read_text(encoding="utf-8")
    assert "python:3.12-slim" in text


def test_dockerfile_has_oci_labels():
    text = DOCKERFILE.read_text(encoding="utf-8")
    for label in [
        "org.opencontainers.image.title",
        "org.opencontainers.image.description",
        "org.opencontainers.image.source",
        "org.opencontainers.image.licenses",
    ]:
        assert label in text, f"missing OCI label: {label}"


def test_dockerfile_uses_non_root_user():
    text = DOCKERFILE.read_text(encoding="utf-8")
    assert "USER app" in text
    assert "useradd" in text
    assert "UID 1000" in text or "uid 1000" in text.lower() or "--uid 1000" in text


def test_dockerfile_exposes_default_port():
    text = DOCKERFILE.read_text(encoding="utf-8")
    assert "EXPOSE 8765" in text


def test_dockerfile_default_cmd_serves_built_site():
    text = DOCKERFILE.read_text(encoding="utf-8")
    # CMD should reference serve + host 0.0.0.0 + site dir
    assert "serve" in text
    assert "0.0.0.0" in text
    assert '"--dir"' in text and '"site"' in text


def test_dockerfile_multi_stage_build():
    text = DOCKERFILE.read_text(encoding="utf-8")
    # Builder stage + final runtime stage
    assert "AS builder" in text
    assert "COPY --from=builder" in text


def test_dockerfile_owns_mount_point_as_app_user():
    text = DOCKERFILE.read_text(encoding="utf-8")
    assert "chown -R app:app /wiki" in text


# ─── docker-compose.yml ───────────────────────────────────────────────


def test_compose_exists():
    assert COMPOSE.is_file()


def test_compose_pulls_ghcr_image():
    text = COMPOSE.read_text(encoding="utf-8")
    assert "image: ghcr.io/pratiyush/llm-wiki" in text


def test_compose_has_build_fallback():
    text = COMPOSE.read_text(encoding="utf-8")
    # Fallback build directive so users can build locally if they want
    assert "build:" in text


def test_compose_maps_default_port():
    text = COMPOSE.read_text(encoding="utf-8")
    assert '"8765:8765"' in text


def test_compose_bind_mounts_user_dirs():
    text = COMPOSE.read_text(encoding="utf-8")
    # Bind-mount raw/, wiki/, site/ so llmwiki reads/writes host data
    assert "./raw:/wiki/raw" in text
    assert "./wiki:/wiki/wiki" in text
    assert "./site:/wiki/site" in text


def test_compose_mounts_examples_readonly():
    text = COMPOSE.read_text(encoding="utf-8")
    # Examples are seed data; mount read-only
    assert "./examples:/wiki/examples:ro" in text


def test_compose_has_healthcheck():
    text = COMPOSE.read_text(encoding="utf-8")
    assert "healthcheck:" in text


def test_compose_has_restart_policy():
    text = COMPOSE.read_text(encoding="utf-8")
    assert "restart: unless-stopped" in text


# ─── Publish workflow ────────────────────────────────────────────────


def test_publish_workflow_exists():
    assert PUBLISH_WORKFLOW.is_file()


def test_publish_triggers_on_version_tags():
    text = PUBLISH_WORKFLOW.read_text(encoding="utf-8")
    assert 'tags: ["v*.*.*"]' in text


def test_publish_has_workflow_dispatch():
    text = PUBLISH_WORKFLOW.read_text(encoding="utf-8")
    assert "workflow_dispatch" in text


def test_publish_builds_multi_arch():
    text = PUBLISH_WORKFLOW.read_text(encoding="utf-8")
    # amd64 + arm64
    assert "linux/amd64" in text
    assert "linux/arm64" in text


def test_publish_requires_packages_write_permission():
    text = PUBLISH_WORKFLOW.read_text(encoding="utf-8")
    assert "packages: write" in text


def test_publish_uses_gha_cache():
    text = PUBLISH_WORKFLOW.read_text(encoding="utf-8")
    assert "type=gha" in text


def test_publish_tags_include_latest_only_for_stable():
    text = PUBLISH_WORKFLOW.read_text(encoding="utf-8")
    # `latest` must NOT apply to rc/alpha/beta/dev pre-releases
    assert "!contains(github.ref, 'rc')" in text
    assert "!contains(github.ref, 'alpha')" in text


def test_publish_logs_into_ghcr():
    text = PUBLISH_WORKFLOW.read_text(encoding="utf-8")
    assert "ghcr.io" in text
    assert "docker/login-action" in text


# ─── Docs ─────────────────────────────────────────────────────────────


def test_docker_docs_exist():
    assert DOCS.is_file()


def test_docker_docs_cover_pull_mode():
    text = DOCS.read_text(encoding="utf-8")
    assert "docker compose pull" in text


def test_docker_docs_cover_build_mode():
    text = DOCS.read_text(encoding="utf-8")
    assert "docker compose build" in text


def test_docker_docs_list_image_details():
    text = DOCS.read_text(encoding="utf-8")
    assert "Image details" in text
    assert "non-root" in text
    assert "8765" in text


def test_docker_docs_list_volumes():
    text = DOCS.read_text(encoding="utf-8")
    assert "./raw" in text
    assert "./wiki" in text
    assert "./site" in text


def test_docker_docs_troubleshooting_section():
    text = DOCS.read_text(encoding="utf-8")
    assert "Troubleshooting" in text


def test_docker_docs_mentions_no_telemetry():
    text = DOCS.read_text(encoding="utf-8")
    assert "no telemetry" in text.lower()
