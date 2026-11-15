"""
Script automatizado para criar a nova branch, aplicar todas as correções arquiteturais,
calibrar Interlagos e adicionar o sincronizador oficial FIA/FastF1 (Opção A).
"""

import json
import os
import subprocess
import sys

ROOT_DIR = os.path.abspath(os.path.dirname(__file__))


def write_file(rel_path: str, content: str) -> None:
    full_path = os.path.join(ROOT_DIR, rel_path)
    os.makedirs(os.path.dirname(full_path), exist_ok=True)
    with open(full_path, "w", encoding="utf-8", newline="\n") as f:
        f.write(content.lstrip("\n"))
    print(f"✅ Atualizado: {rel_path}")


# =====================================================================
# 1. src/core/analyzer.py (Fonte única do motor de análise)
# =====================================================================
CORE_ANALYZER_PY = '''
"""Motor de análise de telemetria e diagnóstico prático curva a curva para o Core."""

import csv
import os
from dataclasses import dataclass
from typing import List, Optional
from tracks.circuits import CircuitInfo, CornerZone, get_circuit_by_track_id


@dataclass
class TelemetryPoint:
    session_time: float
    lap_number: int
    lap_distance: float
    speed: int
    throttle: float
    brake: float
    steer: float
    gear: int
    engine_rpm: int
    drs: int
    lap_time_ms: int
    is_valid: int


@dataclass
class CornerAnalysis:
    corner: CornerZone
    braking_distance: Optional[float]
    braking_speed: Optional[int]
    apex_distance: float
    apex_speed: int
    apex_gear: int
    coasting_time: float
    throttle_pickup_distance: Optional[float]
    full_throttle_distance: Optional[float]


def load_telemetry_csv(csv_path: str) -> List[TelemetryPoint]:
    """Carrega pontos de telemetria de um arquivo CSV."""
    points: List[TelemetryPoint] = []
    if not os.path.exists(csv_path):
        return points

    with open(csv_path, mode="r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            points.append(
                TelemetryPoint(
                    session_time=float(row.get("session_time", 0.0)),
                    lap_number=int(row.get("lap_number", 0)),
                    lap_distance=float(row.get("lap_distance", 0.0)),
                    speed=int(row.get("speed", 0)),
                    throttle=float(row.get("throttle", 0.0)),
                    brake=float(row.get("brake", 0.0)),
                    steer=float(row.get("steer", 0.0)),
                    gear=int(row.get("gear", 0)),
                    engine_rpm=int(row.get("engine_rpm", 0)),
                    drs=int(row.get("drs", 0)),
                    lap_time_ms=int(row.get("lap_time_ms", 0)),
                    is_valid=int(row.get("is_valid", 1)),
                )
            )
    return points


class LapAnalyzer:
    """Analisador cinemático de voltas e gerador de diagnósticos comparativos."""

    PRE_BRAKE_MARGIN_M = 80.0

    def __init__(self, track_id: int = 11, circuit: Optional[CircuitInfo] = None):
        self.track_id = track_id
        self.circuit = circuit or get_circuit_by_track_id(track_id)

    def analyze_corner(self, points: List[TelemetryPoint], corner: CornerZone) -> Optional[CornerAnalysis]:
        """Analisa a passagem por uma curva específica isolando entrada, ápice e saída."""
        zone_points = [p for p in points if corner.start_distance <= p.lap_distance <= corner.end_distance]
        if not zone_points:
            return None

        # 1. Ápice real dentro da zona da curva (menor velocidade registrada)
        min_point = min(zone_points, key=lambda p: p.speed)
        apex_distance = min_point.lap_distance
        apex_speed = min_point.speed
        apex_gear = min_point.gear

        # 2. Ponto de Frenagem: busca desde 80m antes do start_distance até o ápice
        # (Impede que freadas para a curva seguinte após o ápice sejam atribuídas a esta curva)
        search_start = max(0.0, corner.start_distance - self.PRE_BRAKE_MARGIN_M)
        entry_points = [p for p in points if search_start <= p.lap_distance <= apex_distance]

        braking_distance = None
        braking_speed = None
        for p in entry_points:
            if p.brake >= 0.20:
                braking_distance = p.lap_distance
                braking_speed = p.speed
                break

        # 3. Hesitação / Coasting e Retomada de Acelerador
        coasting_time = 0.0
        throttle_pickup_dist = None
        full_throttle_dist = None
        coasting_start_ref = braking_distance if braking_distance is not None else corner.start_distance

        for i in range(1, len(zone_points)):
            curr = zone_points[i]
            prev = zone_points[i - 1]
            dt = curr.session_time - prev.session_time

            if curr.lap_distance >= coasting_start_ref:
                if curr.brake < 0.05 and curr.throttle < 0.10:
                    coasting_time += max(0.0, dt)

            if curr.lap_distance >= apex_distance:
                if throttle_pickup_dist is None and curr.throttle >= 0.20:
                    throttle_pickup_dist = curr.lap_distance
                if full_throttle_dist is None and curr.throttle >= 0.95:
                    full_throttle_dist = curr.lap_distance

        return CornerAnalysis(
            corner=corner,
            braking_distance=braking_distance,
            braking_speed=braking_speed,
            apex_distance=apex_distance,
            apex_speed=apex_speed,
            apex_gear=apex_gear,
            coasting_time=round(coasting_time, 3),
            throttle_pickup_distance=throttle_pickup_dist,
            full_throttle_distance=full_throttle_dist,
        )

    def generate_quick_tip(
        self,
        user_points: List[TelemetryPoint],
        ref_points: Optional[List[TelemetryPoint]] = None,
    ) -> str:
        """Gera um resumo rápido de uma linha para feedback visual instantâneo no HUD."""
        if not self.circuit or not self.circuit.corners:
            return "Volta registrada com sucesso."

        tips = []
        for corner in self.circuit.corners:
            u_analysis = self.analyze_corner(user_points, corner)
            if not u_analysis:
                continue

            r_analysis = self.analyze_corner(ref_points, corner) if ref_points else None

            if u_analysis.braking_distance is not None and r_analysis and r_analysis.braking_distance is not None:
                diff_m = u_analysis.braking_distance - r_analysis.braking_distance
                if diff_m < -12:
                    tips.append(f"C{corner.number} freou {abs(diff_m):.0f}m cedo")
                elif diff_m > 15:
                    tips.append(f"C{corner.number} freou {diff_m:.0f}m tarde")

            if u_analysis.coasting_time > 0.35:
                tips.append(f"C{corner.number} hesitou {u_analysis.coasting_time:.2f}s")

            if len(tips) >= 2:
                break

        if tips:
            return " | ".join(tips)
        return "Volta limpa e consistente!"

    def compare_laps(
        self,
        user_points: List[TelemetryPoint],
        ref_points: Optional[List[TelemetryPoint]] = None,
        user_lap_time_ms: Optional[int] = None,
        ref_lap_time_ms: Optional[int] = None,
    ) -> str:
        """Gera o relatório completo detalhado em texto."""
        circuit_name = self.circuit.name if self.circuit else f"Circuito {self.track_id}"
        lines = [
            "=" * 65,
            f"🏎️  DIAGNÓSTICO PRÁTICO DE PILOTAGEM - {circuit_name.upper()}",
            "=" * 65,
        ]

        if not self.circuit or not self.circuit.corners:
            lines.append(f"⚠️ Circuito ID {self.track_id} ainda não possui mapeamento de curvas.")
            return "\\n".join(lines)

        u_time = user_lap_time_ms if (user_lap_time_ms and user_lap_time_ms > 0) else (user_points[-1].lap_time_ms if user_points else 0)
        r_time = ref_lap_time_ms if (ref_lap_time_ms and ref_lap_time_ms > 0) else (ref_points[-1].lap_time_ms if ref_points else None)

        if u_time > 0:
            lines.append(f"⏱️ Tempo da sua volta: {self._format_ms(u_time)}")
        if r_time and r_time > 0:
            delta_s = (u_time - r_time) / 1000.0
            lines.append(f"⏱️ Tempo de referência: {self._format_ms(r_time)} (Delta: {delta_s:+.3f}s)")
        else:
            lines.append("⏱️ Referência: 1ª volta base registrada na sessão")
        lines.append("-" * 65)

        for corner in self.circuit.corners:
            u_analysis = self.analyze_corner(user_points, corner)
            if not u_analysis:
                continue

            r_analysis = self.analyze_corner(ref_points, corner) if ref_points else None
            lines.append(f"\\n📍 Curva {corner.number} ({corner.name})")

            # 1. Diagnóstico de Ponto de Frenagem
            if u_analysis.braking_distance is not None:
                if r_analysis and r_analysis.braking_distance is not None:
                    diff_m = u_analysis.braking_distance - r_analysis.braking_distance
                    if diff_m < -8:
                        lines.append(
                            f"   🛑 FRENAGEM ANTECIPADA: Freou a {abs(diff_m):.1f}m ANTES do ideal "
                            f"({u_analysis.braking_distance:.0f}m vs {r_analysis.braking_distance:.0f}m)."
                        )
                    elif diff_m > 12:
                        lines.append(
                            f"   ⚠️ FRENAGEM TARDIA: Freou {diff_m:.1f}m mais tarde que a referência "
                            f"({u_analysis.braking_distance:.0f}m vs {r_analysis.braking_distance:.0f}m)."
                        )
                    else:
                        lines.append(f"   ✅ FRENAGEM NO PONTO: Perfeito a {u_analysis.braking_distance:.0f}m.")
                else:
                    lines.append(
                        f"   🛑 Ponto de Frenagem: acionado aos {u_analysis.braking_distance:.0f}m "
                        f"a {u_analysis.braking_speed} km/h."
                    )

            # 2. Diagnóstico de Velocidade de Ápice
            if r_analysis:
                speed_diff = u_analysis.apex_speed - r_analysis.apex_speed
                if speed_diff < -5:
                    lines.append(
                        f"   📉 VELOCIDADE DE ÁPICE BAIXA: {u_analysis.apex_speed} km/h "
                        f"(referência: {r_analysis.apex_speed} km/h)."
                    )
                elif speed_diff > 4:
                    lines.append(
                        f"   ⚡ BOA VELOCIDADE DE ÁPICE: {u_analysis.apex_speed} km/h "
                        f"({speed_diff:+d} km/h vs referência)."
                    )
                else:
                    lines.append(f"   ✅ Velocidade no Ápice: {u_analysis.apex_speed} km/h (equilibrada).")
            else:
                lines.append(f"   🌀 Velocidade no Ápice: {u_analysis.apex_speed} km/h (Marcha: {u_analysis.apex_gear}ª).")

            # 3. Diagnóstico de Marcha (ignora curvas flat-out de 8ª marcha)
            if corner.gear_reference and corner.gear_reference < 8 and u_analysis.apex_gear != corner.gear_reference:
                if 0 < u_analysis.apex_gear < corner.gear_reference:
                    lines.append(
                        f"   ⚙️ MARCHA: Feita em {u_analysis.apex_gear}ª marcha. "
                        f"Referência é {corner.gear_reference}ª marcha."
                    )

            # 4. Hesitação
            if u_analysis.coasting_time > 0.25:
                lines.append(f"   ⏱️ HESITAÇÃO NA SAÍDA: {u_analysis.coasting_time:.2f}s de carro solto.")
            elif u_analysis.coasting_time <= 0.15:
                lines.append(
                    f"   🚀 TRANSIÇÃO RÁPIDA: Transição freio -> acelerador precisa ({u_analysis.coasting_time:.2f}s)."
                )

        lines.append("\\n" + "=" * 65)
        return "\\n".join(lines)

    @staticmethod
    def _format_ms(ms: int) -> str:
        minutes = ms // 60000
        seconds = (ms % 60000) / 1000.0
        return f"{minutes:02d}:{seconds:06.3f}"
'''

