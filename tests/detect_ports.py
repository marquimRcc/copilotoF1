"""Detector multi-portas e multi-interfaces para telemetria UDP."""

import select
import socket
import time


def detect_active_ports(timeout_s: float = 8.0) -> None:
    ports = [20777, 20778, 20779, 10001, 10002]
    sockets = []

    for p in ports:
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            s.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
            s.bind(("0.0.0.0", p))
            s.setblocking(False)
            sockets.append((s, p))
        except Exception as e:
            print(f"Não foi possível abrir porta {p}: {e}")

    print(f"📡 Monitorando portas {[p for _, p in sockets]} por {timeout_s:.0f} segundos...")
    start = time.time()
    found = False

    while time.time() - start < timeout_s:
        rlist = [s for s, _ in sockets]
        if not rlist:
            break
        readable, _, _ = select.select(rlist, [], [], 0.5)
        for s in readable:
            data, addr = s.recvfrom(2048)
            port = next(p for sock, p in sockets if sock == s)
            print(f"✅ PACOTE DETECTADO NA PORTA {port}! De: {addr} | Bytes: {len(data)}")
            found = True
            break
        if found:
            break

    for s, _ in sockets:
        s.close()

    if not found:
        print("❌ Nenhum pacote recebido em nenhuma porta monitorada.")


if __name__ == "__main__":
    detect_active_ports()
