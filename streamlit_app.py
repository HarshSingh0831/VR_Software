from __future__ import annotations

import re
import time

import pandas as pd
import streamlit as st

from adaptive_vr.dashboard_pi import PiConnectionError, PiGateway
from adaptive_vr.dashboard_simulator import SimulatedPiGateway, simulated_predictions
from adaptive_vr.cogniverse_client import (
    CogniverseClient,
    CogniverseConnectionError,
    build_dashboard_packet,
)
from adaptive_vr.taxonomy import StudentState


st.set_page_config(
    page_title="Adaptive VR Live Monitor",
    page_icon=":material/visibility:",
    layout="wide",
)

LABELS = [state.value for state in StudentState]
LABEL_NAMES = {state.value: state.value.replace("_", " ").title() for state in StudentState}
SAFE_COMPONENT = re.compile(r"^[A-Za-z0-9_-]+$")

st.session_state.setdefault("pi_host", "172.18.57.77")
st.session_state.setdefault("pi_user", "vrpi")
st.session_state.setdefault("pi_password", "")
st.session_state.setdefault("participant", "P001")
st.session_state.setdefault("session_name", "")
st.session_state.setdefault("start_label", "focused")
st.session_state.setdefault("new_label", "focused")
st.session_state.setdefault("simulation_mode", False)
st.session_state.setdefault("simulation_scenario", "auto")
st.session_state.setdefault("cogniverse_enabled", False)
st.session_state.setdefault("cogniverse_url", "http://127.0.0.1:8000")
st.session_state.setdefault("cogniverse_session_id", "")
st.session_state.setdefault("cogniverse_last_status", "Not connected")


@st.cache_resource(max_entries=4)
def gateway(host: str, username: str, password: str) -> PiGateway:
    return PiGateway(host, username, password)


@st.cache_resource
def cnn_predictor():
    # Load torch and the model wrapper only when real hardware mode is used.
    from adaptive_vr.cnn_inference import PartialFaceCnnPredictor

    return PartialFaceCnnPredictor("models/cnn", task="expression")


@st.cache_resource
def simulation_gateway() -> SimulatedPiGateway:
    return SimulatedPiGateway()


def validate_component(value: str, field: str, *, optional: bool = False) -> str:
    value = value.strip()
    if optional and not value:
        return value
    if not SAFE_COMPONENT.fullmatch(value):
        raise ValueError(f"{field} can contain only letters, numbers, hyphen, and underscore.")
    return value


with st.sidebar:
    st.subheader(":material/tune: Run mode")
    st.toggle("Simulation mode (no Pi required)", key="simulation_mode")
    if st.session_state.simulation_mode:
        st.caption("Hardware-free demo with simulated cameras, sessions, and student states.")
        st.selectbox(
            "Demo scenario",
            ["auto", *LABELS],
            format_func=lambda value: "Automatic state cycle"
            if value == "auto"
            else LABEL_NAMES[value],
            key="simulation_scenario",
        )
        if st.button(":material/restart_alt: Reset simulation", width="stretch"):
            simulation_gateway.clear()
            st.rerun()
    else:
        st.subheader(":material/cable: Pi connection")
        st.text_input("Pi address", key="pi_host")
        st.text_input("Username", key="pi_user")
        st.text_input("Pi password", type="password", key="pi_password")
        st.caption("The password stays in this browser session and is not written to the project.")
        if st.button(":material/refresh: Reconnect", width="stretch"):
            gateway.clear()
            st.rerun()
    st.divider()
    st.subheader(":material/hub: Cogniverse bridge")
    st.toggle("Forward live predictions", key="cogniverse_enabled")
    st.text_input("Cogniverse URL", key="cogniverse_url")
    st.text_input(
        "VR session ID (optional)",
        key="cogniverse_session_id",
        help="Leave blank to route to the currently active Cogniverse session.",
    )
    st.caption(st.session_state.cogniverse_last_status)
    st.divider()
    st.caption("Dashboard refresh: every 2 seconds")
    st.caption("Preview images are overwritten; they are archived only while REC is active.")


with st.container(horizontal=True, horizontal_alignment="distribute", vertical_alignment="center"):
    st.title(":material/visibility: Adaptive VR Live Monitor")
    st.caption("Upper eyes + lower mouth/chin • Raspberry Pi 4 • ESP32-S3")

if st.session_state.simulation_mode:
    pi = simulation_gateway()
    pi.scenario = st.session_state.simulation_scenario
elif not st.session_state.pi_password:
    st.info(":material/key: Enter the Raspberry Pi password in the sidebar to connect securely.")
    st.stop()
else:
    pi = gateway(
        st.session_state.pi_host.strip(),
        st.session_state.pi_user.strip(),
        st.session_state.pi_password,
    )


def perform(action: str, **values: str) -> None:
    try:
        pi.control(action, **values)
    except (PiConnectionError, ValueError) as exc:
        st.error(f"Command failed: {exc}")
    else:
        st.toast("Raspberry Pi updated", icon=":material/check_circle:")
        st.rerun()


