"""Product photos for partner storefronts live in src/web/store-products/.

Images are studio product photographs (JPG) matched to each catalog item.
Regenerate via the asset pipeline if images need to be refreshed.
"""

from __future__ import annotations

from pathlib import Path

STORE_DIR = Path(__file__).resolve().parents[1] / "src" / "web" / "store-products"

if __name__ == "__main__":
    files = sorted(STORE_DIR.glob("*.jpg"))
    print(f"{len(files)} product photos in {STORE_DIR}")
    for f in files:
        print(f"  {f.name} ({f.stat().st_size // 1024} KB)")
