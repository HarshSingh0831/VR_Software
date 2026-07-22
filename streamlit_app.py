from __future__ import annotations

import re
from pathlib import Path
import time

import pandas as pd
import streamlit as st

from adaptive_vr.dashboard_pi import PiConnectionError, PiGateway
from adaptive_vr.cnn_inference import UpperFaceCnnPredictor
from adaptive_vr.taxonomy import STATE_ENGAGEMENT, StudentState


st.set_page_config(
    page_title="Adaptive VR Live Monitor",
    page_icon=":material/visibility:",
    layout="wide",
)

LABELS = ["focused", "confused", "happy", "bored", "drowsy"]
LABEL_NAMES = {state.value: state.value.replace("_", " ").title() for state in StudentState}
SAFE_COMPONENT = re.compile(r"^[A-Za-z0-9_-]+$")

PROJECT_ROOT = Path(__file__).resolve().parent
PI_KEY = PROJECT_ROOT / ".rpi-provisioning" / "private" / "adaptive_vr_pi_ed25519"

st.session_state.setdefault("pi_host", "10.126.112.77")
st.session_state.setdefault("pi_user", "vrpi")
st.session_state.setdefault("pi_password", "")
st.session_state.setdefault("participant", "P001")
st.session_state.setdefault("session_name", "")
st.session_state.setdefault("start_label", "focused")
st.session_state.setdefault("new_label", "focused")


@st.cache_resource(max_entries=4)
def gateway(host: str, username: str, password: str, key_filename: str) -> PiGateway:
    return PiGateway(host, username, password, key_filename=key_filename or None)


@st.cache_resource
def cnn_predictor() -> UpperFaceCnnPredictor:
    return UpperFaceCnnPredictor("models/cnn", task="expression")


def validate_component(value: str, field: str, *, optional: bool = False) -> str:
    value = value.strip()
    if optional and not value:
        return value
    if not SAFE_COMPONENT.fullmatch(value):
        raise ValueError(f"{field} can contain only letters, numbers, hyphen, and underscore.")
    return value


with st.sidebar:
    st.subheader(":material/cable: Pi connection")
    st.text_input("Pi address", key="pi_host")
    st.text_input("Username", key="pi_user")
    st.text_input("Pi password", type="password", key="pi_password")
    st.caption("Password is optional; the local project SSH key is used when left blank.")
    if st.button(":material/refresh: Reconnect", width="stretch"):
        gateway.clear()
        st.rerun()
    st.divider()
    st.caption("Dashboard refresh: every 2 seconds")
    st.caption("Preview images are overwritten; they are archived only while REC is active.")


with st.container(horizontal=True, horizontal_alignment="distribute", vertical_alignment="center"):
    st.title(":material/visibility: Adaptive VR Live Monitor")
    st.caption("Upper-camera mode: eyes + eyebrows • ESP32-S3 • 5 engagement states")

if not st.session_state.pi_password and not PI_KEY.exists():
    st.info(":material/key: Enter the Raspberry Pi password in the sidebar to connect securely.")
    st.stop()

pi = gateway(
    st.session_state.pi_host.strip(),
    st.session_state.pi_user.strip(),
    st.session_state.pi_password,
    str(PI_KEY) if PI_KEY.exists() else "",
)


def perform(action: str, **values: str) -> None:
    try:
        pi.control(action, **values)
    except (PiConnectionError, ValueError) as exc:
        st.error(f"Command failed: {exc}")
    else:
        st.toast("Raspberry Pi updated", icon=":material/check_circle:")
        st.rerun()


with st.container(border=True):
    st.subheader(":material/fiber_manual_record: Dataset recording controls")
    c1, c2, c3 = st.columns([1, 1, 1])
    with c1:
        st.text_input("Participant ID", key="participant")
    with c2:
        st.text_input("Session name (optional)", key="session_name")
    with c3:
        st.selectbox(
            "Initial state",
            LABELS,
            format_func=lambda value: LABEL_NAMES[value],
            key="start_label",
        )
    with st.container(horizontal=True):
        if st.button(":material/fiber_manual_record: Start recording", type="primary"):
            try:
                participant = validate_component(st.session_state.participant, "Participant ID")
                session_name = validate_component(
                    st.session_state.session_name, "Session name", optional=True
                )
            except ValueError as exc:
                st.error(str(exc))
            else:
                perform(
                    "start",
                    participant=participant,
                    session=session_name,
                    label=st.session_state.start_label,
                )
        st.selectbox(
            "Change current state",
            LABELS,
            format_func=lambda value: LABEL_NAMES[value],
            key="new_label",
            label_visibility="collapsed",
            width=220,
        )
        if st.button(":material/label: Set label"):
            perform("label", label=st.session_state.new_label)
        if st.button(":material/stop_circle: Stop recording"):
            perform("stop")


