"""Detector multi-portas e multi-interfaces para telemetria UDP."""

import socket
import select
import time

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

print(f"📡 Monitorando portas {[p for _, p in sockets]} por 8 segundos...")
print("DICA: Certifique-se de que o jogo está despausado (carro acelerando ou na pista)!")

start = time.time()
found = False

while time.time() - start < 8.0:
    rlist = [s for s, _ in sockets]
    readable, _, _ = select.select(rlist, [], [], 0.5)
    for s in readable:
        data, addr = s.recvfrom(2048)
        # Identifica a porta
        port = next(p for sock, p in sockets if sock == s)
        print(f"✅ PACOTE DETECTADO NA PORTA {port}! De: {addr} | Bytes: {len(data)}")
        found = True
        break
    if found:
        break

for s, _ in sockets:
    s.close()

if not found:
    print("❌ Nenhum pacote recebido em nenhuma porta monitorada durante os 8 segundos.")
