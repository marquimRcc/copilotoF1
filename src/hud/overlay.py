"""HUD Compacto em Tempo Real (450x230) com 3 Layouts Alternáveis e Menu Systray."""

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

# Suporte opcional à bandeja do sistema (Systray)
try:
    import pystray
    from PIL import Image, ImageDraw
    HAS_PYSTRAY = True
except ImportError:
    HAS_PYSTRAY = False

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

# Paleta de Cores de Alto Contraste
COLORS = {
    "reta": {"bg": "#0a0a0a", "text": "#a3a3a3", "sub": "#737373", "top": "#525252"},
    "preparo": {"bg": "#d97706", "text": "#000000", "sub": "#1c1917", "top": "#451a03"},
    "freia": {"bg": "#dc2626", "text": "#ffffff", "sub": "#fef2f2", "top": "#7f1d1d"},
    "freia_pulse": {"bg": "#ef4444", "text": "#ffffff", "sub": "#ffffff", "top": "#991b1b"},
    "apice": {"bg": "#0284c7", "text": "#ffffff", "sub": "#e0f2fe", "top": "#075985"},
    "acelera": {"bg": "#16a34a", "text": "#ffffff", "sub": "#f0fdf4", "top": "#14532d"},
}


class F1HudOverlay:
    def __init__(self, host: str = "127.0.0.1", port: int = 20777, initial_layout: int = 1, record_csv: bool = True, output_dir: str = "data"):
        self.host = host
        self.port = port
        self.active_layout = initial_layout
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
        self.track_name: str = "Monza"
        self.session_name: str = "Aguardando F1..."

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
        self.tray_icon = None

        # Interface Tkinter
        self.root = tk.Tk()
        self.setup_ui()
        self.setup_context_menu()
        self.setup_systray()

    def setup_ui(self):
        """Configura a janela e os containers dos 3 layouts."""
        self.root.title("Copiloto F1 - HUD")
        self.root.geometry("450x230")
        self.root.resizable(False, False)
        self.root.attributes("-topmost", True)
        self.root.configure(bg=COLORS["reta"]["bg"])

        # Container Principal
        self.container = tk.Frame(self.root, bg=COLORS["reta"]["bg"])
        self.container.pack(fill=tk.BOTH, expand=True)

        # Montagem dos 3 Layouts
        self._build_layout_1()
        self._build_layout_2()
        self._build_layout_3()

        # Ativa o layout inicial
        self.set_layout(self.active_layout)

        # Atalhos de Teclado
        self.root.bind("<Key-1>", lambda e: self.set_layout(1))
        self.root.bind("<Key-2>", lambda e: self.set_layout(2))
        self.root.bind("<Key-3>", lambda e: self.set_layout(3))
        self.root.bind("<Escape>", lambda e: self.on_close())
        self.root.bind("<q>", lambda e: self.on_close())
        self.root.protocol("WM_DELETE_WINDOW", self.on_close)

    # -------------------------------------------------------------
    # LAYOUT 1: FLAG PERIFÉRICA (PURA)
    # -------------------------------------------------------------
    def _build_layout_1(self):
        self.f1 = tk.Frame(self.container, bg=COLORS["reta"]["bg"], padx=16, pady=12)

        self.f1_top = tk.Frame(self.f1, bg=COLORS["reta"]["bg"])
        self.f1_top.pack(fill=tk.X)
        self.l1_lbl_track = tk.Label(self.f1_top, text="MONZA • AGUARDANDO", font=("Helvetica", 10, "bold"), fg=COLORS["reta"]["top"], bg=COLORS["reta"]["bg"])
        self.l1_lbl_track.pack(side=tk.LEFT)
        self.l1_lbl_dist = tk.Label(self.f1_top, text="--", font=("Helvetica", 10, "bold"), fg=COLORS["reta"]["top"], bg=COLORS["reta"]["bg"])
        self.l1_lbl_dist.pack(side=tk.RIGHT)

        self.f1_center = tk.Frame(self.f1, bg=COLORS["reta"]["bg"])
        self.f1_center.pack(fill=tk.BOTH, expand=True)
        self.l1_lbl_main = tk.Label(self.f1_center, text="RETA", font=("Helvetica", 36, "bold"), fg=COLORS["reta"]["text"], bg=COLORS["reta"]["bg"])
        self.l1_lbl_main.pack(expand=True, pady=(8, 0))
        self.l1_lbl_sub = tk.Label(self.f1_center, text="VELOCIDADE MÁXIMA", font=("Helvetica", 11, "bold"), fg=COLORS["reta"]["sub"], bg=COLORS["reta"]["bg"])
        self.l1_lbl_sub.pack(pady=(0, 8))

        self.f1_bottom = tk.Frame(self.f1, bg=COLORS["reta"]["bg"])
        self.f1_bottom.pack(fill=tk.X)
        self.l1_lbl_speed = tk.Label(self.f1_bottom, text="0 km/h", font=("Courier", 10, "bold"), fg=COLORS["reta"]["top"], bg=COLORS["reta"]["bg"])
        self.l1_lbl_speed.pack(side=tk.LEFT)
        self.l1_lbl_gear = tk.Label(self.f1_bottom, text="MARCHA: N", font=("Courier", 10, "bold"), fg=COLORS["reta"]["top"], bg=COLORS["reta"]["bg"])
        self.l1_lbl_gear.pack(side=tk.RIGHT)

    # -------------------------------------------------------------
    # LAYOUT 2: BARRA PROGRESSIVA + LEDS (ESTILO VOLANTE)
    # -------------------------------------------------------------
    def _build_layout_2(self):
        self.f2 = tk.Frame(self.container, bg="#111111", padx=14, pady=10)

        # Barra de 8 LEDs superiores
        self.f2_leds_frame = tk.Frame(self.f2, bg="#111111")
        self.f2_leds_frame.pack(fill=tk.X, pady=(0, 6))
        self.f2_leds = []
        for _ in range(8):
            canvas = tk.Canvas(self.f2_leds_frame, width=44, height=8, bg="#262626", highlightthickness=0)
            canvas.pack(side=tk.LEFT, padx=3, expand=True, fill=tk.X)
            self.f2_leds.append(canvas)

        self.f2_top = tk.Frame(self.f2, bg="#111111")
        self.f2_top.pack(fill=tk.X)
        self.l2_lbl_corner = tk.Label(self.f2_top, text="C1: VARIANTE RETTIFILO", font=("Helvetica", 10, "bold"), fg="#e5e5e5", bg="#111111")
        self.l2_lbl_corner.pack(side=tk.LEFT)
        self.l2_lbl_dist = tk.Label(self.f2_top, text="120m", font=("Courier", 10, "bold"), fg="#a3a3a3", bg="#111111")
        self.l2_lbl_dist.pack(side=tk.RIGHT)

        # Centro: Ação + Barra Progressiva
        self.f2_center = tk.Frame(self.f2, bg="#111111")
        self.f2_center.pack(fill=tk.BOTH, expand=True, pady=4)
        self.l2_lbl_action = tk.Label(self.f2_center, text="ACELERAR", font=("Helvetica", 24, "bold"), fg="#ffffff", bg="#111111")
        self.l2_lbl_action.pack(pady=(2, 2))

        # Canvas da barra de progresso horizontal
        self.l2_progress_canvas = tk.Canvas(self.f2_center, height=10, bg="#262626", highlightthickness=0)
        self.l2_progress_canvas.pack(fill=tk.X, padx=10, pady=2)

        # Rodapé: Marcha | Ápice Alvo | Velocidade Atual
        self.f2_bottom = tk.Frame(self.f2, bg="#1c1c1c", padx=8, pady=4)
        self.f2_bottom.pack(fill=tk.X)
        self.l2_lbl_gear_val = tk.Label(self.f2_bottom, text="MARCHA: 8", font=("Helvetica", 9, "bold"), fg="#ffffff", bg="#1c1c1c")
        self.l2_lbl_gear_val.pack(side=tk.LEFT, expand=True)
        self.l2_lbl_apex_target = tk.Label(self.f2_bottom, text="ALVO: 74 km/h", font=("Helvetica", 9, "bold"), fg="#38bdf8", bg="#1c1c1c")
        self.l2_lbl_apex_target.pack(side=tk.LEFT, expand=True)
        self.l2_lbl_speed_val = tk.Label(self.f2_bottom, text="334 km/h", font=("Helvetica", 9, "bold"), fg="#ffffff", bg="#1c1c1c")
        self.l2_lbl_speed_val.pack(side=tk.RIGHT, expand=True)

    # -------------------------------------------------------------
    # LAYOUT 3: COCKPIT DINÂMICO COMPLETO
    # -------------------------------------------------------------
    def _build_layout_3(self):
        self.f3 = tk.Frame(self.container, bg="#0d0d0d", padx=14, pady=10)

        # Topo
        self.f3_top = tk.Frame(self.f3, bg="#0d0d0d")
        self.f3_top.pack(fill=tk.X, pady=(0, 4))
        self.l3_lbl_track = tk.Label(self.f3_top, text="MONZA • CURVA 1", font=("Helvetica", 10, "bold"), fg="#e5e5e5", bg="#0d0d0d")
        self.l3_lbl_track.pack(side=tk.LEFT)
        self.l3_badge_status = tk.Label(self.f3_top, text="RETA PLENA", font=("Helvetica", 8, "bold"), fg="#a3a3a3", bg="#262626", padx=6, pady=1)
        self.l3_badge_status.pack(side=tk.RIGHT)

        # Centro: Card da Marcha Gigante + Instrução
        self.f3_center = tk.Frame(self.f3, bg="#0d0d0d")
        self.f3_center.pack(fill=tk.BOTH, expand=True, pady=2)

        # Card de Marcha
        self.f3_gear_box = tk.Frame(self.f3_center, bg="#171717", padx=14, pady=4, relief=tk.RIDGE, bd=1)
        self.f3_gear_box.pack(side=tk.LEFT, fill=tk.Y, padx=(0, 10))
        tk.Label(self.f3_gear_box, text="ENGATE", font=("Helvetica", 8), fg="#737373", bg="#171717").pack()
        self.l3_lbl_gear_big = tk.Label(self.f3_gear_box, text="8", font=("Helvetica", 32, "bold"), fg="#ffffff", bg="#171717")
        self.l3_lbl_gear_big.pack()

        # Instruções e Dicas
        self.f3_info_box = tk.Frame(self.f3_center, bg="#0d0d0d")
        self.f3_info_box.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        self.l3_lbl_action = tk.Label(self.f3_info_box, text="100% ACELERADOR", font=("Helvetica", 16, "bold"), fg="#ffffff", bg="#0d0d0d", anchor="w")
        self.l3_lbl_action.pack(fill=tk.X, pady=(4, 2))
        self.l3_lbl_tip = tk.Label(self.f3_info_box, text="Mantenha traçado à esquerda na reta", font=("Helvetica", 9), fg="#a3a3a3", bg="#0d0d0d", anchor="w")
        self.l3_lbl_tip.pack(fill=tk.X)

        # Rodapé: Barras Dinâmicas de Pedais (Freio e Acelerador)
        self.f3_bottom = tk.Frame(self.f3, bg="#0d0d0d")
        self.f3_bottom.pack(fill=tk.X, pady=(4, 0))

        # Barra de Freio
        self.f3_brake_frame = tk.Frame(self.f3_bottom, bg="#0d0d0d")
        self.f3_brake_frame.pack(fill=tk.X, pady=1)
        tk.Label(self.f3_brake_frame, text="FREIO", font=("Courier", 8, "bold"), fg="#ef4444", bg="#0d0d0d", width=7, anchor="w").pack(side=tk.LEFT)
        self.l3_canvas_brake = tk.Canvas(self.f3_brake_frame, height=8, bg="#262626", highlightthickness=0)
        self.l3_canvas_brake.pack(side=tk.LEFT, fill=tk.X, expand=True)

        # Barra de Acelerador
        self.f3_throttle_frame = tk.Frame(self.f3_bottom, bg="#0d0d0d")
        self.f3_throttle_frame.pack(fill=tk.X, pady=1)
        tk.Label(self.f3_throttle_frame, text="ACEL.", font=("Courier", 8, "bold"), fg="#22c55e", bg="#0d0d0d", width=7, anchor="w").pack(side=tk.LEFT)
        self.l3_canvas_throttle = tk.Canvas(self.f3_throttle_frame, height=8, bg="#262626", highlightthickness=0)
        self.l3_canvas_throttle.pack(side=tk.LEFT, fill=tk.X, expand=True)

    # -------------------------------------------------------------
    # MUDANÇA DE LAYOUT & MENUS
    # -------------------------------------------------------------
    def set_layout(self, layout_id: int):
        """Alterna dinamicamente entre os 3 layouts."""
        self.active_layout = layout_id

        self.f1.pack_forget()
        self.f2.pack_forget()
        self.f3.pack_forget()

        if layout_id == 1:
            self.f1.pack(fill=tk.BOTH, expand=True)
        elif layout_id == 2:
            self.f2.pack(fill=tk.BOTH, expand=True)
        elif layout_id == 3:
            self.f3.pack(fill=tk.BOTH, expand=True)

        print(f"🔄 HUD alterado para o Layout {layout_id}")

    def setup_context_menu(self):
        """Cria o menu de contexto acionado pelo botão direito."""
        self.menu = tk.Menu(self.root, tearoff=0)

        # Submenu de Layouts
        self.theme_menu = tk.Menu(self.menu, tearoff=0)
        self.theme_menu.add_command(label="1. Flag Periférica (Pura)", command=lambda: self.set_layout(1))
        self.theme_menu.add_command(label="2. Barra Progressiva + LEDs", command=lambda: self.set_layout(2))
        self.theme_menu.add_command(label="3. Cockpit Dinâmico Completo", command=lambda: self.set_layout(3))
        self.menu.add_cascade(label="🎨 Mudar Layout", menu=self.theme_menu)

        self.menu.add_separator()
        self.menu.add_command(label="🛑 Encerrar Copiloto F1", command=self.on_close)

        # Vincula o botão direito a todos os elementos
        self._bind_context_menu_recursive(self.root)

    def _bind_context_menu_recursive(self, widget):
        widget.bind("<Button-3>", self.show_context_menu)
        for child in widget.winfo_children():
            self._bind_context_menu_recursive(child)

    def show_context_menu(self, event):
        """Exibe o menu de contexto no ponto do clique."""
        try:
            self.menu.tk_popup(event.x_root, event.y_root)
        finally:
            self.menu.grab_release()

    def setup_systray(self):
        """Configura o ícone na bandeja do sistema (Windows Systray)."""
        if not HAS_PYSTRAY:
            return

        def _run_systray():
            # Gera ícone dinâmico 64x64 de um volante F1 vermelho
            img = Image.new("RGBA", (64, 64), color=(0, 0, 0, 0))
            draw = ImageDraw.Draw(img)
            draw.ellipse((4, 4, 60, 60), fill="#dc2626", outline="#ffffff", width=2)
            draw.rectangle((18, 26, 46, 38), fill="#171717")
            draw.text((22, 26), "F1", fill="#ffffff")

            systray_menu = pystray.Menu(
                pystray.MenuItem("Copiloto F1 - HUD", None, enabled=False),
                pystray.Menu.SEPARATOR,
                pystray.MenuItem("1. Flag Periférica", lambda: self.root.after(0, self.set_layout, 1)),
                pystray.MenuItem("2. Barra Progressiva", lambda: self.root.after(0, self.set_layout, 2)),
                pystray.MenuItem("3. Cockpit Dinâmico", lambda: self.root.after(0, self.set_layout, 3)),
                pystray.Menu.SEPARATOR,
                pystray.MenuItem("🛑 Encerrar", lambda: self.root.after(0, self.on_close)),
            )

            self.tray_icon = pystray.Icon("copilotoF1", img, "Copiloto F1", systray_menu)
            self.tray_icon.run()

        threading.Thread(target=_run_systray, daemon=True).start()

    # -------------------------------------------------------------
    # LOOP DE TELEMETRIA E ATUALIZAÇÃO
    # -------------------------------------------------------------
    def start_network_thread(self):
        thread = threading.Thread(target=self._udp_listener_loop, daemon=True)
        thread.start()

    def _udp_listener_loop(self):
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

        if header.packet_id == PACKET_ID_SESSION:
            session = parse_session_data(data, header)
            if session:
                if self.track_id != session.track_id:
                    self.track_id = session.track_id
                    self.circuit = get_circuit_by_track_id(self.track_id)
                self.track_name = session.track_name.split("(")[0].strip()
                self.session_name = session.session_type_name

        elif header.packet_id == PACKET_ID_LAP_DATA:
            lap = parse_lap_data(data, header)
            if lap:
                self.lap_distance = lap.lap_distance
                self.lap_num = lap.current_lap_num
                self.is_valid = not lap.current_lap_invalid

                if self.record_csv:
                    if self.last_lap_data and lap.current_lap_num > self.active_lap_num:
                        if len(self.lap_samples) >= 50:
                            self._save_lap_csv(self.active_lap_num, lap.last_lap_time_ms, not self.last_lap_data.current_lap_invalid)
                        self.lap_samples.clear()
                        self.active_lap_num = lap.current_lap_num
                    elif self.active_lap_num == 0 and lap.current_lap_num > 0:
                        self.active_lap_num = lap.current_lap_num
                self.last_lap_data = lap

        elif header.packet_id == PACKET_ID_CAR_TELEMETRY:
            tel = parse_car_telemetry(data, header)
            if tel:
                self.speed = tel.speed
                self.gear = tel.gear
                self.throttle = tel.throttle
                self.brake = tel.brake

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

                self._update_corner_logic()

    def _update_corner_logic(self):
        if not self.circuit or not self.circuit.corners:
            self.current_state = "reta"
            return

        dist = self.lap_distance
        target_corner = None
        closest_dist = 99999.0

        for corner in self.circuit.corners:
            if (corner.start_distance - 65.0) <= dist <= corner.end_distance:
                target_corner = corner
                break
            if corner.start_distance > dist:
                d = corner.start_distance - dist
                if d < closest_dist:
                    closest_dist = d
                    target_corner = corner

        if not target_corner:
            target_corner = self.circuit.corners[0]
            closest_dist = (self.circuit.length - dist) + target_corner.start_distance

        self.next_corner = target_corner

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
        """Loop de renderização a ~60 FPS."""
        if not self.running:
            return

        state = self.current_state
        palette = COLORS.get(state, COLORS["reta"])
        if state == "freia":
            self.pulse_flag = not self.pulse_flag
            if self.pulse_flag:
                palette = COLORS["freia_pulse"]

        corner_name = self.next_corner.name if self.next_corner else "TRAÇADO"
        corner_num = f"C{self.next_corner.number}" if self.next_corner else ""
        gear_target = self.next_corner.gear_reference if self.next_corner else self.gear
        gear_str = "R" if self.gear == -1 else ("N" if self.gear == 0 else f"{self.gear}")

        # ----------------- ATUALIZAÇÃO LAYOUT 1 -----------------
        if self.active_layout == 1:
            bg_color = palette["bg"]
            self.root.configure(bg=bg_color)
            self.f1.configure(bg=bg_color)
            self.f1_top.configure(bg=bg_color)
            self.f1_center.configure(bg=bg_color)
            self.f1_bottom.configure(bg=bg_color)

            self.l1_lbl_track.config(text=f"{self.track_name.upper()} • {corner_num} {corner_name}".strip(), fg=palette["top"], bg=bg_color)
            self.l1_lbl_speed.config(text=f"{self.speed} km/h", fg=palette["top"], bg=bg_color)
            self.l1_lbl_gear.config(text=f"MARCHA: {gear_str}ª", fg=palette["top"], bg=bg_color)

            if state == "reta":
                self.l1_lbl_dist.config(text=f"EM {self.dist_to_brake:.0f}m", fg=palette["top"], bg=bg_color)
                self.l1_lbl_main.config(text="RETA", fg=palette["text"], bg=bg_color)
                self.l1_lbl_sub.config(text="VELOCIDADE MÁXIMA", fg=palette["sub"], bg=bg_color)
            elif state == "preparo":
                self.l1_lbl_dist.config(text=f"FREIO EM {self.dist_to_brake:.0f}m", fg=palette["top"], bg=bg_color)
                self.l1_lbl_main.config(text="ATENÇÃO", fg=palette["text"], bg=bg_color)
                self.l1_lbl_sub.config(text=f"PREPARE A FREADA ({self.dist_to_brake:.0f}m)", fg=palette["sub"], bg=bg_color)
            elif state == "freia":
                self.l1_lbl_dist.config(text="PONTO DE FREIO!", fg=palette["top"], bg=bg_color)
                self.l1_lbl_main.config(text="FREIA!", fg=palette["text"], bg=bg_color)
                self.l1_lbl_sub.config(text=f"100% FREIO • REDUZA ➔ {gear_target}ª", fg=palette["sub"], bg=bg_color)
            elif state == "apice":
                self.l1_lbl_dist.config(text="ÁPICE / CONTORNO", fg=palette["top"], bg=bg_color)
                self.l1_lbl_main.config(text=f"ÁPICE ({gear_target}ª)", fg=palette["text"], bg=bg_color)
                self.l1_lbl_sub.config(text="SOLTE O FREIO / MIRA A ZEBRA", fg=palette["sub"], bg=bg_color)
            elif state == "acelera":
                self.l1_lbl_dist.config(text="SAÍDA DE CURVA", fg=palette["top"], bg=bg_color)
                self.l1_lbl_main.config(text="ACELERA!", fg=palette["text"], bg=bg_color)
                self.l1_lbl_sub.config(text="PROGRESSIVO • EVITE DESTRACIONAR", fg=palette["sub"], bg=bg_color)

        # ----------------- ATUALIZAÇÃO LAYOUT 2 -----------------
        elif self.active_layout == 2:
            self.root.configure(bg="#111111")
            self.l2_lbl_corner.config(text=f"{corner_num}: {corner_name}".upper())
            self.l2_lbl_dist.config(text=f"{self.dist_to_brake:.0f}m" if state == "reta" or state == "preparo" else "PONTO ZERO")
            self.l2_lbl_gear_val.config(text=f"MARCHA: {gear_str}")
            self.l2_lbl_speed_val.config(text=f"{self.speed} km/h")

            # LEDs superiores
            led_colors = {
                "reta": ["#262626"] * 8,
                "preparo": ["#f59e0b"] * 5 + ["#262626"] * 3,
                "freia": ["#ef4444"] * 8,
                "apice": ["#38bdf8"] * 4 + ["#262626"] * 4,
                "acelera": ["#22c55e"] * 8,
            }
            colors_to_use = led_colors.get(state, led_colors["reta"])
            for i, c in enumerate(self.f2_leds):
                c.configure(bg=colors_to_use[i])

            # Ação e Barra de Progresso
            if state == "reta":
                self.l2_lbl_action.config(text="ACELERAR", fg="#a3a3a3")
                bar_color = "#3b82f6"
            elif state == "preparo":
                self.l2_lbl_action.config(text="PREPARAR", fg="#f59e0b")
                bar_color = "#f59e0b"
            elif state == "freia":
                self.l2_lbl_action.config(text="FREIA AGORA!", fg="#ef4444")
                bar_color = "#ef4444"
            elif state == "apice":
                self.l2_lbl_action.config(text="CONTORNO", fg="#38bdf8")
                bar_color = "#38bdf8"
            elif state == "acelera":
                self.l2_lbl_action.config(text="ACELERAÇÃO", fg="#22c55e")
                bar_color = "#22c55e"

            # Desenha barra
            w = self.l2_progress_canvas.winfo_width()
            self.l2_progress_canvas.delete("all")
            fill_pct = 1.0 if state == "freia" else (0.75 if state == "preparo" else 0.3)
            self.l2_progress_canvas.create_rectangle(0, 0, int(w * fill_pct), 10, fill=bar_color, outline="")

        # ----------------- ATUALIZAÇÃO LAYOUT 3 -----------------
        elif self.active_layout == 3:
            self.root.configure(bg="#0d0d0d")
            self.l3_lbl_track.config(text=f"{self.track_name.upper()} • {corner_num}")
            self.l3_lbl_gear_big.config(text=gear_str)

            if state == "reta":
                self.l3_badge_status.config(text="RETA", bg="#262626", fg="#a3a3a3")
                self.l3_lbl_action.config(text="100% ACELERADOR", fg="#ffffff")
                self.l3_lbl_tip.config(text=f"Próxima freada em {self.dist_to_brake:.0f}m")
            elif state == "preparo":
                self.l3_badge_status.config(text="APROXIMAÇÃO", bg="#78350f", fg="#fef08a")
                self.l3_lbl_action.config(text="PREPARE A FREADA", fg="#f59e0b")
                self.l3_lbl_tip.config(text=f"Foco na placa de referência ({self.dist_to_brake:.0f}m)")
            elif state == "freia":
                self.l3_badge_status.config(text="FRENAGEM", bg="#7f1d1d", fg="#fecaca")
                self.l3_lbl_action.config(text=f"FREIA 100%! (➔ {gear_target}ª)", fg="#ef4444")
                self.l3_lbl_tip.config(text="Frenagem em linha reta sem travar")
            elif state == "apice":
                self.l3_badge_status.config(text="ÁPICE", bg="#0c4a6e", fg="#bae6fd")
                self.l3_lbl_action.config(text="SOLTE O FREIO", fg="#38bdf8")
                self.l3_lbl_tip.config(text=f"Mira a zebra em {gear_target}ª marcha")
            elif state == "acelera":
                self.l3_badge_status.config(text="SAÍDA", bg="#14532d", fg="#bbf7d0")
                self.l3_lbl_action.config(text="ACELERAR PROGRESSIVO", fg="#22c55e")
                self.l3_lbl_tip.config(text="Tracionando em direção à zebra externa")

            # Atualização dos Pedais Dinâmicos
            bw = self.l3_canvas_brake.winfo_width()
            self.l3_canvas_brake.delete("all")
            self.l3_canvas_brake.create_rectangle(0, 0, int(bw * self.brake), 8, fill="#ef4444", outline="")

            tw = self.l3_canvas_throttle.winfo_width()
            self.l3_canvas_throttle.delete("all")
            self.l3_canvas_throttle.create_rectangle(0, 0, int(tw * self.throttle), 8, fill="#22c55e", outline="")

        self.root.after(16, self.update_ui_loop)

    def _save_lap_csv(self, lap_number: int, lap_time_ms: int, is_valid: bool):
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
        """Encerra a aplicação de forma limpa."""
        print("🛑 Encerrando Copiloto F1 HUD...")
        self.running = False
        if self.sock:
            self.sock.close()
            self.sock = None
        if self.tray_icon:
            try:
                self.tray_icon.stop()
            except Exception:
                pass
        try:
            self.root.destroy()
        except Exception:
            pass

    def run(self):
        self.start_network_thread()
        self.root.after(100, self.update_ui_loop)
        self.root.mainloop()