# =====================================================================
# 2. src/analyzer.py (Fachada CLI sem duplicação)
# =====================================================================
SRC_ANALYZER_PY = '''
"""Interface de linha de comando (CLI) para o motor de análise de telemetria."""

import argparse
import os
import sys

from core.analyzer import (
    CornerAnalysis,
    LapAnalyzer,
    TelemetryPoint,
    load_telemetry_csv,
)

__all__ = [
    "CornerAnalysis",
    "LapAnalyzer",
    "TelemetryPoint",
    "load_telemetry_csv",
]


def main():
    parser = argparse.ArgumentParser(description="Analisador de Telemetria do F1")
    parser.add_argument("user_csv", help="Caminho do arquivo CSV da sua volta")
    parser.add_argument("--ref-csv", default=None, help="Caminho do arquivo CSV da volta de referência (opcional)")
    parser.add_argument("--track-id", type=int, default=11, help="ID da pista (ex: 11 para Monza, 16 para Interlagos)")
    args = parser.parse_args()

    if not os.path.exists(args.user_csv):
        print(f"Erro: Arquivo '{args.user_csv}' não encontrado.")
        sys.exit(1)

    user_points = load_telemetry_csv(args.user_csv)
    ref_points = load_telemetry_csv(args.ref_csv) if args.ref_csv and os.path.exists(args.ref_csv) else None

    analyzer = LapAnalyzer(track_id=args.track_id)
    report = analyzer.compare_laps(user_points, ref_points)
    print(report)


if __name__ == "__main__":
    main()
'''