@st.fragment(run_every="2s")
def live_monitor() -> None:
    try:
        status = pi.snapshot()
    except PiConnectionError as exc:
        st.error(f":material/wifi_off: Cannot reach Raspberry Pi: {exc}")
        return

    control = status["control"]
    recording = bool(control.get("active"))
    current_label = str(control.get("label", "none"))
    session_id = str(control.get("session_id", "none"))

    if recording:
        started = int(control.get("started_at_ms", int(time.time() * 1000))) / 1000
        elapsed = max(0, int(time.time() - started))
        st.error(
            f"🔴 REC — session **{session_id}** • **{LABEL_NAMES.get(current_label, current_label)}** "
            f"• {elapsed // 60:02d}:{elapsed % 60:02d}"
        )
    else:
        st.info("⏹ STOPPED — live preview is running, but images are not being added to the dataset.")

    with st.container(horizontal=True):
        st.metric(
            "Pi receiver",
            "ONLINE" if status["receiver_active"] else "OFFLINE",
            border=True,
        )
        st.metric(
            "ESP32 upper camera",
            "CONNECTED" if status["upper_connected"] else "DISCONNECTED",
            border=True,
        )
        st.metric("Training mode", "UPPER CAMERA ONLY", border=True)

    with st.container(border=True):
        st.subheader("Upper face — ESP32-S3")
        st.caption("Eyes and eyebrows; low-light normalization enabled")
        try:
            upper_preview = pi.preview(
                "upper_face", None if session_id == "none" else session_id
            )
        except PiConnectionError as exc:
            st.warning(f"Preview unavailable: {exc}")
            upper_preview = None
        if upper_preview is None:
            st.info("Waiting for the first upper-camera preview frame…")
        else:
            st.image(upper_preview.png, width="stretch")
            if upper_preview.age_seconds <= 5:
                st.success(f"LIVE • frame age {upper_preview.age_seconds:.1f} s")
            else:
                st.warning(f"STALE • last frame {upper_preview.age_seconds:.1f} s ago")

    with st.container(border=True):
        st.subheader(":material/psychology: Live upper-camera CNN")
        if upper_preview is None:
            st.info("Waiting for the upper-camera preview…")
        elif upper_preview.age_seconds > 5:
            st.warning("CNN paused because the upper-camera frame is stale.")
        else:
            try:
                prediction = cnn_predictor().predict_bytes(upper_preview.png)
            except Exception as exc:
                st.error(f"CNN inference failed: {exc}")
            else:
                st.metric(
                    "Upper-camera expression",
                    prediction.label.replace("_", " ").title(),
                    f"{prediction.confidence:.1%} confidence",
                    border=True,
                )
                probability_data = pd.DataFrame(
                    {
                        "Expression": [label.title() for label in prediction.probabilities],
                        "Probability": list(prediction.probabilities.values()),
                    }
                )
                st.bar_chart(
                    probability_data,
                    x="Expression",
                    y="Probability",
                    horizontal=True,
                )

    with st.container(border=True):
        st.subheader(":material/analytics: Current session")
        if session_id == "none":
            st.caption("No session has been started yet.")
        else:
            st.write(
                f"Participant: **{control.get('participant_id', 'unknown')}**  ·  "
                f"Session: **{session_id}**  ·  Saved frames: **{status['frames']}**"
            )
            try:
                counts = pi.label_counts(session_id)
            except PiConnectionError as exc:
                st.warning(f"Could not load label totals: {exc}")
            else:
                if counts:
                    label_data = pd.DataFrame(
                        {
                            "State": [LABEL_NAMES.get(label, label) for label in counts],
                            "Frames": list(counts.values()),
                        }
                    )
                    st.bar_chart(label_data, x="State", y="Frames", horizontal=True)

    st.caption(f"Last checked at {time.strftime('%H:%M:%S')}")


live_monitor()
