"""Dumper completo de pacotes UDP para diagnóstico da telemetria do F1 25."""

import os
import socket
import struct
import sys
import time

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "src")))

from packets.car_telemetry import parse_car_telemetry
from packets.header import parse_header
from packets.lap_data import parse_lap_data
from packets.session import parse_session_data

LOG_FILE = "data/live_debug.log"


def start_dumper(duration_seconds: int = 45, port: int = 20777):
    os.makedirs("data", exist_ok=True)
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
    sock.settimeout(1.0)
    sock.bind(("0.0.0.0", port))

    print(f"📡 DUMPER DE TELEMETRIA ATIVO na porta {port} ({duration_seconds}s)...")

    start_time = time.time()
    packet_count = 0

    with open(LOG_FILE, "w", encoding="utf-8") as f:
        f.write("=== LOG COMPLETO DE TELEMETRIA F1 25 ===\n")

    while time.time() - start_time < duration_seconds:
        try:
            data, addr = sock.recvfrom(2048)
            packet_count += 1
            h = parse_header(data)
            if not h:
                line = f"RAW PACKET: bytes={len(data)} (falha no parse_header)\n"
                with open(LOG_FILE, "a", encoding="utf-8") as f:
                    f.write(line)
                continue

            event_code = ""
            if h.packet_id == 3 and len(data) >= 33:
                event_code = data[29:33].decode("ascii", errors="ignore")

            detail = ""
            if h.packet_id == 1:
                sess = parse_session_data(data, h)
                if sess:
                    detail = f"| Sessão: tipo={sess.session_type} ({sess.session_type_name}) track={sess.track_id} ({sess.track_name})"
            elif h.packet_id == 2:
                lap = parse_lap_data(data, h)
                if lap:
                    detail = f"| Volta: num={lap.current_lap_num} dist={lap.lap_distance:.1f}m tempo={lap.current_lap_time_ms}ms status={lap.driver_status}"
            elif h.packet_id == 3:
                detail = f"| EVENTO: {event_code}"
            elif h.packet_id == 6:
                tel = parse_car_telemetry(data, h)
                if tel:
                    detail = f"| Car: vel={tel.speed}km/h marcha={tel.gear} acel={tel.throttle:.2f} freio={tel.brake:.2f}"

            line = f"[{h.session_time:6.2f}s] PktID={h.packet_id:2d} (len={len(data):4d}) fmt={h.packet_format} ano={h.game_year} carIdx={h.player_car_index} {detail}\n"
            with open(LOG_FILE, "a", encoding="utf-8") as f:
                f.write(line)

            # Imprime no terminal pacotes relevantes
            if h.packet_id in (1, 2, 3, 6):
                print(line.strip())

        except socket.timeout:
            continue
        except Exception as e:
            print(f"Erro: {e}")
            break

    sock.close()
    print(f"🏁 Dumper finalizado. Total de pacotes: {packet_count}")


if __name__ == "__main__":
    dur = int(sys.argv[1]) if len(sys.argv) > 1 else 45
    start_dumper(duration_seconds=dur)
