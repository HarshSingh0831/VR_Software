from __future__ import annotations

import hashlib
import json
import lzma
from pathlib import Path


WORKSPACE = Path(__file__).resolve().parent.parent
SOURCE = (
    WORKSPACE
    / ".downloads"
    / "2026-06-18-raspios-trixie-arm64-lite.img.xz"
)
DESTINATION = (
    WORKSPACE
    / ".downloads"
    / "2026-06-18-raspios-trixie-arm64-lite.img"
)
EXPECTED_SIZE = 2_977_955_840
CHUNK_SIZE = 4 * 1024 * 1024
PROGRESS_INTERVAL = 256 * 1024 * 1024


def main() -> None:
    digest = hashlib.sha256()
    bytes_written = 0
    next_progress = PROGRESS_INTERVAL

    with lzma.open(SOURCE, "rb") as compressed, DESTINATION.open("wb") as image:
        while chunk := compressed.read(CHUNK_SIZE):
            image.write(chunk)
            digest.update(chunk)
            bytes_written += len(chunk)

            if bytes_written >= next_progress:
                print(
                    f"Expanded {bytes_written / (1024**3):.2f} GiB "
                    f"of {EXPECTED_SIZE / (1024**3):.2f} GiB",
                    flush=True,
                )
                next_progress += PROGRESS_INTERVAL

        image.flush()

    if bytes_written != EXPECTED_SIZE:
        DESTINATION.unlink(missing_ok=True)
        raise RuntimeError(
            f"Unexpected expanded size: {bytes_written}; expected {EXPECTED_SIZE}"
        )

    result = {
        "source": str(SOURCE),
        "destination": str(DESTINATION),
        "size": bytes_written,
        "sha256": digest.hexdigest(),
    }
    print(json.dumps(result, indent=2), flush=True)


if __name__ == "__main__":
    main()
