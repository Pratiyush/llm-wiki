# Homebrew formula for llm-wiki
# To use: brew tap Pratiyush/tap && brew install llmwiki
# Or: brew install Pratiyush/tap/llmwiki

class Llmwiki < Formula
  include Language::Python::Virtualenv

  desc "Turn AI coding sessions into a searchable static knowledge base"
  homepage "https://github.com/Pratiyush/llm-wiki"
  # Once published to PyPI, replace with:
  # url "https://files.pythonhosted.org/packages/.../llmwiki-0.9.0.tar.gz"
  url "https://github.com/Pratiyush/llm-wiki/archive/refs/tags/v0.9.0.tar.gz"
  sha256 "REPLACE_WITH_RELEASE_TARBALL_SHA256"
  license "MIT"
  head "https://github.com/Pratiyush/llm-wiki.git", branch: "master"

  depends_on "python@3.12"

  resource "markdown" do
    url "https://files.pythonhosted.org/packages/source/M/Markdown/markdown-3.7.tar.gz"
    sha256 "REPLACE_WITH_MARKDOWN_SHA256"
  end

  def install
    virtualenv_install_with_resources
  end

  test do
    assert_match version.to_s, shell_output("#{bin}/llmwiki --version")
    assert_match "adapters", shell_output("#{bin}/llmwiki adapters")
  end
end
