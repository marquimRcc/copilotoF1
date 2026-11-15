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
