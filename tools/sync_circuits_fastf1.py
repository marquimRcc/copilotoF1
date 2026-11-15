"""
Extrator direto de pontos de frenagem e marchas da telemetria oficial FastF1 para o F1 25.
Usa o ponto exato de pressão no freio (Brake > 0) da volta mais rápida de cada pista.
"""

import argparse
import json
import os
import sys
from typing import Dict, List, Tuple

import fastf1

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


def sync_track(year: int, track_id: int, existing_corners: List[Dict]) -> Dict:
    gp_query, name, country, f125_length = F125_TRACK_MAP[track_id]
    print(f"📡 [ID {track_id:02d}] Extraindo telemetria real de frenagem para {name}...")

    session = fastf1.get_session(year, gp_query, "Q")
    session.load(telemetry=True, weather=False, messages=False)
    fastest_lap = session.laps.pick_fastest()
    car_data = fastest_lap.get_car_data().add_distance()
    circuit_info = session.get_circuit_info()

    fia_max_dist = float(car_data["Distance"].max())
    scale = f125_length / fia_max_dist if fia_max_dist > 1000 else 1.0
    existing_names = {str(c.get("number")): c.get("name") for c in existing_corners}

    raw_corners = []
    for _, row in circuit_info.corners.iterrows():
        c_num = f"{int(row['Number'])}{row.get('Letter', '')}".strip()
        fia_corner_dist = float(row["Distance"])

        # Janela na telemetria real [-140m antes da curva até +60m depois]
        win = car_data[
            (car_data["Distance"] >= max(0.0, fia_corner_dist - 140.0))
            & (car_data["Distance"] <= min(fia_max_dist, fia_corner_dist + 60.0))
        ]
        if win.empty:
            continue

        min_idx = win["Speed"].idxmin()
        true_fia_apex = float(win.loc[min_idx, "Distance"])
        min_gear = int(win.loc[min_idx, "nGear"])
        min_speed = float(win.loc[min_idx, "Speed"])

        # Busca o metro EXATO em que o piloto pisou no freio antes do ápice
        pre_apex = win[win["Distance"] <= true_fia_apex]
        braking_rows = pre_apex[(pre_apex["Brake"] > 0) & (pre_apex["Throttle"] < 50)]

        scaled_apex = true_fia_apex * scale
        if not braking_rows.empty and min_speed < 265:
            first_brake_m = float(braking_rows["Distance"].iloc[0]) * scale
            start_dist = max(10.0, min(first_brake_m, scaled_apex - 35.0))
            gear_ref = max(1, min(7, min_gear))
        else:
            start_dist = max(10.0, scaled_apex - 50.0)
            gear_ref = 8 if min_speed >= 260 else max(1, min(8, min_gear))

        end_dist = min(float(f125_length - 15), scaled_apex + 70.0)

        raw_corners.append({
            "number": c_num,
            "name": existing_names.get(c_num, f"Curva {c_num}"),
            "start_distance": round(start_dist, 1),
            "apex_distance": round(scaled_apex, 1),
            "end_distance": round(end_dist, 1),
            "gear_reference": gear_ref,
        })

    # Agrupa pernas de S / Chicanes (< 95m entre ápices) mantendo o ponto de freio da 1ª perna
    merged: List[Dict] = []
    i = 0
    while i < len(raw_corners):
        curr = raw_corners[i]
        if i + 1 < len(raw_corners):
            nxt = raw_corners[i + 1]
            if (nxt["apex_distance"] - curr["apex_distance"]) < 95.0:
                comb_num = f"{curr['number']}-{nxt['number']}"
                comb_name = existing_names.get(comb_num, curr["name"])
                merged.append({
                    "number": comb_num,
                    "name": comb_name,
                    "start_distance": curr["start_distance"],
                    "apex_distance": curr["apex_distance"],
                    "end_distance": nxt["end_distance"],
                    "gear_reference": min(curr["gear_reference"], nxt["gear_reference"]),
                })
                i += 2
                continue
        merged.append(curr)
        i += 1

    return {
        "track_id": track_id,
        "name": name,
        "country": country,
        "length": f125_length,
        "corners": merged,
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--year", type=int, default=2024)
    parser.add_argument("--track-id", type=int, default=None)
    parser.add_argument("--output", default="config/circuits_f125.json")
    args = parser.parse_args()

    cache_dir = os.path.join(os.path.dirname(__file__), "..", ".fastf1_cache")
    os.makedirs(cache_dir, exist_ok=True)
    if hasattr(fastf1.Cache, "configure"):
        fastf1.Cache.configure(cache_dir)
    else:
        fastf1.Cache.enable_cache(cache_dir)

    with open(args.output, "r", encoding="utf-8-sig") as f:
        data = json.load(f)

    targets = [args.track_id] if args.track_id is not None else sorted(F125_TRACK_MAP.keys())
    for tid in targets:
        try:
            old_c = data.get("circuits", {}).get(str(tid), {}).get("corners", [])
            data["circuits"][str(tid)] = sync_track(args.year, tid, old_c)
        except Exception as e:
            print(f"⚠️ Mantido perfil local para ID {tid}: {e}")

    with open(args.output, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    print("✅ Sincronização concluída!")


if __name__ == "__main__":
    main()
