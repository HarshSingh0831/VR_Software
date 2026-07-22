from __future__ import annotations

import argparse
import json
from pathlib import Path
import queue
import sys
import time
from typing import Any

from .commands import build_command_event
from .speech_analysis import analyze_transcript


DEFAULT_MODELS = {
    "en": Path("models/vosk-model-small-en-us-0.15"),
    "hi": Path("models/vosk-model-small-hi-0.22"),
}

ENGLISH_GRAMMAR = [
    "play", "resume", "continue", "play video", "pause", "stop", "pause video",
    "next", "next video", "back", "previous video", "replay this part",
    "restart video", "forward ten seconds", "go back ten seconds",
    "yes", "no", "not sure", "repeat", "say again", "help", "i need help",
    "option a", "option b", "option c", "option d", "submit answer",
    "repeat the question", "show hint", "skip question",
    "volume up", "volume down", "mute audio", "unmute audio",
    "show subtitles", "hide subtitles", "start lesson", "end lesson",
    "i do not understand", "i don't understand", "i do not know",
    "one", "two", "three", "four", "five", "[unk]",
]

HINDI_GRAMMAR = [
    "चलाओ", "शुरू करो", "वीडियो चलाओ", "रोको", "रोक दो", "वीडियो रोक दो",
    "अगला", "आगे", "वापस", "पीछे", "हाँ", "हां", "नहीं", "पता नहीं",
    "दोबारा", "फिर से", "मदद", "मुझे मदद चाहिए",
    "ऑप्शन ए", "ऑप्शन बी", "ऑप्शन सी", "ऑप्शन डी",
    "हिंट दो", "सवाल दोबारा बोलो", "वॉल्यूम बढ़ाओ", "वॉल्यूम कम करो",
    "आवाज़ बंद करो", "आवाज़ चालू करो", "सबटाइटल दिखाओ", "सबटाइटल हटाओ",
    "लेसन शुरू करो", "लेसन खत्म करो",
    "समझ नहीं आया", "मुझे समझ नहीं आया", "मुझे नहीं पता",
    "एक", "दो", "तीन", "चार", "पांच", "[unk]",
]


def _imports():
    try:
        import sounddevice as sounddevice
        from vosk import KaldiRecognizer, Model, SetLogLevel
    except ImportError as exc:
        raise RuntimeError(
            "Live speech dependencies are missing. Install the speech optional dependencies."
        ) from exc
    return sounddevice, KaldiRecognizer, Model, SetLogLevel


def list_input_devices() -> list[dict[str, Any]]:
    sounddevice, _, _, _ = _imports()
    devices = []
    for index, item in enumerate(sounddevice.query_devices()):
        if item["max_input_channels"] > 0:
            devices.append(
                {
                    "index": index,
                    "name": item["name"],
                    "channels": item["max_input_channels"],
                    "default_samplerate": item["default_samplerate"],
                }
            )
    return devices


