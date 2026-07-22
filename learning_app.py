from __future__ import annotations

from io import BytesIO
import array
import hashlib
import json
from pathlib import Path
import threading
import time
from uuid import uuid4
import wave

import pandas as pd
import streamlit as st

from adaptive_vr.commands import build_command_event
from adaptive_vr.cnn_inference import UpperFaceCnnPredictor
from adaptive_vr.dashboard_pi import PiConnectionError, PiGateway
from adaptive_vr.learning_log import append_learning_event, summarize_learning_events
from adaptive_vr.speech_analysis import analyze_transcript


st.set_page_config(
    page_title="Adaptive VR learning studio",
    page_icon=":material/school:",
    layout="wide",
)

PROJECT_ROOT = Path(__file__).resolve().parent
QUIZ_PATH = PROJECT_ROOT / "config" / "learning_quiz.json"
CONTENT_CONFIG_PATH = PROJECT_ROOT / "config" / "learning_content.json"
EVENT_ROOT = PROJECT_ROOT / "data" / "learning_sessions"
LIVE_SPEECH_PATH = PROJECT_ROOT / "data" / "live_speech" / "events.jsonl"
CONTENT_REPOSITORY_URL = "https://github.com/Chenikachhabra/cogniverse"
PI_KEY = PROJECT_ROOT / ".rpi-provisioning" / "private" / "adaptive_vr_pi_ed25519"
MODEL_PATHS = {
    "English": PROJECT_ROOT / "models" / "vosk-model-small-en-us-0.15",
    "Hindi": PROJECT_ROOT / "models" / "vosk-model-small-hi-0.22",
}
PHONE_CA_CERT_PATH = PROJECT_ROOT / "certs" / "adaptive_vr_local_ca.cer"
LABELS = ["focused", "confused", "happy", "bored", "drowsy"]
ANSWER_COMMANDS = {"ANSWER_A": 0, "ANSWER_B": 1, "ANSWER_C": 2, "ANSWER_D": 3}


@st.cache_resource
def shared_dashboard_bus() -> dict[str, object]:
    return {
        "lock": threading.Lock(),
        "version": 0,
        "origin": "",
        "state": {},
    }

PLAYER_CONTROLLER = st.components.v2.component(
    "adaptive_vr_video_controller",
    html="""
    <div id="player-command-status" role="status">Video controller ready</div>
    """,
    css="""
    #player-command-status {
        color: var(--st-text-color);
        background: var(--st-secondary-background-color);
        border: 1px solid var(--st-border-color);
        border-radius: var(--st-border-radius);
        padding: 0.55rem 0.75rem;
        font-size: 0.9rem;
    }
    """,
    js="""
    const controllerStates = new WeakMap()

    export default function(component) {
      const { data, parentElement, setTriggerValue } = component
      const status = parentElement.querySelector("#player-command-status")
      const token = data?.token
      let cancelled = false
      let state = controllerStates.get(parentElement)
      if (!state) {
        state = { appliedToken: null, shown: new Set(), quizEvents: new Set(), emotion: data?.emotion ?? "focused" }
        controllerStates.set(parentElement, state)
      }
      state.emotion = data?.emotion ?? state.emotion

      const applyCommand = (attempt = 0) => {
        if (cancelled) return
        const video = document.querySelector("video")
        if (!video) {
          if (attempt < 50) {
            window.setTimeout(() => applyCommand(attempt + 1), 100)
          } else if (status) {
            status.textContent = "Video controller could not find the player"
          }
          return
        }

        const command = data?.command ?? "ready"
        const show = (message) => { if (status) status.textContent = message }
        if (state.lastContent !== data?.content_id) {
          state.lastContent = data?.content_id
          if (data?.content_id === "main") {
            const saved = Number(window.sessionStorage.getItem("adaptive-vr-main-position") || 0)
            if (saved > 0 && Number.isFinite(saved)) video.currentTime = saved
          }
        }

        if (state.appliedToken !== token && command === "play") {
          video.play()
            .then(() => show("PLAY applied to video"))
            .catch(() => show("Tap the video once to allow playback, then say Play again"))
        } else if (state.appliedToken !== token && command === "pause") {
          video.pause()
          show("PAUSE applied to video")
        } else if (state.appliedToken !== token && command === "stop") {
          video.pause()
          video.currentTime = 0
          show("STOP applied to video — returned to 0:00")
        } else if (state.appliedToken !== token && command === "replay_10") {
          video.currentTime = Math.max(0, video.currentTime - 10)
          show("REPLAY applied — moved back 10 seconds")
        } else if (state.appliedToken !== token && command === "forward_10") {
          video.currentTime = Math.min(video.duration || Infinity, video.currentTime + 10)
          show("FORWARD applied — moved ahead 10 seconds")
        } else if (state.appliedToken !== token && command === "restart") {
          video.currentTime = 0
          video.play()
            .then(() => show("RESTART applied to video"))
            .catch(() => show("Returned to 0:00; tap video once to allow playback"))
        } else if (state.appliedToken !== token && command === "volume_up") {
          video.muted = false
          video.volume = Math.min(1, video.volume + 0.1)
          show(`VOLUME UP applied — ${Math.round(video.volume * 100)}%`)
        } else if (state.appliedToken !== token && command === "volume_down") {
          video.volume = Math.max(0, video.volume - 0.1)
          show(`VOLUME DOWN applied — ${Math.round(video.volume * 100)}%`)
        } else if (state.appliedToken !== token && command === "mute") {
          video.muted = true
          show("MUTE applied to video")
        } else if (state.appliedToken !== token && command === "unmute") {
          video.muted = false
          show("UNMUTE applied to video")
        } else if (state.appliedToken !== token) {
          show("Video controller ready")
        }
        state.appliedToken = token

        const videoHost = video.parentElement
        if (!videoHost || data?.content_id !== "main") return
        videoHost.style.position = "relative"
        const popup = document.createElement("button")
        popup.type = "button"
        popup.setAttribute("aria-label", "Open suggested subcontent")
        Object.assign(popup.style, {
          position: "absolute", top: "10px", left: "10px", zIndex: "30",
          display: "none", maxWidth: "150px", padding: "5px 9px",
          border: "1px solid rgba(255,255,255,.32)", borderRadius: "7px",
          background: "rgba(8,12,20,.88)", color: "white", fontSize: "12px",
          fontWeight: "600", lineHeight: "1.2", cursor: "pointer",
          boxShadow: "0 2px 8px rgba(0,0,0,.3)", whiteSpace: "nowrap",
          overflow: "hidden", textOverflow: "ellipsis"
        })
        videoHost.appendChild(popup)

        let hideTimer = null
        const updateSuggestion = () => {
          const module = [...(data?.modules ?? [])]
            .filter(item => video.currentTime >= item.popup_at_seconds &&
              video.currentTime < item.popup_at_seconds + (item.popup_duration_seconds ?? 30))
            .sort((a, b) => b.popup_at_seconds - a.popup_at_seconds)[0]
          if (!module || state.shown.has(module.content_id)) return
          state.shown.add(module.content_id)
          popup.textContent = module.title
          popup.style.display = "block"
          popup.onclick = () => {
            popup.style.display = "none"
            setTriggerValue("recommendation", {
              event_id: `${module.content_id}-${Date.now()}`,
              content_id: module.content_id,
              title: module.title,
              available: module.available,
              main_position: Math.floor(video.currentTime),
              emotion: state.emotion
            })
          }
          hideTimer = window.setTimeout(
            () => { popup.style.display = "none" },
            (module.popup_duration_seconds ?? 30) * 1000
          )
        }
        const playbackListener = () => {
          if (data?.content_id === "main") {
            window.sessionStorage.setItem("adaptive-vr-main-position", String(video.currentTime))
          }
          if (data?.content_id === "main" && video.currentTime >= (data?.mid_quiz_at ?? 270)
              && !state.quizEvents.has("mid")) {
            state.quizEvents.add("mid")
            video.pause()
            setTriggerValue("playback", {
              event_id: `mid-${Date.now()}`, type: "mid_quiz", position: Math.floor(video.currentTime)
            })
          }
        }
        const endedListener = () => {
          setTriggerValue("playback", {
            event_id: `ended-${Date.now()}`,
            type: data?.content_id === "main" ? "final_quiz" : "subcontent_ended",
            content_id: data?.content_id
          })
        }
        const emotionListener = event => {
          state.emotion = event?.detail ?? "focused"
          updateSuggestion()
        }
        video.addEventListener("timeupdate", updateSuggestion)
        video.addEventListener("timeupdate", playbackListener)
        video.addEventListener("ended", endedListener)
        window.addEventListener("adaptive-vr-emotion", emotionListener)
        updateSuggestion()

        state.cleanup = () => {
          video.removeEventListener("timeupdate", updateSuggestion)
          video.removeEventListener("timeupdate", playbackListener)
          video.removeEventListener("ended", endedListener)
          window.removeEventListener("adaptive-vr-emotion", emotionListener)
          if (hideTimer) window.clearTimeout(hideTimer)
          popup.remove()
        }
      }

      if (state.cleanup) state.cleanup()
      applyCommand()
      return () => {
        cancelled = true
        if (state.cleanup) state.cleanup()
        state.cleanup = null
      }
    }
    """,
)

