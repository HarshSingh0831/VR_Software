from __future__ import annotations

from pathlib import Path

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import (
    BaseDocTemplate,
    Frame,
    PageTemplate,
    Paragraph,
    Spacer,
    Table,
    TableStyle,
    PageBreak,
    KeepTogether,
)


ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "output" / "pdf" / "Adaptive_VR_Project_Handoff.pdf"

NAVY = colors.HexColor("#0B1324")
BLUE = colors.HexColor("#2563EB")
CYAN = colors.HexColor("#06B6D4")
GREEN = colors.HexColor("#16A34A")
AMBER = colors.HexColor("#D97706")
LIGHT = colors.HexColor("#F4F7FB")
MID = colors.HexColor("#D9E2F0")
TEXT = colors.HexColor("#172033")
MUTED = colors.HexColor("#53627A")


def footer(canvas, doc):
    canvas.saveState()
    canvas.setStrokeColor(MID)
    canvas.line(18 * mm, 13 * mm, 192 * mm, 13 * mm)
    canvas.setFont("Helvetica", 8)
    canvas.setFillColor(MUTED)
    canvas.drawString(18 * mm, 8 * mm, "Adaptive VR Learning System - Codex handoff")
    canvas.drawRightString(192 * mm, 8 * mm, f"Page {doc.page}")
    canvas.restoreState()


def table(rows, widths, header=True):
    body_cell = ParagraphStyle(
        "TableBody",
        fontName="Helvetica",
        fontSize=7.7,
        leading=10.2,
        textColor=TEXT,
        wordWrap="LTR",
    )
    header_cell = ParagraphStyle(
        "TableHeader",
        parent=body_cell,
        fontName="Helvetica-Bold",
        textColor=colors.white,
    )
    rendered = [
        [
            cell if isinstance(cell, Paragraph) else Paragraph(str(cell), header_cell if header and row_index == 0 else body_cell)
            for cell in row
        ]
        for row_index, row in enumerate(rows)
    ]
    item = Table(rendered, colWidths=widths, repeatRows=1 if header else 0, hAlign="LEFT")
    style = [
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("FONTNAME", (0, 0), (-1, -1), "Helvetica"),
        ("GRID", (0, 0), (-1, -1), 0.4, MID),
        ("LEFTPADDING", (0, 0), (-1, -1), 6),
        ("RIGHTPADDING", (0, 0), (-1, -1), 6),
        ("TOPPADDING", (0, 0), (-1, -1), 6),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
        ("ROWBACKGROUNDS", (0, 1 if header else 0), (-1, -1), [colors.white, LIGHT]),
    ]
    if header:
        style += [
            ("BACKGROUND", (0, 0), (-1, 0), NAVY),
        ]
    item.setStyle(TableStyle(style))
    return item