def run_demo_mode(initial_layout: int = 1):
    hud = F1HudOverlay(port=20777, initial_layout=initial_layout, record_csv=False)

    def _demo_loop():
        time.sleep(0.5)
        states = [
            ("reta", 350, 335, 8, 0.0, 1.0),
            ("preparo", 45, 340, 8, 0.0, 0.8),
            ("freia", 0, 315, 4, 1.0, 0.0),
            ("apice", 0, 74, 2, 0.1, 0.2),
            ("acelera", 0, 140, 3, 0.0, 0.85),
        ]
        while hud.running:
            for s, dist, spd, gr, brk, thr in states:
                if not hud.running:
                    break
                hud.current_state = s
                hud.dist_to_brake = dist
                hud.speed = spd
                hud.gear = gr
                hud.brake = brk
                hud.throttle = thr
                dur = 1.3 if s in ["freia", "preparo"] else 1.8
                time.sleep(dur)

    threading.Thread(target=_demo_loop, daemon=True).start()
    hud.root.after(100, hud.update_ui_loop)
    hud.root.mainloop()


def main():
    parser = argparse.ArgumentParser(description="HUD Copiloto F1 (3 Layouts + Systray)")
    parser.add_argument("--layout", type=int, default=1, choices=[1, 2, 3], help="Layout inicial (1, 2 ou 3)")
    parser.add_argument("--port", type=int, default=20777, help="Porta UDP (padrão: 20777)")
    parser.add_argument("--host", default="127.0.0.1", help="IP UDP (padrão: 127.0.0.1)")
    parser.add_argument("--no-record", action="store_true", help="Desativa a gravação automática de CSV")
    parser.add_argument("--demo", action="store_true", help="Executa o modo de demonstração/teste")
    args = parser.parse_args()

    if args.demo:
        run_demo_mode(initial_layout=args.layout)
    else:
        hud = F1HudOverlay(host=args.host, port=args.port, initial_layout=args.layout, record_csv=not args.no_record)
        hud.run()


if __name__ == "__main__":
    main()
