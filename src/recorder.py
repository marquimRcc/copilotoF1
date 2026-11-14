"""Gravador de telemetria UDP do EA SPORTS F1 para arquivos CSV."""

import argparse
import csv
import os
import socket
import sys
import time
from datetime import datetime
from typing import Dict, List, Optional

from packets.header import (
    PACKET_ID_CAR_TELEMETRY,
    PACKET_ID_LAP_DATA,
    PACKET_ID_SESSION,
    parse_header,
)
from packets.car_telemetry import CarTelemetryData, parse_car_telemetry
from packets.lap_data import LapData, parse_lap_data
from packets.session import SessionData, parse_session_data

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


class F1TelemetryRecorder:
    def __init__(self, host: str = "127.0.0.1", port: int = 20777, output_dir: str = "data"):
        self.host = host
        self.port = port
        self.output_dir = output_dir

        self.sock: Optional[socket.socket] = None
        self.running = False

        # Estado da sessão
        self.current_session: Optional[SessionData] = None
        self.last_lap_data: Optional[LapData] = None
        self.active_lap_num: int = 0
        self.lap_samples: List[Dict] = []
        self.recorded_laps_count: int = 0

    def start(self):
        """Inicia o socket e o loop de escuta UDP."""
        os.makedirs(self.output_dir, exist_ok=True)
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        # Permite reusar a porta se necessário
        self.sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)

        try:
            self.sock.bind((self.host, self.port))
            self.running = True
            print("=" * 60)
            print(f"🏁 COPILOTO F1 - GRAVADOR DE TELEMETRIA INICIADO")
            print(f"📡 Escutando em {self.host}:{self.port} (UDP)")
            print(f"📁 Salvando voltas em: {os.path.abspath(self.output_dir)}")
            print("Aguardando pacotes do F1... (Pressione Ctrl+C para encerrar)")
            print("=" * 60)

            while self.running:
                data, _ = self.sock.recvfrom(2048)
                self.process_packet(data)

        except KeyboardInterrupt:
            print("\n🛑 Gravador encerrado pelo usuário.")
        finally:
            self.close()

    def process_packet(self, data: bytes):
        """Processa um pacote UDP recebido."""
        header = parse_header(data)
        if not header:
            return

        # 1. Pacote de Sessão (ID 1)
        if header.packet_id == PACKET_ID_SESSION:
            session = parse_session_data(data, header)
            if session:
                if not self.current_session or self.current_session.track_id != session.track_id:
                    self.current_session = session
                    print(f"📍 Circuito detectado: {session.track_name} ({session.track_length}m)")
                    print(f"🎮 Sessão: {session.session_type_name}")

        # 2. Pacote de Dados de Volta (ID 2)
        elif header.packet_id == PACKET_ID_LAP_DATA:
            lap = parse_lap_data(data, header)
            if lap:
                # Detecta mudança de volta
                if self.last_lap_data and lap.current_lap_num > self.active_lap_num:
                    if len(self.lap_samples) >= 50:
                        self._save_lap_to_csv(
                            lap_number=self.active_lap_num,
                            lap_time_ms=lap.last_lap_time_ms,
                            is_valid=not self.last_lap_data.current_lap_invalid,
                        )
                    self.lap_samples.clear()
                    self.active_lap_num = lap.current_lap_num

                elif self.active_lap_num == 0 and lap.current_lap_num > 0:
                    self.active_lap_num = lap.current_lap_num

                self.last_lap_data = lap

        # 3. Pacote de Telemetria do Carro (ID 6)
        elif header.packet_id == PACKET_ID_CAR_TELEMETRY:
            telemetry = parse_car_telemetry(data, header)
            if telemetry and self.last_lap_data:
                sample = {
                    "session_time": round(header.session_time, 3),
                    "lap_number": self.last_lap_data.current_lap_num,
                    "lap_distance": self.last_lap_data.lap_distance,
                    "speed": telemetry.speed,
                    "throttle": telemetry.throttle,
                    "brake": telemetry.brake,
                    "steer": telemetry.steer,
                    "gear": telemetry.gear,
                    "engine_rpm": telemetry.engine_rpm,
                    "drs": telemetry.drs,
                    "lap_time_ms": self.last_lap_data.current_lap_time_ms,
                    "is_valid": 0 if self.last_lap_data.current_lap_invalid else 1,
                }
                self.lap_samples.append(sample)

    def _save_lap_to_csv(self, lap_number: int, lap_time_ms: int, is_valid: bool) -> str:
        """Salva a volta recém-concluída em um arquivo CSV estruturado."""
        track_slug = "circuito"
        if self.current_session and self.current_session.track_name:
            track_slug = "".join(c if c.isalnum() else "_" for c in self.current_session.track_name.lower()).strip("_")

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        valid_tag = "valida" if is_valid else "invalida"
        filename = f"volta_{lap_number:02d}_{track_slug}_{valid_tag}_{timestamp}.csv"
        filepath = os.path.join(self.output_dir, filename)

        with open(filepath, mode="w", newline="", encoding="utf-8") as csvfile:
            writer = csv.DictWriter(csvfile, fieldnames=CSV_COLUMNS)
            writer.writeheader()
            writer.writerows(self.lap_samples)

        self.recorded_laps_count += 1
        time_str = self._format_ms(lap_time_ms) if lap_time_ms > 0 else "N/A"
        print(f"✅ [VOLTA GRAVADA] Volta #{lap_number} | Tempo: {time_str} | Status: {'Válida' if is_valid else '❌ Inválida'} | Amostras: {len(self.lap_samples)}")
        print(f"   Salvo em: {filepath}")
        return filepath

    @staticmethod
    def _format_ms(ms: int) -> str:
        """Formata milissegundos para formato MM:SS.mmm."""
        minutes = ms // 60000
        seconds = (ms % 60000) / 1000.0
        return f"{minutes:02d}:{seconds:06.3f}"

    def close(self):
        """Fecha o socket."""
        self.running = False
        if self.sock:
            self.sock.close()
            self.sock = None


def main():
    parser = argparse.ArgumentParser(description="Gravador de Telemetria UDP para EA SPORTS F1")
    parser.add_argument("--host", default="127.0.0.1", help="Endereço IP para escuta UDP (padrão: 127.0.0.1)")
    parser.add_argument("--port", type=int, default=20777, help="Porta UDP (padrão: 20777)")
    parser.add_argument("--output-dir", default="data", help="Diretório para salvar os CSVs (padrão: data)")
    args = parser.parse_args()

    recorder = F1TelemetryRecorder(host=args.host, port=args.port, output_dir=args.output_dir)
    recorder.start()


if __name__ == "__main__":
    main()