def build():
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    styles = getSampleStyleSheet()
    styles.add(ParagraphStyle(name="CoverTitle", parent=styles["Title"], fontName="Helvetica-Bold", fontSize=28, leading=33, textColor=colors.white, alignment=TA_CENTER, spaceAfter=12))
    styles.add(ParagraphStyle(name="CoverSub", parent=styles["Normal"], fontName="Helvetica", fontSize=12, leading=18, textColor=colors.HexColor("#DDE9FF"), alignment=TA_CENTER))
    styles.add(ParagraphStyle(name="H1x", parent=styles["Heading1"], fontName="Helvetica-Bold", fontSize=18, leading=22, textColor=NAVY, spaceBefore=4, spaceAfter=10))
    styles.add(ParagraphStyle(name="H2x", parent=styles["Heading2"], fontName="Helvetica-Bold", fontSize=12, leading=15, textColor=BLUE, spaceBefore=10, spaceAfter=5))
    styles.add(ParagraphStyle(name="Bodyx", parent=styles["BodyText"], fontName="Helvetica", fontSize=9.3, leading=14, textColor=TEXT, spaceAfter=7))
    styles.add(ParagraphStyle(name="Smallx", parent=styles["BodyText"], fontName="Helvetica", fontSize=8, leading=11, textColor=MUTED, spaceAfter=4))
    styles.add(ParagraphStyle(name="Callout", parent=styles["BodyText"], fontName="Helvetica-Bold", fontSize=10, leading=15, textColor=NAVY, backColor=colors.HexColor("#E8F1FF"), borderColor=BLUE, borderWidth=0.7, borderPadding=9, spaceBefore=6, spaceAfter=10))

    doc = BaseDocTemplate(str(OUTPUT), pagesize=A4, rightMargin=18 * mm, leftMargin=18 * mm, topMargin=18 * mm, bottomMargin=18 * mm, title="Adaptive VR Project Handoff")
    frame = Frame(doc.leftMargin, doc.bottomMargin, doc.width, doc.height, id="normal")
    doc.addPageTemplates(PageTemplate(id="main", frames=frame, onPage=footer))
    story = []

    cover = Table([[Paragraph("ADAPTIVE VR<br/>LEARNING SYSTEM", styles["CoverTitle"])], [Paragraph("Technical handoff: completed work, operating workflow, verification status, and remaining roadmap", styles["CoverSub"])]], colWidths=[174 * mm], rowHeights=[68 * mm, 43 * mm])
    cover.setStyle(TableStyle([("BACKGROUND", (0, 0), (-1, -1), NAVY), ("BOX", (0, 0), (-1, -1), 1, NAVY), ("VALIGN", (0, 0), (-1, -1), "MIDDLE"), ("LEFTPADDING", (0, 0), (-1, -1), 18), ("RIGHTPADDING", (0, 0), (-1, -1), 18)]))
    story += [Spacer(1, 35 * mm), cover, Spacer(1, 12 * mm), Paragraph("Project owner: Harsh Singh", styles["Bodyx"]), Paragraph("Repository target: HarshSingh0831/VR_Software", styles["Bodyx"]), Paragraph("Prepared: 22 July 2026", styles["Bodyx"]), PageBreak()]

    story += [Paragraph("1. Executive summary", styles["H1x"]), Paragraph("This project is an adaptive learning system for a smartphone-based VR headset. It combines a DC motor lesson, eight short supporting videos, bilingual continuous voice commands, upper-face camera inference, timed quizzes, session logging, and rule-based multimodal engagement analysis.", styles["Bodyx"]), Paragraph("Current outcome", styles["H2x"]), Paragraph("The laptop and smartphone can open the same HTTPS Streamlit dashboard simultaneously. A shared in-process synchronization bus distributes content selection, playback commands, quiz phase, and understanding-check state between active browser sessions. The smartphone browser supplies microphone commands; the Raspberry Pi and ESP32 camera pipeline supplies the upper-face signal.", styles["Callout"]), Paragraph("Important portability note", styles["H2x"]), Paragraph("Large MP4 lesson files, trained model weights, runtime recordings, private keys, certificates, Wi-Fi credentials, and Raspberry Pi secrets are intentionally excluded from Git. A new machine must restore those local assets and regenerate its HTTPS certificate.", styles["Bodyx"])]

    story += [Paragraph("2. System architecture", styles["H1x"])]
    arch = [
        ["Layer", "Technology", "Responsibility"],
        ["VR learner", "Smartphone browser + headset", "Displays lesson, subcontent, quizzes, voice status, and analysis."],
        ["Dashboard", "Python 3 + Streamlit + Custom Components v2", "Responsive interface, video control, popup timing, quiz workflow, and synchronization."],
        ["Upper-face sensing", "DFRobot ESP32-S3 AI camera", "Captures the visible eye/forehead region in grayscale-compatible frames."],
        ["Edge gateway", "Raspberry Pi 4 Model B", "Receives camera data, exposes preview/status, stores labeled recordings, and connects to laptop."],
        ["Inference", "CNN inference module", "Produces a live upper-face expression estimate; target states are focused, confused, happy, bored, and drowsy."],
        ["Speech", "Vosk laptop service + browser SpeechRecognition", "English, Hindi, and Hinglish commands; confusion, help, repeat, and hesitation features."],
        ["Analytics", "JSONL session events + rule baseline", "Combines camera emotion, speech behaviour, quiz correctness, and response time."],
    ]
    story += [table(arch, [31 * mm, 49 * mm, 94 * mm]), Spacer(1, 8)]

    story += [Paragraph("3. Implemented learner workflow", styles["H1x"])]
    for title, body in [
        ("Main lesson", "The 9:01 DC motor video is played on the laptop or smartphone. Playback commands are synchronized across active dashboard sessions."),
        ("Timed suggestions", "A compact subcontent name appears in the upper-left corner for 30 seconds at its configured timestamp. Only one suggestion is shown at a time."),
        ("Voice selection", "The learner can say Play Torque, Play Current Reverse, Play Multiple Coils, Play Commutator, Play Brushes, Play Magnets, or Play Electromagnet."),
        ("Understanding check", "After a subcontent video ends, the app asks whether the learner understood. Yes resumes the main video from its stored browser position; No restarts the explanation."),
        ("Quiz schedule", "Seven MID PART 1 questions open at approximately 4:30. Seven LAST PART questions open when the main lesson finishes."),
        ("Adaptation signal", "Support is recommended when the camera indicates a support-needed state, the learner uses confusion/help/repeat language, or quiz accuracy falls below the rule threshold."),
    ]:
        story.append(KeepTogether([Paragraph(title, styles["H2x"]), Paragraph(body, styles["Bodyx"])]))

    story += [PageBreak(), Paragraph("4. Subcontent schedule", styles["H1x"])]
    schedule = [["Popup time", "Subcontent", "Popup", "Media status"]] + [
        ["1:13", "Magnets", "30 seconds", "Integrated"],
        ["2:35", "Electromagnet", "30 seconds", "Integrated"],
        ["4:20", "Curved Magnet", "30 seconds", "Integrated"],
        ["4:50", "Commutator", "30 seconds", "Integrated"],
        ["4:59", "Brushes", "30 seconds", "Integrated"],
        ["5:35", "Current Reverse", "30 seconds", "Integrated"],
        ["6:14", "Multiple Coils", "30 seconds", "Integrated"],
        ["7:02", "Torque", "30 seconds", "Integrated"],
    ]
    story += [table(schedule, [28 * mm, 58 * mm, 35 * mm, 53 * mm]), Spacer(1, 8), Paragraph("The timestamps are lesson positions taken from the supplied WhatsApp schedule, not the durations of the short subcontent files.", styles["Smallx"])]

    story += [Paragraph("5. Quiz content", styles["H1x"]), Paragraph("Two supplied Word documents were parsed into config/learning_quiz.json. The valid LAST PART copy was DC_Motor_LAST_PART_Quiz (2).docx; the same filename without (2) was a zero-byte duplicate.", styles["Bodyx"])]
    quiz = [
        ["Phase", "Trigger", "Questions", "Coverage"],
        ["Midpoint", "Main video reaches about 4:30", "7", "Circuit, magnetic force, armature, torque, commutator, energy conversion"],
        ["Final", "Main video ends", "7", "Brushes, curved poles, multiple coils, components, current path, smooth torque"],
    ]
    story += [table(quiz, [29 * mm, 48 * mm, 23 * mm, 74 * mm])]

    story += [Paragraph("6. Files a future Codex session should inspect first", styles["H1x"])]
    files = [
        ["File", "Purpose"],
        ["learning_app.py", "Primary smartphone/laptop learning dashboard and interaction workflow."],
        ["config/learning_content.json", "Main lesson, eight subcontent paths, popup timestamps, and availability."],
        ["config/learning_quiz.json", "Fourteen MID and LAST quiz questions with answer keys."],
        ["host/adaptive_vr/cnn_inference.py", "Live upper-camera model loading and prediction."],
        ["host/adaptive_vr/speech_live.py", "Continuous offline laptop speech recognition service."],
        ["host/adaptive_vr/dashboard_pi.py", "Raspberry Pi status, preview, and recording control."],
        ["host/adaptive_vr/learning_log.py", "Session event persistence and summary metrics."],
        ["firmware/esp32_local_processor/", "ESP32-S3 camera acquisition and local-processing firmware."],
        ["raspberry-pi/", "Pi receiver/service setup and camera integration resources."],
    ]
    story += [table(files, [64 * mm, 110 * mm])]

    story += [PageBreak(), Paragraph("7. Completed work", styles["H1x"])]
    completed = [
        ["Area", "Status", "Evidence / behaviour"],
        ["Architecture and protocols", "Ready", "ESP32, Pi, laptop, browser, analytics, and Unity message structures exist."],
        ["Eight subcontent videos", "Ready locally", "All eight files are mapped; media remains on D: and is excluded from Git."],
        ["Timed corner popup", "Ready", "Left-corner name, 30-second visibility, timestamp schedule."],
        ["Voice video selection", "Ready", "English/Hindi/Hinglish command routing and named subcontent selection."],
        ["Understanding verification", "Ready", "Automatic end prompt, replay or main-video continuation."],
        ["Two quiz sets", "Ready", "14 verified questions: 7 midpoint and 7 final."],
        ["Upper camera preview", "Ready when hardware online", "Pi gateway and ESP32 connection monitoring are implemented."],
        ["CNN inference integration", "Baseline ready", "Live prediction is connected to the dashboard."],
        ["Multimodal rule analysis", "Ready baseline", "Camera, speech, quiz accuracy, help and replay events are combined."],
        ["Laptop + smartphone HTTPS", "Ready on current network", "Dashboard listens on 0.0.0.0:8502 using a local certificate."],
        ["Automated verification", "Passing", "51 repository tests and Streamlit AppTest passed at handoff time."],
    ]
    story += [table(completed, [47 * mm, 29 * mm, 98 * mm])]

    story += [Paragraph("8. Remaining work and priority", styles["H1x"])]
    remaining = [
        ["Priority", "Remaining item", "Acceptance condition"],
        ["P0", "Collect balanced headset-specific upper-face data", "Five target states have enough labeled samples across users, lighting, and sessions."],
        ["P0", "Fine-tune and validate the five-state CNN", "Held-out participant evaluation, confusion matrix, per-class precision/recall/F1, and saved production weights."],
        ["P0", "Hardware endurance test", "ESP32/Pi/dashboard runs continuously without stream loss, overheating, or memory failure."],
        ["P1", "Persistent multi-device synchronization", "Replace the in-process bus with SQLite/Redis/WebSocket state that survives server restarts and supports multiple learners."],
        ["P1", "Calibrate emotion thresholds", "Rules are derived from real headset trials rather than generic pretrained facial labels."],
        ["P1", "Speech evaluation", "English, Hindi, and Hinglish command accuracy is measured under headset noise."],
        ["P1", "Unity/VR application completion", "Production VR scene consumes live adaptation messages and is tested in the headset."],
        ["P1", "Secure deployment", "Stable hostname, trusted certificate, authentication, credential rotation, and no hard-coded network address."],
        ["P2", "Research evaluation", "Ethics/consent, participant protocol, baseline comparison, statistical analysis, and final paper results."],
    ]
    story += [table(remaining, [20 * mm, 62 * mm, 92 * mm])]

    story += [Paragraph("9. Setup on another computer or Codex account", styles["H1x"])]
    steps = [
        "Clone the repository and create a Python virtual environment from pyproject.toml.",
        "Restore the Vosk models under models/ and the lesson/subcontent MP4 files under the configured local media path.",
        "Create firmware/esp32_local_processor/secrets.h from the example file; never commit credentials.",
        "Configure Raspberry Pi hostname/IP and SSH key locally.",
        "Regenerate HTTPS certificates for the current laptop IP using scripts/generate_local_https_cert.py, then install the CA certificate on the phone.",
        "Run the continuous speech service and then run learning_app.py with Streamlit on port 8502.",
        "Open the HTTPS network URL on the smartphone and localhost/network URL on the laptop.",
        "Run the test suite before collecting data or changing the inference model.",
    ]
    for index, step in enumerate(steps, 1):
        story.append(Paragraph(f"<b>{index}.</b> {step}", styles["Bodyx"]))

    story += [Paragraph("10. Recommended next Codex prompt", styles["H1x"]), Paragraph("Continue the Adaptive VR Learning System from output/pdf/Adaptive_VR_Project_Handoff.pdf. First inspect learning_app.py, config/learning_content.json, config/learning_quiz.json, and the current git status. Preserve the eight-video workflow, 14-question midpoint/final quiz, continuous bilingual speech, Raspberry Pi/ESP32 camera path, and secret exclusions. The next objective is to replace the temporary in-process device synchronization with persistent per-session state, then run a real headset data collection and five-state CNN fine-tuning evaluation. Do not claim hardware or model accuracy without a live verification result.", styles["Callout"]), Paragraph("End of handoff", styles["Smallx"])]

    doc.build(story)
    print(OUTPUT)


if __name__ == "__main__":
    build()
