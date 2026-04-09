Generate a Marp slide deck from wiki content matching a topic.

Usage: /wiki-export-marp <topic>

Searches the wiki for pages related to `<topic>`, extracts key claims
from their Summary / Key Facts / Key Claims sections, and writes a
Marp-format markdown deck with title slide, outline, one content slide
per matching page, and a summary slide.

Output goes to `wiki/exports/<topic-slug>.marp.md` by default.

Run: `python3 -m llmwiki export-marp --topic "$ARGUMENTS"`
