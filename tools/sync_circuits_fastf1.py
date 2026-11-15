"""
Opção A: Sincronizador Oficial de Circuitos via FIA Live Timing (FastF1).
Extrai a distância oficial de cada curva da FIA e a telemetria da Pole Position,
normalizando proporcionalmente para o comprimento exato da pista no EA SPORTS F1 25.

Como usar:
    pip install fastf1
    python tools/sync_circuits_fastf1.py                # Sincroniza todas as pistas
    python tools/sync_circuits_fastf1.py --track-id 16  # Sincroniza apenas Interlagos
"""

import argparse
import json
import os
import sys
from typing import Dict, List, Tuple

try:
    import fastf1
except ImportError:
    print("❌ Biblioteca 'fastf1' não encontrada. Instale com: pip install fastf1")
    sys.exit(1)

# Mapeamento oficial: Track ID do EA SPORTS F1 25 -> (Evento FastF1, Nome Exibição, País, Comprimento Oficial F1 25)
F125_TRACK_MAP: Dict[int, Tuple[str, str, str, int]] = {
    0: ("Australia", "Melbourne", "Austrália", 5278),
    2: ("China", "Shanghai", "China", 5451),
    3: ("Bahrain", "Bahrein (Sakhir)", "Bahrein", 5412),
    4: ("Spain", "Barcelona (Catalunya)", "Espanha", 4657),
    5: ("Monaco", "Monaco", "Mônaco", 3337),
    6: ("Canada", "Montreal (Gilles Villeneuve)", "Canadá", 4361),
    7: ("Great Britain", "Silverstone", "Grã-Bretanha", 5891),
    9: ("Hungary", "Hungaroring", "Hungria", 4381),
    10: ("Belgium", "Spa-Francorchamps", "Bélgica", 7004),
    11: ("Italy", "Monza", "Itália", 5793),
    12: ("Singapore", "Singapore (Marina Bay)", "Singapura", 4940),
    13: ("Japan", "Suzuka", "Japão", 5807),
    14: ("Abu Dhabi", "Yas Marina (Abu Dhabi)", "Emirados Árabes", 5281),
    15: ("United States", "Austin (COTA)", "EUA", 5513),
    16: ("Brazil", "Interlagos", "Brasil", 4309),
    17: ("Austria", "Red Bull Ring", "Áustria", 4318),
    19: ("Mexico", "Mexico City (Hermanos Rodríguez)", "México", 4304),
    20: ("Azerbaijan", "Baku City Circuit", "Azerbaijão", 6003),
    26: ("Netherlands", "Zandvoort", "Holanda", 4259),
    27: ("Emilia Romagna", "Imola (Enzo e Dino Ferrari)", "Itália", 4909),
    29: ("Saudi Arabia", "Jeddah Corniche", "Arábia Saudita", 6174),
    30: ("Miami", "Miami International Autodrome", "EUA", 5412),
    31: ("Las Vegas", "Las Vegas Strip Circuit", "EUA", 6201),
    32: ("Qatar", "Losail (Lusail)", "Catar", 5419),
}