# =====================================================================
# 3. src/core/csv_recorder.py (Corrige auto-comparação de PB)
# =====================================================================
CSV_RECORDER_PY = '''
"""Gravador assíncrono de telemetria em fila (Queue) e gerador de relatórios pós-volta."""

import csv
import os
import queue
import threading
from datetime import datetime
from typing import Dict, List, Optional
from core.analyzer import LapAnalyzer, TelemetryPoint
from core.state import TelemetryState

CSV_COLUMNS = [
    "session_time",
    "lap_number",
    "lap_distance",
    "speed",
    "throttle",
    "brake",
    "steer",
    "gear",
    "engine_rpm",
    "drs",
    "lap_time_ms",
    "is_valid",
]


class AsyncLapRecorder:
    """Consome amostras de voltas completadas via Queue sem bloquear o listener UDP."""

    def __init__(self, output_dir: str = "data", state: Optional[TelemetryState] = None):
        self.output_dir = output_dir
        self.state = state
        self.lap_queue: queue.Queue = queue.Queue()
        self.running = True

        self.best_lap_points: Optional[List[TelemetryPoint]] = None
        self.best_lap_time_ms: Optional[int] = None
        self.best_lap_track_id: Optional[int] = None
        self.recorded_laps_count: int = 0

        os.makedirs(self.output_dir, exist_ok=True)
        self.worker_thread = threading.Thread(target=self._process_queue, daemon=True)
        self.worker_thread.start()

    def enqueue_lap(
        self,
        samples: List[Dict],
        lap_number: int,
        lap_time_ms: int,
        is_valid: bool,
        track_id: int,
        track_name: str,
    ):
        """Adiciona uma volta concluída na fila de escrita assíncrona."""
        if len(samples) < 30:
            return

        payload = {
            "samples": list(samples),
            "lap_number": lap_number,
            "lap_time_ms": lap_time_ms,
            "is_valid": is_valid,
            "track_id": track_id,
            "track_name": track_name,
        }
        self.lap_queue.put(payload)

    def _process_queue(self):
        """Loop executado na thread de I/O em disco."""
        while self.running or not self.lap_queue.empty():
            try:
                item = self.lap_queue.get(timeout=0.2)
            except queue.Empty:
                continue

            try:
                self._save_and_analyze(item)
            except Exception as e:
                print(f"⚠️ Erro ao salvar volta assíncrona: {e}")
            finally:
                self.lap_queue.task_done()

    def _save_and_analyze(self, item: Dict):
        samples: List[Dict] = item["samples"]
        lap_number: int = item["lap_number"]
        lap_time_ms: int = item["lap_time_ms"]
        is_valid: bool = item["is_valid"]
        track_id: int = item["track_id"]
        track_name: str = item["track_name"]

        if self.best_lap_track_id is not None and self.best_lap_track_id != track_id:
            self.best_lap_points = None
            self.best_lap_time_ms = None
        self.best_lap_track_id = track_id

        track_slug = "".join(c if c.isalnum() else "_" for c in track_name.lower()).strip("_") or "circuito"
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        valid_tag = "valida" if is_valid else "invalida"
        csv_filename = f"volta_{lap_number:02d}_{track_slug}_{valid_tag}_{timestamp}.csv"
        csv_path = os.path.join(self.output_dir, csv_filename)

        # 1. Escrita do CSV
        with open(csv_path, mode="w", newline="", encoding="utf-8") as csvfile:
            writer = csv.DictWriter(csvfile, fieldnames=CSV_COLUMNS)
            writer.writeheader()
            writer.writerows(samples)

        self.recorded_laps_count += 1

        # 2. Converte para TelemetryPoint para análise
        points = [
            TelemetryPoint(
                session_time=float(s["session_time"]),
                lap_number=int(s["lap_number"]),
                lap_distance=float(s["lap_distance"]),
                speed=int(s["speed"]),
                throttle=float(s["throttle"]),
                brake=float(s["brake"]),
                steer=float(s["steer"]),
                gear=int(s["gear"]),
                engine_rpm=int(s["engine_rpm"]),
                drs=int(s["drs"]),
                lap_time_ms=int(s["lap_time_ms"]),
                is_valid=int(s["is_valid"]),
            )
            for s in samples
        ]

        # Guarda a referência anterior ANTES de atualizar o novo PB (evita auto-comparação Delta +0.000s)
        prev_best_points = self.best_lap_points
        prev_best_time_ms = self.best_lap_time_ms

        analyzer = LapAnalyzer(track_id=track_id)
        quick_tip = analyzer.generate_quick_tip(points, prev_best_points)

        if is_valid and lap_time_ms > 0:
            if self.best_lap_time_ms is None or lap_time_ms < self.best_lap_time_ms:
                self.best_lap_time_ms = lap_time_ms
                self.best_lap_points = points
                if self.state:
                    self.state.best_session_lap_ms = lap_time_ms
                if prev_best_time_ms is not None:
                    improvement_s = (prev_best_time_ms - lap_time_ms) / 1000.0
                    quick_tip = f"⭐ NOVO RECORDE DA SESSÃO! {self._format_ms(lap_time_ms)} (-{improvement_s:.3f}s)"
                else:
                    quick_tip = f"⭐ NOVO RECORDE DA SESSÃO! {self._format_ms(lap_time_ms)}"

        if self.state:
            self.state.set_lap_feedback(f"V{lap_number}: {quick_tip}")

        report_txt = analyzer.compare_laps(
            user_points=points,
            ref_points=prev_best_points,
            user_lap_time_ms=lap_time_ms,
            ref_lap_time_ms=prev_best_time_ms,
        )
        report_filename = f"relatorio_volta_{lap_number:02d}_{track_slug}_{timestamp}.txt"
        report_path = os.path.join(self.output_dir, report_filename)
        with open(report_path, "w", encoding="utf-8") as rf:
            rf.write(report_txt)

    @staticmethod
    def _format_ms(ms: int) -> str:
        minutes = ms // 60000
        seconds = (ms % 60000) / 1000.0
        return f"{minutes:02d}:{seconds:06.3f}"

    def stop(self):
        """Encerra a thread de gravação aguardando a fila esvaziar."""
        self.running = False
        try:
            self.lap_queue.join()
        except Exception:
            pass
'''

