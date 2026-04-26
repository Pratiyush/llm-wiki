# Synthetic monitoring failure

The nightly synthetic monitoring workflow (`.github/workflows/synthetic.yml`) failed against the deployed demo at `https://pratiyush.github.io/llm-wiki/`.

## Possible causes

- GitHub Pages publish lag or partial publish corruption — try a manual rebuild via the Pages workflow.
- Third-party CDN failure (highlight.js, vis-network, axe-core, fonts.googleapis.com).
- A browser update changed default behaviour for one of the tested features.
- The deploy itself is broken — check the most recent `pages.yml` run.

## Debug

- Download the `synthetic-report` artifact from the failed workflow run for an HTML report with screenshots + traces.
- Re-run the workflow manually via "Run workflow" on the workflow page to confirm the failure isn't transient.

## Triage

If the deployed demo is broken, file a fresh issue describing the user impact and link the failed workflow run. Resolve this tracking issue once the underlying cause is fixed.
