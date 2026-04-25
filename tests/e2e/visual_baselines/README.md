# Visual-regression baselines

This directory holds the canonical PNG screenshots that
`tests/e2e/test_visual_regression.py` compares against on every E2E
run. Each scenario (home, session) captured at every breakpoint
(phone / tablet / laptop / desktop) and theme (light / dark) lands
here as `<tag>.png`.

## How comparison works

The screenshot step is in
[`tests/e2e/steps/ui_steps.py`](../steps/ui_steps.py) (`_capture_screenshot`).
On every run it:

1. Captures a full-page PNG to `tests/e2e/screenshots/<tag>.png`
   (gitignored — these are CI artifacts, not committed).
2. If `tests/e2e/visual_baselines/<tag>.png` does not exist yet,
   the live capture is *seeded* as the new baseline and the test
   passes. The first run on a new scenario is always green.
3. If a baseline exists, the live capture is diffed pixel-by-pixel
   via Pillow + `PIL.ImageChops`. The percentage of differing pixels
   is compared against a tolerance (default 1%, override with
   `LLMWIKI_VR_TOLERANCE_PCT`).
4. On failure, a `<tag>.diff.png` is saved next to the baseline
   showing what changed.

## Updating baselines

When intentional UI changes ship and the diff is expected:

```sh
LLMWIKI_VR_UPDATE=1 pytest tests/e2e/test_visual_regression.py
```

This overwrites every baseline with the live capture. Review the
git diff (the binary blobs will change but you can `git show
--stat` the size delta and visually inspect the new file) before
committing.

## Pillow is optional

`Pillow` is in the `[e2e]` extras (see `pyproject.toml`). On a
minimal install without Pillow, the comparison is skipped with a
warning rather than failing — this lets non-e2e contributors run
the suite without the image dependency.

## Determinism

CI uses Linux + Chromium. Local runs on macOS chromium will
produce small font-rendering differences — this is exactly why
the default tolerance is 1% rather than 0%. Bigger drift than 1%
on identical content is a real regression.

## Disk usage

Each laptop-resolution screenshot is ~30–80 KB. With 8 home
screenshots + 4 session screenshots × matrix variants, this
directory should stay under ~2 MB total. Large drift in repo size
when reviewing a baseline-update PR is a smell — it usually means
a layout regression silently inflated the page height.
