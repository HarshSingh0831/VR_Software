# Hardware-free dashboard simulation

The Streamlit dashboard can now be used without a Raspberry Pi, ESP32, camera, or
CNN checkpoint. Enable **Simulation mode (no Pi required)** in the sidebar.

Simulation mode provides:

- live-looking upper-face and lower-face preview images;
- connected receiver and camera status;
- automatic or manually selected student-state scenarios;
- recording, label changes, frame counts, and label totals;
- deterministic upper, lower, and fused expression predictions.

## Run locally

From the repository root, install the dashboard dependencies and start Streamlit:

```powershell
python -m pip install -e ".[dashboard,dev]"
streamlit run streamlit_app.py
```

Leave the Raspberry Pi password empty when using simulation mode. The existing
Pi connection fields are used only after the toggle is switched off.

The simulation gateway intentionally implements the same small interface used by
the live dashboard (`snapshot`, `preview`, `control`, and `label_counts`). This
keeps the dashboard flow hardware-independent and allows the simulator to be
replaced by the real Pi gateway later without changing the UI.