def sync_track_from_fia(year: int, track_id: int, existing_corners: List[Dict]) -> Dict:
    gp_query, name, country, f125_length = F125_TRACK_MAP[track_id]
    print(f"📡 [ID {track_id:02d}] Baixando telemetria oficial da FIA para {name} ({year})...")

    session = fastf1.get_session(year, gp_query, "Q")
    session.load(telemetry=True, weather=False, messages=False)
    fastest_lap = session.laps.pick_fastest()
    car_data = fastest_lap.get_car_data().add_distance()
    circuit_info = session.get_circuit_info()

    fia_max_dist = float(car_data["Distance"].max())
    scale = f125_length / fia_max_dist if fia_max_dist > 1000 else 1.0

    # Mapa de nomes preservados caso já existam no JSON
    existing_names = {str(c.get("number")): c.get("name") for c in existing_corners}

    raw_corners = []
    for _, row in circuit_info.corners.iterrows():
        c_num = f"{int(row['Number'])}{row.get('Letter', '')}".strip()
        fia_apex = float(row["Distance"])
        scaled_apex = fia_apex * scale

        # Janela de análise na volta da Pole [-130m antes do ápice até +70m depois]
        win = car_data[
            (car_data["Distance"] >= max(0.0, fia_apex - 130.0))
            & (car_data["Distance"] <= min(fia_max_dist, fia_apex + 70.0))
        ]
        if win.empty:
            continue

        min_idx = win["Speed"].idxmin()
        min_gear = int(win.loc[min_idx, "nGear"])
        min_speed = float(win.loc[min_idx, "Speed"])

        # Se a velocidade mínima for > 265 km/h e sem freio, trata como curva de alta / flat (8ª marcha)
        pre_apex = win[win["Distance"] <= fia_apex]
        braking_rows = pre_apex[pre_apex["Brake"] > 0]

        if not braking_rows.empty:
            fia_brake_start = float(braking_rows["Distance"].iloc[0])
            start_dist = max(0.0, (fia_brake_start * scale) - 15.0)
            gear_ref = max(1, min(7, min_gear))
        else:
            start_dist = max(0.0, scaled_apex - 75.0)
            gear_ref = 8 if min_speed >= 260 else max(1, min(8, min_gear))

        end_dist = min(float(f125_length - 10), scaled_apex + 85.0)

        raw_corners.append({
            "number": c_num,
            "name": existing_names.get(c_num, f"Curva {c_num}"),
            "start_distance": round(start_dist, 1),
            "apex_distance": round(scaled_apex, 1),
            "end_distance": round(end_dist, 1),
            "gear_reference": gear_ref,
        })

    # Mescla pernas de chicanes muito próximas (< 75m entre ápices)
    merged_corners: List[Dict] = []
    i = 0
    while i < len(raw_corners):
        curr = raw_corners[i]
        if i + 1 < len(raw_corners):
            nxt = raw_corners[i + 1]
            if (nxt["apex_distance"] - curr["apex_distance"]) < 75.0:
                combined_num = f"{curr['number']}-{nxt['number']}"
                combined_name = existing_names.get(combined_num, f"Chicane {combined_num}")
                merged_corners.append({
                    "number": combined_num,
                    "name": combined_name,
                    "start_distance": curr["start_distance"],
                    "apex_distance": curr["apex_distance"],
                    "end_distance": nxt["end_distance"],
                    "gear_reference": min(curr["gear_reference"], nxt["gear_reference"]),
                })
                i += 2
                continue
        merged_corners.append(curr)
        i += 1

    return {
        "track_id": track_id,
        "name": name,
        "country": country,
        "length": f125_length,
        "corners": merged_corners,
    }


def main():
    parser = argparse.ArgumentParser(description="Sincroniza config/circuits_f125.json com dados oficiais da FIA (FastF1)")
    parser.add_argument("--year", type=int, default=2024, help="Temporada de referência da FIA (padrão: 2024)")
    parser.add_argument("--track-id", type=int, default=None, help="Sincronizar apenas um Track ID específico (ex: 16)")
    parser.add_argument("--output", default="config/circuits_f125.json", help="Caminho do arquivo JSON")
    args = parser.parse_args()

    cache_dir = os.path.join(os.path.dirname(__file__), "..", ".fastf1_cache")
    os.makedirs(cache_dir, exist_ok=True)
    fastf1.Cache.enable_cache(cache_dir)

    existing_data = {"version": "2.0.0", "game": "EA SPORTS F1 25", "circuits": {}}
    if os.path.exists(args.output):
        with open(args.output, "r", encoding="utf-8") as f:
            existing_data = json.load(f)

    target_ids = [args.track_id] if args.track_id is not None else sorted(F125_TRACK_MAP.keys())

    for tid in target_ids:
        if tid not in F125_TRACK_MAP:
            print(f"⚠️ Track ID {tid} não mapeado.")
            continue
        try:
            old_corners = existing_data.get("circuits", {}).get(str(tid), {}).get("corners", [])
            updated_circuit = sync_track_from_fia(args.year, tid, old_corners)
            existing_data.setdefault("circuits", {})[str(tid)] = updated_circuit
            print(f"   ✅ {updated_circuit['name']} atualizado ({len(updated_circuit['corners'])} zonas de curva).")
        except Exception as e:
            print(f"   ⚠️ Erro ao sincronizar ID {tid}: {e}")

    with open(args.output, "w", encoding="utf-8") as f:
        json.dump(existing_data, f, ensure_ascii=False, indent=2)

    print(f"\n🏁 Sincronização concluída em: {args.output}")


if __name__ == "__main__":
    main()