EMOTION_BRIDGE = st.components.v2.component(
    "adaptive_vr_emotion_bridge",
    html="""<span id="emotion-bridge" hidden></span>""",
    js="""
    export default function(component) {
      window.dispatchEvent(new CustomEvent("adaptive-vr-emotion", { detail: component.data?.emotion }))
    }
    """,
)

SMARTPHONE_SPEECH = st.components.v2.component(
    "adaptive_vr_smartphone_speech",
    html="""
    <div id="phone-speech-status" role="status">Smartphone microphone ready</div>
    <button id="phone-speech-toggle" type="button">Start smartphone microphone</button>
    """,
    css="""
    #phone-speech-status { font-size: .82rem; margin-bottom: .45rem; color: var(--st-text-color); }
    #phone-speech-toggle { width: 100%; padding: .55rem; border-radius: var(--st-border-radius);
      border: 1px solid var(--st-border-color); background: var(--st-primary-color); color: white; font-weight: 600; }
    """,
    js="""
    export default function(component) {
      const { parentElement, setTriggerValue } = component
      const status = parentElement.querySelector("#phone-speech-status")
      const button = parentElement.querySelector("#phone-speech-toggle")
      const Recognition = window.SpeechRecognition || window.webkitSpeechRecognition
      if (!Recognition) {
        status.textContent = "Continuous browser speech recognition is not supported here"
        button.disabled = true
        return
      }
      const recognition = new Recognition()
      recognition.continuous = true
      recognition.interimResults = false
      recognition.lang = "en-IN"
      let active = false
      recognition.onresult = event => {
        const result = event.results[event.results.length - 1][0]
        const transcript = result.transcript.trim()
        status.textContent = `Heard: ${transcript}`
        setTriggerValue("transcript", {
          event_id: `phone-${Date.now()}`, transcript, confidence: result.confidence || 0.8, language: "auto"
        })
      }
      recognition.onerror = event => { status.textContent = `Microphone: ${event.error}` }
      recognition.onend = () => { if (active) { try { recognition.start() } catch (_) {} } }
      button.onclick = () => {
        active = !active
        button.textContent = active ? "Stop smartphone microphone" : "Start smartphone microphone"
        status.textContent = active ? "Listening continuously…" : "Smartphone microphone stopped"
        try { active ? recognition.start() : recognition.stop() } catch (_) {}
      }
      return () => { active = false; try { recognition.stop() } catch (_) {} }
    }
    """,
)


