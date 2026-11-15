"""Estado central thread-safe de telemetria e máquina de estados cinemática de curvas."""

import math
import os
import re
import threading
from typing import Dict, List, Optional
from tracks.circuits import CircuitInfo, CornerZone, get_circuit_by_track_id, register_auto_learned_circuit


# Cores e temas de interface
THEMES: Dict[str, Dict] = {
    "padrao": {
        "label": "F1 Padrão (Escuro)",
        "bg": "#0d0d0d",
        "panel": "#171717",
        "panel_alt": "#1c1c1c",
        "track_bg": "#262626",
        "text": "#ffffff",
        "muted": "#a3a3a3",
        "dim": "#737373",
        "accent": "#e10600",
        "reta": {"bg": "#0a0a0a", "text": "#a3a3a3", "sub": "#737373", "top": "#525252"},
        "preparo": {"bg": "#d97706", "text": "#000000", "sub": "#1c1917", "top": "#451a03"},
        "freia": {"bg": "#dc2626", "text": "#ffffff", "sub": "#fef2f2", "top": "#7f1d1d"},
        "freia_pulse": {"bg": "#ef4444", "text": "#ffffff", "sub": "#ffffff", "top": "#991b1b"},
        "apice": {"bg": "#0284c7", "text": "#ffffff", "sub": "#e0f2fe", "top": "#075985"},
        "acelera": {"bg": "#16a34a", "text": "#ffffff", "sub": "#f0fdf4", "top": "#14532d"},
        "lancamento": {"bg": "#78350f", "text": "#fef08a", "sub": "#fef9c3", "top": "#fef08a"},
    },
    "ferrari": {
        "label": "Scuderia Ferrari",
        "bg": "#180404",
        "panel": "#290808",
        "panel_alt": "#330a0a",
        "track_bg": "#450f0f",
        "text": "#fff5f5",
        "muted": "#fca5a5",
        "dim": "#f87171",
        "accent": "#ff2800",
        "reta": {"bg": "#180404", "text": "#fca5a5", "sub": "#f87171", "top": "#b91c1c"},
        "preparo": {"bg": "#facc15", "text": "#000000", "sub": "#422006", "top": "#713f12"},
        "freia": {"bg": "#dc2626", "text": "#ffffff", "sub": "#fef2f2", "top": "#7f1d1d"},
        "freia_pulse": {"bg": "#ff2800", "text": "#ffffff", "sub": "#ffffff", "top": "#991b1b"},
        "apice": {"bg": "#0284c7", "text": "#ffffff", "sub": "#e0f2fe", "top": "#075985"},
        "acelera": {"bg": "#16a34a", "text": "#ffffff", "sub": "#f0fdf4", "top": "#14532d"},
        "lancamento": {"bg": "#422006", "text": "#fef08a", "sub": "#fef9c3", "top": "#fef08a"},
    },
    "mercedes": {
        "label": "Mercedes-AMG Petronas",
        "bg": "#041414",
        "panel": "#092424",
        "panel_alt": "#0d3030",
        "track_bg": "#134242",
        "text": "#ecfeff",
        "muted": "#5eead4",
        "dim": "#2dd4bf",
        "accent": "#00d2be",
        "reta": {"bg": "#041414", "text": "#5eead4", "sub": "#2dd4bf", "top": "#0f766e"},
        "preparo": {"bg": "#d97706", "text": "#000000", "sub": "#1c1917", "top": "#451a03"},
        "freia": {"bg": "#dc2626", "text": "#ffffff", "sub": "#fef2f2", "top": "#7f1d1d"},
        "freia_pulse": {"bg": "#ef4444", "text": "#ffffff", "sub": "#ffffff", "top": "#991b1b"},
        "apice": {"bg": "#00a19c", "text": "#ffffff", "sub": "#ccfbf1", "top": "#115e59"},
        "acelera": {"bg": "#10b981", "text": "#ffffff", "sub": "#ecfdf5", "top": "#065f46"},
        "lancamento": {"bg": "#0f3838", "text": "#a7f3d0", "sub": "#ecfdf5", "top": "#a7f3d0"},
    },
    "redbull": {
        "label": "Red Bull Racing",
        "bg": "#060b1e",
        "panel": "#0d1638",
        "panel_alt": "#131f4d",
        "track_bg": "#1e2e6e",
        "text": "#f8fafc",
        "muted": "#93c5fd",
        "dim": "#60a5fa",
        "accent": "#fcd700",
        "reta": {"bg": "#060b1e", "text": "#93c5fd", "sub": "#60a5fa", "top": "#3b82f6"},
        "preparo": {"bg": "#eab308", "text": "#000000", "sub": "#422006", "top": "#713f12"},
        "freia": {"bg": "#e11d48", "text": "#ffffff", "sub": "#fff1f2", "top": "#881337"},
        "freia_pulse": {"bg": "#f43f5e", "text": "#ffffff", "sub": "#ffffff", "top": "#9f1239"},
        "apice": {"bg": "#0284c7", "text": "#ffffff", "sub": "#e0f2fe", "top": "#075985"},
        "acelera": {"bg": "#16a34a", "text": "#ffffff", "sub": "#f0fdf4", "top": "#14532d"},
        "lancamento": {"bg": "#422006", "text": "#fef08a", "sub": "#fef9c3", "top": "#fef08a"},
    },
    "mclaren": {
        "label": "McLaren Papaya",
        "bg": "#130903",
        "panel": "#241205",
        "panel_alt": "#2e1707",
        "track_bg": "#42210a",
        "text": "#fff7ed",
        "muted": "#fdba74",
        "dim": "#fb923c",
        "accent": "#ff8000",
        "reta": {"bg": "#130903", "text": "#fdba74", "sub": "#fb923c", "top": "#c2410c"},
        "preparo": {"bg": "#f59e0b", "text": "#000000", "sub": "#451a03", "top": "#78350f"},
        "freia": {"bg": "#dc2626", "text": "#ffffff", "sub": "#fef2f2", "top": "#7f1d1d"},
        "freia_pulse": {"bg": "#ef4444", "text": "#ffffff", "sub": "#ffffff", "top": "#991b1b"},
        "apice": {"bg": "#0284c7", "text": "#ffffff", "sub": "#e0f2fe", "top": "#075985"},
        "acelera": {"bg": "#16a34a", "text": "#ffffff", "sub": "#f0fdf4", "top": "#14532d"},
        "lancamento": {"bg": "#451a03", "text": "#fed7aa", "sub": "#ffedd5", "top": "#fed7aa"},
    },
    "astonmartin": {
        "label": "Aston Martin Racing",
        "bg": "#02120e",
        "panel": "#06241c",
        "panel_alt": "#092f25",
        "track_bg": "#0f4234",
        "text": "#f0fdf4",
        "muted": "#6ee7b7",
        "dim": "#34d399",
        "accent": "#00594f",
        "reta": {"bg": "#02120e", "text": "#6ee7b7", "sub": "#34d399", "top": "#047857"},
        "preparo": {"bg": "#eab308", "text": "#000000", "sub": "#422006", "top": "#713f12"},
        "freia": {"bg": "#dc2626", "text": "#ffffff", "sub": "#fef2f2", "top": "#7f1d1d"},
        "freia_pulse": {"bg": "#ef4444", "text": "#ffffff", "sub": "#ffffff", "top": "#991b1b"},
        "apice": {"bg": "#0284c7", "text": "#ffffff", "sub": "#e0f2fe", "top": "#075985"},
        "acelera": {"bg": "#10b981", "text": "#ffffff", "sub": "#ecfdf5", "top": "#065f46"},
        "lancamento": {"bg": "#062e26", "text": "#a7f3d0", "sub": "#ecfdf5", "top": "#a7f3d0"},
    },
}


