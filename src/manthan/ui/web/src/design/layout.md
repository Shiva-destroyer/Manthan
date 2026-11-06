# Layout and navigation

Target: one still frame at 1920×1080 reads well (spec Section 1).

## Grid
- 12 columns, 24 px gutters, content width 1440 px, centred (1504 px including 32 px side padding). The side padding is 24 px below 1280 px wide and 16 px below 768 px.
- Top bar: 64 px high and sticky. The logo and wordmark sit on the left, and the navigation sits on the right. Below 768 px the bar is not sticky, and the navigation wraps under the wordmark.
- Navigation order: Home, Virtual Lab, Run, Results, Judge, System. The current page is a saffron pill with ink text and a 1 px wire edge. Saffron alone is under 3:1 on cream, so the edge carries the state. No icons in the navigation.
- Below 1024 px wide, side panels move under the main panel. At 375 px no page scrolls sideways; wide tables scroll inside their own box. There is no mobile design beyond that.

## Page frames
- Home: a hero in 8 columns (name, tagline, one plain sentence, and two links: the Virtual Lab and the results). The loop drawing takes the full 12 columns. Then why, need and how sit in three 4-column parts, and "What you get" is a paper panel in 8 columns with the live headline result. Below 1024 px every part takes the full width.
- Virtual Lab: the resource strip (40 px) sits under the top bar. Below it, the map takes 8 columns and the event list 4 columns. The lab tabs (Prompt, Agent, RAG) and the Realtime/Simulation switch sit above the map. The map is capped at 43% and the event list at 55% of the window height, so map, replay bar and events fit one 1920x1080 screen with no page scroll.
- Run: the form takes 5 columns, and the pre-run checks and progress take 7.
- Results: a one-line takeaway, then the chart or sentence block in 8 columns. The (i) explanations and the honest-limits panel take 4.
- Judge: like Results.
- System: the readiness checks in one row of text items (not number tiles), then the models table across 12 columns, then the config viewer.

## Text sizes per page (at most three)
| Page | Sizes (px) |
|---|---|
| Home | 40, 20, 15 |
| Virtual Lab | 20, 15, 13 |
| Run | 28, 15, 13 |
| Results | 28, 15, 13 |
| Judge | 28, 15, 13 |
| System | 28, 15, 13 |
