import hashlib
import msvcrt
import time
from pathlib import Path

from PIL import Image, ImageGrab


class SkipImage(Exception):
    pass


def read_image_from_clipboard() -> Image.Image:
    clipboard = ImageGrab.grabclipboard()
    assert isinstance(clipboard, Image.Image), "Clipboard does not contain an image"
    return clipboard


def image_signature(image: Image.Image) -> str:
    # Normalize color model before hashing so equivalent images compare reliably.
    normalized = image.convert("RGBA")
    return hashlib.sha256(normalized.tobytes()).hexdigest()


def wait_for_new_clipboard_image(
    baseline_signature: str, poll_seconds: float = 0.25
) -> tuple[Image.Image, str]:
    print("Waiting for new clipboard image. Press Enter to skip...")

    while True:
        if msvcrt.kbhit():
            key = msvcrt.getwch()
            if key == "\r":
                raise SkipImage()

        clipboard = ImageGrab.grabclipboard()
        if isinstance(clipboard, Image.Image):
            image = clipboard
            signature = image_signature(image)
            if signature != baseline_signature:
                return image, signature

        time.sleep(poll_seconds)


def main() -> None:
    src_dir = Path(__file__).parent.parent / "robot/tests/images"
    dest_dir = Path(__file__).parent.parent / "robot/tests/images_new"

    for src_path in sorted(src_dir.rglob("*.png")):
        dest_path = dest_dir / src_path.relative_to(src_dir)

        if dest_path.exists():
            print(f"\nSkipping existing file: {dest_path}")
            continue

        print(f"\nRetake screenshot for: {src_path}")

        baseline_clipboard = ImageGrab.grabclipboard()
        baseline_signature = (
            image_signature(baseline_clipboard)
            if isinstance(baseline_clipboard, Image.Image)
            else ""
        )

        try:
            image, _ = wait_for_new_clipboard_image(baseline_signature)
        except SkipImage:
            print("Skipped by user.")
            continue

        dest_path.parent.mkdir(parents=True, exist_ok=True)
        image.save(dest_path, format="PNG")
        print(f"Saved: {dest_path}")


if __name__ == "__main__":
    main()
