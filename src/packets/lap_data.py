"""Decodificador do pacote de dados de volta (PacketLapData, ID: 2) — F1 23/24/25."""

import struct
from dataclasses import dataclass
from typing import Optional
from .header import PacketHeader, HEADER_SIZE_29, HEADER_SIZE_24

# Formato base de cada registro de carro no LapData (57 bytes)
LAP_DATA_ENTRY_FORMAT = "<IIHBHBHBHBfff15BHHBfB"
LAP_DATA_ENTRY_SIZE = struct.calcsize(LAP_DATA_ENTRY_FORMAT)  # 57 bytes
TOTAL_CARS = 22


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


def calculate_entry_stride(data_len: int, header_size: int) -> int:
    """Calcula dinamicamente o stride em bytes por carro para evitar corrupção em strides > 57 bytes."""
    body_len = data_len - header_size
    if body_len < TOTAL_CARS * LAP_DATA_ENTRY_SIZE:
        return LAP_DATA_ENTRY_SIZE

    # Verifica se há bytes de cauda (ex: 2 a 4 bytes de Time Trial / flags no F1 24/25)
    for tail_bytes in (0, 2, 3, 4, 1):
        if (body_len - tail_bytes) >= (TOTAL_CARS * LAP_DATA_ENTRY_SIZE):
            stride = (body_len - tail_bytes) // TOTAL_CARS
            if stride >= LAP_DATA_ENTRY_SIZE and ((stride * TOTAL_CARS) + tail_bytes == body_len):
                return stride

    # Fallback seguro: divisão direta descartando resto
    candidate = body_len // TOTAL_CARS
    return candidate if candidate >= LAP_DATA_ENTRY_SIZE else LAP_DATA_ENTRY_SIZE


def parse_lap_data(data: bytes, header: PacketHeader) -> Optional[LapData]:
    """Extrai os dados da volta do carro do jogador ativo (cálculo dinâmico de stride F1 25)."""
    player_idx = header.player_car_index
    if player_idx < 0 or player_idx >= TOTAL_CARS:
        return None

    header_size = HEADER_SIZE_29 if len(data) >= (HEADER_SIZE_29 + TOTAL_CARS * LAP_DATA_ENTRY_SIZE) else HEADER_SIZE_24
    if len(data) < header_size + (TOTAL_CARS * LAP_DATA_ENTRY_SIZE):
        return None

    entry_stride = calculate_entry_stride(len(data), header_size)
    offset = header_size + (player_idx * entry_stride)

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
