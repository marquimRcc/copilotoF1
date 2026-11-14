"""Gravador de telemetria UDP do EA SPORTS F1 para arquivos CSV (Serviço consolidado)."""

import argparse
import os
import sys
import time
from typing import Dict, List, Optional

from core.csv_recorder import CSV_COLUMNS, AsyncLapRecorder
from core.state import TelemetryState
from core.udp_listener import F1UdpListener
from packets.session import SessionData


class F1TelemetryRecorder:
    """Gravador dedicado de telemetria F1 usando o Core desacoplado."""

    def __init__(self, host: str = "127.0.0.1", port: int = 20777, output_dir: str = "data"):
        self.host = host
        self.port = port
        self.output_dir = output_dir

        self.state = TelemetryState()
        self.recorder = AsyncLapRecorder(output_dir=output_dir, state=self.state)
        self.listener = F1UdpListener(
            host=host,
            port=port,
            state=self.state,
            recorder=self.recorder,
            record_csv=True,
        )
        self.running = False

    @property
    def recorded_laps_count(self) -> int:
        return 1 if self.recorder.best_lap_time_ms is not None else 0

    def start(self):
        """Inicia o listener UDP e mantém o loop em execução."""
        self.running = True
        self.listener.start()
        print("=" * 60)
        print(f"🏁 COPILOTO F1 - GRAVADOR DE TELEMETRIA INICIADO")
        print(f"📡 Escutando em {self.host}:{self.port} (UDP)")
        print(f"📁 Salvando voltas em: {os.path.abspath(self.output_dir)}")
        print("Aguardando pacotes do F1... (Pressione Ctrl+C para encerrar)")
        print("=" * 60)

        try:
            while self.running:
                time.sleep(0.1)
        except KeyboardInterrupt:
            print("\n🛑 Gravador encerrado pelo usuário.")
        finally:
            self.close()

    def process_packet(self, data: bytes):
        """Encaminha pacote manualmente para processamento (compatibilidade)."""
        self.listener.process_packet(data)

    def close(self):
        """Encerra com segurança o listener e o gravador assíncrono."""
        self.running = False
        if self.listener:
            self.listener.stop()
        if self.recorder:
            self.recorder.stop()


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