def initialize_state() -> None:
    defaults = {
        "participant_id": "P001",
        "learning_session_id": f"dc_motor_{time.strftime('%Y%m%d_%H%M%S')}",
        "lesson_active": False,
        "media_status": "ready",
        "media_position": 0,
        "player_command": "ready",
        "player_command_token": 0,
        "question_index": 0,
        "question_started_ms": time.time_ns() // 1_000_000,
        "events": [],
        "attempts": [],
        "last_audio_hash": "",
        "last_live_command_id": "",
        "live_speech_started_ms": time.time_ns() // 1_000_000,
        "command_feedback": "No command received yet.",
        "last_voice_transcript": "",
        "last_voice_language": "",
        "last_voice_confidence": 0.0,
        "last_voice_peak": 0,
        "last_voice_mean": 0.0,
        "show_hint": False,
        "pi_host": "10.126.112.77",
        "pi_user": "vrpi",
        "pi_password": "",
        "recording_label": "focused",
        "selected_content_id": "main",
        "show_subcontent_dialog": False,
        "detected_emotion": "focused",
        "emotion_confidence": 0.0,
        "last_recommendation_id": "",
        "last_playback_event_id": "",
        "last_phone_transcript_id": "",
        "active_subcontent_id": "",
        "awaiting_understanding": False,
        "quiz_phase": "hidden",
        "dashboard_client_id": uuid4().hex,
        "shared_dashboard_version": 0,
    }
    for key, value in defaults.items():
        st.session_state.setdefault(key, value)


initialize_state()


@st.cache_data
def load_quiz(path: str) -> list[dict[str, object]]:
    return json.loads(Path(path).read_text(encoding="utf-8"))


@st.cache_data
def load_content_config(path: str) -> dict[str, object]:
    return json.loads(Path(path).read_text(encoding="utf-8"))


@st.cache_resource(max_entries=4)
def pi_gateway(host: str, username: str, password: str, key_filename: str) -> PiGateway:
    return PiGateway(host, username, password, key_filename=key_filename or None)


@st.cache_resource
def upper_predictor() -> UpperFaceCnnPredictor:
    return UpperFaceCnnPredictor(PROJECT_ROOT / "models" / "cnn", task="expression")


@st.cache_resource(max_entries=2)
def speech_model(language: str):
    from vosk import Model, SetLogLevel

    path = MODEL_PATHS[language]
    if not path.exists():
        raise FileNotFoundError(f"Missing speech model: {path}")
    SetLogLevel(-1)
    return Model(str(path))


def recognize_with_model(audio: bytes, language: str) -> tuple[str, float]:
    from vosk import KaldiRecognizer

    with wave.open(BytesIO(audio), "rb") as source:
        if source.getnchannels() != 1 or source.getsampwidth() != 2:
            raise ValueError("Microphone audio must be mono 16-bit PCM")
        recognizer = KaldiRecognizer(speech_model(language), source.getframerate())
        recognizer.SetWords(True)
        while chunk := source.readframes(4000):
            recognizer.AcceptWaveform(chunk)
    result = json.loads(recognizer.FinalResult())
    words = result.get("result", [])
    confidence = sum(float(word.get("conf", 0.0)) for word in words) / len(words) if words else 0.0
    return str(result.get("text", "")).strip(), confidence


def wav_audio_level(audio: bytes) -> tuple[int, float]:
    with wave.open(BytesIO(audio), "rb") as source:
        if source.getsampwidth() != 2:
            return 0, 0.0
        samples = array.array("h", source.readframes(source.getnframes()))
    if not samples:
        return 0, 0.0
    absolute = [abs(value) for value in samples]
    return max(absolute), sum(absolute) / len(absolute)


def transcribe_audio(audio: bytes, language_mode: str) -> tuple[str, str, float]:
    candidates = (
        [language_mode] if language_mode in MODEL_PATHS else ["English", "Hindi"]
    )
    results = [(*recognize_with_model(audio, language), language) for language in candidates]
    transcript, confidence, language = max(
        results, key=lambda item: (item[1], len(item[0]))
    )
    return transcript, language.lower(), confidence


def record_event(event: str, payload: dict[str, object] | None = None) -> dict[str, object]:
    item = append_learning_event(
        EVENT_ROOT,
        st.session_state.learning_session_id,
        event,
        payload,
    ).to_dict()
    st.session_state.events.append(item)
    return item


def current_question(questions: list[dict[str, object]]) -> dict[str, object]:
    index = max(0, min(st.session_state.question_index, len(questions) - 1))
    st.session_state.question_index = index
    return questions[index]


def change_question(questions: list[dict[str, object]], amount: int) -> None:
    old_index = st.session_state.question_index
    st.session_state.question_index = max(0, min(old_index + amount, len(questions) - 1))
    if st.session_state.question_index != old_index:
        st.session_state.question_started_ms = time.time_ns() // 1_000_000
        st.session_state.show_hint = False
        record_event(
            "quiz_question",
            {"question_id": current_question(questions)["id"], "index": st.session_state.question_index},
        )


def submit_answer(questions: list[dict[str, object]], source: str) -> bool:
    question = current_question(questions)
    key = f"quiz_selection_{st.session_state.question_index}"
    selected = st.session_state.get(key)
    display_options = [f"{chr(65 + index)}. {option}" for index, option in enumerate(question["options"])]
    if selected not in display_options:
        st.session_state.command_feedback = "Select an answer before submitting."
        return False
    selected_index = display_options.index(selected)
    correct = selected_index == int(question["correct_index"])
    now_ms = time.time_ns() // 1_000_000
    response_seconds = max(0.0, (now_ms - st.session_state.question_started_ms) / 1000)
    attempt = {
        "question_id": question["id"],
        "selected_index": selected_index,
        "correct_index": int(question["correct_index"]),
        "correct": correct,
        "response_time_seconds": round(response_seconds, 3),
        "source": source,
    }
    st.session_state.attempts.append(attempt)
    record_event("quiz_answer", attempt)
    st.session_state.command_feedback = "Correct answer." if correct else "Incorrect answer."
    return True


