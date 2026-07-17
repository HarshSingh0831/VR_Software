from __future__ import annotations

from dataclasses import asdict, dataclass, field
import re
import time
import unicodedata
from uuid import uuid4


@dataclass(frozen=True, slots=True)
class VoiceCommand:
    action: str
    matched_phrase: str
    confidence: float


@dataclass(frozen=True, slots=True)
class CommandDefinition:
    aliases: tuple[str, ...]
    contexts: frozenset[str] = field(default_factory=frozenset)


COMMANDS = {
    "PLAY": CommandDefinition(("play", "play video", "start video", "video chalao", "shuru karo", "video start karo", "चलाओ", "वीडियो चलाओ", "शुरू करो")),
    "PAUSE": CommandDefinition(("pause", "pause video", "stop for now", "video roko", "video rok do", "thodi der roko", "pause karo", "रोको", "वीडियो रोक दो", "थोड़ी देर रोको")),
    "RESUME": CommandDefinition(("resume", "continue", "continue video", "aage chalao", "continue karo", "video wapas chalao", "आगे चलाओ", "जारी रखो")),
    "STOP": CommandDefinition(("stop", "stop video", "video band karo", "rok do", "वीडियो बंद करो", "रोक दो")),
    "NEXT": CommandDefinition(("next", "next video", "continue to next", "agla video", "agla video chalao", "aage badho", "next pe jao", "अगला वीडियो", "अगला वीडियो चलाओ", "आगे बढ़ो")),
    "BACK": CommandDefinition(("back", "previous video", "peeche jao", "pichla video chalao", "पीछे जाओ", "पिछला वीडियो चलाओ")),
    "REPLAY_SEGMENT": CommandDefinition(("replay this part", "play this part again", "ye part dobara chalao", "is part ko repeat karo", "ये पार्ट दोबारा चलाओ", "इस पार्ट को दोहराओ")),
    "RESTART_VIDEO": CommandDefinition(("restart video", "start from beginning", "video shuru se chalao", "video dobara start karo", "वीडियो शुरू से चलाओ")),
    "SEEK_FORWARD": CommandDefinition(("forward ten seconds", "go forward", "das second aage karo", "thoda aage karo", "दस सेकंड आगे करो", "थोड़ा आगे करो")),
    "SEEK_BACKWARD": CommandDefinition(("go back ten seconds", "rewind", "das second peeche karo", "thoda peeche karo", "दस सेकंड पीछे करो", "थोड़ा पीछे करो")),
    "HELP": CommandDefinition(("help", "i need help", "mujhe help chahiye", "meri madad karo", "मुझे मदद चाहिए", "मेरी मदद करो")),
    "CONFUSION_YES": CommandDefinition(("yes", "yes i am confused", "explain it", "haan", "haan mujhe confusion hai", "haan samajh nahi aaya", "हाँ", "हाँ मुझे समझ नहीं आया"), frozenset({"confusion"})),
    "CONFUSION_NO": CommandDefinition(("no", "no continue", "i understand", "nahi", "nahi continue karo", "mujhe samajh aa gaya", "नहीं", "मुझे समझ आ गया"), frozenset({"confusion"})),
    "CONFUSION_UNSURE": CommandDefinition(("not sure", "maybe", "i am not certain", "pata nahi", "shayad", "thoda confusion hai", "पता नहीं", "शायद", "थोड़ा कन्फ्यूजन है"), frozenset({"confusion"})),
    "SHOW_MINI_TUTORIAL": CommandDefinition(("show the tutorial", "explain this", "chhota tutorial dikhao", "isko explain karo", "mujhe samjhao", "छोटा ट्यूटोरियल दिखाओ", "मुझे समझाओ")),
    "REPEAT_EXPLANATION": CommandDefinition(("explain again", "repeat explanation", "dobara samjhao", "explanation repeat karo", "दोबारा समझाओ")),
    "SHOW_SIMPLER_EXPLANATION": CommandDefinition(("explain it simply", "make it easier", "aasan language mein samjhao", "simple karke samjhao", "आसान तरीके से समझाओ")),
    "RETURN_TO_MAIN_VIDEO": CommandDefinition(("return to the lesson", "continue main video", "main video par wapas jao", "lesson continue karo", "मेन वीडियो पर वापस जाओ")),
    "ANSWER_A": CommandDefinition(("option a", "answer a", "mera answer a hai", "मेरा उत्तर ए है"), frozenset({"quiz"})),
    "ANSWER_B": CommandDefinition(("option b", "answer b", "mera answer b hai", "मेरा उत्तर बी है"), frozenset({"quiz"})),
    "ANSWER_C": CommandDefinition(("option c", "answer c", "mera answer c hai", "मेरा उत्तर सी है"), frozenset({"quiz"})),
    "ANSWER_D": CommandDefinition(("option d", "answer d", "mera answer d hai", "मेरा उत्तर डी है"), frozenset({"quiz"})),
    "SUBMIT_ANSWER": CommandDefinition(("submit answer", "confirm answer", "answer submit karo", "answer lock karo", "उत्तर जमा करो"), frozenset({"quiz"})),
    "CHANGE_ANSWER": CommandDefinition(("change my answer", "mera answer change karo", "मेरा उत्तर बदलो"), frozenset({"quiz"})),
    "REPEAT_QUESTION": CommandDefinition(("repeat the question", "question dobara bolo", "sawal repeat karo", "सवाल दोबारा बोलो"), frozenset({"quiz"})),
    "SHOW_HINT": CommandDefinition(("show hint", "give me a hint", "hint do", "mujhe hint chahiye", "हिंट दो"), frozenset({"quiz"})),
    "SKIP_QUESTION": CommandDefinition(("skip question", "question skip karo", "सवाल छोड़ो"), frozenset({"quiz"})),
    "CONTINUE_AFTER_QUIZ": CommandDefinition(("continue lesson", "lesson continue karo", "aage chalo", "लेसन जारी रखो"), frozenset({"quiz"})),
    "VOLUME_UP": CommandDefinition(("increase volume", "volume up", "volume badhao", "aawaz tez karo", "वॉल्यूम बढ़ाओ", "आवाज़ तेज करो")),
    "VOLUME_DOWN": CommandDefinition(("decrease volume", "volume down", "volume kam karo", "aawaz dheemi karo", "वॉल्यूम कम करो", "आवाज़ धीमी करो")),
    "MUTE": CommandDefinition(("mute audio", "aawaz band karo", "mute karo", "आवाज़ बंद करो")),
    "UNMUTE": CommandDefinition(("unmute audio", "aawaz chalu karo", "unmute karo", "आवाज़ चालू करो")),
    "CAPTIONS_ON": CommandDefinition(("turn on captions", "show subtitles", "captions chalu karo", "subtitles dikhao", "सबटाइटल दिखाओ")),
    "CAPTIONS_OFF": CommandDefinition(("turn off captions", "hide subtitles", "captions band karo", "subtitles hatao", "सबटाइटल हटाओ")),
    "START_SESSION": CommandDefinition(("start lesson", "begin session", "lesson start karo", "session shuru karo", "लेसन शुरू करो")),
    "PAUSE_SESSION": CommandDefinition(("pause session", "session pause karo", "lesson abhi roko", "सेशन रोक दो")),
    "RESUME_SESSION": CommandDefinition(("resume session", "session continue karo", "lesson wapas chalao", "सेशन जारी रखो")),
    "END_SESSION": CommandDefinition(("end lesson", "finish session", "lesson khatam karo", "session end karo", "लेसन खत्म करो")),
    "COMPLETE_LESSON": CommandDefinition(("complete lesson", "lesson complete karo", "लेसन पूरा करो")),
}

