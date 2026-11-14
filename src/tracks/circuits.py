"""Definição de circuitos e zonas de curvas (F1 25) com suporte a JSON e auto-aprendizado."""

import json
import os
from dataclasses import dataclass, field
from typing import Dict, List, Optional


@dataclass
class CornerZone:
    number: str
    name: str
    start_distance: float
    apex_distance: float
    end_distance: float
    gear_reference: Optional[int] = None


@dataclass
class CircuitInfo:
    track_id: int
    name: str
    length: int
    corners: List[CornerZone] = field(default_factory=list)
    country: str = ""
    is_auto_learned: bool = False


# Dicionário global de circuitos em memória
CIRCUITS: Dict[int, CircuitInfo] = {}


def load_circuits_from_json(json_path: str = "config/circuits_f125.json") -> Dict[int, CircuitInfo]:
    """Carrega circuitos a partir do arquivo JSON oficial ou relativo ao projeto."""
    global CIRCUITS
    circuits_dict: Dict[int, CircuitInfo] = {}

    candidates = [
        json_path,
        os.path.join(os.path.dirname(__file__), "..", "..", json_path),
        os.path.join(os.getcwd(), json_path),
    ]

    target_path = None
    for p in candidates:
        if os.path.exists(p):
            target_path = p
            break

    if target_path:
        try:
            with open(target_path, "r", encoding="utf-8") as f:
                data = json.load(f)
                circuits_raw = data.get("circuits", {})
                for str_id, cdata in circuits_raw.items():
                    tid = int(str_id)
                    corners = [
                        CornerZone(
                            number=c["number"],
                            name=c["name"],
                            start_distance=float(c["start_distance"]),
                            apex_distance=float(c["apex_distance"]),
                            end_distance=float(c["end_distance"]),
                            gear_reference=c.get("gear_reference"),
                        )
                        for c in cdata.get("corners", [])
                    ]
                    circuits_dict[tid] = CircuitInfo(
                        track_id=tid,
                        name=cdata.get("name", f"Circuito {tid}"),
                        length=int(cdata.get("length", 5000)),
                        corners=corners,
                        country=cdata.get("country", ""),
                    )
        except Exception:
            pass

    # Garante pelo menos as pistas essenciais se o arquivo falhar
    if 11 not in circuits_dict:
        circuits_dict[11] = CircuitInfo(
            track_id=11,
            name="Monza",
            length=5793,
            corners=[
                CornerZone(number="1-2", name="Variante del Rettifilo", start_distance=420.0, apex_distance=620.0, end_distance=850.0, gear_reference=2),
                CornerZone(number="3", name="Curva Grande (Biassono)", start_distance=950.0, apex_distance=1250.0, end_distance=1500.0, gear_reference=8),
                CornerZone(number="4-5", name="Variante della Roggia", start_distance=1600.0, apex_distance=1820.0, end_distance=2000.0, gear_reference=3),
                CornerZone(number="6-7", name="Curve di Lesmo (1 e 2)", start_distance=2150.0, apex_distance=2550.0, end_distance=2850.0, gear_reference=5),
                CornerZone(number="8-10", name="Variante Ascari", start_distance=3480.0, apex_distance=3780.0, end_distance=4050.0, gear_reference=5),
                CornerZone(number="11", name="Curva Alboreto (Parabolica)", start_distance=4900.0, apex_distance=5200.0, end_distance=5550.0, gear_reference=5),
            ],
        )

    CIRCUITS.clear()
    CIRCUITS.update(circuits_dict)
    return CIRCUITS


# Inicialização automática ao importar
load_circuits_from_json()


def get_circuit_by_track_id(track_id: int) -> Optional[CircuitInfo]:
    """Retorna as informações do circuito pelo seu trackId oficial da Codemasters/EA."""
    if not CIRCUITS:
        load_circuits_from_json()
    return CIRCUITS.get(track_id)


def register_auto_learned_circuit(circuit: CircuitInfo):
    """Registra em memória um circuito calibrado automaticamente."""
    global CIRCUITS
    CIRCUITS[circuit.track_id] = circuit
