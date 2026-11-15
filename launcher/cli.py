"""Command line entry point for the F1 25 discovery POC."""
from __future__ import annotations

import argparse
import json
import sys

from launcher.steam import discover_installation, is_game_running, launch_game, wait_for_game


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="copiloto-f1-launcher",
        description="Descobre a instalação Steam do F1 25 e pode solicitar sua inicialização.",
    )
    parser.add_argument("--diagnose", action="store_true", help="Mostra Steam, instalação e estado do processo.")
    parser.add_argument("--launch", action="store_true", help="Solicita à Steam a inicialização do F1 25.")
    parser.add_argument("--wait", type=int, default=0, metavar="SEGUNDOS", help="Após --launch, aguarda o processo F1_25.exe.")
    parser.add_argument("--json", action="store_true", help="Imprime o diagnóstico em JSON.")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    installation = discover_installation()
    running = is_game_running()
    if args.json or args.diagnose:
        payload = installation.to_dict()
        payload["game_running"] = running
        if args.json:
            print(json.dumps(payload, ensure_ascii=False, indent=2))
        else:
            print("=== Diagnóstico F1 25 ===")
            for key, value in payload.items():
                print(f"{key}: {value or 'não encontrado'}")
    if args.launch:
        ok, message = launch_game(installation)
        print(message)
        if not ok:
            return 2
        if args.wait > 0:
            print(f"Aguardando F1_25.exe por até {args.wait}s...")
            if wait_for_game(args.wait):
                print("Processo F1_25.exe detectado.")
            else:
                print("Tempo esgotado: processo do jogo ainda não detectado.")
                return 3
    if not (args.diagnose or args.launch or args.json):
        build_parser().print_help()
    return 0


if __name__ == "__main__":
    sys.exit(main())
