"""HUD Compacto em Tempo Real (450x230) - Layout 1: Flag Periférica."""

import argparse
import csv
import os
import socket
import sys
import threading
import time
import tkinter as tk
from datetime import datetime
from typing import Dict, List, Optional

# Adiciona o diretório src ao sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from packets.header import (
    PACKET_ID_CAR_TELEMETRY,
    PACKET_ID_LAP_DATA,
    PACKET_ID_SESSION,
    parse_header,
)
from packets.car_telemetry import parse_car_telemetry
from packets.lap_data import parse_lap_data
from packets.session import parse_session_data
from tracks.circuits import CornerZone, get_circuit_by_track_id

# Paleta de Cores de Alto Contraste (Layout 1)
COLORS = {
    "reta": {"bg": "#0a0a0a", "text": "#a3a3a3", "sub": "#737373", "top": "#525252"},
    "preparo": {"bg": "#d97706", "text": "#000000", "sub": "#1c1917", "top": "#451a03"},
    "freia": {"bg": "#dc2626", "text": "#ffffff", "sub": "#fef2f2", "top": "#7f1d1d"},
    "freia_pulse": {"bg": "#ef4444", "text": "#ffffff", "sub": "#ffffff", "top": "#991b1b"},
    "apice": {"bg": "#0284c7", "text": "#ffffff", "sub": "#e0f2fe", "top": "#075985"},
    "acelera": {"bg": "#16a34a", "text": "#ffffff", "sub": "#f0fdf4", "top": "#14532d"},
}


