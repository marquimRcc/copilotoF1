"""Decodificador do pacote de sessão (PacketSessionData, ID: 1) — Especificação F1 25."""

import struct
from dataclasses import dataclass
from typing import Optional
from .header import PacketHeader, HEADER_SIZE_29

# Formato dos primeiros campos do PacketSessionData após o Header (29 bytes):
# B: weather (uint8)
# b: trackTemperature (int8)
# b: airTemperature (int8)
# B: totalLaps (uint8)
# H: trackLength (uint16)
# B: sessionType (uint8)
# b: trackId (int8)
SESSION_DATA_FORMAT = "<BbbBHBb"
SESSION_DATA_SIZE = struct.calcsize(SESSION_DATA_FORMAT)  # 8 bytes

# Mapeamento oficial EA SPORTS F1 25 de pistas (Track IDs)
TRACK_NAMES = {
    0: "Melbourne (Austrália)",
    1: "Paul Ricard (França)",
    2: "Shanghai (China)",
    3: "Sakhir (Bahrein)",
    4: "Catalunya (Espanha)",
    5: "Monaco (Mônaco)",
    6: "Montreal (Canadá)",
    7: "Silverstone (Grã-Bretanha)",
    8: "Hockenheim (Alemanha)",
    9: "Hungaroring (Hungria)",
    10: "Spa-Francorchamps (Bélgica)",
    11: "Monza (Itália)",
    12: "Singapura",
    13: "Suzuka (Japão)",
    14: "Abu Dhabi",
    15: "Austin / COTA (EUA)",
    16: "Interlagos (Brasil)",
    17: "Red Bull Ring (Áustria)",
    18: "Sochi (Rússia)",
    19: "Cidade do México",
    20: "Baku (Azerbaijão)",
    21: "Portimão (Portugal)",
    22: "Jeddah (Arábia Saudita)",
    23: "Miami (EUA)",
    24: "Las Vegas (EUA)",
    25: "Losail (Catar)",
    26: "Zandvoort (Holanda)",
    27: "Imola (Itália)",
    29: "Jeddah (Arábia Saudita)",
    30: "Miami (EUA)",
    31: "Las Vegas (EUA)",
    32: "Losail (Catar)",
}

SESSION_TYPES = {
    0: "Desconhecido",
    1: "Treino Livre 1 (FP1)",
    2: "Treino Livre 2 (FP2)",
    3: "Treino Livre 3 (FP3)",
    4: "Treino Curto",
    5: "Classificação 1 (Q1)",
    6: "Classificação 2 (Q2)",
    7: "Classificação 3 (Q3)",
    8: "Classificação Curta",
    9: "Classificação One-Shot",
    10: "Corrida",
    11: "Corrida 2",
    12: "Corrida 3",
    13: "Time Trial (Tomada de Tempo)",
    14: "Time Trial (F1 25)",
}


@dataclass
class SessionData:
    weather: int
    track_temperature: int
    air_temperature: int
    total_laps: int
    track_length: int          # Comprimento da pista em metros
    session_type: int
    session_type_name: str
    track_id: int
    track_name: str


def parse_session_data(data: bytes, header: PacketHeader) -> Optional[SessionData]:
    """Extrai informações da sessão e do circuito atual (F1 25)."""
    header_size = HEADER_SIZE_29 if len(data) >= (HEADER_SIZE_29 + SESSION_DATA_SIZE) else 24
    if len(data) < header_size + SESSION_DATA_SIZE:
        return None

    fields = struct.unpack_from(SESSION_DATA_FORMAT, data, header_size)
    track_id = fields[6]
    session_type = fields[5]

    return SessionData(
        weather=fields[0],
        track_temperature=fields[1],
        air_temperature=fields[2],
        total_laps=fields[3],
        track_length=fields[4],
        session_type=session_type,
        session_type_name=SESSION_TYPES.get(session_type, f"Tipo {session_type}"),
        track_id=track_id,
        track_name=TRACK_NAMES.get(track_id, f"Circuito ID {track_id}"),
    )
