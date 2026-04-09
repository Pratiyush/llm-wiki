# Homebrew formula for llmwiki (v0.6 · closes #41)
#
# Install: brew install Pratiyush/tap/llmwiki
# Or:      brew tap Pratiyush/tap && brew install llmwiki
#
# This formula lives in the main repo under `homebrew/llmwiki.rb` as a
# reference. To publish it for real, copy it into a Homebrew tap repo
# at `https://github.com/Pratiyush/homebrew-tap/Formula/llmwiki.rb`
# and update the `url` + `sha256` on every release.
#
# Users who install via Homebrew get:
# - `llmwiki` command on PATH (all subcommands: init, sync, build, serve, …)
# - Python 3.12 as a dependency (Homebrew manages it)
# - `markdown` pip package installed in the formula's virtualenv
# - No other runtime deps — highlight.js loads from CDN at view time

class Llmwiki < Formula
  include Language::Python::Virtualenv

  desc "LLM-powered knowledge base from Claude Code, Codex CLI, Cursor, and Obsidian sessions"
  homepage "https://github.com/Pratiyush/llm-wiki"
  url "https://github.com/Pratiyush/llm-wiki/archive/refs/tags/v0.9.0.tar.gz"
  sha256 "PLACEHOLDER_SHA256_REPLACE_ON_RELEASE"
  license "MIT"
  head "https://github.com/Pratiyush/llm-wiki.git", branch: "master"

  depends_on "python@3.12"

  resource "markdown" do
    url "https://files.pythonhosted.org/packages/b5/4c/a80f8c5b57d21f498f3e0b0319b0cc0e3e1b9a4c4b77a0aff98f1efb730e/markdown-3.7.tar.gz"
    sha256 "2ae2471477cfd02dbbf038d5d9bc226d40def84b4fe2986e49b59b6b472bbed2"
  end

  def install
    virtualenv_install_with_resources
  end

  def caveats
    <<~EOS
      llmwiki is installed. Quick start:

        llmwiki init          # scaffold raw/ wiki/ site/
        llmwiki sync          # convert your agent sessions
        llmwiki build         # compile the static site
        llmwiki serve         # browse at http://127.0.0.1:8765

      Session stores are auto-detected:
        Claude Code:  ~/.claude/projects/
        Codex CLI:    ~/.codex/sessions/
        Cursor:       ~/Library/Application Support/Cursor/

      Docs: https://github.com/Pratiyush/llm-wiki
      Demo: https://pratiyush.github.io/llm-wiki/
    EOS
  end

  test do
    system bin/"llmwiki", "--version"
    system bin/"llmwiki", "adapters"
    # Scaffold + build against an empty wiki (no real session data needed)
    system bin/"llmwiki", "init"
    assert_predicate testpath/"raw", :directory?
    assert_predicate testpath/"wiki", :directory?
    assert_predicate testpath/"site", :directory?
  end
end