class CornerStateMachine:
    """Máquina de estados cinemática de frenagem e contorno com aritmética modular."""

    # Desaceleração de F1 real com efeito solo e freios de carbono (~3.3G = 32.5 m/s²)
    DECEL_BRAKE_MS2 = 32.5
    # Janela de alerta amarelo / preparação antes do ponto de frenagem (140 metros de antecedência)
    PREPARATION_WINDOW_M = 140.0

    @classmethod
    def calculate_braking_distance(cls, current_speed_kmh: int, target_speed_kmh: int) -> float:
        """Calcula a distância ideal e antecipada de frenagem com margem segura."""
        if target_speed_kmh >= 285:
            return 0.0

        v1 = max(0.0, float(current_speed_kmh) / 3.6)
        v2 = max(0.0, float(target_speed_kmh) / 3.6)
        if v1 <= v2:
            return 20.0

        phys_dist = (v1**2 - v2**2) / (2.0 * cls.DECEL_BRAKE_MS2)
        reaction_margin = (v1 * 0.35) + 8.0
        total_dist = phys_dist + reaction_margin
        return max(20.0, min(total_dist, 250.0))

    @classmethod
    def estimate_apex_speed(cls, corner: CornerZone) -> int:
        """Estima velocidade de ápice baseada na marcha de referência."""
        gear = corner.gear_reference or 3
        gear_speeds = {1: 70, 2: 90, 3: 125, 4: 165, 5: 205, 6: 240, 7: 270, 8: 305}
        return gear_speeds.get(gear, 125)

    @classmethod
    def update(
        cls,
        lap_distance: float,
        speed_kmh: int,
        circuit: Optional[CircuitInfo],
        current_lap_time_ms: int = 1000,
        driver_status: int = 1,
    ) -> tuple[str, Optional[CornerZone], float, float]:
        """Calcula com precisão a máquina de estados de curva e ponto de frenagem."""
        if not circuit or not circuit.corners:
            return "reta", None, 999.0, 999.0

        track_len = max(1000.0, float(circuit.length))
        first_corner = circuit.corners[0]

        # 0. Trava de Volta de Lançamento / Grid Parado / Boxes
        # Só ativa se o cronômetro estiver zerado (current_lap_time_ms == 0)
        # Se o cronômetro já estiver rodando (> 0), a volta é ativa independente de driver_status
        is_out_lap = (
            current_lap_time_ms == 0
            and (
                lap_distance < 0.0
                or driver_status in (0, 3)
                or lap_distance > (track_len - 1600.0)
                or lap_distance < 15.0
            )
        )
        if is_out_lap:
            if lap_distance < 0.0:
                dist_to_start_line = abs(lap_distance)
            elif lap_distance > 500.0:
                dist_to_start_line = max(0.0, track_len - lap_distance)
            else:
                dist_to_start_line = max(0.0, -lap_distance)
            dist_to_apex = dist_to_start_line + first_corner.apex_distance
            return "lancamento", first_corner, dist_to_start_line, dist_to_apex

        norm_dist = lap_distance % track_len

        # 1. Verifica se o carro está dentro de alguma curva ativa (entre start e end)
        active_corner: Optional[CornerZone] = None
        for corner in circuit.corners:
            corner_len = (corner.end_distance - corner.start_distance) % track_len
            progress_in_corner = (norm_dist - corner.start_distance) % track_len
            if progress_in_corner <= corner_len:
                active_corner = corner
                break

        if active_corner:
            is_flat = (active_corner.gear_reference or 3) >= 8
            fwd_apex = (active_corner.apex_distance - norm_dist) % track_len
            is_before_apex = fwd_apex <= (track_len / 2)
            past_apex = (norm_dist - active_corner.apex_distance) % track_len

            if (is_before_apex and fwd_apex <= 25.0) or (not is_before_apex and past_apex <= 25.0):
                return "apice", active_corner, 0.0, 0.0

            if not is_before_apex and past_apex > 25.0:
                return "acelera", active_corner, 0.0, 0.0

            if is_flat:
                return "acelera", active_corner, 0.0, fwd_apex

            target_speed = cls.estimate_apex_speed(active_corner)
            effective_speed = max(speed_kmh, 270) if speed_kmh > 0 else target_speed
            brake_dist = cls.calculate_braking_distance(effective_speed, target_speed)
            dist_to_brake = max(0.0, fwd_apex - brake_dist)

            if fwd_apex <= (brake_dist + 3.0):
                return "freia", active_corner, 0.0, fwd_apex
            if dist_to_brake <= cls.PREPARATION_WINDOW_M:
                return "preparo", active_corner, dist_to_brake, fwd_apex
            return "reta", active_corner, dist_to_brake, fwd_apex

        closest_corner: Optional[CornerZone] = None
        min_forward_apex = float("inf")

        for corner in circuit.corners:
            fwd_apex = (corner.apex_distance - norm_dist) % track_len
            if fwd_apex < min_forward_apex:
                min_forward_apex = fwd_apex
                closest_corner = corner

        if not closest_corner:
            closest_corner = first_corner
            min_forward_apex = (first_corner.apex_distance - norm_dist) % track_len

        is_flat = (closest_corner.gear_reference or 3) >= 8
        if is_flat:
            return "reta", closest_corner, 999.0, min_forward_apex

        target_speed = cls.estimate_apex_speed(closest_corner)
        effective_speed = max(speed_kmh, 270) if speed_kmh > 0 else target_speed
        brake_dist = cls.calculate_braking_distance(effective_speed, target_speed)
        dist_to_brake = max(0.0, min_forward_apex - brake_dist)

        if min_forward_apex <= (brake_dist + 3.0):
            return "freia", closest_corner, 0.0, min_forward_apex

        if dist_to_brake <= cls.PREPARATION_WINDOW_M:
            return "preparo", closest_corner, dist_to_brake, min_forward_apex

        return "reta", closest_corner, dist_to_brake, min_forward_apex

