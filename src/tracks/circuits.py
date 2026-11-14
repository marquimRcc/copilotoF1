"""Definição de circuitos e zonas de curvas para análise de telemetria."""

from dataclasses import dataclass
from typing import Dict, List, Optional


@dataclass
class CornerZone:
    number: str                # Ex: "1", "4-5", "11"
    name: str                  # Ex: "Variante del Rettifilo"
    start_distance: float      # Início da zona de aproximação/frenagem em metros
    apex_distance: float       # Ponto aproximado do ápice em metros
    end_distance: float        # Saída da curva / retomada plena em metros
    gear_reference: int        # Marcha típica recomendada no ápice


@dataclass
class CircuitInfo:
    track_id: int
    name: str
    length: int                # Comprimento em metros
    corners: List[CornerZone]


# Base de dados de circuitos conhecidos
CIRCUITS: Dict[int, CircuitInfo] = {
    # Autodromo Nazionale Monza (trackId = 11)
    11: CircuitInfo(
        track_id=11,
        name="Autodromo Nazionale Monza",
        length=5793,
        corners=[
            CornerZone(number="1-2", name="Variante del Rettifilo", start_distance=420.0, apex_distance=620.0, end_distance=850.0, gear_reference=2),
            CornerZone(number="3", name="Curva Grande / Biassono", start_distance=950.0, apex_distance=1250.0, end_distance=1450.0, gear_reference=8),
            CornerZone(number="4-5", name="Variante della Roggia", start_distance=1550.0, apex_distance=1750.0, end_distance=1950.0, gear_reference=3),
            CornerZone(number="6", name="Primeira Lesmo", start_distance=2100.0, apex_distance=2250.0, end_distance=2400.0, gear_reference=4),
            CornerZone(number="7", name="Segunda Lesmo", start_distance=2450.0, apex_distance=2600.0, end_distance=2800.0, gear_reference=4),
            CornerZone(number="8-10", name="Variante Ascari", start_distance=3400.0, apex_distance=3650.0, end_distance=3950.0, gear_reference=4),
            CornerZone(number="11", name="Curva Parabolica (Alboreto)", start_distance=4900.0, apex_distance=5200.0, end_distance=5550.0, gear_reference=4),
        ],
    ),
    # Autódromo de Interlagos (trackId = 16)
    16: CircuitInfo(
        track_id=16,
        name="Autódromo José Carlos Pace (Interlagos)",
        length=4309,
        corners=[
            CornerZone(number="1-2", name="S do Senna", start_distance=150.0, apex_distance=350.0, end_distance=600.0, gear_reference=3),
            CornerZone(number="3", name="Curva do Sol", start_distance=650.0, apex_distance=850.0, end_distance=1100.0, gear_reference=6),
            CornerZone(number="4", name="Descida do Lago", start_distance=1400.0, apex_distance=1600.0, end_distance=1800.0, gear_reference=4),
            CornerZone(number="6-7", name="Ferradura / Laranjinha", start_distance=1950.0, apex_distance=2200.0, end_distance=2400.0, gear_reference=5),
            CornerZone(number="8", name="Pinheirinho", start_distance=2450.0, apex_distance=2600.0, end_distance=2750.0, gear_reference=2),
            CornerZone(number="9", name="Bico de Pato", start_distance=2800.0, apex_distance=2950.0, end_distance=3100.0, gear_reference=2),
            CornerZone(number="10", name="Mergulho", start_distance=3150.0, apex_distance=3300.0, end_distance=3450.0, gear_reference=5),
            CornerZone(number="12", name="Junção", start_distance=3500.0, apex_distance=3650.0, end_distance=3850.0, gear_reference=3),
        ],
    ),
    # Red Bull Ring (trackId = 17)
    17: CircuitInfo(
        track_id=17,
        name="Red Bull Ring (Spielberg)",
        length=4318,
        corners=[
            CornerZone(number="1", name="Niki Lauda Kurve", start_distance=120.0, apex_distance=280.0, end_distance=480.0, gear_reference=3),
            CornerZone(number="3", name="Remus (Subida)", start_distance=1100.0, apex_distance=1350.0, end_distance=1550.0, gear_reference=2),
            CornerZone(number="4", name="Schlossgold", start_distance=1900.0, apex_distance=2150.0, end_distance=2350.0, gear_reference=3),
            CornerZone(number="6-7", name="Rauch / Wurth", start_distance=2550.0, apex_distance=2800.0, end_distance=3100.0, gear_reference=4),
            CornerZone(number="9-10", name="Rindt / Red Bull Mobile", start_distance=3500.0, apex_distance=3850.0, end_distance=4200.0, gear_reference=5),
        ],
    ),
    # Silverstone (trackId = 7)
    7: CircuitInfo(
        track_id=7,
        name="Silverstone Circuit",
        length=5891,
        corners=[
            CornerZone(number="1", name="Abbey", start_distance=150.0, apex_distance=350.0, end_distance=500.0, gear_reference=7),
            CornerZone(number="3-4", name="Village / The Loop", start_distance=700.0, apex_distance=950.0, end_distance=1250.0, gear_reference=2),
            CornerZone(number="6", name="Brooklands", start_distance=1900.0, apex_distance=2150.0, end_distance=2350.0, gear_reference=3),
            CornerZone(number="7", name="Luffield", start_distance=2400.0, apex_distance=2600.0, end_distance=2850.0, gear_reference=3),
            CornerZone(number="9", name="Copse", start_distance=3100.0, apex_distance=3300.0, end_distance=3500.0, gear_reference=7),
            CornerZone(number="10-14", name="Maggotts / Becketts / Chapel", start_distance=3600.0, apex_distance=4000.0, end_distance=4400.0, gear_reference=5),
            CornerZone(number="15", name="Stowe", start_distance=4850.0, apex_distance=5100.0, end_distance=5300.0, gear_reference=5),
            CornerZone(number="16-18", name="Vale / Club", start_distance=5400.0, apex_distance=5650.0, end_distance=5850.0, gear_reference=3),
        ],
    ),
    # Spa-Francorchamps (trackId = 10)
    10: CircuitInfo(
        track_id=10,
        name="Circuit de Spa-Francorchamps",
        length=7004,
        corners=[
            CornerZone(number="1", name="La Source", start_distance=120.0, apex_distance=280.0, end_distance=500.0, gear_reference=2),
            CornerZone(number="2-4", name="Eau Rouge / Raidillon", start_distance=700.0, apex_distance=1100.0, end_distance=1400.0, gear_reference=8),
            CornerZone(number="5-7", name="Les Combes / Malmedy", start_distance=2850.0, apex_distance=3150.0, end_distance=3450.0, gear_reference=4),
            CornerZone(number="8", name="Bruxelles / Rivage", start_distance=3600.0, apex_distance=3850.0, end_distance=4100.0, gear_reference=3),
            CornerZone(number="10-11", name="Pouhon", start_distance=4550.0, apex_distance=4800.0, end_distance=5100.0, gear_reference=6),
            CornerZone(number="14-15", name="Campus / Stavelot", start_distance=5350.0, apex_distance=5650.0, end_distance=5950.0, gear_reference=5),
            CornerZone(number="16-17", name="Blanchimont", start_distance=6150.0, apex_distance=6450.0, end_distance=6700.0, gear_reference=8),
            CornerZone(number="18-19", name="Bus Stop Chicane", start_distance=6750.0, apex_distance=6900.0, end_distance=7004.0, gear_reference=2),
        ],
    ),
}


def get_circuit_by_track_id(track_id: int) -> Optional[CircuitInfo]:
    """Retorna os dados do circuito ou None se não cadastrado."""
    return CIRCUITS.get(track_id)