# =====================================================================
# 4. src/core/udp_listener.py (Propagação correta de volta inválida)
# =====================================================================
UDP_LISTENER_PY = '''
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
'''

# =====================================================================
# 5. src/hud/win32_window.py (Ponteiros HWND 64-bit seguros)
# =====================================================================
WIN32_WINDOW_PY = '''
"""Integração nativa Win32 via ctypes para controle avançado de janela e foco no Windows."""

import ctypes
import sys
from typing import Optional

GWL_EXSTYLE = -20
WS_EX_TOPMOST = 0x00000008
WS_EX_TRANSPARENT = 0x00000020
WS_EX_TOOLWINDOW = 0x00000080
WS_EX_LAYERED = 0x00080000
WS_EX_NOACTIVATE = 0x08000000

HWND_TOPMOST = -1
HWND_NOTOPMOST = -2

SWP_NOSIZE = 0x0001
SWP_NOMOVE = 0x0002
SWP_NOACTIVATE = 0x0010
SWP_SHOWWINDOW = 0x0040

IS_WINDOWS = sys.platform == "win32"

if IS_WINDOWS:
    from ctypes import wintypes

    _user32 = ctypes.windll.user32
    _user32.GetParent.argtypes = [wintypes.HWND]
    _user32.GetParent.restype = wintypes.HWND
    _user32.GetWindowLongW.argtypes = [wintypes.HWND, ctypes.c_int]
    _user32.GetWindowLongW.restype = wintypes.LONG
    _user32.SetWindowLongW.argtypes = [wintypes.HWND, ctypes.c_int, wintypes.LONG]
    _user32.SetWindowLongW.restype = wintypes.LONG
    _user32.SetWindowPos.argtypes = [
        wintypes.HWND,
        wintypes.HWND,
        ctypes.c_int,
        ctypes.c_int,
        ctypes.c_int,
        ctypes.c_int,
        wintypes.UINT,
    ]
    _user32.SetWindowPos.restype = wintypes.BOOL


class Win32WindowManager:
    """Gerenciador de atributos avançados de janela para Desktop Window Manager (DWM)."""

    def __init__(self, root=None):
        self.root = root
        self.hwnd: Optional[int] = None
        self.click_through_active = False

        if IS_WINDOWS and self.root:
            self.refresh_hwnd()

    def refresh_hwnd(self) -> Optional[int]:
        """Obtém ou atualiza o handle (HWND) nativo da janela Tkinter."""
        if not IS_WINDOWS or not self.root:
            return None
        try:
            self.root.update_idletasks()
            raw_id = self.root.winfo_id()
            parent = _user32.GetParent(raw_id)
            self.hwnd = parent if parent else raw_id
            return self.hwnd
        except Exception:
            return None

    def apply_overlay_styles(self) -> bool:
        """Aplica estilos para impedir roubo de foco do jogo e remover do Alt+Tab."""
        if not IS_WINDOWS or not self.hwnd:
            return False
        try:
            style = _user32.GetWindowLongW(self.hwnd, GWL_EXSTYLE)
            new_style = style | WS_EX_NOACTIVATE | WS_EX_TOOLWINDOW | WS_EX_TOPMOST
            _user32.SetWindowLongW(self.hwnd, GWL_EXSTYLE, new_style)
            self.force_topmost()
            return True
        except Exception:
            return False

    def force_topmost(self) -> bool:
        """Força a posição no topo da pilha Z-order sem ativar foco."""
        if not IS_WINDOWS or not self.hwnd:
            return False
        try:
            _user32.SetWindowPos(
                self.hwnd,
                wintypes.HWND(HWND_TOPMOST),
                0,
                0,
                0,
                0,
                SWP_NOMOVE | SWP_NOSIZE | SWP_NOACTIVATE | SWP_SHOWWINDOW,
            )
            return True
        except Exception:
            return False

    def set_click_through(self, enabled: bool) -> bool:
        """Ativa ou desativa o modo Click-Through (clique passa direto para o jogo)."""
        if not IS_WINDOWS or not self.hwnd:
            self.click_through_active = enabled
            return False
        try:
            style = _user32.GetWindowLongW(self.hwnd, GWL_EXSTYLE)
            if enabled:
                new_style = style | WS_EX_TRANSPARENT | WS_EX_LAYERED
            else:
                new_style = style & ~WS_EX_TRANSPARENT

            _user32.SetWindowLongW(self.hwnd, GWL_EXSTYLE, new_style)
            self.force_topmost()
            self.click_through_active = enabled
            return True
        except Exception:
            return False
'''