def start_subcontent(content_id: str, source: str) -> None:
    video = next(
        (item for item in configured_videos if item["content_id"] == content_id), None
    )
    if video is None or content_id == "main":
        return
    st.session_state.selected_content_id = content_id
    st.session_state.active_subcontent_id = content_id
    st.session_state.awaiting_understanding = False
    st.session_state.media_position = 0
    st.session_state.media_status = "playing"
    queue_player_command("play")
    record_event(
        "subcontent_selected",
        {
            "content_id": content_id,
            "source": source,
            "emotion": st.session_state.detected_emotion,
        },
    )


def resume_main_video(source: str) -> None:
    previous = st.session_state.active_subcontent_id
    st.session_state.selected_content_id = "main"
    st.session_state.active_subcontent_id = ""
    st.session_state.awaiting_understanding = False
    st.session_state.media_status = "playing"
    queue_player_command("play")
    record_event("subcontent_understood", {"content_id": previous, "source": source})


def requested_subcontent(transcript: str) -> str | None:
    normalized = transcript.casefold().replace("_", " ")
    play_words = ("play", "show", "open", "chalao", "chala do", "dikhao")
    if not any(word in normalized for word in play_words):
        return None
    aliases = {
        "torque": ("torque",),
        "curved_magnets": ("curved magnet", "curve magnet"),
        "current_reverse": ("current reverse", "reverse current"),
        "multiple_coils": ("multiple coil", "multiple coils"),
        "commutator_rings": ("commutator", "commutator ring"),
        "carbon_brushes": ("brush", "brushes", "carbon brush"),
        "magnets": ("magnets", "magnet"),
        "electromagnet": ("electromagnet", "electro magnet"),
    }
    return next(
        (content_id for content_id, names in aliases.items() if any(name in normalized for name in names)),
        None,
    )


def apply_command(action: str, questions: list[dict[str, object]]) -> None:
    if action in {"PLAY", "RESUME", "RESUME_SESSION", "START_SESSION"}:
        st.session_state.media_status = "playing"
        st.session_state.lesson_active = True
        queue_player_command("play")
    elif action in {"PAUSE", "PAUSE_SESSION"}:
        st.session_state.media_status = "paused"
        queue_player_command("pause")
    elif action in {"STOP", "END_SESSION", "COMPLETE_LESSON"}:
        st.session_state.media_status = "stopped"
        st.session_state.lesson_active = False
        queue_player_command("stop")
    elif action in {"NEXT", "CONTINUE_AFTER_QUIZ"}:
        change_question(questions, 1)
    elif action == "BACK":
        change_question(questions, -1)
    elif action in {"SEEK_BACKWARD", "REPLAY_SEGMENT"}:
        st.session_state.media_position = max(0, st.session_state.media_position - 10)
        queue_player_command("replay_10")
    elif action == "SEEK_FORWARD":
        st.session_state.media_position += 10
        queue_player_command("forward_10")
    elif action == "RESTART_VIDEO":
        st.session_state.media_position = 0
        queue_player_command("restart")
    elif action == "VOLUME_UP":
        queue_player_command("volume_up")
    elif action == "VOLUME_DOWN":
        queue_player_command("volume_down")
    elif action == "MUTE":
        queue_player_command("mute")
    elif action == "UNMUTE":
        queue_player_command("unmute")
    elif action in ANSWER_COMMANDS:
        question = current_question(questions)
        index = ANSWER_COMMANDS[action]
        if index < len(question["options"]):
            st.session_state[f"quiz_selection_{st.session_state.question_index}"] = (
                f"{chr(65 + index)}. {question['options'][index]}"
            )
    elif action == "SUBMIT_ANSWER":
        submit_answer(questions, "voice")
    elif action == "CHANGE_ANSWER":
        st.session_state.pop(f"quiz_selection_{st.session_state.question_index}", None)
    elif action in {"SHOW_HINT", "HELP", "SHOW_MINI_TUTORIAL", "SHOW_SIMPLER_EXPLANATION"}:
        st.session_state.show_hint = True
        st.session_state.show_subcontent_dialog = True
    elif action == "SKIP_QUESTION":
        record_event("quiz_skip", {"question_id": current_question(questions)["id"]})
        change_question(questions, 1)
    elif action == "REPEAT_QUESTION":
        record_event("quiz_repeat", {"question_id": current_question(questions)["id"]})
    st.session_state.command_feedback = f"Command applied: {action.replace('_', ' ').title()}"


def queue_player_command(command: str, *, publish: bool = True) -> None:
    st.session_state.player_command = command
    st.session_state.player_command_token += 1
    if publish:
        bus = shared_dashboard_bus()
        with bus["lock"]:
            bus["version"] = int(bus["version"]) + 1
            bus["origin"] = st.session_state.dashboard_client_id
            bus["state"] = {
                "selected_content_id": st.session_state.selected_content_id,
                "active_subcontent_id": st.session_state.active_subcontent_id,
                "awaiting_understanding": st.session_state.awaiting_understanding,
                "quiz_phase": st.session_state.quiz_phase,
                "media_status": st.session_state.media_status,
                "player_command": command,
            }
            st.session_state.shared_dashboard_version = bus["version"]


def process_transcript(
    transcript: str,
    language: str,
    confidence: float,
    questions: list[dict[str, object]],
) -> None:
    normalized = transcript.casefold().strip()
    if st.session_state.awaiting_understanding:
        negative = ("no", "not", "again", "nahi", "dobara", "samajh nahi")
        positive = ("yes", "understand", "haan", "samajh aa", "continue")
        if any(word in normalized for word in negative):
            st.session_state.awaiting_understanding = False
            st.session_state.media_status = "playing"
            queue_player_command("restart")
            record_event(
                "subcontent_replay_requested",
                {"content_id": st.session_state.active_subcontent_id, "source": "voice"},
            )
            st.session_state.command_feedback = "Playing the explanation again."
            return
        if any(word in normalized for word in positive):
            resume_main_video("voice_verification")
            st.session_state.command_feedback = "Continuing the main video."
            return
    content_id = requested_subcontent(transcript)
    if content_id:
        start_subcontent(content_id, "voice_name")
        st.session_state.command_feedback = f"Playing {content_id.replace('_', ' ').title()}."
        return
    event = analyze_transcript(
        transcript,
        language=language,
        confidence=confidence,
        timestamp_ms=time.time_ns() // 1_000_000,
        context="quiz",
    )
    record_event("speech", event.to_dict())
    st.session_state.last_voice_transcript = event.transcript
    st.session_state.last_voice_language = event.language
    st.session_state.last_voice_confidence = event.confidence
    if event.command is None:
        if not event.transcript:
            st.session_state.command_feedback = (
                "No speech detected. Record for 1–3 seconds, speak clearly, then tap Stop."
            )
        else:
            st.session_state.command_feedback = (
                f"Speech heard, but no command matched: {event.transcript}"
            )
        return
    command_event = build_command_event(
        event.command,
        session_id=st.session_state.learning_session_id,
        recognized_text=event.transcript,
        detected_language=event.language,
    )
    record_event("voice_command", command_event.to_dict())
    apply_command(event.command.action, questions)