VALID_COMMAND_SOURCES = frozenset(
    {
        "student_voice",
        "vr_controller",
        "confusion_detector",
        "adaptation_manager",
        "quiz_manager",
        "system",
    }
)


@dataclass(frozen=True, slots=True)
class CommandEvent:
    command_id: str
    session_id: str
    source: str
    command: str
    recognized_text: str
    detected_language: str
    confidence: float
    timestamp_ms: int
    parameters: dict[str, object] = field(default_factory=dict)

    def to_dict(self) -> dict[str, object]:
        return asdict(self)


def normalize_transcript(text: str) -> str:
    text = unicodedata.normalize("NFC", text.lower())
    cleaned = []
    for character in text:
        category = unicodedata.category(character)
        if character.isalnum() or category.startswith("M") or character == "'":
            cleaned.append(character)
        else:
            cleaned.append(" ")
    return " ".join("".join(cleaned).split())


def _contains_phrase(normalized: str, phrase: str) -> bool:
    if phrase.isascii():
        return bool(re.search(rf"\b{re.escape(phrase)}\b", normalized))
    return phrase in normalized


def detect_command(text: str, *, context: str | None = None) -> VoiceCommand | None:
    normalized = normalize_transcript(text)
    if not normalized:
        return None
    matches: list[tuple[int, str, str]] = []
    for action, definition in COMMANDS.items():
        if definition.contexts and context not in definition.contexts:
            continue
        for phrase in definition.aliases:
            if _contains_phrase(normalized, phrase):
                matches.append((len(phrase), action, phrase))
    if not matches:
        return None
    _, action, phrase = max(matches)
    confidence = 1.0 if normalized == phrase else 0.85
    return VoiceCommand(action, phrase, confidence)


def build_command_event(
    command: VoiceCommand,
    *,
    session_id: str,
    recognized_text: str,
    detected_language: str,
    source: str = "student_voice",
    timestamp_ms: int | None = None,
    parameters: dict[str, object] | None = None,
) -> CommandEvent:
    if source not in VALID_COMMAND_SOURCES:
        raise ValueError(f"Invalid command source: {source}")
    return CommandEvent(
        command_id=f"cmd_{uuid4().hex[:12]}",
        session_id=session_id,
        source=source,
        command=command.action,
        recognized_text=recognized_text,
        detected_language=detected_language,
        confidence=command.confidence,
        timestamp_ms=timestamp_ms if timestamp_ms is not None else time.time_ns() // 1_000_000,
        parameters=parameters or {},
    )
