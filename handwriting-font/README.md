# Julia Age 3

A font made from Julia's handwriting sheet, filled in at 3 years old.

![Sample](sample.png)

## Files

| File | Use |
|---|---|
| `fonts/JuliaAge3-Regular.otf` | Install on a Mac or PC (double-click it) |
| `fonts/JuliaAge3-Regular.ttf` | Same font with TrueType outlines, for apps that only take TTF |
| `fonts/JuliaAge3-Regular.woff2` | For web pages (`@font-face`) |
| `specimen.html` | The sample sheet above. Open it in a browser. |
| `source/julia-handwriting-sheet.jpg` | The photo the font was made from |
| `build_font.py` | Rebuilds all three fonts from the photo |

## What's in it

- **From her sheet:** `A–Z`, `a–z`, `0–9` and `? ! % & : ; . ,`
- **Added to fill gaps:** space, `' ’ ‘ " ” “` (her comma, raised or turned round), and `-` and `–`
  (drawn to match her marker stroke, since the sheet had no hyphen).
- **Not in it:** the rows she left blank on the sheet (`+ - ~ = ± # $ € £ ¢ [ ] ( ) { } < > \ / * @` and so on).
  Apps will show these in a fallback font.

## How it was made

1. The lighting in the photo is evened out, and the printed grid lines are found and fitted with curves,
   because the paper was not lying flat.
2. Each cell is straightened with its own perspective correction, and her marker strokes are cut out at 4×
   the photo's resolution. The printed labels and grid lines are thinner than the marker, so they are left out.
3. Each letter is traced into smooth outlines with potrace.
4. **Sizes are kept as she drew them** (her `a` is big and her `z` is tiny). One scale is used for the whole
   sheet, set so her typical capital letter is 0.7 em tall.
5. Every letter is set on a common baseline. `g j p q y` hang below the baseline by at least 30% of their
   height, because at three she mostly wrote them sitting on the line.
6. Spacing is even on both sides of each letter. Automatic kerning (about 1,800 pairs) closes the gaps that
   open shapes leave, such as after her `J`, `T` and `L`.

## Rebuild

```
pip install -r requirements.txt     # plus the potrace program (apt install potrace / brew install potrace)
python3 build_font.py               # writes fonts/ and build/ (extracted letters, kerning)
```

The sizing, baseline and spacing settings are at the top of the placement section of `build_font.py`.
