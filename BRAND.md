# Slabwatch brand kit

**Direction:** the meter itself. Grey-green casing, a backlit LCD readout, one red line at the limit. Calm, plain,
hyperlegible. Nothing on the page is louder than the readout, and red means only one thing: the limit.

Tokens live in `slabwatch/static/tokens.css` (served at `/static/tokens.css`). Change a value there and the whole
page follows. `scripts/post_images.py` uses the same hex values for the DEV post images; keep them in sync.

## Mark
`slabwatch/static/mark.svg`: a dark casing square holding an LCD, with a forecast bar stopping just short of a red
limit line. Also the favicon. The header draws it inline with tokens so it follows dark mode.

## Colour (light / dark)
| Token | Light | Dark | Use |
|---|---|---|---|
| `--casing` | #E4E9E1 | #121815 | page background |
| `--surface` | #EEF2EB | #18201B | the form panel |
| `--ink` | #14201A | #E2E8E1 | text, primary button |
| `--muted` | #55615A | #9AA79E | secondary text (5.2:1 / 7.2:1) |
| `--rule` | #C4CCC0 | #2B3530 | hairlines, input borders |
| `--lcd` / `--lcd-ink` | #C3D1AC / #1C2914 | #A7B98F / #16200F | the readout only |
| `--limit` | #B42318 | #F0614F | limit line, "over" verdicts, cost callout |
| `--lcd-limit` | #8E1B12 | #7A1A10 | small red text on the LCD (5.6:1 / 5.0:1) |
| `--safe` | #2F6B3E | #6FBF85 | "on track" verdict |
| `--watch` | #8A5600 | #E2A642 | "close" and "too early" verdicts |
| `--band` | #5F7F64 | #6E9174 | focus rings |

Rules: one LCD per screen. Red never decorates. Status always has a word next to the colour (the verdict text).

## Type
Atkinson Hyperlegible (400, 700) for everything; Atkinson Hyperlegible Mono (500, 700) for anything a meter would
show: digits, ticks, uppercase labels, step numbers. Body 17px / 1.5. Headline `clamp(1.6rem, 5.4vw, 2.25rem)`.
LCD digits `clamp(3.4rem, 18vw, 5.25rem)`, tabular, with faint unlit "888" segments behind them.
Uppercase labels: mono, 0.78rem, tracking 0.08em.

## Space, shape, motion
4px base scale (`--s-1` 4px to `--s-8` 72px). Radius 4 / 6 / 10px. Touch targets at least 44px. Single column
34rem; two columns from 960px (readout left, form right, 68rem). Motion only where a value changes: the forecast
band slides with `cubic-bezier(.23, 1, .32, 1)` over 450ms, off under reduced motion. Nothing animates on load.

## Voice
Calm and exact. Say what was assumed. Units first, rupees as an estimate. No hype, no exclamation marks. Roman Urdu
under each message for households that read it more easily.
