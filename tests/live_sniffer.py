"""Sniffer em tempo real para capturar e inspecionar a telemetria do F1 25."""

import socket
import sys
import time
import os

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "src")))

from packets.header import parse_header
from packets.session import parse_session_data
from packets.lap_data import parse_lap_data
from packets.car_telemetry import parse_car_telemetry


def sniff(duration: float = 6.0, host: str = "0.0.0.0", port: int = 20777):
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
    sock.settimeout(2.0)
    
    try:
        sock.bind((host, port))
    except Exception as e:
        print(f"Erro ao dar bind em {host}:{port}: {e}")
        return

    print("=" * 65)
    print(f"📡 SNIFFER INICIADO EM {host}:{port} por {duration} segundos")
    print("Aguardando pacotes do F1... (Certifique-se de que o carro está na pista)")
    print("=" * 65)

    start_time = time.time()
    packet_count = 0
    sample_prints = 0

    while time.time() - start_time < duration:
        try:
            data, addr = sock.recvfrom(2048)
            packet_count += 1
            header = parse_header(data)
            if not header:
                continue

            # Inspeciona pacotes de Volta (ID 2), Carro (ID 6) e Sessão (ID 1)
            if header.packet_id == 2:
                lap = parse_lap_data(data, header)
                if lap and sample_prints < 25:
                    sample_prints += 1
                    print(
                        f"⏱️ [LAP_DATA] Car #{header.player_car_index} | Lap: {lap.current_lap_num} | "
                        f"Dist: {lap.lap_distance:7.1f}m | Time: {lap.current_lap_time_ms:6d}ms | "
                        f"Status: {lap.driver_status} | Valid: {not lap.current_lap_invalid}"
                    )
            elif header.packet_id == 1 and sample_prints < 5:
                session = parse_session_data(data, header)
                if session:
                    print(
                        f"🎮 [SESSION] Tipo: {session.session_type} ({session.session_type_name}) | "
                        f"Pista ID: {session.track_id} ({session.track_name}) | Ext: {session.track_length}m"
                    )
            elif header.packet_id == 6 and sample_prints < 15:
                tel = parse_car_telemetry(data, header)
                if tel:
                    print(
                        f"🏎️ [TELEMETRY] Vel: {tel.speed:3d} km/h | Marcha: {tel.gear:2d} | "
                        f"Acel: {tel.throttle:.2f} | Freio: {tel.brake:.2f}"
                    )

        except socket.timeout:
            print("⏳ Aguardando pacotes...")
            continue
        except Exception as e:
            print(f"Erro no sniffer: {e}")
            break

    sock.close()
    print("=" * 65)
    print(f"🏁 Finalizado. Total de pacotes capturados: {packet_count}")
    print("=" * 65)


if __name__ == "__main__":
    sniff(duration=6.0)
