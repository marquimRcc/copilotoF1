"""HUD Compacto em Tempo Real (450x230) com 3 Layouts, Temas de Cores e Otimização Win32."""

import argparse
import os
import sys
import time

# Garante localização correta dos scripts Tcl/Tk no Windows
if sys.platform == "win32":
    _tcl_dir = os.path.join(sys.base_prefix, "tcl", "tcl8.6")
    _tk_dir = os.path.join(sys.base_prefix, "tcl", "tk8.6")
    if os.path.exists(_tcl_dir) and "TCL_LIBRARY" not in os.environ:
        os.environ["TCL_LIBRARY"] = _tcl_dir
    if os.path.exists(_tk_dir) and "TK_LIBRARY" not in os.environ:
        os.environ["TK_LIBRARY"] = _tk_dir

import tkinter as tk
from typing import Dict, Optional

from core.settings import SettingsManager
from core.state import THEMES, CornerStateMachine, TelemetryState
from core.udp_listener import F1UdpListener
from core.csv_recorder import AsyncLapRecorder
from hud.systray import SystrayController
from hud.win32_window import Win32WindowManager
from packets.session import TRACK_NAMES
from tracks.circuits import CIRCUITS, CornerZone, get_circuit_by_track_id


class F1HudOverlay:
    """Interface gráfica HUD de telemetria em tempo real com alta performance e dirty-checking."""

    def __init__(
        self,
        host: str = "127.0.0.1",
        port: int = 20777,
        initial_layout: Optional[int] = None,
        initial_theme: Optional[str] = None,
        record_csv: bool = True,
    ):
        self.host = host
        self.port = port
        self.record_csv = record_csv

        # Gerenciador de configurações persistentes
        self.settings_mgr = SettingsManager()
        cfg = self.settings_mgr.settings

        self.active_layout: int = initial_layout if initial_layout in (1, 2, 3) else cfg.active_layout
        self.active_theme: str = initial_theme if initial_theme in THEMES else cfg.active_theme
        self.click_through_locked: bool = cfg.locked_click_through

        # Estado central thread-safe
        self.state = TelemetryState(initial_layout=self.active_layout, initial_theme=self.active_theme)
        if cfg.selected_track_id != -1:
            self.state.set_manual_track(cfg.selected_track_id)

        # Gravador assíncrono e receptor UDP
        self.recorder: Optional[AsyncLapRecorder] = None
        if self.record_csv:
            self.recorder = AsyncLapRecorder(output_dir="data", state=self.state)

        self.udp_listener: Optional[F1UdpListener] = None
        if self.port > 0:
            self.udp_listener = F1UdpListener(
                host=self.host,
                port=self.port,
                state=self.state,
                recorder=self.recorder,
                record_csv=self.record_csv,
            )

        self.running: bool = True
        self.win32_mgr: Optional[Win32WindowManager] = None
        self.systray: Optional[SystrayController] = None
        self._last_rendered: Dict = {}
        self._drag_start_x = 0
        self._drag_start_y = 0

        # Interface Tkinter
        self.root = tk.Tk()
        self.setup_ui(cfg.window_x, cfg.window_y)
        self.setup_context_menu()
        self.set_theme(self.active_theme)
        self.setup_systray()

    # --- Propriedades de compatibilidade para testes unitários ---
    @property
    def lap_distance(self) -> float:
        return self.state.lap_distance

    @lap_distance.setter
    def lap_distance(self, value: float):
        self.state.lap_distance = value

    @property
    def speed(self) -> int:
        return self.state.speed

    @speed.setter
    def speed(self, value: int):
        self.state.speed = value

    @property
    def track_id(self) -> int:
        return self.state.track_id

    @track_id.setter
    def track_id(self, value: int):
        self.state.track_id = value

    @property
    def track_name(self) -> str:
        return self.state.track_name

    @track_name.setter
    def track_name(self, value: str):
        self.state.track_name = value

    @property
    def circuit(self):
        return self.state.circuit

    @circuit.setter
    def circuit(self, value):
        self.state.circuit = value

    @property
    def manual_track_override(self) -> bool:
        return self.state.manual_track_override

    @manual_track_override.setter
    def manual_track_override(self, value: bool):
        self.state.manual_track_override = value

    @property
    def current_state(self) -> str:
        return self.state.current_state

    @current_state.setter
    def current_state(self, value: str):
        self.state.current_state = value

    @property
    def dist_to_brake(self) -> float:
        return self.state.dist_to_brake

    @dist_to_brake.setter
    def dist_to_brake(self, value: float):
        self.state.dist_to_brake = value

    @property
    def next_corner(self):
        return self.state.next_corner

    @next_corner.setter
    def next_corner(self, value):
        self.state.next_corner = value

    def _update_corner_logic(self):
        """Atualiza a máquina de estados (compatibilidade e testes)."""
        # Trava de Volta de Lançamento / Aquecimento (Out-Lap / Grid / Garagem)
        if (
            self.state.lap_distance < 0.0
            or self.state.driver_status in (0, 3)
            or (self.state.lap_time_ms == 0 and self.state.lap_distance < 100.0)
        ):
            c0 = self.state.circuit.corners[0] if (self.state.circuit and self.state.circuit.corners) else None
            d = abs(self.state.lap_distance) if self.state.lap_distance < 0.0 else max(0.0, 0.0 - self.state.lap_distance)
            self.state.current_state = "lancamento"
            self.state.next_corner = c0
            self.state.dist_to_brake = d
            self.state.dist_to_apex = d + (c0.apex_distance if c0 else 100.0)
            return

        # Se o carro está em movimento (speed > 0), aplica a cinemática modular adaptativa
        if self.state.speed > 0:
            st, corner, d_brake, d_apex = CornerStateMachine.update(
                self.state.lap_distance, self.state.speed, self.state.circuit, self.state.lap_time_ms, self.state.driver_status
            )
            self.state.current_state = st
            self.state.next_corner = corner
            self.state.dist_to_brake = d_brake
            self.state.dist_to_apex = d_apex
            return

        # Fallback estático para testes unitários com speed == 0
        if not self.state.circuit or not self.state.circuit.corners:
            self.state.current_state = "reta"
            return

        dist = self.state.lap_distance
        target_corner = None
        closest_dist = 99999.0

        for corner in self.state.circuit.corners:
            if (corner.start_distance - 65.0) <= dist <= corner.end_distance:
                target_corner = corner
                break
            if corner.start_distance > dist:
                d = corner.start_distance - dist
                if d < closest_dist:
                    closest_dist = d
                    target_corner = corner

        if not target_corner:
            target_corner = self.state.circuit.corners[0]
            closest_dist = (self.state.circuit.length - dist) + target_corner.start_distance

        self.state.next_corner = target_corner

        if (target_corner.start_distance - 60.0) <= dist < target_corner.start_distance:
            self.state.current_state = "preparo"
            self.state.dist_to_brake = target_corner.start_distance - dist
        elif target_corner.start_distance <= dist < (target_corner.start_distance + 45.0):
            self.state.current_state = "freia"
            self.state.dist_to_brake = 0.0
        elif (target_corner.apex_distance - 30.0) <= dist <= (target_corner.apex_distance + 35.0):
            self.state.current_state = "apice"
            self.state.dist_to_brake = 0.0
        elif (target_corner.end_distance - 40.0) <= dist <= target_corner.end_distance:
            self.state.current_state = "acelera"
            self.state.dist_to_brake = 0.0
        else:
            self.state.current_state = "reta"
            if target_corner.start_distance > dist:
                self.state.dist_to_brake = target_corner.start_distance - dist
            else:
                self.state.dist_to_brake = (self.state.circuit.length - dist) + target_corner.start_distance

    def setup_ui(self, win_x: int, win_y: int):
        """Inicializa a janela Tkinter compacta sem moldura e topmost."""
        self.root.title("Copiloto F1 - HUD")
        self.root.geometry(f"450x230+{win_x}+{win_y}")
        self.root.resizable(False, False)
        self.root.overrideredirect(True)
        self.root.attributes("-topmost", True)
        self.root.attributes("-alpha", 0.94)

        theme = THEMES[self.active_theme]
        self.root.configure(bg=theme["bg"])

        # Ícone oficial McLaren MP4/4
        assets_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "assets"))
        icon_png = os.path.join(assets_dir, "icon.png")
        icon_ico = os.path.join(assets_dir, "icon.ico")
        if os.path.exists(icon_png):
            try:
                self.icon_photo = tk.PhotoImage(file=icon_png)
                self.root.iconphoto(False, self.icon_photo)
            except Exception:
                pass
        if os.path.exists(icon_ico) and sys.platform.startswith("win"):
            try:
                self.root.iconbitmap(icon_ico)
            except Exception:
                pass

        # Container Principal
        self.container = tk.Frame(self.root, bg=theme["bg"], highlightbackground=theme["accent"], highlightthickness=1)
        self.container.pack(fill=tk.BOTH, expand=True)

        self._build_layout_1()
        self._build_layout_2()
        self._build_layout_3()
        self.set_layout(self.active_layout)

        # Eventos de teclado e arraste com o mouse
        self.root.bind("<Key-1>", lambda e: self.set_layout(1))
        self.root.bind("<Key-2>", lambda e: self.set_layout(2))
        self.root.bind("<Key-3>", lambda e: self.set_layout(3))
        self.root.bind("<Escape>", lambda e: self.on_close())
        self.root.bind("<q>", lambda e: self.on_close())
        self.root.protocol("WM_DELETE_WINDOW", self.on_close)

        # Arraste de janela
        self.container.bind("<Button-1>", self._start_drag)
        self.container.bind("<B1-Motion>", self._do_drag)
        self.container.bind("<ButtonRelease-1>", self._on_drag_release)

        # Integração Win32 API
        self.win32_mgr = Win32WindowManager(self.root)
        self.win32_mgr.apply_overlay_styles()
        if self.click_through_locked:
            self.win32_mgr.set_click_through(True)

    def _start_drag(self, event):
        if not self.click_through_locked:
            self._drag_start_x = event.x
            self._drag_start_y = event.y

    def _do_drag(self, event):
        if not self.click_through_locked:
            x = self.root.winfo_x() + (event.x - self._drag_start_x)
            y = self.root.winfo_y() + (event.y - self._drag_start_y)
            self.root.geometry(f"+{x}+{y}")

    def _on_drag_release(self, event):
        if not self.click_through_locked:
            self.settings_mgr.update(
                window_x=self.root.winfo_x(),
                window_y=self.root.winfo_y(),
            )

    # -------------------------------------------------------------
    # LAYOUT 1: CARDS COMPACTOS
    # -------------------------------------------------------------
    def _build_layout_1(self):
        t = THEMES[self.active_theme]
        self.f1 = tk.Frame(self.container, bg=t["reta"]["bg"], padx=16, pady=12)

        self.f1_top = tk.Frame(self.f1, bg=t["reta"]["bg"])
        self.f1_top.pack(fill=tk.X)
        self.l1_lbl_track = tk.Label(self.f1_top, text="MONZA • AGUARDANDO", font=("Helvetica", 10, "bold"), fg=t["reta"]["top"], bg=t["reta"]["bg"])
        self.l1_lbl_track.pack(side=tk.LEFT)
        self.l1_lbl_dist = tk.Label(self.f1_top, text="--", font=("Helvetica", 10, "bold"), fg=t["reta"]["top"], bg=t["reta"]["bg"])
        self.l1_lbl_dist.pack(side=tk.RIGHT)

        self.f1_center = tk.Frame(self.f1, bg=t["reta"]["bg"])
        self.f1_center.pack(fill=tk.BOTH, expand=True)
        self.l1_lbl_main = tk.Label(self.f1_center, text="RETA", font=("Helvetica", 36, "bold"), fg=t["reta"]["text"], bg=t["reta"]["bg"])
        self.l1_lbl_main.pack(expand=True, pady=(8, 0))
        self.l1_lbl_sub = tk.Label(self.f1_center, text="VELOCIDADE MÁXIMA", font=("Helvetica", 11, "bold"), fg=t["reta"]["sub"], bg=t["reta"]["bg"])
        self.l1_lbl_sub.pack(pady=(0, 8))

        self.f1_bottom = tk.Frame(self.f1, bg=t["reta"]["bg"])
        self.f1_bottom.pack(fill=tk.X)
        self.l1_lbl_speed = tk.Label(self.f1_bottom, text="0 km/h", font=("Courier", 10, "bold"), fg=t["reta"]["top"], bg=t["reta"]["bg"])
        self.l1_lbl_speed.pack(side=tk.LEFT)
        self.l1_lbl_gear = tk.Label(self.f1_bottom, text="MARCHA: N", font=("Courier", 10, "bold"), fg=t["reta"]["top"], bg=t["reta"]["bg"])
        self.l1_lbl_gear.pack(side=tk.RIGHT)

    # -------------------------------------------------------------
    # LAYOUT 2: BARRA PROGRESSIVA E LEDS
    # -------------------------------------------------------------
    def _build_layout_2(self):
        t = THEMES[self.active_theme]
        self.f2 = tk.Frame(self.container, bg=t["bg"], padx=14, pady=10)

        # Barra de 8 LEDs superiores
        self.f2_leds_frame = tk.Frame(self.f2, bg=t["bg"])
        self.f2_leds_frame.pack(fill=tk.X, pady=(0, 6))
        self.f2_leds = []
        for _ in range(8):
            canvas = tk.Canvas(self.f2_leds_frame, width=44, height=8, bg=t["track_bg"], highlightthickness=0)
            canvas.pack(side=tk.LEFT, padx=3, expand=True, fill=tk.X)
            self.f2_leds.append(canvas)

        self.f2_top = tk.Frame(self.f2, bg=t["bg"])
        self.f2_top.pack(fill=tk.X)
        self.l2_lbl_corner = tk.Label(self.f2_top, text="C1: VARIANTE RETTIFILO", font=("Helvetica", 10, "bold"), fg=t["text"], bg=t["bg"])
        self.l2_lbl_corner.pack(side=tk.LEFT)
        self.l2_lbl_dist = tk.Label(self.f2_top, text="120m", font=("Courier", 10, "bold"), fg=t["muted"], bg=t["bg"])
        self.l2_lbl_dist.pack(side=tk.RIGHT)

        self.f2_center = tk.Frame(self.f2, bg=t["bg"])
        self.f2_center.pack(fill=tk.BOTH, expand=True, pady=4)
        self.l2_lbl_action = tk.Label(self.f2_center, text="ACELERAR", font=("Helvetica", 24, "bold"), fg=t["text"], bg=t["bg"])
        self.l2_lbl_action.pack(pady=(2, 2))

        # Canvas da barra horizontal com retângulo persistente (coords diffing)
        self.l2_progress_canvas = tk.Canvas(self.f2_center, height=10, bg=t["track_bg"], highlightthickness=0)
        self.l2_progress_canvas.pack(fill=tk.X, padx=10, pady=2)
        self.l2_bar_rect = self.l2_progress_canvas.create_rectangle(0, 0, 0, 10, fill=t["accent"], width=0)

        # Rodapé
        self.f2_bottom = tk.Frame(self.f2, bg=t["panel_alt"], padx=8, pady=4)
        self.f2_bottom.pack(fill=tk.X)
        self.l2_lbl_gear_val = tk.Label(self.f2_bottom, text="MARCHA: 8", font=("Helvetica", 9, "bold"), fg=t["text"], bg=t["panel_alt"])
        self.l2_lbl_gear_val.pack(side=tk.LEFT, expand=True)
        self.l2_lbl_apex_target = tk.Label(self.f2_bottom, text="ALVO: 74 km/h", font=("Helvetica", 9, "bold"), fg=t["accent"], bg=t["panel_alt"])
        self.l2_lbl_apex_target.pack(side=tk.LEFT, expand=True)
        self.l2_lbl_speed_val = tk.Label(self.f2_bottom, text="334 km/h", font=("Helvetica", 9, "bold"), fg=t["text"], bg=t["panel_alt"])
        self.l2_lbl_speed_val.pack(side=tk.RIGHT, expand=True)

    # -------------------------------------------------------------
    # LAYOUT 3: COCKPIT MINIMALISTA + FEEDBACK PÓS-VOLTA
    # -------------------------------------------------------------
    def _build_layout_3(self):
        t = THEMES[self.active_theme]
        self.f3 = tk.Frame(self.container, bg=t["bg"], padx=14, pady=10)

        self.f3_top = tk.Frame(self.f3, bg=t["bg"])
        self.f3_top.pack(fill=tk.X, pady=(0, 4))
        self.l3_lbl_track = tk.Label(self.f3_top, text="MONZA • CURVA 1", font=("Helvetica", 10, "bold"), fg=t["text"], bg=t["bg"])
        self.l3_lbl_track.pack(side=tk.LEFT)
        self.l3_badge_status = tk.Label(self.f3_top, text="RETA", font=("Helvetica", 8, "bold"), fg=t["muted"], bg=t["track_bg"], padx=6, pady=1)
        self.l3_badge_status.pack(side=tk.RIGHT)

        self.f3_center = tk.Frame(self.f3, bg=t["bg"])
        self.f3_center.pack(fill=tk.BOTH, expand=True, pady=2)

        # Card de Marcha Gigante
        self.f3_gear_box = tk.Frame(self.f3_center, bg=t["panel"], padx=14, pady=4, relief=tk.RIDGE, bd=1)
        self.f3_gear_box.pack(side=tk.LEFT, fill=tk.Y, padx=(0, 10))
        self.l3_lbl_gear_title = tk.Label(self.f3_gear_box, text="ENGATE", font=("Helvetica", 8), fg=t["dim"], bg=t["panel"])
        self.l3_lbl_gear_title.pack()
        self.l3_lbl_gear_big = tk.Label(self.f3_gear_box, text="8", font=("Helvetica", 32, "bold"), fg=t["accent"], bg=t["panel"])
        self.l3_lbl_gear_big.pack()

        # Instruções e Dicas Pós-Volta
        self.f3_info_box = tk.Frame(self.f3_center, bg=t["bg"])
        self.f3_info_box.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        self.l3_lbl_action = tk.Label(self.f3_info_box, text="100% ACELERADOR", font=("Helvetica", 16, "bold"), fg=t["text"], bg=t["bg"], anchor="w")
        self.l3_lbl_action.pack(fill=tk.X, pady=(4, 2))
        self.l3_lbl_tip = tk.Label(self.f3_info_box, text="Aguardando 1ª volta...", font=("Helvetica", 9), fg=t["muted"], bg=t["bg"], anchor="w")
        self.l3_lbl_tip.pack(fill=tk.X)

        # Pedais com Canvas otimizados
        self.f3_bottom = tk.Frame(self.f3, bg=t["bg"])
        self.f3_bottom.pack(fill=tk.X, pady=(4, 0))

        # Freio
        self.f3_brake_frame = tk.Frame(self.f3_bottom, bg=t["bg"])
        self.f3_brake_frame.pack(fill=tk.X, pady=1)
        self.l3_lbl_brake_title = tk.Label(self.f3_brake_frame, text="FREIO", font=("Courier", 8, "bold"), fg="#ef4444", bg=t["bg"], width=7, anchor="w")
        self.l3_lbl_brake_title.pack(side=tk.LEFT)
        self.l3_canvas_brake = tk.Canvas(self.f3_brake_frame, height=8, bg=t["track_bg"], highlightthickness=0)
        self.l3_canvas_brake.pack(side=tk.LEFT, fill=tk.X, expand=True)
        self.l3_brake_rect = self.l3_canvas_brake.create_rectangle(0, 0, 0, 8, fill="#ef4444", width=0)

        # Acelerador
        self.f3_throttle_frame = tk.Frame(self.f3_bottom, bg=t["bg"])
        self.f3_throttle_frame.pack(fill=tk.X, pady=1)
        self.l3_lbl_throttle_title = tk.Label(self.f3_throttle_frame, text="ACEL.", font=("Courier", 8, "bold"), fg="#22c55e", bg=t["bg"], width=7, anchor="w")
        self.l3_lbl_throttle_title.pack(side=tk.LEFT)
        self.l3_canvas_throttle = tk.Canvas(self.f3_throttle_frame, height=8, bg=t["track_bg"], highlightthickness=0)
        self.l3_canvas_throttle.pack(side=tk.LEFT, fill=tk.X, expand=True)
        self.l3_throttle_rect = self.l3_canvas_throttle.create_rectangle(0, 0, 0, 8, fill="#22c55e", width=0)

    def set_layout(self, layout_id: int):
        """Alterna visibilidade entre os layouts 1, 2 e 3."""
        if layout_id not in (1, 2, 3):
            return
        self.active_layout = layout_id
        self.state.set_layout(layout_id)
        self.settings_mgr.update(active_layout=layout_id)

        self.f1.pack_forget()
        self.f2.pack_forget()
        self.f3.pack_forget()

        if layout_id == 1:
            self.f1.pack(fill=tk.BOTH, expand=True)
        elif layout_id == 2:
            self.f2.pack(fill=tk.BOTH, expand=True)
        elif layout_id == 3:
            self.f3.pack(fill=tk.BOTH, expand=True)

        self._last_rendered.clear()

    def set_theme(self, theme_id: str):
        """Aplica tema de cores ao HUD."""
        if theme_id not in THEMES:
            return
        self.active_theme = theme_id
        self.state.set_theme(theme_id)
        self.settings_mgr.update(active_theme=theme_id)
        t = THEMES[theme_id]

        self.container.configure(bg=t["bg"], highlightbackground=t["accent"])

        # Layout 2
        self.f2.configure(bg=t["bg"])
        self.f2_leds_frame.configure(bg=t["bg"])
        for c in self.f2_leds:
            c.configure(bg=t["track_bg"])
        self.f2_top.configure(bg=t["bg"])
        self.l2_lbl_corner.configure(fg=t["text"], bg=t["bg"])
        self.l2_lbl_dist.configure(fg=t["muted"], bg=t["bg"])
        self.f2_center.configure(bg=t["bg"])
        self.l2_lbl_action.configure(bg=t["bg"])
        self.l2_progress_canvas.configure(bg=t["track_bg"])
        self.f2_bottom.configure(bg=t["panel_alt"])
        self.l2_lbl_gear_val.configure(fg=t["text"], bg=t["panel_alt"])
        self.l2_lbl_apex_target.configure(fg=t["accent"], bg=t["panel_alt"])
        self.l2_lbl_speed_val.configure(fg=t["text"], bg=t["panel_alt"])

        # Layout 3
        self.f3.configure(bg=t["bg"])
        self.f3_top.configure(bg=t["bg"])
        self.l3_lbl_track.configure(fg=t["text"], bg=t["bg"])
        self.f3_center.configure(bg=t["bg"])
        self.f3_gear_box.configure(bg=t["panel"])
        self.l3_lbl_gear_title.configure(fg=t["dim"], bg=t["panel"])
        self.l3_lbl_gear_big.configure(fg=t["accent"], bg=t["panel"])
        self.f3_info_box.configure(bg=t["bg"])
        self.l3_lbl_action.configure(bg=t["bg"])
        self.l3_lbl_tip.configure(fg=t["muted"], bg=t["bg"])
        self.f3_bottom.configure(bg=t["bg"])
        self.f3_brake_frame.configure(bg=t["bg"])
        self.l3_lbl_brake_title.configure(bg=t["bg"])
        self.l3_canvas_brake.configure(bg=t["track_bg"])
        self.f3_throttle_frame.configure(bg=t["bg"])
        self.l3_lbl_throttle_title.configure(bg=t["bg"])
        self.l3_canvas_throttle.configure(bg=t["track_bg"])

        self._last_rendered.clear()

    def set_track(self, track_id: int, manual: bool = True):
        """Seleciona pista manual ou restaura automático."""
        if track_id == -1:
            self.state.set_auto_track_detection()
            self.settings_mgr.update(selected_track_id=-1)
        else:
            self.state.set_manual_track(track_id)
            self.settings_mgr.update(selected_track_id=track_id)
        self._update_corner_logic()
        self._last_rendered.clear()

    def toggle_click_through(self, locked: bool):
        """Ativa/desativa modo Click-Through (ignora cliques no jogo)."""
        self.click_through_locked = locked
        self.state.set_click_through(locked)
        self.settings_mgr.update(locked_click_through=locked)
        if self.win32_mgr:
            self.win32_mgr.set_click_through(locked)

    def setup_context_menu(self):
        """Menu de contexto acionado pelo botão direito na janela."""
        self.context_menu = tk.Menu(self.root, tearoff=0)

        # Submenu Layouts
        layout_menu = tk.Menu(self.context_menu, tearoff=0)
        layout_menu.add_command(label="Layout 1 (Cards)", command=lambda: self.set_layout(1))
        layout_menu.add_command(label="Layout 2 (Barras)", command=lambda: self.set_layout(2))
        layout_menu.add_command(label="Layout 3 (Minimalista)", command=lambda: self.set_layout(3))
        self.context_menu.add_cascade(label="Layouts", menu=layout_menu)

        # Submenu Temas
        theme_menu = tk.Menu(self.context_menu, tearoff=0)
        for k, v in THEMES.items():
            theme_menu.add_command(label=v["label"], command=lambda key=k: self.set_theme(key))
        self.context_menu.add_cascade(label="Temas de Cores", menu=theme_menu)

        self.context_menu.add_separator()
        self.context_menu.add_command(
            label="🔒 Travar Posição (Click-Through)",
            command=lambda: self.toggle_click_through(not self.click_through_locked),
        )
        self.context_menu.add_separator()
        self.context_menu.add_command(label="Fechar HUD", command=self.on_close)

        self.container.bind("<Button-3>", self._show_context_menu)

    def _show_context_menu(self, event):
        if not self.click_through_locked:
            self.context_menu.post(event.x_root, event.y_root)

    def setup_systray(self):
        """Inicializa ícone de bandeja isolado em thread."""
        assets_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "assets"))
        icon_path = os.path.join(assets_dir, "icon.png")

        self.systray = SystrayController(
            icon_path=icon_path,
            on_change_layout=self.set_layout,
            on_change_theme=self.set_theme,
            on_change_track=self.set_track,
            on_toggle_click_through=self.toggle_click_through,
            on_quit=self.on_close,
            initial_layout=self.active_layout,
            initial_theme=self.active_theme,
            initial_click_through=self.click_through_locked,
        )
        self.systray.start()

    # -------------------------------------------------------------
    # LOOP PRINCIPAL DE RENDERIZAÇÃO (DIRTY CHECKING / DIFFING)
    # -------------------------------------------------------------
    def update_ui_loop(self):
        """Loop a ~60 FPS com dirty-checking para evitar recriação e recalculo de widgets."""
        if not self.running:
            return

        snap = self.state.get_snapshot()
        state = snap["current_state"]
        speed = snap["speed"]
        gear = snap["gear"]
        dist_to_brake = snap["dist_to_brake"]
        next_corner = snap["next_corner"]
        theme = THEMES[self.active_theme]

        gear_str = "R" if gear == -1 else ("N" if gear == 0 else str(gear))
        corner_num = f"C{next_corner.number}" if next_corner else "RETA"
        corner_name = next_corner.name if next_corner else "RETA DOS BOXES"
        dist_str = f"{dist_to_brake:.0f}m" if dist_to_brake < 800 else "--"

        # Dirty-check chave para Layout 1
        if self.active_layout == 1:
            color_cfg = theme.get(state, theme["reta"])
            l1_key = (state, speed, gear, dist_str, corner_num, self.active_theme)
            if self._last_rendered.get("l1") != l1_key:
                self._last_rendered["l1"] = l1_key
                self.f1.configure(bg=color_cfg["bg"])
                self.f1_top.configure(bg=color_cfg["bg"])
                self.f1_center.configure(bg=color_cfg["bg"])
                self.f1_bottom.configure(bg=color_cfg["bg"])

                self.l1_lbl_track.config(text=f"{snap['track_name'].upper()} • {corner_num}", fg=color_cfg["top"], bg=color_cfg["bg"])
                self.l1_lbl_dist.config(text=dist_str, fg=color_cfg["top"], bg=color_cfg["bg"])
                self.l1_lbl_speed.config(text=f"{speed} km/h", fg=color_cfg["top"], bg=color_cfg["bg"])
                self.l1_lbl_gear.config(text=f"MARCHA: {gear_str}", fg=color_cfg["top"], bg=color_cfg["bg"])

                state_labels = {
                    "reta": ("RETA", "VELOCIDADE MÁXIMA"),
                    "preparo": ("PREPARAÇÃO", f"FREAR EM {dist_str}"),
                    "freia": ("FREIA AGORA!", f"ALVO: {gear_str}ª MARCHA"),
                    "freia_pulse": ("FREIA AGORA!", f"ALVO: {gear_str}ª MARCHA"),
                    "apice": ("ÁPICE / CONTORNO", "MANTENHA A TRAJETÓRIA"),
                    "acelera": ("ACELERAÇÃO!", "TRACIONAR NA SAÍDA"),
                    "lancamento": ("VOLTA DE LANÇAMENTO", f"LARGADA EM {dist_str}"),
                }
                main_txt, sub_txt = state_labels.get(state, ("RETA", ""))
                self.l1_lbl_main.config(text=main_txt, fg=color_cfg["text"], bg=color_cfg["bg"])
                self.l1_lbl_sub.config(text=sub_txt, fg=color_cfg["sub"], bg=color_cfg["bg"])

        # Dirty-check chave para Layout 2
        elif self.active_layout == 2:
            l2_key = (state, speed, gear, dist_str, corner_num, self.active_theme)
            if self._last_rendered.get("l2") != l2_key:
                self._last_rendered["l2"] = l2_key
                self.l2_lbl_corner.config(text=f"{corner_num}: {corner_name}".upper())
                self.l2_lbl_dist.config(text=dist_str if state in ("reta", "preparo") else "PONTO ZERO")
                self.l2_lbl_gear_val.config(text=f"MARCHA: {gear_str}")
                self.l2_lbl_speed_val.config(text=f"{speed} km/h")

                # LEDs superiores
                off = theme["track_bg"]
                led_colors = {
                    "reta": [off] * 8,
                    "preparo": ["#f59e0b"] * 5 + [off] * 3,
                    "freia": ["#ef4444"] * 8,
                    "freia_pulse": ["#ff2800"] * 8,
                    "apice": ["#38bdf8"] * 4 + [off] * 4,
                    "acelera": ["#22c55e"] * 8,
                    "lancamento": ["#f59e0b"] * 4 + [off] * 4,
                }
                colors = led_colors.get(state, led_colors["reta"])
                for i, col in enumerate(colors):
                    self.f2_leds[i].configure(bg=col)

                if state == "lancamento":
                    self.l2_lbl_corner.config(text="VOLTA DE LANÇAMENTO")
                    self.l2_lbl_dist.config(text=dist_str)
                    self.l2_lbl_action.config(text=f"LARGADA EM {dist_str}", fg="#f59e0b")
                    bar_color = "#f59e0b"
                    pct = max(0.0, min(1.0, 1.0 - (dist_to_brake / 500.0)))
                elif state == "reta":
                    self.l2_lbl_action.config(text="ACELERAR", fg=theme["muted"])
                    bar_color = theme["accent"]
                    pct = 0.0
                elif state == "preparo":
                    self.l2_lbl_action.config(text="PREPARAR", fg="#f59e0b")
                    bar_color = "#f59e0b"
                    pct = max(0.0, min(1.0, 1.0 - (dist_to_brake / 75.0)))
                elif "freia" in state:
                    self.l2_lbl_action.config(text="FREAR", fg="#ef4444")
                    bar_color = "#ef4444"
                    pct = 1.0
                elif state == "apice":
                    self.l2_lbl_action.config(text="CONTORNO", fg="#38bdf8")
                    bar_color = "#38bdf8"
                    pct = 0.5
                else:
                    self.l2_lbl_action.config(text="RETOMADA", fg="#22c55e")
                    bar_color = "#22c55e"
                    pct = 1.0

                width_px = int(pct * 400)
                self.l2_progress_canvas.coords(self.l2_bar_rect, 0, 0, width_px, 10)
                self.l2_progress_canvas.itemconfig(self.l2_bar_rect, fill=bar_color)

        # Dirty-check chave para Layout 3
        elif self.active_layout == 3:
            throttle = snap["throttle"]
            brake = snap["brake"]
            feedback = snap["last_lap_feedback"]
            l3_key = (state, gear_str, corner_num, int(throttle * 50), int(brake * 50), feedback, self.active_theme)

            if self._last_rendered.get("l3") != l3_key:
                self._last_rendered["l3"] = l3_key
                self.l3_lbl_track.config(text=f"{snap['track_name'].upper()} • {corner_num}")
                self.l3_lbl_gear_big.config(text=gear_str)

                if state == "lancamento":
                    self.l3_badge_status.config(text="LANÇAMENTO", bg="#78350f", fg="#fef08a")
                    self.l3_lbl_action.config(text=f"LARGADA EM {dist_str}", fg="#f59e0b")
                    self.l3_lbl_tip.config(text="Prepare a saída da última curva para abrir a volta rápida")
                elif state == "reta":
                    self.l3_badge_status.config(text="RETA", bg=theme["track_bg"], fg=theme["muted"])
                    self.l3_lbl_action.config(text="100% ACELERADOR", fg=theme["text"])
                    self.l3_lbl_tip.config(text=f"Próxima freada em {dist_str}" if dist_to_brake < 800 else feedback)
                elif state == "preparo":
                    self.l3_badge_status.config(text="APROXIMAÇÃO", bg="#78350f", fg="#fef08a")
                    self.l3_lbl_action.config(text=f"PREPARAR FREADA ({dist_str})", fg="#f59e0b")
                    self.l3_lbl_tip.config(text=f"Reduzir para {gear_str}ª marcha no ápice")
                elif "freia" in state:
                    self.l3_badge_status.config(text="FRENAGEM", bg="#7f1d1d", fg="#fecaca")
                    self.l3_lbl_action.config(text="100% FREIO", fg="#ef4444")
                    self.l3_lbl_tip.config(text="Frenagem em linha reta, alivie no contorno")
                elif state == "apice":
                    self.l3_badge_status.config(text="ÁPICE", bg="#075985", fg="#bae6fd")
                    self.l3_lbl_action.config(text="SOLTAR FREIO / VIRAR", fg="#38bdf8")
                    self.l3_lbl_tip.config(text="Aponte a frente do carro para a zebra interna")
                else:
                    self.l3_badge_status.config(text="SAÍDA", bg="#14532d", fg="#bbf7d0")
                    self.l3_lbl_action.config(text="TRACIONAR PROGRESSIVO", fg="#22c55e")
                    self.l3_lbl_tip.config(text=feedback)

                # Atualiza coordenadas das barras de freio e acelerador sem delete("all")
                brake_px = int(max(0.0, min(1.0, brake)) * 340)
                throttle_px = int(max(0.0, min(1.0, throttle)) * 340)
                self.l3_canvas_brake.coords(self.l3_brake_rect, 0, 0, brake_px, 8)
                self.l3_canvas_throttle.coords(self.l3_throttle_rect, 0, 0, throttle_px, 8)

        # Reagenda para 16ms (~60 FPS)
        self.root.after(16, self.update_ui_loop)

    def _periodic_win32_topmost(self):
        """Garante que jogos em Borderless Windowed não cubram o HUD."""
        if self.running and self.win32_mgr:
            self.win32_mgr.force_topmost()
            self.root.after(2000, self._periodic_win32_topmost)

    def on_close(self):
        """Encerra a aplicação de forma graciosa e limpa."""
        self.running = False
        if self.udp_listener:
            self.udp_listener.stop()
        if self.recorder:
            self.recorder.stop()
        if self.systray:
            self.systray.stop()
        try:
            self.root.destroy()
        except Exception:
            pass

    def run(self):
        """Inicia o listener UDP, as threads auxiliares e o loop do Tkinter."""
        if self.udp_listener:
            self.udp_listener.start()
        self.root.after(16, self.update_ui_loop)
        self.root.after(2000, self._periodic_win32_topmost)
        self.root.mainloop()


