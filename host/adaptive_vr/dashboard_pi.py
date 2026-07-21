from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
from io import BytesIO
import json
import shlex
import threading
import time
from typing import Any

try:
    import paramiko
except ModuleNotFoundError:  # Simulation mode does not need SSH support.
    paramiko = None  # type: ignore[assignment]
from PIL import Image


CALIBRATION_ROOT = "/var/lib/adaptive-vr/calibration"
CONTROL_MODULE = "PYTHONPATH=/opt/adaptive-vr/host python3 -m adaptive_vr.calibration_control"


class PiConnectionError(RuntimeError):
    pass


@dataclass(frozen=True, slots=True)
class Preview:
    png: bytes
    age_seconds: float


class PiGateway:
    """Small, thread-safe SSH/SFTP client used by the local dashboard."""

    def __init__(self, host: str, username: str, password: str):
        self.host = host
        self.username = username
        self.password = password
        self._client: paramiko.SSHClient | None = None
        self._lock = threading.RLock()

    def _connected_client(self) -> paramiko.SSHClient:
        if paramiko is None:
            raise PiConnectionError(
                "Pi mode requires paramiko. Install the dashboard dependencies with "
                "python -m pip install 'paramiko>=5,<6'."
            )
        with self._lock:
            if self._client is not None:
                transport = self._client.get_transport()
                if transport is not None and transport.is_active():
                    return self._client
                self._client.close()
            client = paramiko.SSHClient()
            client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
            try:
                client.connect(
                    self.host,
                    username=self.username,
                    password=self.password,
                    timeout=5,
                    auth_timeout=5,
                    banner_timeout=5,
                    look_for_keys=False,
                    allow_agent=False,
                )
            except Exception as exc:
                client.close()
                raise PiConnectionError(str(exc)) from exc
            self._client = client
            return client

    def run(self, command: str, timeout: float = 8) -> str:
        with self._lock:
            client = self._connected_client()
            try:
                _, stdout, stderr = client.exec_command(command, timeout=timeout)
                output = stdout.read().decode("utf-8", errors="replace")
                error = stderr.read().decode("utf-8", errors="replace").strip()
                status = stdout.channel.recv_exit_status()
            except Exception as exc:
                if self._client is not None:
                    self._client.close()
                self._client = None
                raise PiConnectionError(str(exc)) from exc
            if status != 0:
                raise PiConnectionError(error or f"Remote command failed with status {status}")
            return output

    def read_bytes(self, path: str) -> tuple[bytes, float]:
        with self._lock:
            client = self._connected_client()
            try:
                with client.open_sftp() as sftp:
                    stat = sftp.stat(path)
                    with sftp.open(path, "rb") as stream:
                        return stream.read(), stat.st_mtime
            except FileNotFoundError:
                raise
            except Exception as exc:
                raise PiConnectionError(str(exc)) from exc

    def control(self, action: str, **values: str) -> dict[str, Any]:
        if action == "start":
            command = (
                f"{CONTROL_MODULE} start --participant {shlex.quote(values['participant'])} "
                f"--label {shlex.quote(values['label'])}"
            )
            if values.get("session"):
                command += f" --session {shlex.quote(values['session'])}"
        elif action == "label":
            command = f"{CONTROL_MODULE} label {shlex.quote(values['label'])}"
        elif action == "stop":
            command = f"{CONTROL_MODULE} stop"
        else:
            raise ValueError(f"Unknown action: {action}")
        return json.loads(self.run(command))

    def snapshot(self) -> dict[str, Any]:
        command = f"""
printf 'receiver='; systemctl is-active adaptive-vr-receiver.service 2>/dev/null || true
printf 'lower='; systemctl is-active adaptive-vr-lower-face.service 2>/dev/null || true
printf 'connections='; ss -Htn state established 2>/dev/null | grep -c ':8765' || true
printf 'upper='; ss -Htn state established 2>/dev/null | grep ':8765' | grep -c '172.18.57.241' || true
printf 'lower_socket='; ss -Htn state established 2>/dev/null | grep ':8765' | grep -c '127.0.0.1' || true
printf 'sync10='; journalctl -u adaptive-vr-receiver.service --since '10 seconds ago' --no-pager -q 2>/dev/null | grep -c 'Synchronized upper=' || true
printf 'control='; test -f {CALIBRATION_ROOT}/control.json && tr -d '\\n' < {CALIBRATION_ROOT}/control.json || printf '{{"active":false}}'
printf '\nframes='; control_session=$(python3 -c "import json; p='{CALIBRATION_ROOT}/control.json'; print(json.load(open(p)).get('session_id',''))" 2>/dev/null || true); test -n "$control_session" && wc -l < "{CALIBRATION_ROOT}/sessions/$control_session/frames.jsonl" 2>/dev/null || printf '0'
"""
        lines = self.run(command).splitlines()
        values: dict[str, str] = {}
        for line in lines:
            if "=" in line:
                key, value = line.split("=", 1)
                values[key.strip()] = value.strip()
        try:
            control = json.loads(values.get("control", '{"active":false}'))
        except json.JSONDecodeError:
            control = {"active": False}
        return {
            "receiver_active": values.get("receiver") == "active",
            "lower_active": values.get("lower") == "active",
            "connections": int(values.get("connections", "0") or 0),
            "upper_connected": int(values.get("upper", "0") or 0) > 0,
            "lower_connected": int(values.get("lower_socket", "0") or 0) > 0,
            "sync_10s": int(values.get("sync10", "0") or 0),
            "frames": int(values.get("frames", "0") or 0),
            "control": control,
            "checked_at": time.time(),
        }

    def preview(self, role: str, session_id: str | None = None) -> Preview | None:
        try:
            raw, modified = self.read_bytes(f"{CALIBRATION_ROOT}/preview/{role}.pgm")
        except FileNotFoundError:
            if not session_id:
                return None
            directory = f"{CALIBRATION_ROOT}/sessions/{session_id}/images/{role}"
            with self._lock:
                try:
                    client = self._connected_client()
                    with client.open_sftp() as sftp:
                        images = [
                            item
                            for item in sftp.listdir_attr(directory)
                            if item.filename.endswith(".pgm")
                        ]
                        if not images:
                            return None
                        latest = max(images, key=lambda item: item.st_mtime)
                        with sftp.open(f"{directory}/{latest.filename}", "rb") as stream:
                            raw = stream.read()
                        modified = latest.st_mtime
                except FileNotFoundError:
                    return None
                except Exception as exc:
                    raise PiConnectionError(str(exc)) from exc
        with Image.open(BytesIO(raw)) as image:
            converted = image.convert("L")
            output = BytesIO()
            converted.save(output, format="PNG")
        return Preview(output.getvalue(), max(0.0, time.time() - modified))

    def label_counts(self, session_id: str, max_bytes: int = 2_000_000) -> Counter[str]:
        path = f"{CALIBRATION_ROOT}/sessions/{session_id}/frames.jsonl"
        try:
            raw, _ = self.read_bytes(path)
        except FileNotFoundError:
            return Counter()
        if len(raw) > max_bytes:
            raw = raw[-max_bytes:]
            raw = raw.split(b"\n", 1)[-1]
        counts: Counter[str] = Counter()
        for line in raw.splitlines():
            try:
                counts[str(json.loads(line)["label"])] += 1
            except (json.JSONDecodeError, KeyError):
                continue
        return counts