class F1HudOverlay:
    def __init__(self, host: str = "127.0.0.1", port: int = 20777, record_csv: bool = True, output_dir: str = "data"):
        self.host = host
        self.port = port
        self.record_csv = record_csv
        self.output_dir = output_dir

        # Estado da telemetria
        self.track_id: int = 11  # Padrão: Monza
        self.circuit = get_circuit_by_track_id(self.track_id)
        self.lap_distance: float = 0.0
        self.speed: int = 0
        self.gear: int = 0
        self.throttle: float = 0.0
        self.brake: float = 0.0
        self.lap_num: int = 0
        self.is_valid: bool = True
        self.session_name: str = "Aguardando F1..."
        self.track_name: str = "Monza"

        # Estado visual
        self.current_state: str = "reta"
        self.pulse_flag: bool = False
        self.next_corner: Optional[CornerZone] = None
        self.dist_to_brake: float = 0.0

        # Gravação de CSV integrada
        self.active_lap_num: int = 0
        self.lap_samples: List[Dict] = []
        self.last_lap_data = None

        # Threading e socket
        self.running: bool = True
        self.sock: Optional[socket.socket] = None

        # Montagem da Interface Tkinter
        self.root = tk.Tk()
        self.setup_ui()

    def setup_ui(self):
        """Configura a janela 450x230 com propriedades Always on Top."""
        self.root.title("Copiloto F1 - HUD")
        self.root.geometry("450x230")
        self.root.resizable(False, False)
        # Manter sempre sobre o jogo
        self.root.attributes("-topmost", True)
        self.root.configure(bg=COLORS["reta"]["bg"])

        # Container Principal
        self.container = tk.Frame(self.root, bg=COLORS["reta"]["bg"], padx=16, pady=12)
        self.container.pack(fill=tk.BOTH, expand=True)

        # 1. Barra Superior (Pista • Curva | Distância)
        self.top_frame = tk.Frame(self.container, bg=COLORS["reta"]["bg"])
        self.top_frame.pack(fill=tk.X)

        self.lbl_track = tk.Label(
            self.top_frame,
            text="MONZA • AGUARDANDO",
            font=("Helvetica", 10, "bold"),
            fg=COLORS["reta"]["top"],
            bg=COLORS["reta"]["bg"],
        )
        self.lbl_track.pack(side=tk.LEFT)

        self.lbl_dist = tk.Label(
            self.top_frame,
            text="--",
            font=("Helvetica", 10, "bold"),
            fg=COLORS["reta"]["top"],
            bg=COLORS["reta"]["bg"],
        )
        self.lbl_dist.pack(side=tk.RIGHT)

        # 2. Centro (Alerta Gigante de Flag e Subtítulo)
        self.center_frame = tk.Frame(self.container, bg=COLORS["reta"]["bg"])
        self.center_frame.pack(fill=tk.BOTH, expand=True)

        self.lbl_main_alert = tk.Label(
            self.center_frame,
            text="RETA",
            font=("Helvetica", 36, "bold"),
            fg=COLORS["reta"]["text"],
            bg=COLORS["reta"]["bg"],
        )
        self.lbl_main_alert.pack(expand=True, pady=(8, 0))

        self.lbl_sub_alert = tk.Label(
            self.center_frame,
            text="VELOCIDADE MÁXIMA",
            font=("Helvetica", 11, "bold"),
            fg=COLORS["reta"]["sub"],
            bg=COLORS["reta"]["bg"],
        )
        self.lbl_sub_alert.pack(pady=(0, 8))

        # 3. Barra Inferior (Velocidade | Marcha | Pedais)
        self.bottom_frame = tk.Frame(self.container, bg=COLORS["reta"]["bg"])
        self.bottom_frame.pack(fill=tk.X)

        self.lbl_speed = tk.Label(
            self.bottom_frame,
            text="0 km/h",
            font=("Courier", 10, "bold"),
            fg=COLORS["reta"]["top"],
            bg=COLORS["reta"]["bg"],
        )
        self.lbl_speed.pack(side=tk.LEFT)

        self.lbl_gear = tk.Label(
            self.bottom_frame,
            text="MARCHA: N",
            font=("Courier", 10, "bold"),
            fg=COLORS["reta"]["top"],
            bg=COLORS["reta"]["bg"],
        )
        self.lbl_gear.pack(side=tk.RIGHT)

        self.root.protocol("WM_DELETE_WINDOW", self.on_close)

    def start_network_thread(self):
        """Inicia a escuta UDP em uma thread paralela."""
        thread = threading.Thread(target=self._udp_listener_loop, daemon=True)
        thread.start()

    def _udp_listener_loop(self):
        """Loop de escuta UDP do F1."""
        os.makedirs(self.output_dir, exist_ok=True)
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)

        try:
            self.sock.bind((self.host, self.port))
            print(f"📡 HUD escutando UDP em {self.host}:{self.port}...")
            while self.running:
                data, _ = self.sock.recvfrom(2048)
                self._handle_packet(data)
        except Exception as e:
            if self.running:
                print(f"Erro no socket UDP: {e}")
        finally:
            if self.sock:
                self.sock.close()

    def _handle_packet(self, data: bytes):
        header = parse_header(data)
        if not header:
            return

        # 1. Sessão (ID 1)
        if header.packet_id == PACKET_ID_SESSION:
            session = parse_session_data(data, header)
            if session:
                if self.track_id != session.track_id:
                    self.track_id = session.track_id
                    self.circuit = get_circuit_by_track_id(self.track_id)
                self.track_name = session.track_name.split("(")[0].strip()
                self.session_name = session.session_type_name

        # 2. Lap Data (ID 2)
        elif header.packet_id == PACKET_ID_LAP_DATA:
            lap = parse_lap_data(data, header)
            if lap:
                self.lap_distance = lap.lap_distance
                self.lap_num = lap.current_lap_num
                self.is_valid = not lap.current_lap_invalid

                # Gravação de volta concluída
                if self.record_csv:
                    if self.last_lap_data and lap.current_lap_num > self.active_lap_num:
                        if len(self.lap_samples) >= 50:
                            self._save_lap_csv(self.active_lap_num, lap.last_lap_time_ms, not self.last_lap_data.current_lap_invalid)
                        self.lap_samples.clear()
                        self.active_lap_num = lap.current_lap_num
                    elif self.active_lap_num == 0 and lap.current_lap_num > 0:
                        self.active_lap_num = lap.current_lap_num
                self.last_lap_data = lap

        # 3. Telemetria do Carro (ID 6)
        elif header.packet_id == PACKET_ID_CAR_TELEMETRY:
            tel = parse_car_telemetry(data, header)
            if tel:
                self.speed = tel.speed
                self.gear = tel.gear
                self.throttle = tel.throttle
                self.brake = tel.brake

                # Registra amostra para CSV
                if self.record_csv and self.last_lap_data:
                    self.lap_samples.append({
                        "session_time": round(header.session_time, 3),
                        "lap_number": self.last_lap_data.current_lap_num,
                        "lap_distance": self.last_lap_data.lap_distance,
                        "speed": tel.speed,
                        "throttle": tel.throttle,
                        "brake": tel.brake,
                        "steer": tel.steer,
                        "gear": tel.gear,
                        "engine_rpm": tel.engine_rpm,
                        "drs": tel.drs,
                        "lap_time_ms": self.last_lap_data.current_lap_time_ms,
                        "is_valid": 0 if self.last_lap_data.current_lap_invalid else 1,
                    })

                # Atualiza a lógica de decisão da curva
                self._update_corner_logic()

    def _update_corner_logic(self):
        """Determina o estado atual (Reta, Preparo, Freia, Ápice, Acelera)."""
        if not self.circuit or not self.circuit.corners:
            self.current_state = "reta"
            return

        dist = self.lap_distance
        target_corner = None
        closest_dist = 99999.0

        for corner in self.circuit.corners:
            # Se o carro está dentro da zona ativa da curva
            if (corner.start_distance - 65.0) <= dist <= corner.end_distance:
                target_corner = corner
                break
            # Próxima curva à frente
            if corner.start_distance > dist:
                d = corner.start_distance - dist
                if d < closest_dist:
                    closest_dist = d
                    target_corner = corner

        if not target_corner:
            # Curva 1 após a linha de chegada
            target_corner = self.circuit.corners[0]
            closest_dist = (self.circuit.length - dist) + target_corner.start_distance

        self.next_corner = target_corner

        # Lógica de estados baseada na distância
        if (target_corner.start_distance - 60.0) <= dist < target_corner.start_distance:
            self.current_state = "preparo"
            self.dist_to_brake = target_corner.start_distance - dist

        elif target_corner.start_distance <= dist < (target_corner.start_distance + 45.0):
            self.current_state = "freia"
            self.dist_to_brake = 0.0

        elif (target_corner.apex_distance - 30.0) <= dist <= (target_corner.apex_distance + 35.0):
            self.current_state = "apice"
            self.dist_to_brake = 0.0

        elif (target_corner.end_distance - 40.0) <= dist <= target_corner.end_distance:
            self.current_state = "acelera"
            self.dist_to_brake = 0.0

        else:
            self.current_state = "reta"
            if target_corner.start_distance > dist:
                self.dist_to_brake = target_corner.start_distance - dist
            else:
                self.dist_to_brake = (self.circuit.length - dist) + target_corner.start_distance

    def update_ui_loop(self):
        """Loop de atualização gráfica (~60 FPS)."""
        if not self.running:
            return

        state = self.current_state
        palette = COLORS.get(state, COLORS["reta"])

        # Pulso visual vibrante durante a frenagem
        if state == "freia":
            self.pulse_flag = not self.pulse_flag
            if self.pulse_flag:
                palette = COLORS["freia_pulse"]

        # Aplica cores no container e labels
        bg_color = palette["bg"]
        text_color = palette["text"]
        sub_color = palette["sub"]
        top_color = palette["top"]

        self.root.configure(bg=bg_color)
        self.container.configure(bg=bg_color)
        self.top_frame.configure(bg=bg_color)
        self.center_frame.configure(bg=bg_color)
        self.bottom_frame.configure(bg=bg_color)

        # Atualiza Barra Superior
        corner_name = self.next_corner.name if self.next_corner else "TRAÇADO"
        corner_num = f"C{self.next_corner.number}" if self.next_corner else ""
        self.lbl_track.config(
            text=f"{self.track_name.upper()} • {corner_num} {corner_name}".strip(),
            fg=top_color,
            bg=bg_color,
        )

        if state == "reta":
            self.lbl_dist.config(text=f"EM {self.dist_to_brake:.0f}m", fg=top_color, bg=bg_color)
            self.lbl_main_alert.config(text="RETA", fg=text_color, bg=bg_color)
            self.lbl_sub_alert.config(text="VELOCIDADE MÁXIMA", fg=sub_color, bg=bg_color)

        elif state == "preparo":
            self.lbl_dist.config(text=f"FREIO EM {self.dist_to_brake:.0f}m", fg=top_color, bg=bg_color)
            self.lbl_main_alert.config(text="ATENÇÃO", fg=text_color, bg=bg_color)
            self.lbl_sub_alert.config(text=f"PREPARE A FREADA ({self.dist_to_brake:.0f}m)", fg=sub_color, bg=bg_color)

        elif state == "freia":
            self.lbl_dist.config(text="PONTO DE FREIO!", fg=top_color, bg=bg_color)
            self.lbl_main_alert.config(text="FREIA!", fg=text_color, bg=bg_color)
            gear_target = f"REDUZA ➔ {self.next_corner.gear_reference}ª" if self.next_corner else "FRENAGEM FORTE"
            self.lbl_sub_alert.config(text=f"100% FREIO • {gear_target}", fg=sub_color, bg=bg_color)

        elif state == "apice":
            gear_ref = self.next_corner.gear_reference if self.next_corner else self.gear
            self.lbl_dist.config(text="ÁPICE / CONTORNO", fg=top_color, bg=bg_color)
            self.lbl_main_alert.config(text=f"ÁPICE ({gear_ref}ª)", fg=text_color, bg=bg_color)
            self.lbl_sub_alert.config(text="SOLTE O FREIO / MIRA A ZEBRA", fg=sub_color, bg=bg_color)

        elif state == "acelera":
            self.lbl_dist.config(text="SAÍDA DE CURVA", fg=top_color, bg=bg_color)
            self.lbl_main_alert.config(text="ACELERA!", fg=text_color, bg=bg_color)
            self.lbl_sub_alert.config(text="PROGRESSIVO • EVITE DESTRACIONAR", fg=sub_color, bg=bg_color)

        # Barra Inferior
        gear_str = "R" if self.gear == -1 else ("N" if self.gear == 0 else f"{self.gear}ª")
        self.lbl_speed.config(text=f"{self.speed} km/h", fg=top_color, bg=bg_color)
        self.lbl_gear.config(text=f"MARCHA: {gear_str}", fg=top_color, bg=bg_color)

        # Agenda próximo quadro (16ms = ~60 FPS)
        self.root.after(16, self.update_ui_loop)

    def _save_lap_csv(self, lap_number: int, lap_time_ms: int, is_valid: bool):
        """Salva a volta no diretório data."""
        track_slug = "".join(c if c.isalnum() else "_" for c in self.track_name.lower()).strip("_")
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        valid_tag = "valida" if is_valid else "invalida"
        filename = f"volta_{lap_number:02d}_{track_slug}_{valid_tag}_{timestamp}.csv"
        filepath = os.path.join(self.output_dir, filename)

        with open(filepath, mode="w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=[
                "session_time", "lap_number", "lap_distance", "speed",
                "throttle", "brake", "steer", "gear", "engine_rpm",
                "drs", "lap_time_ms", "is_valid",
            ])
            writer.writeheader()
            writer.writerows(self.lap_samples)

        minutos = lap_time_ms // 60000
        segundos = (lap_time_ms % 60000) / 1000.0
        print(f"🏁 [VOLTA GRAVADA] #{lap_number} | Tempo: {minutos:02d}:{segundos:06.3f} | {filename}")

    def on_close(self):
        """Encerra a aplicação limpa."""
        self.running = False
        if self.sock:
            self.sock.close()
        self.root.destroy()

    def run(self):
        """Inicia a interface e o loop UDP."""
        self.start_network_thread()
        self.root.after(100, self.update_ui_loop)
        self.root.mainloop()


