"""Motor de análise de telemetria e diagnóstico prático curva a curva."""

import argparse
import csv
import os
import sys
from dataclasses import dataclass
from typing import Dict, List, Optional

from tracks.circuits import CornerZone, get_circuit_by_track_id, CIRCUITS


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
    braking_distance: Optional[float]   # Metro exato do início da frenagem
    braking_speed: Optional[int]        # Velocidade ao tocar no freio
    apex_distance: float                # Metro onde ocorreu a menor velocidade
    apex_speed: int                     # Velocidade mínima no contorno (km/h)
    apex_gear: int                      # Marcha no contorno
    coasting_time: float                # Tempo (s) com acelerador e freio zerados
    throttle_pickup_distance: Optional[float] # Metro onde voltou a acelerar (>20%)
    full_throttle_distance: Optional[float]   # Metro onde atingiu >95% acelerador


def load_telemetry_csv(csv_path: str) -> List[TelemetryPoint]:
    """Carrega pontos de telemetria a partir de um arquivo CSV."""
    points: List[TelemetryPoint] = []
    with open(csv_path, mode="r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            points.append(
                TelemetryPoint(
                    session_time=float(row["session_time"]),
                    lap_number=int(row["lap_number"]),
                    lap_distance=float(row["lap_distance"]),
                    speed=int(row["speed"]),
                    throttle=float(row["throttle"]),
                    brake=float(row["brake"]),
                    steer=float(row["steer"]),
                    gear=int(row["gear"]),
                    engine_rpm=int(row["engine_rpm"]),
                    drs=int(row["drs"]),
                    lap_time_ms=int(row["lap_time_ms"]),
                    is_valid=int(row["is_valid"]),
                )
            )
    return points


