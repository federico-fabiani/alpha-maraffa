"""
Genera le icone PWA e la favicon a partire da un'immagine sorgente.

Uso:
    uv run python src/scripts/generate_icons.py <immagine>
    uv run python src/scripts/generate_icons.py <immagine> --out ../../game/frontend/public

L'immagine sorgente dovrebbe essere almeno 512×512 px.
Output di default: ../../game/frontend/public/
"""

import argparse
import sys
from pathlib import Path

from PIL import Image


ICON_SIZES = [72, 96, 128, 144, 152, 192, 384, 512]
APPLE_TOUCH_SIZE = 180
FAVICON_SIZES = [16, 32, 48]  # dimensioni incluse nel .ico multi-layer


def open_source(path: Path) -> Image.Image:
    img = Image.open(path).convert("RGBA")
    w, h = img.size
    if w < 512 or h < 512:
        print(f"[warn] immagine sorgente {w}×{h} px — consigliato almeno 512×512")
    return img


def crop_square(img: Image.Image) -> Image.Image:
    w, h = img.size
    if w == h:
        return img
    side = min(w, h)
    left = (w - side) // 2
    top = (h - side) // 2
    return img.crop((left, top, left + side, top + side))


def resize(img: Image.Image, size: int) -> Image.Image:
    return img.resize((size, size), Image.LANCZOS)


def save_png(img: Image.Image, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    img.save(path, format="PNG", optimize=True)
    kb = path.stat().st_size / 1024
    print(f"  {path}  ({kb:.1f} KB)")


def save_ico(img: Image.Image, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    layers = [img.resize((s, s), Image.LANCZOS).convert("RGBA") for s in FAVICON_SIZES]
    layers[0].save(path, format="ICO", sizes=[(s, s) for s in FAVICON_SIZES],
                   append_images=layers[1:])
    kb = path.stat().st_size / 1024
    print(f"  {path}  ({kb:.1f} KB)")


def main() -> None:
    parser = argparse.ArgumentParser(description="Genera icone PWA dalla sorgente")
    parser.add_argument("source", type=Path, help="Immagine sorgente (PNG/JPG/…)")
    parser.add_argument(
        "--out",
        type=Path,
        default=Path(__file__).resolve().parents[4] / "game" / "frontend" / "public",
        help="Directory di output (default: game/frontend/public/)",
    )
    args = parser.parse_args()

    if not args.source.exists():
        print(f"Errore: file non trovato — {args.source}", file=sys.stderr)
        sys.exit(1)

    out: Path = args.out
    icons_dir = out / "icons"

    print(f"Sorgente : {args.source}")
    print(f"Output   : {out}")
    print()

    src = crop_square(open_source(args.source))

    print("Icone PWA:")
    for size in ICON_SIZES:
        save_png(resize(src, size), icons_dir / f"icon-{size}x{size}.png")

    print("\nApple Touch Icon:")
    save_png(resize(src, APPLE_TOUCH_SIZE), icons_dir / "apple-touch-icon.png")

    print("\nFavicon:")
    # Salva anche favicon.png (usata da alcuni browser moderni)
    save_png(resize(src, 32), out / "favicon.png")
    save_ico(src, out / "favicon.ico")

    print("\nFatto.")


if __name__ == "__main__":
    main()