class AutoCornerLearner:
    """Aprende automaticamente o traçado e zonas de frenagem na Volta 1 para pistas desconhecidas."""

    def __init__(self, track_id: int, track_name: str, track_length: int):
        self.track_id = track_id
        self.track_name = track_name
        self.track_length = track_length
        self.active_braking = False
        self.current_zone_start = 0.0
        self.current_zone_min_speed = 999
        self.current_zone_min_speed_dist = 0.0
        self.current_zone_min_gear = 8
        self.detected_corners: List[CornerZone] = []

    def feed_sample(self, lap_distance: float, speed: int, brake: float, throttle: float, gear: int):
        """Monitora telemetria para isolar zonas de frenagem e ápice."""
        if brake >= 0.25:
            if not self.active_braking:
                self.active_braking = True
                self.current_zone_start = lap_distance
                self.current_zone_min_speed = speed
                self.current_zone_min_speed_dist = lap_distance
                self.current_zone_min_gear = gear if gear > 0 else 3
            else:
                if speed < self.current_zone_min_speed:
                    self.current_zone_min_speed = speed
                    self.current_zone_min_speed_dist = lap_distance
                    if gear > 0:
                        self.current_zone_min_gear = gear

        elif self.active_braking and (throttle >= 0.60 or brake < 0.05):
            # Encerra zona de frenagem
            end_dist = lap_distance
            zone_len = end_dist - self.current_zone_start
            if zone_len >= 30.0:  # Descarta toques leves
                c_idx = len(self.detected_corners) + 1
                corner = CornerZone(
                    number=str(c_idx),
                    name=f"Curva {c_idx}",
                    start_distance=round(self.current_zone_start, 1),
                    apex_distance=round(self.current_zone_min_speed_dist, 1),
                    end_distance=round(end_dist + 50.0, 1),
                    gear_reference=self.current_zone_min_gear,
                )
                self.detected_corners.append(corner)
            self.active_braking = False

    def finalize(self) -> CircuitInfo:
        """Gera e registra o CircuitInfo com as curvas aprendidas."""
        circuit = CircuitInfo(
            track_id=self.track_id,
            name=self.track_name,
            length=self.track_length,
            corners=self.detected_corners,
            is_auto_learned=True,
        )
        register_auto_learned_circuit(circuit)
        return circuit


