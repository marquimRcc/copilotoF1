"""Decodificador do pacote de telemetria do carro (PacketCarTelemetryData, ID: 6)."""

import struct
from dataclasses import dataclass
from typing import List, Optional
from .header import PacketHeader, HEADER_SIZE_29

# Formato de cada registro de carro (60 bytes)
# H: speed (uint16)
# f: throttle (float)
# f: steer (float)
# f: brake (float)
# B: clutch (uint8)
# b: gear (int8)
# H: engineRPM (uint16)
# B: drs (uint8)
# B: revLightsPercent (uint8)
# H: revLightsBitValue (uint16)
# 4H: brakesTemperature[4] (uint16)
# 4B: tyresSurfaceTemperature[4] (uint8)
# 4B: tyresInnerTemperature[4] (uint8)
# H: engineTemperature (uint16)
# 4f: tyresPressure[4] (float)
# 4B: surfaceType[4] (uint8)
CAR_TELEMETRY_ENTRY_FORMAT = "<HfffBbHBBH4H4B4BH4f4B"
CAR_TELEMETRY_ENTRY_SIZE = struct.calcsize(CAR_TELEMETRY_ENTRY_FORMAT)  # 60 bytes


@dataclass
class CarTelemetryData:
    speed: int                 # Velocidade em km/h
    throttle: float            # Acelerador (0.0 a 1.0)
    steer: float               # Volante (-1.0 esq a 1.0 dir)
    brake: float               # Freio (0.0 a 1.0)
    clutch: int                # Embreagem (0 a 100)
    gear: int                  # Marcha (-1=R, 0=N, 1 a 8)
    engine_rpm: int            # RPM do motor
    drs: int                   # 0 = desligado, 1 = ligado
    rev_lights_percent: int    # Luzes de rotação (0-100)
    engine_temperature: int    # Temperatura do motor em ºC
    brakes_temperature: List[int] # [RL, RR, FL, FR] em ºC
    tyres_surface_temperature: List[int] # [RL, RR, FL, FR] em ºC


def parse_car_telemetry(data: bytes, header: PacketHeader) -> Optional[CarTelemetryData]:
    """Extrai os dados de telemetria do carro do jogador ativo."""
    player_idx = header.player_car_index
    if player_idx < 0 or player_idx > 23:
        return None

    # Offset inicial após o header
    header_size = HEADER_SIZE_29 if len(data) >= (HEADER_SIZE_29 + 22 * CAR_TELEMETRY_ENTRY_SIZE) else 24
    offset = header_size + (player_idx * CAR_TELEMETRY_ENTRY_SIZE)

    if len(data) < offset + CAR_TELEMETRY_ENTRY_SIZE:
        return None

    fields = struct.unpack_from(CAR_TELEMETRY_ENTRY_FORMAT, data, offset)
    return CarTelemetryData(
        speed=fields[0],
        throttle=round(fields[1], 4),
        steer=round(fields[2], 4),
        brake=round(fields[3], 4),
        clutch=fields[4],
        gear=fields[5],
        engine_rpm=fields[6],
        drs=fields[7],
        rev_lights_percent=fields[8],
        brakes_temperature=[fields[10], fields[11], fields[12], fields[13]],
        tyres_surface_temperature=[fields[14], fields[15], fields[16], fields[17]],
        engine_temperature=fields[22],
    )
