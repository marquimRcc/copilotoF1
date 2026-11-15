"""Receptor UDP único e desacoplado para telemetria do EA SPORTS F1."""

import socket
import threading
from typing import Dict, List, Optional
from packets.header import (
    PACKET_ID_CAR_TELEMETRY,
    PACKET_ID_LAP_DATA,
    PACKET_ID_SESSION,
    parse_header,
)
from packets.car_telemetry import parse_car_telemetry
from packets.lap_data import parse_lap_data
from packets.session import parse_session_data
from core.state import TelemetryState
from core.csv_recorder import AsyncLapRecorder


class F1UdpListener:
    """Escuta e distribui datagramas UDP em thread dedicada sem travar a interface."""

    def __init__(
        self,
        host: str = "127.0.0.1",
        port: int = 20777,
        state: Optional[TelemetryState] = None,
        recorder: Optional[AsyncLapRecorder] = None,
        record_csv: bool = True,
    ):
        self.host = host
        self.port = port
        self.state = state or TelemetryState()
        self.recorder = recorder
        self.record_csv = record_csv

        self.sock: Optional[socket.socket] = None
        self.running = False
        self.thread: Optional[threading.Thread] = None

        self.active_lap_num: int = 0
        self.last_lap_invalid: bool = False
        self.lap_samples: List[Dict] = []
        self._lock = threading.Lock()

    def start(self):
        """Inicia o socket e a thread de escuta UDP."""
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.sock.settimeout(0.5)
        self.sock.bind((self.host, self.port))
        self.running = True

        self.thread = threading.Thread(target=self._listen_loop, daemon=True)
        self.thread.start()

    def _listen_loop(self):
        """Loop contínuo de recepção de pacotes."""
        while self.running:
            try:
                if not self.sock:
                    break
                data, _ = self.sock.recvfrom(2048)
                self.process_packet(data)
            except socket.timeout:
                continue
            except OSError:
                break
            except Exception:
                continue

    def process_packet(self, data: bytes):
        """Decodifica e despacha pacotes de telemetria."""
        header = parse_header(data)
        if not header:
            return

        if header.packet_id == PACKET_ID_SESSION:
            session = parse_session_data(data, header)
            if session and self.state:
                self.state.set_session_info(
                    track_id=session.track_id,
                    track_name=session.track_name,
                    track_length=session.track_length,
                )

        elif header.packet_id == PACKET_ID_LAP_DATA:
            lap = parse_lap_data(data, header)
            if lap and self.state:
                self.state.update_lap_data(
                    lap_dist=lap.lap_distance,
                    total_dist=lap.total_distance,
                    lap_num=lap.current_lap_num,
                    lap_time_ms=lap.current_lap_time_ms,
                    last_time_ms=lap.last_lap_time_ms,
                    is_valid=not lap.current_lap_invalid,
                    driver_status=lap.driver_status,
                )

                is_flying_lap = (
                    lap.lap_distance >= 0.0
                    and lap.current_lap_time_ms > 0
                    and lap.driver_status != 2
                )

                with self._lock:
                    # 1. Conclusão de volta (lap_num incrementou)
                    if self.active_lap_num > 0 and lap.current_lap_num > self.active_lap_num:
                        completed_lap_valid = not self.last_lap_invalid

                        if completed_lap_valid and lap.last_lap_time_ms > 0:
                            if (
                                self.state.best_session_lap_ms is None
                                or lap.last_lap_time_ms < self.state.best_session_lap_ms
                            ):
                                self.state.best_session_lap_ms = lap.last_lap_time_ms

                        if (
                            self.record_csv
                            and self.recorder
                            and len(self.lap_samples) >= 30
                            and lap.last_lap_time_ms > 0
                        ):
                            self.recorder.enqueue_lap(
                                samples=self.lap_samples,
                                lap_number=self.active_lap_num,
                                lap_time_ms=lap.last_lap_time_ms,
                                is_valid=completed_lap_valid,
                                track_id=self.state.track_id,
                                track_name=self.state.track_name,
                            )

                        if self.active_lap_num == 1:
                            self.state.finalize_auto_learning()

                        self.lap_samples.clear()
                        self.active_lap_num = lap.current_lap_num if is_flying_lap else 0
                        self.last_lap_invalid = lap.current_lap_invalid

                    # 2. Descarta volta se entrou nos boxes
                    elif lap.driver_status == 2:
                        self.lap_samples.clear()
                        self.active_lap_num = 0
                        self.last_lap_invalid = False

                    # 3. Descarta se reiniciou a volta no Time Trial
                    elif lap.current_lap_time_ms == 0 and len(self.lap_samples) > 0:
                        self.lap_samples.clear()
                        self.active_lap_num = 0
                        self.last_lap_invalid = False

                    # 4. Início de nova volta rápida
                    elif is_flying_lap and self.active_lap_num == 0:
                        self.active_lap_num = lap.current_lap_num
                        self.last_lap_invalid = lap.current_lap_invalid

                    # 5. Durante a volta: propaga flag de volta inválida
                    elif self.active_lap_num > 0 and lap.current_lap_num == self.active_lap_num:
                        if lap.current_lap_invalid:
                            self.last_lap_invalid = True

        elif header.packet_id == PACKET_ID_CAR_TELEMETRY:
            tel = parse_car_telemetry(data, header)
            if tel and self.state:
                self.state.update_telemetry(
                    speed=tel.speed,
                    throttle=tel.throttle,
                    brake=tel.brake,
                    steer=tel.steer,
                    gear=tel.gear,
                    rpm=tel.engine_rpm,
                    drs=tel.drs,
                )

                if self.record_csv and self.active_lap_num > 0 and self.state.lap_distance >= 0.0:
                    with self._lock:
                        sample = {
                            "session_time": round(header.session_time, 3),
                            "lap_number": self.state.current_lap_num,
                            "lap_distance": self.state.lap_distance,
                            "speed": tel.speed,
                            "throttle": tel.throttle,
                            "brake": tel.brake,
                            "steer": tel.steer,
                            "gear": tel.gear,
                            "engine_rpm": tel.engine_rpm,
                            "drs": tel.drs,
                            "lap_time_ms": self.state.lap_time_ms,
                            "is_valid": 0 if (not self.state.is_lap_valid or self.last_lap_invalid) else 1,
                        }
                        self.lap_samples.append(sample)

    def stop(self):
        """Encerra a recepção UDP de forma segura."""
        self.running = False
        if self.sock:
            try:
                self.sock.close()
            except Exception:
                pass
            self.sock = None
        if self.thread and self.thread.is_alive():
            self.thread.join(timeout=1.0)
