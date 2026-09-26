"""Rebuild every output from data/processed: phases 1–3, the Excel workbook, site assets and the technical note."""

import shutil
import subprocess
from pathlib import Path

from lifemodel import excel_build, run_phase1, run_phase2, run_phase3

ROOT = Path(__file__).resolve().parents[2]
CHROME = Path("/Applications/Google Chrome.app/Contents/MacOS/Google Chrome")


def copy_site_assets():
    """Charts and the Excel workbook are published with the project page."""
    dest = ROOT / "site" / "assets" / "charts"
    dest.mkdir(parents=True, exist_ok=True)
    for png in (ROOT / "outputs" / "charts").glob("*.png"):
        shutil.copy2(png, dest / png.name)
    shutil.copy2(ROOT / "excel" / "single_policy_check.xlsx", ROOT / "site" / "assets" / "single_policy_check.xlsx")


def render_technical_note():
    """report/technical_note.html → PDF with headless Chrome (skipped if Chrome is not installed)."""
    html = ROOT / "report" / "technical_note.html"
    if not (html.exists() and CHROME.exists()):
        print("Technical note PDF skipped (no HTML or no Chrome).")
        return
    pdf = ROOT / "report" / "technical_note.pdf"
    subprocess.run([str(CHROME), "--headless=new", "--disable-gpu", "--no-pdf-header-footer",
                    f"--print-to-pdf={pdf}", html.as_uri()], check=True, capture_output=True)
    shutil.copy2(pdf, ROOT / "site" / "technical_note.pdf")


def main():
    run_phase1.main()
    run_phase2.main()
    run_phase3.main()
    excel_build.build()
    copy_site_assets()
    render_technical_note()
    print("All outputs rebuilt.")


if __name__ == "__main__":
    main()
