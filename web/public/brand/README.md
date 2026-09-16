# Brand assets

Put the Scope Dental Practice logo here as `logo.png`. It appears in the app header. Until the file
exists, the header shows the tooth mark instead.

- The practice logo is white, so the header places it on a dark tile. If you use a dark or coloured
  logo, set `logoOnDark: false` in `web/src/lib/brand.ts`.
- Recommended: a transparent PNG or SVG about 2:1 wide (e.g. 768×384). To use SVG, save it as
  `logo.svg` and update `logo` in `brand.ts`.
- Optional: replace `web/src/app/icon.svg` with the practice's icon for the browser tab.