@st.fragment(run_every="1s")
def continuous_speech_feed(questions: list[dict[str, object]]) -> None:
    if not LIVE_SPEECH_PATH.exists():
        st.caption(":material/mic_off: Continuous laptop microphone service is not running.")
        return
    age_seconds = max(0.0, time.time() - LIVE_SPEECH_PATH.stat().st_mtime)
    st.caption(
        ":material/mic: Continuous laptop microphone active"
        if age_seconds < 30
        else ":material/mic: Continuous microphone ready; waiting for speech"
    )
    try:
        lines = LIVE_SPEECH_PATH.read_text(encoding="utf-8").splitlines()
        recent = [json.loads(line) for line in lines[-100:] if line.strip()]
        latest = next((item for item in reversed(recent) if item.get("transcript")), {})
    except (OSError, json.JSONDecodeError):
        return
    command = latest.get("command_event") if isinstance(latest.get("command_event"), dict) else {}
    command_timestamp = int(latest.get("timestamp_ms", 0))
    if command_timestamp < st.session_state.live_speech_started_ms:
        return
    command_id = str(command.get("command_id") or f"speech-{command_timestamp}")
    if not command_id or command_id == st.session_state.last_live_command_id:
        return
    st.session_state.last_live_command_id = command_id
    process_transcript(
        str(latest.get("transcript", "")),
        str(latest.get("language", "unknown")),
        float(latest.get("confidence", 0.0)),
        questions,
    )
    st.rerun()


questions = load_quiz(str(QUIZ_PATH))
content_config = load_content_config(str(CONTENT_CONFIG_PATH))
configured_videos = list(content_config["videos"])
expected_modules = list(content_config.get("expected_modules", []))


@st.fragment(run_every="1s")
def shared_dashboard_feed() -> None:
    bus = shared_dashboard_bus()
    with bus["lock"]:
        version = int(bus["version"])
        origin = str(bus["origin"])
        shared = dict(bus["state"])
    if (
        version <= st.session_state.shared_dashboard_version
        or origin == st.session_state.dashboard_client_id
        or not shared
    ):
        st.caption(":material/sync: Laptop and smartphone synchronization active")
        return
    st.session_state.shared_dashboard_version = version
    for key in (
        "selected_content_id",
        "active_subcontent_id",
        "awaiting_understanding",
        "quiz_phase",
        "media_status",
    ):
        if key in shared:
            st.session_state[key] = shared[key]
    queue_player_command(str(shared.get("player_command", "ready")), publish=False)
    st.rerun()


def normalize_adaptive_emotion(label: str) -> str:
    normalized = label.strip().lower().replace(" ", "_")
    aliases = {
        "neutral": "focused",
        "surprise": "confused",
        "fear": "confused",
        "angry": "frustrated",
        "anger": "frustrated",
        "sad": "bored",
        "disgust": "frustrated",
    }
    return aliases.get(normalized, normalized)


def content_option_label(content_id: str) -> str:
    video = next(video for video in configured_videos if video["content_id"] == content_id)
    duration = video.get("expected_duration_label")
    return f"{duration}  {video['title']}" if duration else str(video["title"])


@st.dialog("Choose a short explanation", width="small")
def subcontent_dialog() -> None:
    st.caption("The main lesson stays paused while you choose a supporting video.")
    modules = [video for video in configured_videos if video["content_id"] != "main"]
    for video in modules:
        if st.button(
            content_option_label(str(video["content_id"])),
            key=f"subcontent_{video['content_id']}",
            icon=":material/play_circle:",
            width="stretch",
        ):
            st.session_state.selected_content_id = video["content_id"]
            st.session_state.media_position = 0
            st.session_state.media_status = "playing"
            st.session_state.show_subcontent_dialog = False
            record_event(
                "subcontent_selected",
                {"content_id": video["content_id"], "source": "adaptive_popup"},
            )
            st.rerun()
    if st.button("Continue the main lesson", icon=":material/close:"):
        st.session_state.show_subcontent_dialog = False
        st.rerun()


if st.session_state.show_subcontent_dialog:
    subcontent_dialog()

