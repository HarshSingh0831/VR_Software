# Cogniverse bridge

The Streamlit dashboard can now forward simulator or preview predictions to the
Cogniverse backend. This is a software-only bridge for testing before the
Raspberry Pi is available.

1. Start Cogniverse on the laptop (`node backend/server.mjs`).
2. Start Streamlit from this repository (`streamlit run streamlit_app.py`).
3. In the sidebar, enable **Forward live predictions**.
4. Keep the URL as `http://127.0.0.1:8000` when both applications run on the
   same laptop. Use the laptop Wi-Fi IP when Streamlit runs elsewhere.
5. Leave the VR session ID blank to route to the currently active Cogniverse
   session, or enter the ID shown by the Cogniverse live-session page.

Simulation mode sends the selected taxonomy state. Real-camera mode currently
sends `unknown` for the inference state because the existing expression CNN is
not yet the trained engagement-state model. The Pi inference loop should use
the same packet schema through `raspberry_pi_sender.py` once hardware is live.
