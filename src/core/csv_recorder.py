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