with st.sidebar:
    st.subheader(":material/settings: Session settings")
    st.text_input("Participant ID", key="participant_id")
    st.text_input("Learning session ID", key="learning_session_id")
    st.divider()
    st.subheader(":material/movie: Lesson content")
    st.link_button(
        "Open Cogniverse content repository",
        CONTENT_REPOSITORY_URL,
        icon=":material/code:",
        width="stretch",
    )
    st.caption(
        "Cogniverse is connected. The lesson media is stored on D: to protect the nearly full C: drive."
    )
    if PHONE_CA_CERT_PATH.exists():
        st.download_button(
            "Download smartphone microphone certificate",
            PHONE_CA_CERT_PATH.read_bytes(),
            file_name="adaptive_vr_local_ca.cer",
            mime="application/x-x509-ca-cert",
            icon=":material/download:",
            help="Install this CA certificate on the Vivo before switching the dashboard to HTTPS.",
            width="stretch",
        )
    selected_from_sidebar = st.selectbox(
        "Cogniverse lesson video",
        [video["content_id"] for video in configured_videos],
        format_func=content_option_label,
        index=next(
            index for index, video in enumerate(configured_videos)
            if video["content_id"] == st.session_state.selected_content_id
        ),
    )
    if selected_from_sidebar != st.session_state.selected_content_id:
        if selected_from_sidebar == "main":
            resume_main_video("sidebar")
        else:
            start_subcontent(selected_from_sidebar, "sidebar")
        st.rerun()
    if expected_modules:
        available_count = sum(bool(module["available"]) for module in expected_modules)
        with st.expander(f"Module availability ({available_count}/{len(expected_modules)} ready)"):
            for module in expected_modules:
                status = ":material/check_circle:" if module["available"] else ":material/pending:"
                st.markdown(
                    f"{status} **{module['expected_duration_label']}** — {module['title']}"
                )
    uploaded_video = st.file_uploader(
        "Upload the DC motor video",
        type=["mp4", "webm", "mov"],
        max_upload_size=500,
        help="The video slot is ready; upload the lesson when it is available.",
    )
    video_url = st.text_input("Or enter a video URL", placeholder="https://...")
    st.divider()
    st.subheader(":material/cable: Raspberry Pi")
    st.text_input("Pi address", key="pi_host")
    st.text_input("Pi username", key="pi_user")
    st.text_input("Pi password", type="password", key="pi_password")
    st.caption("The project SSH key is used when the password is blank.")

st.title(":material/school: Adaptive VR learning studio")
st.caption("DC motor content, MID PART 1 quiz, bilingual commands, upper-camera monitoring, and learning analytics")
shared_dashboard_feed()

summary = summarize_learning_events(st.session_state.events)
with st.container(horizontal=True):
    st.metric("Lesson", "ACTIVE" if st.session_state.lesson_active else "READY", border=True)
    st.metric("Quiz progress", f"{st.session_state.question_index + 1}/{len(questions)}", border=True)
    accuracy = summary["accuracy"]
    st.metric("Accuracy", "--" if accuracy is None else f"{accuracy:.0%}", border=True)
    st.metric("Voice commands", summary["voice_commands"], border=True)

content_column, control_column = st.columns([3, 2])

with content_column:
    with st.container(border=True):
        selected_video = next(
            video for video in configured_videos
            if video["content_id"] == st.session_state.selected_content_id
        )
        st.subheader(f":material/movie: {selected_video['title']}")
        if selected_video.get("expected_duration_label"):
            st.caption(
                f"Expected duration: {selected_video['expected_duration_label']} (minutes:seconds)"
            )
        configured_path = Path(str(selected_video["path"]))
        source = (
            uploaded_video
            if uploaded_video is not None
            else video_url.strip() or (configured_path if configured_path.exists() else None)
        )
        if source is None:
            st.info("Video slot ready. Upload the DC motor lesson or enter its URL when available.")
            st.markdown(
                "The installed quiz covers **DC Motor - MID PART 1 (0:00-4:50)**. "
                "Quiz events can already be tested without the video."
            )
        else:
            st.video(
                source,
                start_time=st.session_state.media_position,
            )
            player_result = PLAYER_CONTROLLER(
                key="lesson_video_controller",
                data={
                    "command": st.session_state.player_command,
                    "token": st.session_state.player_command_token,
                    "content_id": selected_video["content_id"],
                    "emotion": st.session_state.detected_emotion,
                    "support_emotions": ["confused", "bored", "drowsy", "frustrated"],
                    "modules": expected_modules,
                },
                on_recommendation_change=lambda: None,
                height="content",
            )
            recommendation = getattr(player_result, "recommendation", None)
            if recommendation:
                recommendation_id = str(recommendation.get("event_id", ""))
                if recommendation_id and recommendation_id != st.session_state.last_recommendation_id:
                    st.session_state.last_recommendation_id = recommendation_id
                    content_id = str(recommendation.get("content_id", ""))
                    title = str(recommendation.get("title", "Subcontent"))
                    if bool(recommendation.get("available")):
                        start_subcontent(content_id, "timeline_popup")
                    else:
                        st.session_state.command_feedback = (
                            f"{title} is scheduled, but its MP4 file has not been added yet."
                        )
                        record_event(
                            "subcontent_unavailable",
                            {
                                "content_id": content_id,
                                "source": "emotion_timeline_popup",
                                "emotion": st.session_state.detected_emotion,
                            },
                        )
                    st.rerun()
            playback = getattr(player_result, "playback", None)
            if playback:
                playback_id = str(playback.get("event_id", ""))
                if playback_id and playback_id != st.session_state.last_playback_event_id:
                    st.session_state.last_playback_event_id = playback_id
                    event_type = str(playback.get("type", ""))
                    if event_type == "subcontent_ended":
                        st.session_state.awaiting_understanding = True
                        st.session_state.media_status = "paused"
                        record_event(
                            "subcontent_completed",
                            {"content_id": st.session_state.active_subcontent_id},
                        )
                    elif event_type == "mid_quiz":
                        st.session_state.quiz_phase = "mid"
                        st.session_state.question_index = 0
                        st.session_state.media_status = "paused"
                        record_event("quiz_started", {"phase": "mid", "position": playback.get("position")})
                    elif event_type == "final_quiz":
                        st.session_state.quiz_phase = "final"
                        st.session_state.question_index = 3
                        st.session_state.media_status = "paused"
                        record_event("quiz_started", {"phase": "final"})
                    st.rerun()
            st.caption(":material/volume_up: Audio plays through the speaker of the device running this browser.")
        with st.container(horizontal=True):
            if st.button("Play", icon=":material/play_arrow:"):
                st.session_state.lesson_active = True
                st.session_state.media_status = "playing"
                queue_player_command("play")
                record_event(
                    "content_play",
                    {
                        "content_id": selected_video["content_id"],
                        "position_seconds": st.session_state.media_position,
                    },
                )
                st.rerun()
            if st.button("Pause", icon=":material/pause:"):
                st.session_state.media_status = "paused"
                queue_player_command("pause")
                record_event(
                    "content_pause",
                    {
                        "content_id": selected_video["content_id"],
                        "position_seconds": st.session_state.media_position,
                    },
                )
                st.rerun()
            if st.button("Replay 10 seconds", icon=":material/replay_10:"):
                st.session_state.media_position = max(0, st.session_state.media_position - 10)
                queue_player_command("replay_10")
                record_event(
                    "content_replay",
                    {
                        "content_id": selected_video["content_id"],
                        "position_seconds": st.session_state.media_position,
                    },
                )
                st.rerun()
        st.caption(f"Logical player status: {st.session_state.media_status.upper()} • start position: {st.session_state.media_position}s")

