"""Ponto único de entrada da aplicação Copiloto F1 (EA SPORTS F1 25)."""

import argparse
import sys
from hud.overlay import F1HudOverlay, run_demo_mode
from recorder import F1TelemetryRecorder


def main():
    parser = argparse.ArgumentParser(
        description="🏎️ Copiloto F1 - Assistente de Telemetria e HUD para EA SPORTS F1 25",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "--mode",
        choices=["hud", "recorder", "demo"],
        default="hud",
        help="Modo de execução: 'hud' (padrão com interface), 'recorder' (gravação dedicada CLI) ou 'demo' (demonstração visual)",
    )
    parser.add_argument("--layout", type=int, default=None, choices=[1, 2, 3], help="Layout inicial (1, 2 ou 3)")
    parser.add_argument("--theme", default=None, help="Tema de cores inicial (ex: padrao, ferrari, mercedes, redbull, mclaren)")
    parser.add_argument("--port", type=int, default=20777, help="Porta UDP (padrão: 20777)")
    parser.add_argument("--host", default="127.0.0.1", help="Endereço IP para escuta UDP (padrão: 127.0.0.1)")
    parser.add_argument("--output-dir", default="data", help="Diretório para salvar arquivos CSV de volta (padrão: data)")
    parser.add_argument("--no-record", action="store_true", help="Desativa o salvamento automático de voltas em CSV")

    args = parser.parse_args()

    if args.mode == "demo":
        run_demo_mode(initial_layout=args.layout or 1, initial_theme=args.theme or "padrao")
    elif args.mode == "recorder":
        recorder = F1TelemetryRecorder(host=args.host, port=args.port, output_dir=args.output_dir)
        recorder.start()
    else:
        hud = F1HudOverlay(
            host=args.host,
            port=args.port,
            initial_layout=args.layout,
            initial_theme=args.theme,
            record_csv=not args.no_record,
        )
        hud.run()


if __name__ == "__main__":
    main()