def run_demo_mode():
    """Modo demonstração com loop de simulação sem o jogo aberto."""
    hud = F1HudOverlay(port=20777, record_csv=False)

    def _demo_loop():
        time.sleep(0.5)
        states = [
            ("reta", 350, 335, 8),
            ("preparo", 45, 340, 8),
            ("freia", 0, 315, 4),
            ("apice", 0, 74, 2),
            ("acelera", 0, 140, 3),
        ]
        while hud.running:
            for s, dist, spd, gr in states:
                if not hud.running:
                    break
                hud.current_state = s
                hud.dist_to_brake = dist
                hud.speed = spd
                hud.gear = gr
                dur = 1.2 if s in ["freia", "preparo"] else 1.8
                time.sleep(dur)

    threading.Thread(target=_demo_loop, daemon=True).start()
    hud.root.after(100, hud.update_ui_loop)
    hud.root.mainloop()


def main():
    parser = argparse.ArgumentParser(description="HUD Copiloto F1 (Layout 1: Flag Periférica)")
    parser.add_argument("--port", type=int, default=20777, help="Porta UDP (padrão: 20777)")
    parser.add_argument("--host", default="127.0.0.1", help="IP UDP (padrão: 127.0.0.1)")
    parser.add_argument("--no-record", action="store_true", help="Desativa a gravação automática de CSV")
    parser.add_argument("--demo", action="store_true", help="Executa o modo de demonstração/teste")
    args = parser.parse_args()

    if args.demo:
        run_demo_mode()
    else:
        hud = F1HudOverlay(host=args.host, port=args.port, record_csv=not args.no_record)
        hud.run()


if __name__ == "__main__":
    main()