with control_column:
    with st.container(border=True):
        st.subheader(":material/video_library: Subcontent")
        st.caption("Tap a topic or say **Play + topic name**.")
        for module in sorted(expected_modules, key=lambda item: item["popup_at_seconds"]):
            timestamp = time.strftime("%M:%S", time.gmtime(module["popup_at_seconds"]))
            if st.button(
                f"{timestamp}  {module['title']}",
                key=f"dashboard_module_{module['content_id']}",
                icon=":material/play_circle:",
                width="stretch",
            ):
                start_subcontent(str(module["content_id"]), "dashboard_list")
                st.rerun()
    with st.container(border=True):
        st.subheader(":material/hearing: Continuous voice commands")
        st.info(
            "The laptop microphone stays active. Say a command normally; no Record or Stop "
            "button is required. English, Hindi, and Hinglish are monitored automatically."
        )
        continuous_speech_feed(questions)
        phone_speech = SMARTPHONE_SPEECH(
            key="smartphone_continuous_speech",
            on_transcript_change=lambda: None,
            height="content",
        )
        phone_transcript = getattr(phone_speech, "transcript", None)
        if phone_transcript:
            phone_id = str(phone_transcript.get("event_id", ""))
            if phone_id and phone_id != st.session_state.last_phone_transcript_id:
                st.session_state.last_phone_transcript_id = phone_id
                process_transcript(
                    str(phone_transcript.get("transcript", "")),
                    str(phone_transcript.get("language", "auto")),
                    float(phone_transcript.get("confidence", 0.8)),
                    questions,
                )
                st.rerun()
        st.info(st.session_state.command_feedback)
        if st.session_state.last_voice_transcript:
            st.caption(
                f"Recognized: **{st.session_state.last_voice_transcript}** · "
                f"{st.session_state.last_voice_language} · "
                f"{st.session_state.last_voice_confidence:.0%}"
            )

if st.session_state.awaiting_understanding:
    with st.container(border=True):
        st.subheader(":material/psychology_alt: Did you understand?")
        st.caption("Say **Yes, I understand** to continue the main video, or **No, play again**.")
        with st.container(horizontal=True):
            if st.button("Yes, continue main video", type="primary", icon=":material/check_circle:"):
                resume_main_video("verification_button")
                st.rerun()
            if st.button("No, play again", icon=":material/replay:"):
                st.session_state.awaiting_understanding = False
                st.session_state.media_status = "playing"
                queue_player_command("restart")
                record_event(
                    "subcontent_replay_requested",
                    {"content_id": st.session_state.active_subcontent_id, "source": "button"},
                )
                st.rerun()

with st.container(border=True):
    phase_ranges = {"mid": (0, 6), "final": (7, len(questions) - 1)}
    quiz_phase = st.session_state.quiz_phase
    quiz_locked = quiz_phase not in phase_ranges
    phase_start, phase_end = phase_ranges.get(quiz_phase, (0, 0))
    question = current_question(questions)
    phase_name = "Midpoint quiz" if quiz_phase == "mid" else "Final quiz" if quiz_phase == "final" else "Scheduled quiz"
    st.subheader(f":material/quiz: {phase_name}")
    if quiz_locked:
        st.info("The midpoint quiz opens automatically at 4:30. The final quiz opens when the main video ends.")
    st.caption(f"Question {st.session_state.question_index + 1} of {len(questions)}")
    st.caption(f"{question['section']} • video segment {question['video_range']}")
    st.markdown(f"**{question['question']}**")
    displayed_options = [
        f"{chr(65 + index)}. {option}" for index, option in enumerate(question["options"])
    ]
    st.segmented_control(
        "Select an answer",
        displayed_options,
        key=f"quiz_selection_{st.session_state.question_index}",
        disabled=quiz_locked,
    )
    with st.container(horizontal=True):
        if st.button("Previous", icon=":material/arrow_back:", disabled=quiz_locked or st.session_state.question_index <= phase_start):
            change_question(questions, -1)
            st.rerun()
        if st.button("Submit answer", type="primary", icon=":material/check:", disabled=quiz_locked):
            submit_answer(questions, "button")
            st.rerun()
        if st.button("Show hint", icon=":material/lightbulb:", disabled=quiz_locked):
            st.session_state.show_hint = True
            record_event("quiz_hint", {"question_id": question["id"]})
        if st.button("Next", icon=":material/arrow_forward:", disabled=quiz_locked or st.session_state.question_index >= phase_end):
            change_question(questions, 1)
            st.rerun()
    if st.session_state.show_hint:
        hint = str(question.get("hint", "")).strip()
        st.info(hint or "Review the matching section of the lesson before answering.")
    if st.session_state.attempts:
        latest = st.session_state.attempts[-1]
        if latest["question_id"] == question["id"]:
            if latest["correct"]:
                st.success(f"Correct • response time {latest['response_time_seconds']:.1f}s")
            else:
                correct_index = int(question["correct_index"])
                st.error(f"Incorrect. Correct answer: {chr(65 + correct_index)} • response time {latest['response_time_seconds']:.1f}s")
    if not quiz_locked and st.session_state.question_index == phase_end:
        if quiz_phase == "mid" and st.button(
            "Finish midpoint quiz and continue video", type="primary", icon=":material/play_arrow:"
        ):
            st.session_state.quiz_phase = "hidden"
            st.session_state.selected_content_id = "main"
            st.session_state.media_status = "playing"
            queue_player_command("play")
            record_event("quiz_completed", {"phase": "mid"})
            st.rerun()
        if quiz_phase == "final" and st.button(
            "Complete final quiz", type="primary", icon=":material/task_alt:"
        ):
            st.session_state.quiz_phase = "complete"
            record_event("quiz_completed", {"phase": "final"})
            st.rerun()