class LapAnalyzer:
    def __init__(self, track_id: int = 11):
        self.track_id = track_id
        self.circuit = get_circuit_by_track_id(track_id)

    def analyze_corner(self, points: List[TelemetryPoint], corner: CornerZone) -> Optional[CornerAnalysis]:
        """Analisa a passagem por uma zona de curva específica."""
        # Filtra pontos dentro da janela da curva
        zone_points = [p for p in points if corner.start_distance <= p.lap_distance <= corner.end_distance]
        if not zone_points:
            return None

        # 1. Ponto de Frenagem (primeiro ponto onde brake > 0.20)
        braking_distance = None
        braking_speed = None
        for p in zone_points:
            if p.brake >= 0.20:
                braking_distance = p.lap_distance
                braking_speed = p.speed
                break

        # 2. Velocidade de Ápice (menor velocidade registrada na zona)
        min_point = min(zone_points, key=lambda p: p.speed)
        apex_distance = min_point.lap_distance
        apex_speed = min_point.speed
        apex_gear = min_point.gear

        # 3. Hesitação / Coasting (tempo sem freio e sem acelerador)
        coasting_time = 0.0
        throttle_pickup_dist = None
        full_throttle_dist = None

        for i in range(1, len(zone_points)):
            curr = zone_points[i]
            prev = zone_points[i - 1]
            dt = curr.session_time - prev.session_time

            # Se freio < 0.05 e acelerador < 0.10 após a aproximação
            if curr.lap_distance >= (braking_distance or corner.start_distance):
                if curr.brake < 0.05 and curr.throttle < 0.10:
                    coasting_time += max(0.0, dt)

            # Retomada de acelerador
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

    def compare_laps(
        self,
        user_points: List[TelemetryPoint],
        ref_points: Optional[List[TelemetryPoint]] = None,
    ) -> str:
        """Gera o relatório prático comparativo em texto."""
        circuit_name = self.circuit.name if self.circuit else f"Circuito {self.track_id}"
        lines = []
        lines.append("=" * 65)
        lines.append(f"🏎️  DIAGNÓSTICO PRÁTICO DE PILOTAGEM - {circuit_name.upper()}")
        lines.append("=" * 65)

        if not self.circuit:
            lines.append(f"⚠️ Circuito ID {self.track_id} ainda não possui mapeamento detalhado de curvas.")
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
                    if diff_m < -8:  # Freou antes da referência
                        lines.append(f"   🛑 FRENAGEM ANTECIPADA: Você freou a {abs(diff_m):.1f} metros ANTES do ponto ideal ({u_analysis.braking_distance:.0f}m vs {r_analysis.braking_distance:.0f}m).")
                        lines.append(f"      👉 Recomendação: Confie mais no carro e atrase a freada em direção à placa de referência.")
                    elif diff_m > 12:  # Passou do ponto
                        lines.append(f"   ⚠️ FRENAGEM TARDIA: Você freou {diff_m:.1f}m mais tarde que a referência e corre risco de espalhar na entrada.")
                    else:
                        lines.append(f"   ✅ FRENAGEM NO PONTO: Excelente! Ponto de freio a {u_analysis.braking_distance:.0f}m alinhado com a referência.")
                else:
                    lines.append(f"   🛑 Ponto de Frenagem: acionado aos {u_analysis.braking_distance:.0f}m a {u_analysis.braking_speed} km/h.")

            # Diagnóstico de Velocidade de Ápice
            if r_analysis:
                speed_diff = u_analysis.apex_speed - r_analysis.apex_speed
                if speed_diff < -5:
                    lines.append(f"   📉 VELOCIDADE DE ÁPICE BAIXA: Você passou pelo meio da curva a {u_analysis.apex_speed} km/h (referência: {r_analysis.apex_speed} km/h, {speed_diff} km/h).")
                    lines.append(f"      👉 Você super-desacelerou o carro na entrada. Carregue mais velocidade para dentro.")
                elif speed_diff > 4:
                    lines.append(f"   ⚡ BOA VELOCIDADE DE ÁPICE: {u_analysis.apex_speed} km/h ({speed_diff:+d} km/h vs referência).")
                else:
                    lines.append(f"   ✅ Velocidade no Ápice: {u_analysis.apex_speed} km/h (bem equilibrada).")
            else:
                lines.append(f"   🌀 Velocidade no Ápice: {u_analysis.apex_speed} km/h (Marcha: {u_analysis.apex_gear}ª).")

            # Diagnóstico de Marcha
            if corner.gear_reference and u_analysis.apex_gear != corner.gear_reference:
                if u_analysis.apex_gear < corner.gear_reference:
                    lines.append(f"   ⚙️ MARCHA: Você fez em {u_analysis.apex_gear}ª marcha. Fazer em {corner.gear_reference}ª marcha evita destracionar e melhora a tração na saída.")

            # Diagnóstico de Hesitação / Retomada de Acelerador
            if u_analysis.coasting_time > 0.25:
                lines.append(f"   ⏱️ HESITAÇÃO NA SAÍDA: {u_analysis.coasting_time:.2f}s de carro 'solto' (sem freio e sem acelerador).")
                lines.append(f"      👉 Retome o acelerador mais cedo e de forma progressiva para não perder velocidade de reta.")
            elif u_analysis.coasting_time <= 0.15:
                lines.append(f"   🚀 TRANSIÇÃO RÁPIDA: Transição freio -> acelerador precisa ({u_analysis.coasting_time:.2f}s).")

        lines.append("\n" + "=" * 65)
        return "\n".join(lines)

    @staticmethod
    def _format_ms(ms: int) -> str:
        minutes = ms // 60000
        seconds = (ms % 60000) / 1000.0
        return f"{minutes:02d}:{seconds:06.3f}"


def main():
    parser = argparse.ArgumentParser(description="Analisador de Telemetria do F1")
    parser.add_argument("user_csv", help="Caminho do arquivo CSV da sua volta")
    parser.add_argument("--ref-csv", default=None, help="Caminho do arquivo CSV da volta de referência (opcional)")
    parser.add_argument("--track-id", type=int, default=11, help="ID da pista (ex: 11 para Monza, 16 para Interlagos)")
    args = parser.parse_args()

    if not os.path.exists(args.user_csv):
        print(f"Erro: Arquivo '{args.user_csv}' não encontrado.")
        sys.exit(1)

    user_points = load_telemetry_csv(args.user_csv)
    ref_points = load_telemetry_csv(args.ref_csv) if args.ref_csv and os.path.exists(args.ref_csv) else None

    analyzer = LapAnalyzer(track_id=args.track_id)
    report = analyzer.compare_laps(user_points, ref_points)
    print(report)


if __name__ == "__main__":
    main()
