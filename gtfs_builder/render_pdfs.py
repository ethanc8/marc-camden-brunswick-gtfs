"""Render every page of every source PDF to a PNG, for eyeballing a cell in
extracted/*.csv against the actual brochure. Requires poppler's pdftoppm
(pulled in via pixi from conda-forge)."""

import argparse
import subprocess
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
SOURCE_PDF_DIR = REPO_ROOT / "source-pdf"


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out-dir", type=Path, default=REPO_ROOT / "build" / "pdf-preview")
    parser.add_argument("--dpi", type=int, default=150)
    args = parser.parse_args()
    args.out_dir.mkdir(parents=True, exist_ok=True)

    for pdf_path in sorted(SOURCE_PDF_DIR.glob("*.pdf")):
        prefix = args.out_dir / pdf_path.stem
        subprocess.run(
            ["pdftoppm", "-png", "-r", str(args.dpi), str(pdf_path), str(prefix)],
            check=True,
        )
        print(f"rendered {pdf_path.name}")


if __name__ == "__main__":
    main()
