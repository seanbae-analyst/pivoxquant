# Monthly Brag Card — Font Bundle

`MonthlyBragService.render_png()` looks for three font files in this
directory. If none are present it falls back to PIL's built-in bitmap
font — the PNG still renders, but with limited typography quality.

## Required files

| Filename                      | Usage                          | License |
|-------------------------------|--------------------------------|---------|
| `Pretendard-Bold.otf`         | Hero return percentage, 220pt  | SIL OFL |
| `Pretendard-Regular.otf`      | Name / meta / watermark        | SIL OFL |
| `SourceSerif-Regular.otf`     | Month label, 56pt              | SIL OFL |

## Download

- **Pretendard** — https://github.com/orioncactus/pretendard/releases
  - Grab `Pretendard-1.3.x.zip` → copy `Pretendard-Bold.otf` and
    `Pretendard-Regular.otf` here.
- **Source Serif** — https://fonts.google.com/specimen/Source+Serif+4
  - Download → copy `SourceSerif4-Regular.ttf` (rename the extension
    to `.otf` or update the loader to accept `.ttf`).

Both licenses (SIL Open Font License) permit redistribution in a
commercial SaaS. Once the files are in place, no runtime download or
network I/O is required — the PNG renderer reads from disk.

## License files

When committing the font files, also include their LICENSE.txt copies
in this directory. Pillow doesn't enforce the license, but our
legal checklist (`memory/legal_licenses.md`) does.
