"""Decodificador do pacote de dados de volta (PacketLapData, ID: 2) — F1 25."""

import struct
from dataclasses import dataclass
from typing import Optional
from .header import PacketHeader, HEADER_SIZE_29, HEADER_SIZE_24

LAP_DATA_ENTRY_FORMAT = "<IIHBHBHBHBfff15BHHBfB"
LAP_DATA_ENTRY_SIZE = struct.calcsize(LAP_DATA_ENTRY_FORMAT)  # 57 bytes
MAX_CARS = 24


@dataclass
class LapData:
    last_lap_time_ms: int
    current_lap_time_ms: int
    lap_distance: float
    total_distance: float
    car_position: int
    current_lap_num: int
    sector: int
    current_lap_invalid: bool
    driver_status: int


def calculate_entry_stride(data_len: int, header_size: int) -> int:
    """Calcula o stride exato por carro para pacotes de 22 carros (1285b) ou 24 carros (1399b) no F1 25."""
    body_len = data_len - header_size
    for num_cars in (22, 24, 20):
        for tail_bytes in (2, 0, 3, 4, 1):
            rem = body_len - tail_bytes
            if rem > 0 and rem % num_cars == 0:
                stride = rem // num_cars
                if stride == LAP_DATA_ENTRY_SIZE:
                    return stride
    for num_cars in (22, 24):
        for tail_bytes in (2, 0, 3, 4, 1):
            rem = body_len - tail_bytes
            if rem > 0 and rem % num_cars == 0:
                stride = rem // num_cars
                if 53 <= stride <= 64:
                    return stride
    return LAP_DATA_ENTRY_SIZE


def parse_lap_data(data: bytes, header: PacketHeader) -> Optional[LapData]:
    """Extrai os dados da volta do carro do jogador ativo no F1 25."""
    player_idx = header.player_car_index
    if player_idx < 0 or player_idx >= MAX_CARS:
        return None

    header_size = HEADER_SIZE_29 if len(data) >= (HEADER_SIZE_29 + 20 * LAP_DATA_ENTRY_SIZE) else HEADER_SIZE_24
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
