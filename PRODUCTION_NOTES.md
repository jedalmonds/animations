# Documentary diagram: production notes

These notes record how the brief (`Animation_Production_Prompt.pdf`) has been built, including every addition to it or departure from it.
Last updated: 2026-09-25.

## Status

| Seq | Content | Clip | Status |
|---|---|---|---|
| 1 | National Budget | `out/seq1-7-preview-720p60.mp4` (1–7 combined, 97.0 s) | Preview; ₱ builds itself |
| 2 | DPWH + District Engineering Office | same | Preview |
| 3 | Budget Approval | same | Preview; extra elements added (now 18.5 s) |
| 4 | Bidding + Winning Contractor | same | Preview (starts 3.5 s later on the master clock) |
| 5 | (no sequence requested; square stays empty) | n/a | n/a |
| 6 | Inspection | same, and `out/seq6-preview-720p60.mp4` (10.0 s) | Preview |
| 7 | Certificate of Completion | same, and `out/seq7-preview-720p60.mp4` (10.0 s) | Preview |

The previews are 1280×720 at 60 fps with no audio; the client said low resolution is fine for review. The final export
is 3840×2160 at 60 fps from the same master (`--w 3840`).

## System

- **One master canvas:** `master.html`. World units equal the reference overview frame (1920×1080 at zoom 1).
  Output resolution never changes the layout.
- **One master clock:** each clip is a window of it, so a clip's last frame is identical to the next clip's first frame.
  Byte-identical seams checked with `check-seams.mjs`: 1→2, 2→3, 3→4, 4→6 and 6→7. Combined windows: `12` (0–41.5 s),
  `34` (41.5–77 s), `67` (77–97 s), `1234` (0–77 s) and `1234567` (0–97 s, the whole film).
- **Frames are order-independent:** every frame is drawn from the master time alone. Before 2026-09-25 two scratch
  layers kept line settings from the previous frame, so a clip rendered on its own started with slightly different
  pixels than the previous clip ended with (seams 2→3 and 3→4, a pixel or so on the tile corners and the river-wall
  joints). Those settings are now fixed to the look the preview showed, and `check-seams.mjs` draws each clip's last
  frame after earlier frames, as a real render does, so such a leak would show up.
- **Camera:** keyframes `[t, x, y, zoom]` with cubic ease-in-out. Zoom interpolates logarithmically. Holds are
  perfectly still, so the editor can trim them without jumps.
- **Rendering:** `render.mjs` streams frames straight into ffmpeg with no PNGs written to disk, because drive C: is
  nearly full.

```
npm install                        # puppeteer-core; point CHROME at a Chrome/Chromium binary
node render.mjs --seq 1234567 --w 1280 --out out/seq1-7-preview-720p60.mp4
node render.mjs --seq 6 --w 3840 --out out/seq6-4k60.mp4
node render.mjs --seq 3 --w 1280 --stills 0,300 --out out/stills
node check-seams.mjs --w 1280      # exits non-zero if any seam differs
```

## Style decisions

- **Font:** Montserrat (OFL) stands in for **Nexa**, which is not installed and is a commercial font. Bold (700–800) is
  used for headings and 400 for descriptions. To swap, replace the embedded file in `font.js`.
