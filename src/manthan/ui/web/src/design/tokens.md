# Design tokens

Source of truth: `tokens.json`. Check: `~/.venvs/manthan/bin/python tools/check_contrast.py` (exit 0 means every pair passes).

## Colours and contrast (WCAG 2.1 AA, output of the check)

Light theme only, by owner decision of 2026-10-27. Backgrounds: cream (page), paper (raised panels), sand (inset areas and message bodies).

| kind | colour | hex | on cream | on paper | on sand | needs | result |
|---|---|---|---|---|---|---|---|
| text | ink | #0D1117 | 16.49 | 17.99 | 14.95 | 4.5 | pass |
| text | muted | #5B6470 | 5.23 | 5.70 | 4.74 | 4.5 | pass |
| non-text | wire | #6F7A87 | 3.80 | 4.15 | 3.45 | 3.0 | pass |
| non-text | ink | #0D1117 | 16.49 | 17.99 | 14.95 | 3.0 | pass |
| non-text | poison | #05070A | 17.58 | 19.17 | 15.93 | 3.0 | pass |

Fills with text on them:
- ink text on saffron fill: 8.98 (needs 4.5) pass
- ink text on teal fill: 7.56 (needs 4.5) pass
- cream text on poison fill: 17.58 (needs 4.5) pass

Rules:
- Text uses ink or muted only. Each passes 4.5:1 on cream, paper and sand.
- Saffron and teal are fills only, never text or lines. On the light grounds they reach 1.66 to 2.38, under 3:1. A saffron or teal fill always has ink text. When the fill alone marks a state (a dot, a bar, the current-page pill), it also gets a 1 px `wire` edge.
- A solid near-black fill means poison and nothing else. No black buttons, chips, tags or toggles. Ink text and ink outlines are fine. Reason: poison #05070A is only ΔE 4 from ink, so a black fill anywhere else would read as "attack worked".
- `wire` (#6F7A87) is for lines that carry meaning: map connections, chart axes, input borders. It passes 3:1 (3.45 at worst on sand). It is never text.
- `line` and `line-strong` are for decorative dividers only. They fail 3:1, so nothing a user must see depends on them.
- Meaning: saffron is nectar, highlights and the current page. Teal is the system under test, live activity and "defence held". Poison (Kalakuta smoke, #05070A) is "attack worked".
- Colour never carries meaning alone. Every badge and every chart mark also has a word or a label.

## Type
- Sizes: 13, 15, 20, 28, 40 px. A page uses at most three of them (`layout.md` lists them per page).
- Line height 1.5 for body text, 1.2 for headings. Body lines stay under 80 characters.
- Roles: serif for headings, sans for body, mono for data and IDs. The families wait for approval (`fonts-and-logos.md`). Until then the preview uses system fonts.

## Spacing, radius, motion
- Spacing: 4, 8, 12, 16, 24, 32, 48, 64 px. No other values.
- Radius: 4 px for small controls and badges, 8 px for panels and packet windows, 999 px for pills and device glows. These three replace the nine radii (2 to 12 px) in the mockups.
- Motion: 150 ms for answers to a click, 300 ms for the packet trip and the verdict moment. All motion stops under `prefers-reduced-motion`. Packets then jump to their end point.
