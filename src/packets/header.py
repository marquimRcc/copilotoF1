"""Decodificador do cabeçalho comum (PacketHeader) de pacotes UDP do F1."""

import struct
from dataclasses import dataclass
from typing import Optional

# Cabeçalho padrão F1 23 / F1 24 / F1 25: 29 bytes
# uint16 packetFormat
# uint8  gameYear
# uint8  gameMajorVersion
# uint8  gameMinorVersion
# uint8  packetVersion
# uint8  packetId
# uint64 sessionUID
# float  sessionTime
# uint32 frameIdentifier
# uint32 overallFrameIdentifier
# uint8  playerCarIndex
# uint8  secondaryPlayerCarIndex
HEADER_FORMAT_29 = "<HBBBBBQfIIBB"
HEADER_SIZE_29 = struct.calcsize(HEADER_FORMAT_29)  # 29 bytes

# Cabeçalho legado (F1 2020 - 2022): 24 bytes
HEADER_FORMAT_24 = "<HBBBBBQfIB"
HEADER_SIZE_24 = struct.calcsize(HEADER_FORMAT_24)  # 24 bytes

HEADER_SIZE = HEADER_SIZE_29


# Identificadores de Pacote (Packet IDs)
PACKET_ID_MOTION = 0
PACKET_ID_SESSION = 1
PACKET_ID_LAP_DATA = 2
PACKET_ID_EVENT = 3
PACKET_ID_PARTICIPANTS = 4
PACKET_ID_CAR_SETUPS = 5
PACKET_ID_CAR_TELEMETRY = 6
PACKET_ID_CAR_STATUS = 7
PACKET_ID_FINAL_CLASSIFICATION = 8
PACKET_ID_LOBBY_INFO = 9
PACKET_ID_CAR_DAMAGE = 10
PACKET_ID_SESSION_HISTORY = 11
PACKET_ID_TYRE_SETS = 12
PACKET_ID_MOTION_EX = 13
PACKET_ID_TIME_TRIAL = 14


@dataclass
class PacketHeader:
    packet_format: int          # Ano do formato do pacote (ex: 2024)
    game_year: int              # Últimos 2 dígitos do ano (ex: 24)
    game_major_version: int     # Versão principal
    game_minor_version: int     # Versão secundária
    packet_version: int         # Versão do pacote
    packet_id: int              # ID do pacote (ex: 2=LapData, 6=CarTelemetry)
    session_uid: int            # ID único da sessão
    session_time: float         # Timestamp da sessão em segundos
    frame_identifier: int       # Identificador do quadro
    overall_frame_identifier: int # Identificador contínuo do quadro
    player_car_index: int       # Índice do carro do jogador no grid (0-21)
    secondary_player_car_index: int # Segundo jogador (splitscreen)


def parse_header(data: bytes) -> Optional[PacketHeader]:
    """Decodifica os bytes do cabeçalho UDP."""
    if len(data) >= HEADER_SIZE_29:
        fields = struct.unpack_from(HEADER_FORMAT_29, data, 0)
        return PacketHeader(
            packet_format=fields[0],
            game_year=fields[1],
            game_major_version=fields[2],
            game_minor_version=fields[3],
            packet_version=fields[4],
            packet_id=fields[5],
            session_uid=fields[6],
            session_time=fields[7],
            frame_identifier=fields[8],
            overall_frame_identifier=fields[9],
            player_car_index=fields[10],
            secondary_player_car_index=fields[11],
        )
    elif len(data) >= HEADER_SIZE_24:
        fields = struct.unpack_from(HEADER_FORMAT_24, data, 0)
        return PacketHeader(
            packet_format=fields[0],
            game_year=fields[1],
            game_major_version=fields[2],
            game_minor_version=fields[3],
            packet_version=fields[4],
            packet_id=fields[5],
            session_uid=fields[6],
            session_time=fields[7],
            frame_identifier=fields[8],
            overall_frame_identifier=fields[8],
            player_car_index=fields[9],
            secondary_player_car_index=255,
        )
    return None