@st.fragment(run_every="3s")
def camera_and_recording() -> None:
    with st.container(border=True):
        st.subheader(":material/visibility: Upper-camera learning signal")
        try:
            pi = pi_gateway(
                st.session_state.pi_host.strip(),
                st.session_state.pi_user.strip(),
                st.session_state.pi_password,
                str(PI_KEY) if PI_KEY.exists() else "",
            )
            status = pi.snapshot()
            preview = pi.preview("upper_face")
        except (PiConnectionError, OSError) as exc:
            st.error(f"Raspberry Pi unavailable: {exc}")
            return
        with st.container(horizontal=True):
            st.metric("Receiver", "ONLINE" if status["receiver_active"] else "OFFLINE", border=True)
            st.metric("ESP32 eye camera", "CONNECTED" if status["upper_connected"] else "DISCONNECTED", border=True)
            st.metric("Mode", "UPPER ONLY", border=True)
        if preview is None:
            st.warning("Waiting for the eye-camera preview.")
        else:
            preview_column, prediction_column = st.columns([3, 2])
            with preview_column:
                st.image(preview.png, caption=f"Frame age {preview.age_seconds:.1f}s", width="stretch")
            with prediction_column:
                try:
                    prediction = upper_predictor().predict_bytes(preview.png)
                except Exception as exc:
                    st.warning(f"CNN unavailable: {exc}")
                else:
                    adaptive_emotion = normalize_adaptive_emotion(prediction.label)
                    st.session_state.detected_emotion = adaptive_emotion
                    st.session_state.emotion_confidence = prediction.confidence
                    EMOTION_BRIDGE(
                        key="live_emotion_bridge",
                        data={"emotion": adaptive_emotion},
                        height=0,
                    )
                    st.metric(
                        "Live adaptive emotion",
                        adaptive_emotion.replace("_", " ").title(),
                        f"{prediction.confidence:.1%} confidence",
                        border=True,
                    )
                    st.caption("This becomes the five-state model after headset fine-tuning.")
        control = status["control"]
        recording = bool(control.get("active"))
        with st.container(horizontal=True, vertical_alignment="bottom"):
            label = st.selectbox("Dataset label", LABELS, key="recording_label")
            if st.button(
                "Start labeled recording",
                type="primary",
                icon=":material/fiber_manual_record:",
                disabled=recording or not status["upper_connected"],
            ):
                dataset_session = f"{st.session_state.learning_session_id}_{label}"
                pi.control(
                    "start",
                    participant=st.session_state.participant_id,
                    session=dataset_session,
                    label=label,
                )
                record_event("dataset_start", {"session_id": dataset_session, "label": label})
                st.rerun(scope="fragment")
            if st.button(
                "Stop recording",
                icon=":material/stop_circle:",
                disabled=not recording,
            ):
                stopped = pi.control("stop")
                record_event("dataset_stop", {"session_id": stopped.get("session_id"), "label": stopped.get("label")})
                st.rerun(scope="fragment")
        if recording:
            st.error(f"REC • {control.get('session_id')} • {str(control.get('label')).upper()}")


camera_and_recording()

with st.container(border=True):
    st.subheader(":material/analytics: Multimodal engagement analysis")
    summary = summarize_learning_events(st.session_state.events)
    speech_events = [row for row in st.session_state.events if row["event"] == "speech"]
    speech_confusion = sum(
        bool(row["payload"].get("confusion_keyword"))
        or bool(row["payload"].get("repeat_request"))
        or bool(row["payload"].get("help_request"))
        for row in speech_events
    )
    accuracy = summary["accuracy"]
    support_emotions = {"confused", "bored", "drowsy", "frustrated"}
    needs_support = (
        st.session_state.detected_emotion in support_emotions
        or speech_confusion > 0
        or (accuracy is not None and accuracy < 0.6)
    )
    engagement_state = "Support recommended" if needs_support else "Engaged"
    with st.container(horizontal=True):
        st.metric("Combined state", engagement_state, border=True)
        st.metric("Camera emotion", st.session_state.detected_emotion.title(), border=True)
        st.metric("Speech confusion", speech_confusion, border=True)
        st.metric("Quiz accuracy", "--" if accuracy is None else f"{accuracy:.0%}", border=True)
    with st.container(horizontal=True):
        st.metric("Quiz attempts", summary["quiz_attempts"], border=True)
        st.metric("Correct", summary["correct_answers"], border=True)
        average = summary["average_response_seconds"]
        st.metric("Average response", "--" if average is None else f"{average:.1f}s", border=True)
        st.metric("Help / replay", summary["help_requests"] + summary["replay_requests"], border=True)
    if st.session_state.attempts:
        st.dataframe(pd.DataFrame(st.session_state.attempts), hide_index=True, width="stretch")
    else:
        st.info("Submit quiz answers to populate the learning analysis.")
    if st.session_state.events:
        event_rows = [
            {
                "Time": time.strftime("%H:%M:%S", time.localtime(row["timestamp_ms"] / 1000)),
                "Event": row["event"],
                "Details": json.dumps(row["payload"], ensure_ascii=False),
            }
            for row in st.session_state.events[-30:]
        ]
        st.dataframe(event_rows, hide_index=True, width="stretch")
        event_text = "\n".join(
            json.dumps(row, ensure_ascii=False, separators=(",", ":"))
            for row in st.session_state.events
        )
        st.download_button(
            "Download session events",
            event_text,
            file_name=f"{st.session_state.learning_session_id}_events.jsonl",
            mime="application/x-ndjson",
            icon=":material/download:",
        )

st.caption(
    "Quiz sources loaded: DC_Motor_MID_PART_1_Quiz (7 questions) and "
    "DC_Motor_LAST_PART_Quiz (7 questions)."
)
