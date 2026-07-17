from __future__ import annotations

import argparse
import array
import json
import time

from .speech_live import _imports, list_input_devices


def main() -> None:
    parser = argparse.ArgumentParser(description="Check microphone availability and input level")
    parser.add_argument("--device", type=int)
    parser.add_argument("--seconds", type=float, default=3.0)
    args = parser.parse_args()
    sounddevice, _, _, _ = _imports()
    if args.device is None:
        print(json.dumps(list_input_devices(), indent=2, ensure_ascii=False))
        print("Pass --device INDEX to test a specific microphone.")
        return
    samples = array.array("h")
    deadline = time.monotonic() + args.seconds
    with sounddevice.RawInputStream(
        samplerate=16_000,
        blocksize=2000,
        device=args.device,
        dtype="int16",
        channels=1,
    ) as stream:
        while time.monotonic() < deadline:
            data, _ = stream.read(2000)
            samples.extend(array.array("h", bytes(data)))
    peak = max((abs(value) for value in samples), default=0)
    mean = sum(abs(value) for value in samples) / len(samples) if samples else 0.0
    print(json.dumps({"device": args.device, "samples": len(samples), "peak": peak, "mean_absolute": mean}))
    if peak < 100:
        print("Input is nearly silent. Check microphone mute/privacy settings and speak during the test.")


if __name__ == "__main__":
    main()