- **Background:** a screen-fixed warm off-white gradient (#efede4 to #e3e0d7), faint diagonal sheen and very subtle
  static grain, matching the reference.
- **Ink:** #141412. Squares, arrows and outlines are 2.2 world units wide.
- **Icons:** the ₱, DPWH emblem, list icons, task tiles and river-wall diagram are drawn in code. The handshake,
  assignment, woman, man, home, check_circle and location_on icons come from Google **Material Symbols Rounded
  (filled)** under the Apache 2.0 licence (`icons/LICENSE`).
- **Squares 6 and 7 icons:** the prepared `content_paste_search` is an outline icon and `workspace_premium` reads as an
  award badge. Next to the solid handshake and assignment icons neither matched, so both are solid composites drawn in
  code on the same Material grid, with the same rounded ends and knockout gaps:
  - **Inspection:** a clipboard with three ticked rows, and a magnifying glass over its lower right (the brief's
    suggestion). The clipboard tab matches the assignment icon in square 4.
  - **Certificate:** a certificate sheet with an inner border, text lines and a ribboned seal. The border is about
    the same weight as the square outlines.

  The prepared Material paths stay in `icons.js`, so swapping back is a one-line change in `seq6()` or `seq7()`
  (`sym(...)` in place of `composite(...)`).
- **DPWH emblem:** simplified black-and-white gear, road and "DPWH" band, based on the approved infographic. It is
  **not** the official seal; swap in the official black-and-white logo if supplied.
- **Reveal grammar:**
  - **Text:** hard cuts only. The DEO title and the job description use the permitted typing effect, with the left
    edge fixed.
  - **Graphics:** a short 0.4–0.6 s fade (as in the reference), or a draw-on such as a line tracing or an arrow
    growing.
  - **Never:** bounce, spin, pulse, scale or slide. No element moves after it appears, except the pie separation that
    the brief requests.

## Sequence timings (seconds from the start of each clip)

### Sequence 1: National Budget (17.0 s)
| t | Event |
|---|---|
| 0–1.0 | Hold on seven empty numbered squares |
| 1.0–4.2 | Zoom and pan into square 1 (3×) |
| 4.3–5.55 | **₱ builds (updated):** outline traced (4.3–4.9), ink fills bottom-up (4.75–5.25), two bars drawn left to right (5.1–5.55) |
| 5.55–9.2 | Hold during the "your money / taxes" lines, with no new graphics |
| 9.2–9.6 | Down arrow grows; camera follows down (9.2–11.2) |
| 10.6–11.3 | Circle drawn in one continuous stroke |
| 12.2–12.7 | Dividers grow from the centre; slices fill one by one clockwise (12.5 onward, 0.12 s stagger) |
| 13.4–14.4 | Slices separate slightly outward (7 units), with no rotation or bounce |
| 14.4–17.0 | Hold (final frame) |

### Sequence 2: DPWH and District Engineering Office (24.5 s)
| t | Event |
|---|---|
| 0.4–3.0 | Pan to square 2 (mostly horizontal, with an upward adjustment) |
| 3.3–3.9 | DPWH emblem fades in |
| 4.6 | "Department of Public Works and Highways" (hard cut) |
| 5.8–7.6 | Camera down to the list |
| 7.7 | *Added:* "RESPONSIBLE FOR:" label (hard cut) |
| 7.9–10.9 | Roads, Bridges, Water Resources, then Public Buildings, School Buildings, **Flood Control last** (hard cuts, each with its icon) |
| 11.8 | "etc." |
| 12.8–13.2 | Down arrow; camera down to the rectangle (13.2–15.2) |
| 15.0 / 15.5–16.8 | Rectangle (with *added* office icon); "DISTRICT ENGINEERING OFFICE" types in |
| 17.3–18.5 | Camera slightly down |
| 18.6 / 18.9–21.6 | "JOB:" then the exact description types in, left-aligned |
| as typed | *Added:* four task tiles (magnifier, grid and pencil, clipboard, hard hat) each hard-cut in as its phrase finishes |
| 21.6–24.5 | Hold (final frame) |

### Sequence 3: Budget Approval (18.5 s)
| t | Event |
|---|---|
| 0.4–3.4 | Pan from the district-office frame to square 3 |
| 3.7–4.3 | Handshake icon fades in and then stays still |
| 4.9 | "BUDGET APPROVAL" beneath the square (hard cut) |
| 5.9–7.7 | Camera down to the project details |
| 7.8 | *Added:* "PROPOSED PROJECT:" label (hard cut) |
| 8.0–9.0 | "220-METER REINFORCED / CONCRETE RIVER WALL" word by word (hard cuts; the line break follows the approved screenshot) |
| 9.7–10.45 | "Barangay Piel, Baliuag, Bulacan" word by word; *added* location pin appears with the first word |
| 11.0–11.3 | Thin rule drawn |
| 11.5 | "₱55,739,911.60" as one complete item, with no counting. The amount is taken as supplied in the brief. |
| 12.3–13.5 | *Added:* camera moves slightly down |
| 13.7–14.3 | *Added:* river-wall diagram fades in (concrete panels in perspective, water on the river side) |
| 14.6–15.1 | *Added:* dimension line grows out from the centre, then gets end ticks and arrowheads |
| 15.3 | *Added:* "220 m" (hard cut) |
| 15.3–18.5 | Hold (final frame) |

### Sequence 4: Bidding (17.0 s; master clock 60.0–77.0)
| t | Event |
|---|---|
| 0.4–3.1 | Pan to square 4 |
| 3.4–4.0 | Bid-document (assignment) icon fades in |
| 4.6 | "BIDDING" (hard cut) |
| 5.6–7.4 | Camera down |
| 7.7–8.1 | Woman pictogram (with a small static house, as in the approved screenshot) |
| 8.5 / 9.1 / 9.7 | Three men appear; each man's dashed line with an arrowhead draws toward her. The men do not move. |
| 10.2–13.3 | Hold on the woman and the three suitors |
| 13.3 | Check badge beside the right-hand man only |
| 13.6 | "WINNING CONTRACTOR" (hard cut). The other figures stay visible, with no celebration. |
| 13.6–17.0 | Hold (final frame) |

### Sequence 6: Inspection (10.0 s; master clock 77.0–87.0)
| t | Event |
|---|---|
| 0–0.4 | Hold on the winning-contractor frame |
| 0.4–4.0 | Pan up and right past the empty square 5 to square 6. This pan is longer, so its peak speed stays within that of the earlier pans. |
| 4.3–4.9 | Inspection icon fades in and then stays still |
| 5.5 | "INSPECTION" beneath the square (hard cut) |
| 5.5–10.0 | Hold (final frame). No paragraph or inspection scene, per the brief. |

### Sequence 7: Certificate of Completion (10.0 s; master clock 87.0–97.0)
| t | Event |
|---|---|
| 0.4–3.0 | Pan right to square 7 (horizontal only) |
| 3.3–3.9 | Certificate icon fades in and then stays still |
| 4.5 | "CERTIFICATE OF COMPLETION" beneath the square on one line (hard cut), same size as the other step headings. It is wider than the square, like the DPWH name. |
| 4.5–10.0 | Hold (final frame of the film). No paperwork animation or full-diagram reveal, per the brief. |

## Additions beyond the brief (client-requested "more elements", kept within the rules)
1. The circle is drawn as a single line rather than faded in, and the pie slices fill in sequence.
2. List items have flat icons instead of bullets. No categories were added.
3. A "RESPONSIBLE FOR:" label sits above the list.
4. An office icon sits inside the DEO rectangle.
5. Four task tiles, with no text labels, sit under JOB:. The brief's ban on large "Implement"/"Monitor" labels is
   respected.
6. The ₱ builds itself (trace, fill, bars) instead of fading.
7. Sequence 3: a "PROPOSED PROJECT:" label, a location pin, and a river-wall diagram with a 220 m dimension line. All are
   static after they appear; no numbers were added beyond the brief's.

## QA performed and its limits
- Squares 6 and 7 were rendered in a Linux container (Chromium, same master). Stills of the unchanged 1–4 section
  were compared with the Windows-rendered 1–4 preview; they differ only in text anti-aliasing and compression noise.
- `check-seams.mjs`: all five seams (1→2, 2→3, 3→4, 4→6, 6→7) are byte-identical at 1280 wide.
- Camera: peak screen speed per move, measured at 1920 wide, is 6–25 px per frame. The 4→6 pan peaks at 24.6 and 6→7
  at 15.2, both within the range of the earlier pans (up to 25.2 on 2→3).
- Stills and frame sheets (every 0.5–1 s) were inspected, along with strips of the ₱ build and the pie build.
- A numeric camera check found no speed discontinuities.
- **Playback was not watched directly;** the review is based on extracted frames and camera maths.

## Open items
- Nexa font files, if Nexa should replace Montserrat.
- An official DPWH logo (black and white), if the simplified emblem should be replaced.
- Voiceover timings, to retime the reveals and holds.
- Approval of the squares 6 and 7 icons, and of their provisional timings.
- The final 4K export after approval.
