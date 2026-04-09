#!/usr/bin/env python3
"""Generate an asciinema v2 .cast file from real command outputs.

Runs each command, captures output, and writes a timestamped .cast
file with simulated typing. Produces docs/demo.cast.
"""
import json, subprocess, time, sys
from pathlib import Path

COLS, ROWS = 100, 30
ROOT = Path(__file__).resolve().parent.parent

def run(cmd, cwd=None):
    r = subprocess.run(
        cmd, shell=True, capture_output=True, text=True,
        cwd=cwd or str(ROOT), timeout=120,
    )
    return (r.stdout + r.stderr).rstrip("\n")

# Build the demo sequence: (description, command, pause_after)
STEPS = [
    ("banner", None, 2.0),
    ("version", "python3 -m llmwiki --version", 1.0),
    ("adapters", "python3 -m llmwiki adapters", 2.0),
    ("sync", "python3 -m llmwiki sync --dry-run", 2.0),
    ("build", "python3 -m llmwiki build", 2.5),
    ("ls_site", "ls site/ | head -15", 1.0),
    ("count", "find site -name '*.html' | wc -l | tr -d ' '", 1.5),
    ("llms_txt", "head -20 site/llms.txt", 2.0),
    ("projects", "ls raw/sessions/ | head -10", 1.5),
    ("cta", None, 3.0),
]

events: list[tuple[float, str, str]] = []
t = 0.0  # current timestamp

def emit(text: str):
    global t
    events.append((round(t, 3), "o", text))

def type_prompt(cmd: str):
    global t
    emit("\r\n\x1b[1;32m$ \x1b[0m")
    t += 0.3
    for ch in cmd:
        emit(ch)
        t += 0.04
    emit("\r\n")
    t += 0.2

def add_output(text: str):
    global t
    for line in text.split("\n"):
        emit(line + "\r\n")
        t += 0.03

# -- Banner --
emit("\x1b[2J\x1b[H")  # clear screen
t += 0.1
banner = [
    "╔══════════════════════════════════════════════════════════╗",
    "║  llm-wiki — Turn AI coding sessions into a wiki          ║",
    "║  github.com/Pratiyush/llm-wiki                           ║",
    "╚══════════════════════════════════════════════════════════╝",
]
for line in banner:
    emit(f"\x1b[1;36m{line}\x1b[0m\r\n")
    t += 0.1
t += 2.0

# -- Commands --
for label, cmd, pause in STEPS:
    if cmd is None:
        continue
    # Show the command with prompt
    display_cmd = cmd.replace("python3 -m llmwiki", "llmwiki")
    display_cmd = display_cmd.replace("find site -name '*.html' | wc -l | tr -d ' '",
                                      "find site -name '*.html' | wc -l")
    type_prompt(display_cmd)

    # Run and capture real output
    output = run(cmd)
    add_output(output)
    t += pause

# -- CTA --
emit("\r\n")
t += 0.5
cta_lines = [
    "\x1b[1;33m★\x1b[0m Star the repo: \x1b[4mgithub.com/Pratiyush/llm-wiki\x1b[0m",
    "\x1b[1;33m★\x1b[0m Live demo:     \x1b[4mpratiyush.github.io/llm-wiki\x1b[0m",
    "",
    "Features: heatmap, token stats, tool charts, model directory,",
    "          Cmd+K search, dark mode, AI exports (llms.txt, JSON-LD, MCP)",
]
for line in cta_lines:
    emit(line + "\r\n")
    t += 0.15
t += 3.0

# -- Write .cast file (v2 format) --
out_path = ROOT / "docs" / "demo.cast"
header = {
    "version": 2,
    "width": COLS,
    "height": ROWS,
    "timestamp": int(time.time()),
    "title": "llm-wiki: Full Workflow Demo",
    "env": {"SHELL": "/bin/bash", "TERM": "xterm-256color"},
}
with open(out_path, "w") as f:
    f.write(json.dumps(header) + "\n")
    for ts, typ, data in events:
        f.write(json.dumps([ts, typ, data]) + "\n")

print(f"Wrote {out_path} ({len(events)} events, {t:.1f}s duration)")