# =====================================================================
# 6. tools/sync_circuits_fastf1.py (OPÇÃO A - Sincronizador Oficial FIA)
# =====================================================================
SYNC_FASTF1_PY = '''
"""
Opção A: Sincronizador Oficial de Circuitos via FIA Live Timing (FastF1).
Extrai a distância oficial de cada curva da FIA e a telemetria da Pole Position,
normalizando proporcionalmente para o comprimento exato da pista no EA SPORTS F1 25.

Como usar:
    pip install fastf1
    python tools/sync_circuits_fastf1.py                # Sincroniza todas as pistas
    python tools/sync_circuits_fastf1.py --track-id 16  # Sincroniza apenas Interlagos
"""

import argparse
import json
import os
import sys
from typing import Dict, List, Tuple

try:
    import fastf1
except ImportError:
    print("❌ Biblioteca 'fastf1' não encontrada. Instale com: pip install fastf1")
    sys.exit(1)

# Mapeamento oficial: Track ID do EA SPORTS F1 25 -> (Evento FastF1, Nome Exibição, País, Comprimento Oficial F1 25)
F125_TRACK_MAP: Dict[int, Tuple[str, str, str, int]] = {
    0: ("Australia", "Melbourne", "Austrália", 5278),
    2: ("China", "Shanghai", "China", 5451),
    3: ("Bahrain", "Bahrein (Sakhir)", "Bahrein", 5412),
    4: ("Spain", "Barcelona (Catalunya)", "Espanha", 4657),
    5: ("Monaco", "Monaco", "Mônaco", 3337),
    6: ("Canada", "Montreal (Gilles Villeneuve)", "Canadá", 4361),
    7: ("Great Britain", "Silverstone", "Grã-Bretanha", 5891),
    9: ("Hungary", "Hungaroring", "Hungria", 4381),
    10: ("Belgium", "Spa-Francorchamps", "Bélgica", 7004),
    11: ("Italy", "Monza", "Itália", 5793),
    12: ("Singapore", "Singapore (Marina Bay)", "Singapura", 4940),
    13: ("Japan", "Suzuka", "Japão", 5807),
    14: ("Abu Dhabi", "Yas Marina (Abu Dhabi)", "Emirados Árabes", 5281),
    15: ("United States", "Austin (COTA)", "EUA", 5513),
    16: ("Brazil", "Interlagos", "Brasil", 4309),
    17: ("Austria", "Red Bull Ring", "Áustria", 4318),
    19: ("Mexico", "Mexico City (Hermanos Rodríguez)", "México", 4304),
    20: ("Azerbaijan", "Baku City Circuit", "Azerbaijão", 6003),
    26: ("Netherlands", "Zandvoort", "Holanda", 4259),
    27: ("Emilia Romagna", "Imola (Enzo e Dino Ferrari)", "Itália", 4909),
    29: ("Saudi Arabia", "Jeddah Corniche", "Arábia Saudita", 6174),
    30: ("Miami", "Miami International Autodrome", "EUA", 5412),
    31: ("Las Vegas", "Las Vegas Strip Circuit", "EUA", 6201),
    32: ("Qatar", "Losail (Lusail)", "Catar", 5419),
}


def sync_track_from_fia(year: int, track_id: int, existing_corners: List[Dict]) -> Dict:
    gp_query, name, country, f125_length = F125_TRACK_MAP[track_id]
    print(f"📡 [ID {track_id:02d}] Baixando telemetria oficial da FIA para {name} ({year})...")

    session = fastf1.get_session(year, gp_query, "Q")
    session.load(telemetry=True, weather=False, messages=False)
    fastest_lap = session.laps.pick_fastest()
    car_data = fastest_lap.get_car_data().add_distance()
    circuit_info = session.get_circuit_info()

    fia_max_dist = float(car_data["Distance"].max())
    scale = f125_length / fia_max_dist if fia_max_dist > 1000 else 1.0

    # Mapa de nomes preservados caso já existam no JSON
    existing_names = {str(c.get("number")): c.get("name") for c in existing_corners}

    raw_corners = []
    for _, row in circuit_info.corners.iterrows():
        c_num = f"{int(row['Number'])}{row.get('Letter', '')}".strip()
        fia_apex = float(row["Distance"])
        scaled_apex = fia_apex * scale

        # Janela de análise na volta da Pole [-130m antes do ápice até +70m depois]
        win = car_data[
            (car_data["Distance"] >= max(0.0, fia_apex - 130.0))
            & (car_data["Distance"] <= min(fia_max_dist, fia_apex + 70.0))
        ]
        if win.empty:
            continue

        min_idx = win["Speed"].idxmin()
        min_gear = int(win.loc[min_idx, "nGear"])
        min_speed = float(win.loc[min_idx, "Speed"])

        # Se a velocidade mínima for > 265 km/h e sem freio, trata como curva de alta / flat (8ª marcha)
        pre_apex = win[win["Distance"] <= fia_apex]
        braking_rows = pre_apex[pre_apex["Brake"] > 0]

        if not braking_rows.empty:
            fia_brake_start = float(braking_rows["Distance"].iloc[0])
            start_dist = max(0.0, (fia_brake_start * scale) - 15.0)
            gear_ref = max(1, min(7, min_gear))
        else:
            start_dist = max(0.0, scaled_apex - 75.0)
            gear_ref = 8 if min_speed >= 260 else max(1, min(8, min_gear))

        end_dist = min(float(f125_length - 10), scaled_apex + 85.0)

        raw_corners.append({
            "number": c_num,
            "name": existing_names.get(c_num, f"Curva {c_num}"),
            "start_distance": round(start_dist, 1),
            "apex_distance": round(scaled_apex, 1),
            "end_distance": round(end_dist, 1),
            "gear_reference": gear_ref,
        })

    # Mescla pernas de chicanes muito próximas (< 75m entre ápices)
    merged_corners: List[Dict] = []
    i = 0
    while i < len(raw_corners):
        curr = raw_corners[i]
        if i + 1 < len(raw_corners):
            nxt = raw_corners[i + 1]
            if (nxt["apex_distance"] - curr["apex_distance"]) < 75.0:
                combined_num = f"{curr['number']}-{nxt['number']}"
                combined_name = existing_names.get(combined_num, f"Chicane {combined_num}")
                merged_corners.append({
                    "number": combined_num,
                    "name": combined_name,
                    "start_distance": curr["start_distance"],
                    "apex_distance": curr["apex_distance"],
                    "end_distance": nxt["end_distance"],
                    "gear_reference": min(curr["gear_reference"], nxt["gear_reference"]),
                })
                i += 2
                continue
        merged_corners.append(curr)
        i += 1

    return {
        "track_id": track_id,
        "name": name,
        "country": country,
        "length": f125_length,
        "corners": merged_corners,
    }


def main():
    parser = argparse.ArgumentParser(description="Sincroniza config/circuits_f125.json com dados oficiais da FIA (FastF1)")
    parser.add_argument("--year", type=int, default=2024, help="Temporada de referência da FIA (padrão: 2024)")
    parser.add_argument("--track-id", type=int, default=None, help="Sincronizar apenas um Track ID específico (ex: 16)")
    parser.add_argument("--output", default="config/circuits_f125.json", help="Caminho do arquivo JSON")
    args = parser.parse_args()

    cache_dir = os.path.join(os.path.dirname(__file__), "..", ".fastf1_cache")
    os.makedirs(cache_dir, exist_ok=True)
    fastf1.Cache.enable_cache(cache_dir)

    existing_data = {"version": "2.0.0", "game": "EA SPORTS F1 25", "circuits": {}}
    if os.path.exists(args.output):
        with open(args.output, "r", encoding="utf-8") as f:
            existing_data = json.load(f)

    target_ids = [args.track_id] if args.track_id is not None else sorted(F125_TRACK_MAP.keys())

    for tid in target_ids:
        if tid not in F125_TRACK_MAP:
            print(f"⚠️ Track ID {tid} não mapeado.")
            continue
        try:
            old_corners = existing_data.get("circuits", {}).get(str(tid), {}).get("corners", [])
            updated_circuit = sync_track_from_fia(args.year, tid, old_corners)
            existing_data.setdefault("circuits", {})[str(tid)] = updated_circuit
            print(f"   ✅ {updated_circuit['name']} atualizado ({len(updated_circuit['corners'])} zonas de curva).")
        except Exception as e:
            print(f"   ⚠️ Erro ao sincronizar ID {tid}: {e}")

    with open(args.output, "w", encoding="utf-8") as f:
        json.dump(existing_data, f, ensure_ascii=False, indent=2)

    print(f"\\n🏁 Sincronização concluída em: {args.output}")


if __name__ == "__main__":
    main()
'''


