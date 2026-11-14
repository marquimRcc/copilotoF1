"""Motor de análise de telemetria e diagnóstico prático curva a curva para o Core."""

import csv
import os
from dataclasses import dataclass
from typing import Dict, List, Optional
from tracks.circuits import CircuitInfo, CornerZone, get_circuit_by_track_id


@dataclass
class TelemetryPoint:
    session_time: float
    lap_number: int
    lap_distance: float
    speed: int
    throttle: float
    brake: float
    steer: float
    gear: int
    engine_rpm: int
    drs: int
    lap_time_ms: int
    is_valid: int


@dataclass
class CornerAnalysis:
    corner: CornerZone
    braking_distance: Optional[float]
    braking_speed: Optional[int]
    apex_distance: float
    apex_speed: int
    apex_gear: int
    coasting_time: float
    throttle_pickup_distance: Optional[float]
    full_throttle_distance: Optional[float]


def load_telemetry_csv(csv_path: str) -> List[TelemetryPoint]:
    """Carrega pontos de telemetria de um arquivo CSV."""
    points: List[TelemetryPoint] = []
    if not os.path.exists(csv_path):
        return points

    with open(csv_path, mode="r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            points.append(
                TelemetryPoint(
                    session_time=float(row.get("session_time", 0.0)),
                    lap_number=int(row.get("lap_number", 0)),
                    lap_distance=float(row.get("lap_distance", 0.0)),
                    speed=int(row.get("speed", 0)),
                    throttle=float(row.get("throttle", 0.0)),
                    brake=float(row.get("brake", 0.0)),
                    steer=float(row.get("steer", 0.0)),
                    gear=int(row.get("gear", 0)),
                    engine_rpm=int(row.get("engine_rpm", 0)),
                    drs=int(row.get("drs", 0)),
                    lap_time_ms=int(row.get("lap_time_ms", 0)),
                    is_valid=int(row.get("is_valid", 1)),
                )
            )
    return points


