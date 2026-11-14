"""Logger de telemetria ao vivo para capturar o comportamento exato da largada."""

import os
import socket
import sys
import time

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "src")))

from packets.car_telemetry import parse_car_telemetry
from packets.header import parse_header
from packets.lap_data import parse_lap_data
from packets.session import parse_session_data

LOG_FILE = "data/live_debug.log"


def start_live_logger(duration_seconds: int = 30, port: int = 20777):
    os.makedirs("data", exist_ok=True)
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
    sock.settimeout(1.0)
    sock.bind(("0.0.0.0", port))

    print("=" * 65)
    print(f"📡 GRAVADOR DE DIAGNÓSTICO EM TEMPO REAL INICIADO (Porta {port})")
    print(f"Gravando em: {os.path.abspath(LOG_FILE)}")
    print("=" * 65)

    start_time = time.time()
    packet_count = 0

    with open(LOG_FILE, "w", encoding="utf-8") as f:
        f.write("=== LOG DE TELEMETRIA AO VIVO ===\n")

    while time.time() - start_time < duration_seconds:
        try:
            data, addr = sock.recvfrom(2048)
            packet_count += 1
            header = parse_header(data)
            if not header:
                continue

            log_entry = ""
            if header.packet_id == 1:
                sess = parse_session_data(data, header)
                if sess:
                    log_entry = (
                        f"[{header.session_time:7.2f}s] [SESSION] tipo={sess.session_type} "
                        f"({sess.session_type_name}) track={sess.track_id} ({sess.track_name})\n"
                    )
            elif header.packet_id == 2:
                lap = parse_lap_data(data, header)
                if lap:
                    log_entry = (
                        f"[{header.session_time:7.2f}s] [LAP_DATA] lap={lap.current_lap_num} "
                        f"dist={lap.lap_distance:7.1f}m tempo={lap.current_lap_time_ms:6d}ms "
                        f"status={lap.driver_status} valida={not lap.current_lap_invalid}\n"
                    )
            elif header.packet_id == 6:
                tel = parse_car_telemetry(data, header)
                if tel:
                    log_entry = (
                        f"[{header.session_time:7.2f}s] [TELEMETRY] vel={tel.speed:3d}km/h "
                        f"marcha={tel.gear:2d} acel={tel.throttle:.2f} freio={tel.brake:.2f}\n"
                    )

            if log_entry:
                with open(LOG_FILE, "a", encoding="utf-8") as f:
                    f.write(log_entry)
                # Exibe uma amostra a cada 20 pacotes para não inundar o terminal
                if packet_count % 20 == 0:
                    print(log_entry.strip())

        except socket.timeout:
            continue
        except Exception as e:
            print(f"Erro: {e}")
            break

    sock.close()
    print("=" * 65)
    print(f"🏁 Finalizado. Total de pacotes capturados: {packet_count}")
    print(f"Arquivo salvo em: {LOG_FILE}")
    print("=" * 65)


if __name__ == "__main__":
    dur = int(sys.argv[1]) if len(sys.argv) > 1 else 30
    start_live_logger(duration_seconds=dur)