def find_best_recorded_lap_ms(track_id: int) -> Optional[int]:
    """Busca a volta mais rápida válida registrada para o circuito na pasta data/."""
    try:
        data_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "data"))
        if not os.path.exists(data_dir):
            return None

        track_slugs = {16: "interlagos", 11: "monza", 17: "austria", 1: "bahrain", 0: "melbourne"}
        slug = track_slugs.get(track_id, "").lower()
        if not slug:
            c = get_circuit_by_track_id(track_id)
            if c:
                slug = c.name.lower().split()[0]

        best_ms: Optional[int] = None
        for fname in os.listdir(data_dir):
            if fname.startswith("relatorio_") and (slug and slug in fname.lower()):
                fpath = os.path.join(data_dir, fname)
                try:
                    with open(fpath, "r", encoding="utf-8") as f:
                        content = f.read()
                        match = re.search(r"Tempo da sua volta:\s*(\d{2}):(\d{2})\.(\d{3})", content)
                        if match:
                            mins, secs, millis = int(match.group(1)), int(match.group(2)), int(match.group(3))
                            total_ms = (mins * 60000) + (secs * 1000) + millis
                            if best_ms is None or total_ms < best_ms:
                                best_ms = total_ms
                except Exception:
                    pass
        return best_ms
    except Exception:
        return None