class LapAnalyzer:
    def __init__(self, track_id: int = 11, circuit: Optional[CircuitInfo] = None):
        self.track_id = track_id
        self.circuit = circuit or get_circuit_by_track_id(track_id)

    def analyze_corner(self, points: List[TelemetryPoint], corner: CornerZone) -> Optional[CornerAnalysis]:
        """Analisa a passagem por uma curva específica."""
        zone_points = [p for p in points if corner.start_distance <= p.lap_distance <= corner.end_distance]
        if not zone_points:
            return None

        # 1. Ponto de Frenagem
        braking_distance = None
        braking_speed = None
        for p in zone_points:
            if p.brake >= 0.20:
                braking_distance = p.lap_distance
                braking_speed = p.speed
                break

        # 2. Ápice
        min_point = min(zone_points, key=lambda p: p.speed)
        apex_distance = min_point.lap_distance
        apex_speed = min_point.speed
        apex_gear = min_point.gear

        # 3. Hesitação / Coasting
        coasting_time = 0.0
        throttle_pickup_dist = None
        full_throttle_dist = None

        for i in range(1, len(zone_points)):
            curr = zone_points[i]
            prev = zone_points[i - 1]
            dt = curr.session_time - prev.session_time

            if curr.lap_distance >= (braking_distance or corner.start_distance):
                if curr.brake < 0.05 and curr.throttle < 0.10:
                    coasting_time += max(0.0, dt)

            if curr.lap_distance >= apex_distance:
                if throttle_pickup_dist is None and curr.throttle >= 0.20:
                    throttle_pickup_dist = curr.lap_distance
                if full_throttle_dist is None and curr.throttle >= 0.95:
                    full_throttle_dist = curr.lap_distance

        return CornerAnalysis(
            corner=corner,
            braking_distance=braking_distance,
            braking_speed=braking_speed,
            apex_distance=apex_distance,
            apex_speed=apex_speed,
            apex_gear=apex_gear,
            coasting_time=round(coasting_time, 3),
            throttle_pickup_distance=throttle_pickup_dist,
            full_throttle_distance=full_throttle_dist,
        )

    def generate_quick_tip(
        self,
        user_points: List[TelemetryPoint],
        ref_points: Optional[List[TelemetryPoint]] = None,
    ) -> str:
        """Gera um resumo rápido de uma linha para feedback visual instantâneo no HUD."""
        if not self.circuit or not self.circuit.corners:
            return "Volta registrada com sucesso."

        tips = []
        for corner in self.circuit.corners:
            u_analysis = self.analyze_corner(user_points, corner)
            if not u_analysis:
                continue

            r_analysis = self.analyze_corner(ref_points, corner) if ref_points else None

            # Checa frenagem
            if u_analysis.braking_distance is not None:
                if r_analysis and r_analysis.braking_distance is not None:
                    diff_m = u_analysis.braking_distance - r_analysis.braking_distance
                    if diff_m < -12:
                        tips.append(f"C{corner.number} freou {abs(diff_m):.0f}m cedo")
                    elif diff_m > 15:
                        tips.append(f"C{corner.number} freou {diff_m:.0f}m tarde")

            # Checa hesitação
            if u_analysis.coasting_time > 0.35:
                tips.append(f"C{corner.number} hesitou {u_analysis.coasting_time:.2f}s")

            if len(tips) >= 2:
                break

        if tips:
            return " | ".join(tips)
        return "Volta limpa e consistente!"

    def compare_laps(
        self,
        user_points: List[TelemetryPoint],
        ref_points: Optional[List[TelemetryPoint]] = None,
    ) -> str:
        """Gera o relatório completo detalhado em texto."""
        circuit_name = self.circuit.name if self.circuit else f"Circuito {self.track_id}"
        lines = []
        lines.append("=" * 65)
        lines.append(f"🏎️  DIAGNÓSTICO PRÁTICO DE PILOTAGEM - {circuit_name.upper()}")
        lines.append("=" * 65)

        if not self.circuit or not self.circuit.corners:
            lines.append(f"⚠️ Circuito ID {self.track_id} ainda não possui mapeamento de curvas.")
            return "\n".join(lines)

        user_lap_time = user_points[-1].lap_time_ms if user_points else 0
        ref_lap_time = ref_points[-1].lap_time_ms if ref_points else None

        if user_lap_time > 0:
            lines.append(f"⏱️ Tempo da sua volta: {self._format_ms(user_lap_time)}")
        if ref_lap_time and ref_lap_time > 0:
            delta_s = (user_lap_time - ref_lap_time) / 1000.0
            lines.append(f"⏱️ Tempo de referência: {self._format_ms(ref_lap_time)} (Delta: {delta_s:+.3f}s)")
        lines.append("-" * 65)

        for corner in self.circuit.corners:
            u_analysis = self.analyze_corner(user_points, corner)
            if not u_analysis:
                continue

            r_analysis = self.analyze_corner(ref_points, corner) if ref_points else None
            lines.append(f"\n📍 Curva {corner.number} ({corner.name})")

            # Diagnóstico de Ponto de Frenagem
            if u_analysis.braking_distance is not None:
                if r_analysis and r_analysis.braking_distance is not None:
                    diff_m = u_analysis.braking_distance - r_analysis.braking_distance
                    if diff_m < -8:
                        lines.append(f"   🛑 FRENAGEM ANTECIPADA: Freou a {abs(diff_m):.1f}m ANTES do ideal ({u_analysis.braking_distance:.0f}m vs {r_analysis.braking_distance:.0f}m).")
                    elif diff_m > 12:
                        lines.append(f"   ⚠️ FRENAGEM TARDIA: Freou {diff_m:.1f}m mais tarde que a referência.")
                    else:
                        lines.append(f"   ✅ FRENAGEM NO PONTO: Perfeito a {u_analysis.braking_distance:.0f}m.")
                else:
                    lines.append(f"   🛑 Ponto de Frenagem: acionado aos {u_analysis.braking_distance:.0f}m a {u_analysis.braking_speed} km/h.")

            # Diagnóstico de Velocidade de Ápice
            if r_analysis:
                speed_diff = u_analysis.apex_speed - r_analysis.apex_speed
                if speed_diff < -5:
                    lines.append(f"   📉 VELOCIDADE DE ÁPICE BAIXA: {u_analysis.apex_speed} km/h (referência: {r_analysis.apex_speed} km/h).")
                elif speed_diff > 4:
                    lines.append(f"   ⚡ BOA VELOCIDADE DE ÁPICE: {u_analysis.apex_speed} km/h ({speed_diff:+d} km/h vs referência).")
                else:
                    lines.append(f"   ✅ Velocidade no Ápice: {u_analysis.apex_speed} km/h (equilibrada).")
            else:
                lines.append(f"   🌀 Velocidade no Ápice: {u_analysis.apex_speed} km/h (Marcha: {u_analysis.apex_gear}ª).")

            # Diagnóstico de Marcha
            if corner.gear_reference and u_analysis.apex_gear != corner.gear_reference:
                if u_analysis.apex_gear < corner.gear_reference:
                    lines.append(f"   ⚙️ MARCHA: Feita em {u_analysis.apex_gear}ª marcha. Referência é {corner.gear_reference}ª marcha.")

            # Hesitação
            if u_analysis.coasting_time > 0.25:
                lines.append(f"   ⏱️ HESITAÇÃO NA SAÍDA: {u_analysis.coasting_time:.2f}s de carro solto.")
            elif u_analysis.coasting_time <= 0.15:
                lines.append(f"   🚀 TRANSIÇÃO RÁPIDA: Transição freio -> acelerador precisa ({u_analysis.coasting_time:.2f}s).")

        lines.append("\n" + "=" * 65)
        return "\n".join(lines)

    @staticmethod
    def _format_ms(ms: int) -> str:
        minutes = ms // 60000
        seconds = (ms % 60000) / 1000.0
        return f"{minutes:02d}:{seconds:06.3f}"
