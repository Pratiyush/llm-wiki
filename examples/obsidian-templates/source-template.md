<%*
// Obsidian Templater template for wiki/sources/ pages.
// Install: copy to your vault's templates folder, then use
// "Templater: Create new note from template" with this template.

const slug = await tp.system.prompt("Source slug (kebab-case)", "my-source");
const project = await tp.system.prompt("Project slug", "general");
const date = tp.date.now("YYYY-MM-DD");
_%>---
title: "<% await tp.system.prompt('Title', slug) %>"
type: source
tags: [source]
date: <% date %>
source_file: raw/sessions/<% date %>-<% project %>-<% slug %>.md
project: <% project %>
confidence: 0.5
lifecycle: draft
last_updated: <% date %>
---

# <% await tp.file.title %>

> [!info] Source page
> Summarizes a single raw session or document. Keep to 2-4 sentences.

## Summary

(Write 2-4 sentence synthesis of what this source accomplished.)

## Key Claims

- Claim 1
- Claim 2
- Claim 3

## Key Quotes

> "Quote here" — context

## Connections

- [[EntityName]] — how they relate
- [[ConceptName]] — how it connects

## Contradictions

(If this source contradicts other wiki content, record both claims here.)