def apply_all_updates():
    print("=" * 65)
    print("🚀 INICIANDO ATUALIZAÇÃO E CRIAÇÃO DE BRANCH - COPILOTO F1")
    print("=" * 65)

    # 1. Cria a nova branch git
    try:
        subprocess.run(["git", "checkout", "-b", "fix/refatoracao-e-calibracao-fia"], cwd=ROOT_DIR, check=False)
    except Exception as e:
        print(f"Aviso Git: {e}")

    # 2. Grava os módulos principais refatorados
    write_file("src/core/analyzer.py", CORE_ANALYZER_PY)
    write_file("src/analyzer.py", SRC_ANALYZER_PY)
    write_file("src/core/csv_recorder.py", CSV_RECORDER_PY)
    write_file("src/core/udp_listener.py", UDP_LISTENER_PY)
    write_file("src/hud/win32_window.py", WIN32_WINDOW_PY)
    write_file("tools/sync_circuits_fastf1.py", SYNC_FASTF1_PY)

    # 3. Atualiza src/recorder.py para retornar a contagem real de voltas
    recorder_path = os.path.join(ROOT_DIR, "src", "recorder.py")
    if os.path.exists(recorder_path):
        with open(recorder_path, "r", encoding="utf-8") as f:
            rec_code = f.read()
        rec_code = rec_code.replace(
            "return 1 if self.recorder.best_lap_time_ms is not None else 0",
            "return self.recorder.recorded_laps_count",
        )
        write_file("src/recorder.py", rec_code)

    # 4. Atualiza src/hud/overlay.py para callbacks thread-safe no Systray
    overlay_path = os.path.join(ROOT_DIR, "src", "hud", "overlay.py")
    if os.path.exists(overlay_path):
        with open(overlay_path, "r", encoding="utf-8") as f:
            ov_code = f.read()
        if "def _run_on_ui_thread" not in ov_code:
            old_systray_call = """        self.systray = SystrayController(
            icon_path=icon_path,
            on_change_layout=self.set_layout,
            on_change_theme=self.set_theme,
            on_change_track=self.set_track,
            on_toggle_click_through=self.toggle_click_through,
            on_quit=self.on_close,
            initial_layout=self.active_layout,
            initial_theme=self.active_theme,
            initial_click_through=self.click_through_locked,
        )"""
            new_systray_call = """        self.systray = SystrayController(
            icon_path=icon_path,
            on_change_layout=lambda l: self._run_on_ui_thread(self.set_layout, l),
            on_change_theme=lambda t: self._run_on_ui_thread(self.set_theme, t),
            on_change_track=lambda tid, m: self._run_on_ui_thread(self.set_track, tid, m),
            on_toggle_click_through=lambda locked: self._run_on_ui_thread(self.toggle_click_through, locked),
            on_quit=lambda: self._run_on_ui_thread(self.on_close),
            initial_layout=self.active_layout,
            initial_theme=self.active_theme,
            initial_click_through=self.click_through_locked,
        )"""
            helper_method = """    def _run_on_ui_thread(self, func, *args, **kwargs):
        \"\"\"Executa callbacks vindos do Systray na thread principal do Tkinter.\"\"\"
        import threading
        if threading.current_thread() is threading.main_thread():
            func(*args, **kwargs)
        elif self.running and self.root:
            try:
                self.root.after(0, lambda: func(*args, **kwargs))
            except Exception:
                pass

    def setup_systray(self):"""
            ov_code = ov_code.replace("    def setup_systray(self):", helper_method)
            ov_code = ov_code.replace(old_systray_call, new_systray_call)
            write_file("src/hud/overlay.py", ov_code)

    # 5. Corrige tests/detect_ports.py para não bloquear test runners ao ser importado
    detect_ports_code = '''"""Detector multi-portas e multi-interfaces para telemetria UDP."""

import select
import socket
import time


def detect_active_ports(timeout_s: float = 8.0) -> None:
    ports = [20777, 20778, 20779, 10001, 10002]
    sockets = []

    for p in ports:
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            s.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
            s.bind(("0.0.0.0", p))
            s.setblocking(False)
            sockets.append((s, p))
        except Exception as e:
            print(f"Não foi possível abrir porta {p}: {e}")

    print(f"📡 Monitorando portas {[p for _, p in sockets]} por {timeout_s:.0f} segundos...")
    start = time.time()
    found = False

    while time.time() - start < timeout_s:
        rlist = [s for s, _ in sockets]
        if not rlist:
            break
        readable, _, _ = select.select(rlist, [], [], 0.5)
        for s in readable:
            data, addr = s.recvfrom(2048)
            port = next(p for sock, p in sockets if sock == s)
            print(f"✅ PACOTE DETECTADO NA PORTA {port}! De: {addr} | Bytes: {len(data)}")
            found = True
            break
        if found:
            break

    for s, _ in sockets:
        s.close()

    if not found:
        print("❌ Nenhum pacote recebido em nenhuma porta monitorada.")


if __name__ == "__main__":
    detect_active_ports()
'''
    write_file("tests/detect_ports.py", detect_ports_code)

    # 6. Calibra Interlagos (Track ID 16) no config/circuits_f125.json com base nas voltas reais
    circuits_path = os.path.join(ROOT_DIR, "config", "circuits_f125.json")
    if os.path.exists(circuits_path):
        with open(circuits_path, "r", encoding="utf-8") as f:
            circuits_json = json.load(f)

        circuits_json["circuits"]["16"] = {
            "track_id": 16,
            "name": "Interlagos",
            "country": "Brasil",
            "length": 4309,
            "corners": [
                {"number": "1-2", "name": "S do Senna", "start_distance": 120.0, "apex_distance": 380.0, "end_distance": 620.0, "gear_reference": 3},
                {"number": "3", "name": "Curva do Sol", "start_distance": 680.0, "apex_distance": 920.0, "end_distance": 1100.0, "gear_reference": 8},
                {"number": "4", "name": "Descida do Lago", "start_distance": 1420.0, "apex_distance": 1650.0, "end_distance": 1850.0, "gear_reference": 4},
                {"number": "6-7", "name": "Ferradura / Laranjinha", "start_distance": 1880.0, "apex_distance": 2040.0, "end_distance": 2180.0, "gear_reference": 4},
                {"number": "8", "name": "Pinheirinho", "start_distance": 2200.0, "apex_distance": 2380.0, "end_distance": 2550.0, "gear_reference": 2},
                {"number": "9", "name": "Bico de Pato", "start_distance": 2600.0, "apex_distance": 2760.0, "end_distance": 2920.0, "gear_reference": 2},
                {"number": "10", "name": "Mergulho", "start_distance": 2950.0, "apex_distance": 3050.0, "end_distance": 3140.0, "gear_reference": 5},
                {"number": "12", "name": "Junção", "start_distance": 3150.0, "apex_distance": 3320.0, "end_distance": 3520.0, "gear_reference": 3}
            ]
        }
        with open(circuits_path, "w", encoding="utf-8") as f:
            json.dump(circuits_json, f, ensure_ascii=False, indent=2)
        print("✅ Calibrado: config/circuits_f125.json (Interlagos alinhado com telemetria real)")

    # 7. Atualiza o teste da Junção em tests/test_hud.py para refletir os metros reais da Junção (3150m-3520m)
    test_hud_path = os.path.join(ROOT_DIR, "tests", "test_hud.py")
    if os.path.exists(test_hud_path):
        with open(test_hud_path, "r", encoding="utf-8") as f:
            th_code = f.read()
        th_code = th_code.replace(
            """        # C12: Junção e Reta dos Boxes
        self.hud.state.lap_distance = 3650.0
        self.hud._update_corner_logic()
        self.assertEqual(self.hud.current_state, "freia")
        self.assertEqual(self.hud.next_corner.number, "12")

        self.hud.state.lap_distance = 3740.0
        self.hud._update_corner_logic()
        self.assertEqual(self.hud.current_state, "apice")""",
            """        # C12: Junção e Reta dos Boxes (calibrado com telemetria real: 3150m a 3520m)
        self.hud.state.lap_distance = 3220.0
        self.hud._update_corner_logic()
        self.assertEqual(self.hud.current_state, "freia")
        self.assertEqual(self.hud.next_corner.number, "12")

        self.hud.state.lap_distance = 3320.0
        self.hud._update_corner_logic()
        self.assertEqual(self.hud.current_state, "apice")""",
        )
        write_file("tests/test_hud.py", th_code)

    # 8. Atualiza .gitignore
    gitignore_path = os.path.join(ROOT_DIR, ".gitignore")
    existing_ignore = ""
    if os.path.exists(gitignore_path):
        with open(gitignore_path, "r", encoding="utf-8") as f:
            existing_ignore = f.read()
    extra_ignores = ["\n# Cache e telemetria local", ".pytest_cache/", ".fastf1_cache/", "data/*.csv", "data/*.txt", "data/*.log"]
    for item in extra_ignores:
        if item.strip() not in existing_ignore:
            existing_ignore += f"\n{item}"
    write_file(".gitignore", existing_ignore)

    print("\n🧪 Executando suíte de testes automatizados (pytest)...")
    subprocess.run([sys.executable, "-m", "pytest", "-v"], cwd=ROOT_DIR, check=False)


if __name__ == "__main__":
    apply_all_updates()