class LiveSpeechRecognizer:
    def __init__(
        self,
        *,
        language: str,
        model_paths: dict[str, Path] | None = None,
        sample_rate: int = 16_000,
        device: int | str | None = None,
        context: str | None = None,
        session_id: str = "development_session",
        output_path: Path | None = None,
    ):
        if language not in {"en", "hi", "auto"}:
            raise ValueError("language must be en, hi, or auto")
        sounddevice, recognizer_class, model_class, set_log_level = _imports()
        set_log_level(-1)
        self.sounddevice = sounddevice
        self.sample_rate = sample_rate
        self.device = device
        self.context = context
        self.session_id = session_id
        self.output_path = Path(output_path) if output_path else None
        if self.output_path is not None:
            self.output_path.parent.mkdir(parents=True, exist_ok=True)
            self.output_path.touch(exist_ok=True)
        self.audio_queue: queue.Queue[bytes] = queue.Queue(maxsize=30)
        paths = model_paths or DEFAULT_MODELS
        languages = ("en", "hi") if language == "auto" else (language,)
        self.recognizers = {}
        for code in languages:
            path = Path(paths[code])
            if not path.exists():
                raise FileNotFoundError(f"Missing {code} Vosk model: {path}")
            grammar = ENGLISH_GRAMMAR if code == "en" else HINDI_GRAMMAR
            self.recognizers[code] = recognizer_class(
                model_class(str(path)),
                sample_rate,
                json.dumps(grammar, ensure_ascii=False),
            )

    def _callback(self, indata, frames, callback_time, status) -> None:
        if status:
            print(f"Audio warning: {status}", file=sys.stderr)
        try:
            self.audio_queue.put_nowait(bytes(indata))
        except queue.Full:
            try:
                self.audio_queue.get_nowait()
                self.audio_queue.put_nowait(bytes(indata))
            except queue.Empty:
                pass

    @staticmethod
    def _confidence(result: dict[str, Any]) -> float:
        words = result.get("result", [])
        values = [float(word.get("conf", 0.0)) for word in words]
        return sum(values) / len(values) if values else (0.5 if result.get("text") else 0.0)

    def run(self) -> None:
        print("Listening offline. Press Ctrl+C to stop.")
        with self.sounddevice.RawInputStream(
            samplerate=self.sample_rate,
            blocksize=4000,
            device=self.device,
            dtype="int16",
            channels=1,
            callback=self._callback,
        ):
            while True:
                audio = self.audio_queue.get()
                completed = []
                for language, recognizer in self.recognizers.items():
                    if recognizer.AcceptWaveform(audio):
                        result = json.loads(recognizer.Result())
                        if result.get("text"):
                            completed.append((self._confidence(result), language, result["text"]))
                if not completed:
                    continue
                confidence, language, transcript = max(completed)
                event = analyze_transcript(
                    transcript,
                    language=language,
                    confidence=confidence,
                    timestamp_ms=time.time_ns() // 1_000_000,
                    context=self.context,
                )
                output = event.to_dict()
                if event.command:
                    output["command_event"] = build_command_event(
                        event.command,
                        session_id=self.session_id,
                        recognized_text=event.transcript,
                        detected_language=event.language,
                        timestamp_ms=event.timestamp_ms,
                    ).to_dict()
                serialized = json.dumps(output, ensure_ascii=False)
                print(json.dumps(output, ensure_ascii=True), flush=True)
                if self.output_path is not None:
                    self.output_path.parent.mkdir(parents=True, exist_ok=True)
                    with self.output_path.open("a", encoding="utf-8") as stream:
                        stream.write(serialized + "\n")


def main() -> None:
    parser = argparse.ArgumentParser(description="Offline English/Hindi live speech recognition")
    parser.add_argument("--language", choices=["en", "hi", "auto"], default="auto")
    parser.add_argument("--context", choices=["confusion", "quiz"])
    parser.add_argument("--session-id", default="development_session")
    parser.add_argument("--device", help="Input device index or name")
    parser.add_argument("--list-devices", action="store_true")
    parser.add_argument("--english-model", type=Path, default=DEFAULT_MODELS["en"])
    parser.add_argument("--hindi-model", type=Path, default=DEFAULT_MODELS["hi"])
    parser.add_argument("--output", type=Path, help="Append recognized events as JSON Lines")
    args = parser.parse_args()
    if args.list_devices:
        print(json.dumps(list_input_devices(), indent=2, ensure_ascii=False))
        return
    device: int | str | None = args.device
    if isinstance(device, str) and device.isdigit():
        device = int(device)
    service = LiveSpeechRecognizer(
        language=args.language,
        model_paths={"en": args.english_model, "hi": args.hindi_model},
        device=device,
        context=args.context,
        session_id=args.session_id,
        output_path=args.output,
    )
    try:
        service.run()
    except KeyboardInterrupt:
        print("\nStopped.")


if __name__ == "__main__":
    main()