class TelemetryState:
    """Estado thread-safe completo da aplicação consumido pela UI e threads de background."""

    def __init__(self, initial_layout: int = 1, initial_theme: str = "padrao"):
        self._lock = threading.Lock()

        # Telemetria do carro
        self.speed: int = 0
        self.throttle: float = 0.0
        self.brake: float = 0.0
        self.steer: float = 0.0
        self.gear: int = 0
        self.engine_rpm: int = 0
        self.drs: int = 0

        # Volta
        self.lap_distance: float = 0.0
        self.total_distance: float = 0.0
        self.current_lap_num: int = 0
        self.lap_time_ms: int = 0
        self.last_lap_time_ms: int = 0
        self.is_lap_valid: bool = True
        self.driver_status: int = 1  # 1=Flying Lap, 2=In-lap, 3=Out-lap, 4=On track

        # Circuito e Sessão
        self.track_id: int = 11  # Padrão: Monza
        self.track_name: str = "Monza"
        self.track_length: int = 5793
        self.session_time: float = 0.0
        self.manual_track_override: bool = False
        self.circuit: Optional[CircuitInfo] = get_circuit_by_track_id(11)

        # Máquina de estados
        self.current_state: str = "reta"
        self.next_corner: Optional[CornerZone] = None
        self.dist_to_brake: float = 999.0
        self.dist_to_apex: float = 999.0
        self.pulse_counter: int = 0

        # Pós-volta e PB
        self.best_session_lap_ms: Optional[int] = find_best_recorded_lap_ms(11)
        self.last_lap_feedback: str = ""

        # UI e Temas
        self.active_layout: int = initial_layout
        self.active_theme: str = initial_theme
        self.locked_click_through: bool = False

        # Auto Learner
        self.auto_learner: Optional[AutoCornerLearner] = None

    def update_telemetry(self, speed: int, throttle: float, brake: float, steer: float, gear: int, rpm: int, drs: int):
        with self._lock:
            self.speed = speed
            self.throttle = throttle
            self.brake = brake
            self.steer = steer
            self.gear = gear
            self.engine_rpm = rpm
            self.drs = drs

            # Auto-learning se a pista não tem curvas oficiais
            if self.auto_learner and self.current_lap_num == 1:
                self.auto_learner.feed_sample(self.lap_distance, speed, brake, throttle, gear)

            # Atualiza máquina de estados
            st, corner, d_brake, d_apex = CornerStateMachine.update(
                self.lap_distance, self.speed, self.circuit, self.lap_time_ms, self.driver_status
            )
            self.current_state = st
            self.next_corner = corner
            self.dist_to_brake = d_brake
            self.dist_to_apex = d_apex

    def update_lap_data(self, lap_dist: float, total_dist: float, lap_num: int, lap_time_ms: int, last_time_ms: int, is_valid: bool, driver_status: int = 1):
        with self._lock:
            self.lap_distance = lap_dist
            self.total_distance = total_dist
            self.current_lap_num = lap_num
            self.lap_time_ms = lap_time_ms
            self.last_lap_time_ms = last_time_ms
            self.is_lap_valid = is_valid
            self.driver_status = driver_status

            # Mantém máquina de estados atualizada em sincronia com o avanço da volta
            st, corner, d_brake, d_apex = CornerStateMachine.update(
                self.lap_distance, self.speed, self.circuit, self.lap_time_ms, self.driver_status
            )
            self.current_state = st
            self.next_corner = corner
            self.dist_to_brake = d_brake
            self.dist_to_apex = d_apex

    def set_session_info(self, track_id: int, track_name: str, track_length: int):
        with self._lock:
            if not self.manual_track_override:
                self.track_id = track_id
                self.track_name = track_name
                self.track_length = track_length
                self.circuit = get_circuit_by_track_id(track_id)
                if self.best_session_lap_ms is None:
                    self.best_session_lap_ms = find_best_recorded_lap_ms(track_id)
                if not self.circuit or not self.circuit.corners:
                    self.auto_learner = AutoCornerLearner(track_id, track_name, track_length)
                else:
                    self.auto_learner = None

    def set_manual_track(self, track_id: int):
        with self._lock:
            self.manual_track_override = True
            self.track_id = track_id
            self.circuit = get_circuit_by_track_id(track_id)
            if self.circuit:
                self.track_name = self.circuit.name
                self.track_length = self.circuit.length
            best_lap = find_best_recorded_lap_ms(track_id)
            if best_lap is not None:
                self.best_session_lap_ms = best_lap
            self.next_corner = None

    def set_auto_track_detection(self):
        with self._lock:
            self.manual_track_override = False
            self.circuit = get_circuit_by_track_id(self.track_id)

    def set_theme(self, theme_key: str):
        with self._lock:
            if theme_key in THEMES:
                self.active_theme = theme_key

    def set_layout(self, layout_id: int):
        with self._lock:
            if layout_id in (1, 2, 3):
                self.active_layout = layout_id

    def set_click_through(self, locked: bool):
        with self._lock:
            self.locked_click_through = locked

    def set_lap_feedback(self, feedback: str):
        with self._lock:
            self.last_lap_feedback = feedback

    def finalize_auto_learning(self):
        """Finaliza a volta 1 e ativa o traçado aprendido."""
        with self._lock:
            if self.auto_learner:
                learned = self.auto_learner.finalize()
                self.circuit = learned
                self.auto_learner = None

    def get_snapshot(self) -> Dict:
        """Copia atômica do estado para a thread da interface gráfica Tkinter."""
        with self._lock:
            self.pulse_counter = (self.pulse_counter + 1) % 60
            pulse = self.pulse_counter > 30

            state = self.current_state
            if state == "freia" and pulse:
                state = "freia_pulse"

            return {
                "speed": self.speed,
                "throttle": self.throttle,
                "brake": self.brake,
                "steer": self.steer,
                "gear": self.gear,
                "engine_rpm": self.engine_rpm,
                "drs": self.drs,
                "lap_distance": self.lap_distance,
                "lap_number": self.current_lap_num,
                "lap_time_ms": self.lap_time_ms,
                "last_lap_time_ms": self.last_lap_time_ms,
                "is_lap_valid": self.is_lap_valid,
                "track_id": self.track_id,
                "track_name": self.track_name,
                "track_length": self.track_length,
                "current_state": state,
                "base_state": self.current_state,
                "next_corner": self.next_corner,
                "dist_to_brake": self.dist_to_brake,
                "dist_to_apex": self.dist_to_apex,
                "active_layout": self.active_layout,
                "active_theme": self.active_theme,
                "locked_click_through": self.locked_click_through,
                "last_lap_feedback": self.last_lap_feedback,
                "best_session_lap_ms": self.best_session_lap_ms,
                "driver_status": self.driver_status,
            }
