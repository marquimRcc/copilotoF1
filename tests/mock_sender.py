"""Emissor simulado de pacotes UDP para testes locais sem o jogo F1 aberto."""

import socket
import struct
import sys
import time

# Formatos
HEADER_FORMAT_29 = "<HBBBBBQfIIBB"
CAR_TELEMETRY_ENTRY_FORMAT = "<HfffBbHBBH4H4B4BH4f4B"
LAP_DATA_ENTRY_FORMAT = "<IIHBHBHBHBfff15BHHBfB"
SESSION_DATA_FORMAT = "<BbbBHBb"

UDP_IP = "127.0.0.1"
UDP_PORT = 20777


def send_simulated_lap(ip: str = "127.0.0.1", port: int = 20777, delay: float = 0.005):
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    print(f"🚀 Iniciando emissor simulado de telemetria para {ip}:{port}...")

    # 1. Envia Pacote de Sessão (Monza, ID 11)
    session_header = struct.pack(HEADER_FORMAT_29, 2024, 24, 1, 0, 1, 1, 999999, 10.0, 1, 1, 0, 255)
    session_body = struct.pack(SESSION_DATA_FORMAT, 0, 32, 24, 20, 5793, 13, 11)
    sock.sendto(session_header + session_body, (ip, port))
    time.sleep(0.02)

    total_distance = 5793.0
    current_dist = 0.0
    step_m = 30.0
    lap_time_ms = 0

    print("Simulando volta em Monza...")
    lap_num = 1
    session_time = 10.0

    while current_dist < total_distance:
        session_time += 0.05
        lap_time_ms += 50
        current_dist += step_m

        # Lógica simplificada de velocidade e pedais em Monza
        speed = 330
        throttle = 1.0
        brake = 0.0
        gear = 8

        # Curva 1-2 (Variante del Rettifilo: 450m a 800m)
        if 480 <= current_dist <= 620:
            speed = max(75, int(330 - (current_dist - 480) * 1.8))
            throttle = 0.0
            brake = 0.95
            gear = 2
        elif 620 < current_dist <= 800:
            speed = int(75 + (current_dist - 620) * 0.9)
            throttle = 0.7
            brake = 0.0
            gear = 3

        # Curva 4-5 (Variante della Roggia: 1550m a 1850m)
        elif 1600 <= current_dist <= 1720:
            speed = max(110, int(320 - (current_dist - 1600) * 1.7))
            throttle = 0.0
            brake = 0.90
            gear = 3
        elif 1720 < current_dist <= 1850:
            speed = int(110 + (current_dist - 1720) * 0.9)
            throttle = 0.8
            brake = 0.0
            gear = 4

        # Pacote LapData (ID 2)
        lap_header = struct.pack(HEADER_FORMAT_29, 2024, 24, 1, 0, 1, 2, 999999, session_time, 10, 10, 0, 255)
        lap_entry = struct.pack(
            LAP_DATA_ENTRY_FORMAT,
            81400, lap_time_ms,
            30000, 1,
            32000, 1,
            0, 0,
            0, 0,
            float(current_dist), float(current_dist), 0.0,
            1, lap_num,
            0, 0, 1, 0,
            0, 0, 0, 0, 0,
            1, 4, 2, 0,
            0, 0, 0,
            340.0, 1
        )
        sock.sendto(lap_header + (lap_entry * 22) + b"\xff\xff", (ip, port))

        # Pacote CarTelemetry (ID 6)
        tel_header = struct.pack(HEADER_FORMAT_29, 2024, 24, 1, 0, 1, 6, 999999, session_time, 10, 10, 0, 255)
        tel_entry = struct.pack(
            CAR_TELEMETRY_ENTRY_FORMAT,
            speed, throttle, 0.0, brake, 0, gear, 11500, 0, 80, 0,
            400, 400, 420, 420, 95, 95, 90, 90, 100, 100, 95, 95,
            105, 23.5, 23.5, 24.0, 24.0, 0, 0, 0, 0
        )
        sock.sendto(tel_header + (tel_entry * 22) + b"\x00\x00\x00", (ip, port))

        time.sleep(delay)

    # Conclusão da volta (incrementa lap_num para 2 para disparar o salvamento)
    lap_num = 2
    session_time += 0.05
    lap_header = struct.pack(HEADER_FORMAT_29, 2024, 24, 1, 0, 1, 2, 999999, session_time, 11, 11, 0, 255)
    lap_entry = struct.pack(
        LAP_DATA_ENTRY_FORMAT,
        lap_time_ms, 0,
        30000, 1,
        32000, 1,
        0, 0,
        0, 0,
        10.0, float(total_distance + 10), 0.0,
        1, lap_num,
        0, 0, 0, 0,
        0, 0, 0, 0, 0,
        1, 4, 2, 0,
        0, 0, 0,
        340.0, 1
    )
    sock.sendto(lap_header + (lap_entry * 22) + b"\xff\xff", (ip, port))
    print("🏁 Volta simulada enviada com sucesso!")
    sock.close()


if __name__ == "__main__":
    send_simulated_lap()