def run_demo_mode(initial_layout: int = 1, initial_theme: str = "padrao"):
    """Modo demonstrativo para visualização de layouts e animações sem o jogo aberto."""
    hud = F1HudOverlay(port=0, initial_layout=initial_layout, initial_theme=initial_theme, record_csv=False)

    import threading
    def _demo_loop():
        time.sleep(0.5)
        dist = 0.0
        while hud.running:
            dist = (dist + 25.0) % 5793.0
            speed = 330
            gear = 8
            throttle = 1.0
            brake = 0.0

            if 420.0 <= dist <= 620.0:
                speed = 85
                gear = 2
                throttle = 0.0
                brake = 0.95
            elif 620.0 < dist <= 820.0:
                speed = 140
                gear = 3
                throttle = 0.75
                brake = 0.0

            hud.state.update_telemetry(speed, throttle, brake, 0.0, gear, 11500, 0)
            hud.state.update_lap_data(dist, dist, 1, 45000, 0, True)
            time.sleep(0.05)

    th = threading.Thread(target=_demo_loop, daemon=True)
    th.start()
    hud.run()


def main():
    parser = argparse.ArgumentParser(description="HUD Copiloto F1 (3 Layouts + Temas + Systray)")
    parser.add_argument("--layout", type=int, default=None, choices=[1, 2, 3], help="Layout inicial (1, 2 ou 3)")
    parser.add_argument("--theme", default=None, choices=list(THEMES.keys()), help="Tema de cores inicial")
    parser.add_argument("--port", type=int, default=20777, help="Porta UDP (padrão: 20777)")
    parser.add_argument("--host", default="127.0.0.1", help="IP UDP (padrão: 127.0.0.1)")
    parser.add_argument("--no-record", action="store_true", help="Desativa a gravação de CSV")
    parser.add_argument("--demo", action="store_true", help="Inicia em modo demonstração")
    args = parser.parse_args()

    if args.demo:
        run_demo_mode(initial_layout=args.layout or 1, initial_theme=args.theme or "padrao")
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
