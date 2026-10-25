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
34rem; two columns from 960px (readout left, form right, 68rem). 
Motion (tokens `--ease-*`, `--dur-*`, `--stagger`):
- **Boot screen**: the page opens on a small meter that runs a self-test, like a real meter at power-on. All
  segments light (`888`), flicker out to `---`, and the needle sweeps past the red limit line and settles under it.
  It lifts away as a shutter (slides up, red line on its trailing edge). Full test once per tab, about 1.1 s; it
  never waits on the server (the status line covers a cold Render start). Capped at 2.4 s.
- **Page transition**: links to another page drop the same shutter from below, then navigate; the next page opens
  already covered and lifts it. No browser flash, no loading bar. In-page anchors scroll smoothly instead.
- **On the page**: content rises in with a 70ms stagger after the shutter lifts; "How it decides" rises in on scroll.
  A new forecast flickers the LCD like a refresh and counts the digits up; the band and needle slide (450ms);
  the red limit line pulses when the verdict is over. The check button scans an LCD segment while it waits.
- **Reduced motion**: no travel, no count-up, no pulse. The boot screen shows a still meter and fades.

## Voice
Calm and exact. Say what was assumed. Units first, rupees as an estimate. No hype, no exclamation marks. Roman Urdu
under each message for households that read it more easily.
