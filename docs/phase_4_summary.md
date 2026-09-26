# Phase 4 summary — packaging

Status: **done.** Every claim on the README, project page and technical note is taken from `outputs/tables/` or a test.

- `README.md`: business question, six key findings, charts, model map, validation, limitations, how to run.
- `report/technical_note.html` → `report/technical_note.pdf` (7 pages, A4; rendered with headless Chrome).
- `site/`: one-page project site (Overview · Pricing · Experience · Solvency II · IFRS 17 · Change · Validation · Limitations) with charts, the PDF and the Excel workbook; checked at 1280 px and 375 px (no horizontal scroll, all 13 assets load). `.github/workflows/deploy-pages.yml` publishes `site/` to the `gh-pages` branch on push (as in the shipping-insurance project).
- `lifemodel.build_all`: one command rebuilds phases 1–3, the Excel workbook, site assets and the PDF (~1 minute).

Owner action: GitHub → Settings → Pages → Source "Deploy from a branch", branch `gh-pages` / root (once).
