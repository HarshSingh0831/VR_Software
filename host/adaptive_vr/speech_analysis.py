from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any

from .commands import VoiceCommand, detect_command, normalize_transcript
from .features import SpeechFeatures


CONFUSION_PHRASES = (
    "i do not understand",
    "i don't understand",
    "i dont understand",
    "i do not know",
    "i don't know",
    "i dont know",
    "not clear",
    "समझ नहीं आया",
    "मुझे समझ नहीं आया",
    "मुझे नहीं पता",
    "पता नहीं",
    "samajh nahi aaya",
    "mujhe nahi pata",
)

REPEAT_PHRASES = (
    "repeat",
    "say again",
    "repeat that",
    "दोबारा",
    "फिर से",
    "दोबारा बोलो",
    "dobara",
    "phir se",
)

HELP_PHRASES = (
    "help",
    "i need help",
    "मदद",
    "मुझे मदद चाहिए",
    "madad",
)

HESITATIONS = ("um", "uh", "hmm", "erm", "अम्म", "हम्म", "मतलब")


@dataclass(frozen=True, slots=True)
class SpeechRecognitionEvent:
    timestamp_ms: int
    language: str
    transcript: str
    confidence: float
    partial: bool
    command: VoiceCommand | None
    confusion_keyword: bool
    repeat_request: bool
    help_request: bool
    hesitation_count: int

    def to_dict(self) -> dict[str, Any]:
        data = asdict(self)
        data["command"] = asdict(self.command) if self.command else None
        return data

    def to_features(self) -> SpeechFeatures:
        return SpeechFeatures(
            voice_active=bool(self.transcript),
            hesitation_count=self.hesitation_count,
            repeat_request=self.repeat_request,
            help_request=self.help_request,
            confusion_keyword=self.confusion_keyword,
            detected_command=self.command.action if self.command else None,
        )


def analyze_transcript(
    transcript: str,
    *,
    language: str,
    confidence: float,
    timestamp_ms: int,
    partial: bool = False,
    context: str | None = None,
) -> SpeechRecognitionEvent:
    normalized = normalize_transcript(transcript)
    contains = lambda phrases: any(phrase in normalized for phrase in phrases)
    hesitation_count = sum(normalized.split().count(word) for word in HESITATIONS)
    return SpeechRecognitionEvent(
        timestamp_ms=timestamp_ms,
        language=language,
        transcript=normalized,
        confidence=max(0.0, min(1.0, confidence)),
        partial=partial,
        command=None if partial else detect_command(normalized, context=context),
        confusion_keyword=contains(CONFUSION_PHRASES),
        repeat_request=contains(REPEAT_PHRASES),
        help_request=contains(HELP_PHRASES),
        hesitation_count=hesitation_count,
    )
