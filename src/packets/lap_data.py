"""Decodificador do pacote de dados de volta (PacketLapData, ID: 2)."""

import struct
from dataclasses import dataclass
from typing import Optional
from .header import PacketHeader, HEADER_SIZE_29

# Formato de cada registro de carro no LapData (57 bytes no F1 23 / 24 / 25)
LAP_DATA_ENTRY_FORMAT = "<IIHBHBHBHBfff15BHHBfB"
LAP_DATA_ENTRY_SIZE = struct.calcsize(LAP_DATA_ENTRY_FORMAT)  # 57 bytes


@dataclass
class LapData:
    last_lap_time_ms: int        # Tempo da última volta em milissegundos
    current_lap_time_ms: int     # Tempo da volta atual em milissegundos
    lap_distance: float          # Distância percorrida na volta em metros
    total_distance: float        # Distância total percorrida na sessão
    car_position: int            # Posição na corrida / sessão (1 a 22)
    current_lap_num: int         # Número da volta atual
    sector: int                  # 0 = Setor 1, 1 = Setor 2, 2 = Setor 3
    current_lap_invalid: bool    # True se a volta foi invalidada (cortou curva/excedeu limites)
    driver_status: int           # 0=na garagem, 1=volta lançada, 2=volta de retorno, 3=volta de saída, 4=em pista


def parse_lap_data(data: bytes, header: PacketHeader) -> Optional[LapData]:
    """Extrai os dados da volta do carro do jogador ativo."""
    player_idx = header.player_car_index
    if player_idx < 0 or player_idx > 21:
        return None

    header_size = HEADER_SIZE_29 if len(data) >= (HEADER_SIZE_29 + 22 * LAP_DATA_ENTRY_SIZE) else 24
    offset = header_size + (player_idx * LAP_DATA_ENTRY_SIZE)

    if len(data) < offset + LAP_DATA_ENTRY_SIZE:
        return None

    fields = struct.unpack_from(LAP_DATA_ENTRY_FORMAT, data, offset)
    return LapData(
        last_lap_time_ms=fields[0],
        current_lap_time_ms=fields[1],
        lap_distance=round(fields[10], 2),
        total_distance=round(fields[11], 2),
        car_position=fields[13],
        current_lap_num=fields[14],
        sector=fields[17],
        current_lap_invalid=bool(fields[18]),
        driver_status=fields[25],
    )