def forward_to_cogniverse(predictions: dict[str, object], status: dict[str, object], control: dict[str, object], pi: object) -> None:
    """Forward the dashboard result without making Cogniverse mandatory."""

    if not st.session_state.cogniverse_enabled:
        return

    if st.session_state.simulation_mode:
        state = pi.current_state.value
        duration_ms = 4_000 if state == StudentState.CONFUSED.value else 1_500
    else:
        # The current real CNN predicts facial expressions, not the project
        # engagement taxonomy. Do not label an expression as confusion here.
        state = "unknown"
        duration_ms = 0

    upper_preview = st.session_state.get("_cogniverse_upper_preview")
    lower_preview = st.session_state.get("_cogniverse_lower_preview")
    upper_quality = 0.0 if upper_preview is None else max(0.0, 1.0 - upper_preview.age_seconds / 5.0)
    lower_quality = 0.0 if lower_preview is None else max(0.0, 1.0 - lower_preview.age_seconds / 5.0)
    session_id = st.session_state.cogniverse_session_id.strip() or None
    packet = build_dashboard_packet(
        predictions=predictions,
        upper_quality=upper_quality,
        lower_quality=lower_quality,
        inference_state=state,
        inference_confidence=float(predictions["fused"].confidence),
        inference_duration_ms=duration_ms,
        session_id=session_id,
        receiver_active=bool(status.get("receiver_active")),
    )
    try:
        response = CogniverseClient(st.session_state.cogniverse_url.strip()).send_features(packet)
    except CogniverseConnectionError as exc:
        st.session_state.cogniverse_last_status = f"Bridge error: {exc}"
    else:
        accepted = bool(response.get("accepted"))
        st.session_state.cogniverse_last_status = (
            f"Last packet: {'accepted' if accepted else 'rejected'} · {time.strftime('%H:%M:%S')}"
        )


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
        st.metric(
            "Pi lower camera",
            "CONNECTED" if status["lower_connected"] and status["lower_active"] else "DISCONNECTED",
            border=True,
        )
        st.metric("Synchronized pairs / 10 s", status["sync_10s"], border=True)
        if st.session_state.simulation_mode:
            simulated_state = str(status["simulated_state"])
            st.metric(
                "Simulated student state",
                LABEL_NAMES.get(simulated_state, simulated_state),
                "demo signal",
                border=True,
            )

    left, right = st.columns(2)
    previews = {}
    for column, role, title, description in (
        (left, "upper_face", "Upper face — ESP32-S3", "Eyes and eyebrows"),
        (right, "lower_face", "Lower face — Pi Camera", "Lips, mouth and chin"),
    ):
        with column:
            with st.container(border=True):
                st.subheader(title)
                st.caption(description)
                try:
                    preview = pi.preview(role, None if session_id == "none" else session_id)
                except PiConnectionError as exc:
                    st.warning(f"Preview unavailable: {exc}")
                    continue
                if preview is None:
                    st.info("Waiting for the first camera preview frame…")
                else:
                    previews[role] = preview
                    st.image(preview.png, width="stretch")
                    if preview.age_seconds <= 5:
                        st.success(f"LIVE • frame age {preview.age_seconds:.1f} s")
                    else:
                        st.warning(f"STALE • last frame {preview.age_seconds:.1f} s ago")

    with st.container(border=True):
        st.subheader(":material/psychology: Live two-camera CNN")
        upper_preview = previews.get("upper_face")
        lower_preview = previews.get("lower_face")
        if upper_preview is None or lower_preview is None:
            st.info("Waiting for both synchronized camera previews…")
        elif upper_preview.age_seconds > 5 or lower_preview.age_seconds > 5:
            st.warning("CNN paused because at least one camera frame is stale.")
        else:
            try:
                if st.session_state.simulation_mode:
                    predictions = simulated_predictions(pi.current_state)
                else:
                    predictions = cnn_predictor().predict_bytes(
                        upper_preview.png, lower_preview.png
                    )
            except Exception as exc:
                st.error(f"CNN inference failed: {exc}")
            else:
                with st.container(horizontal=True):
                    for key, title in (
                        ("upper_face", "Upper expression"),
                        ("lower_face", "Lower expression"),
                        ("fused", "Fused expression"),
                    ):
                        prediction = predictions[key]
                        st.metric(
                            title,
                            prediction.label.replace("_", " ").title(),
                            f"{prediction.confidence:.1%} confidence",
                            border=True,
                        )
                st.session_state["_cogniverse_upper_preview"] = upper_preview
                st.session_state["_cogniverse_lower_preview"] = lower_preview
                forward_to_cogniverse(predictions, status, control, pi)
                fused = predictions["fused"]
                probability_data = pd.DataFrame(
                    {
                        "Expression": [label.title() for label in fused.probabilities],
                        "Probability": list(fused.probabilities.values()),
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
