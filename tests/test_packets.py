"""Testes unitários dos parsers de pacotes UDP do F1."""

import struct
import sys
import os
import unittest

# Adiciona o diretório src ao path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "src")))

from packets.header import (
    HEADER_FORMAT_29,
    PACKET_ID_CAR_TELEMETRY,
    PACKET_ID_LAP_DATA,
    PACKET_ID_SESSION,
    PacketHeader,
    parse_header,
)
from packets.car_telemetry import (
    CAR_TELEMETRY_ENTRY_FORMAT,
    CAR_TELEMETRY_ENTRY_SIZE,
    parse_car_telemetry,
)
from packets.lap_data import (
    LAP_DATA_ENTRY_FORMAT,
    LAP_DATA_ENTRY_SIZE,
    parse_lap_data,
)
from packets.session import (
    SESSION_DATA_FORMAT,
    parse_session_data,
)
from tracks.circuits import get_circuit_by_track_id


class TestPacketParsers(unittest.TestCase):
    def _create_mock_header(self, packet_id: int, player_idx: int = 0) -> bytes:
        return struct.pack(
            HEADER_FORMAT_29,
            2024,  # packetFormat
            24,    # gameYear
            1,     # gameMajorVersion
            0,     # gameMinorVersion
            1,     # packetVersion
            packet_id,
            1234567890, # sessionUID
            125.5,      # sessionTime
            1000,       # frameIdentifier
            1000,       # overallFrameIdentifier
            player_idx, # playerCarIndex
            255,        # secondaryPlayerCarIndex
        )

    def test_parse_header(self):
        header_bytes = self._create_mock_header(PACKET_ID_CAR_TELEMETRY, player_idx=3)
        header = parse_header(header_bytes)
        self.assertIsNotNone(header)
        self.assertEqual(header.packet_format, 2024)
        self.assertEqual(header.packet_id, PACKET_ID_CAR_TELEMETRY)
        self.assertEqual(header.player_car_index, 3)

    def test_parse_car_telemetry(self):
        header_bytes = self._create_mock_header(PACKET_ID_CAR_TELEMETRY, player_idx=0)
        header = parse_header(header_bytes)

        # Cria payload com 22 carros
        single_car = struct.pack(
            CAR_TELEMETRY_ENTRY_FORMAT,
            310,     # speed (km/h)
            1.0,     # throttle
            0.0,     # steer
            0.0,     # brake
            0,       # clutch
            8,       # gear
            12000,   # engineRPM
            1,       # drs
            85,      # revLightsPercent
            1234,    # revLightsBitValue
            450, 450, 500, 500, # brakesTemperature[4]
            95, 95, 90, 90,     # tyresSurfaceTemperature[4]
            100, 100, 95, 95,   # tyresInnerTemperature[4]
            105,     # engineTemperature
            23.5, 23.5, 24.0, 24.0, # tyresPressure[4]
            0, 0, 0, 0 # surfaceType[4]
        )
        packet_bytes = header_bytes + (single_car * 22) + b"\x00\x00\x00"

        telemetry = parse_car_telemetry(packet_bytes, header)
        self.assertIsNotNone(telemetry)
        self.assertEqual(telemetry.speed, 310)
        self.assertAlmostEqual(telemetry.throttle, 1.0)
        self.assertEqual(telemetry.gear, 8)
        self.assertEqual(telemetry.drs, 1)
        self.assertEqual(telemetry.engine_temperature, 105)

    def test_parse_lap_data(self):
        header_bytes = self._create_mock_header(PACKET_ID_LAP_DATA, player_idx=0)
        header = parse_header(header_bytes)

        single_lap = struct.pack(
            LAP_DATA_ENTRY_FORMAT,
            81500,   # lastLapTimeInMS
            42300,   # currentLapTimeInMS
            30000, 1, # sector1
            32000, 1, # sector2
            0, 0,    # delta front
            0, 0,    # delta leader
            1520.5,  # lapDistance
            1520.5,  # totalDistance
            0.0,     # safetyCarDelta
            1,       # carPosition
            3,       # currentLapNum
            0,       # pitStatus
            0,       # numPitStops
            1,       # sector
            0,       # currentLapInvalid (válida)
            0, 0, 0, 0, 0, # penalties, warnings
            1,       # gridPosition
            4,       # driverStatus (on track)
            2,       # resultStatus (active)
            0,       # pitLaneTimerActive
            0, 0, 0, # pit times
            345.5, 3 # speedTrap
        )
        packet_bytes = header_bytes + (single_lap * 22) + b"\xff\xff"

        lap = parse_lap_data(packet_bytes, header)
        self.assertIsNotNone(lap)
        self.assertEqual(lap.last_lap_time_ms, 81500)
        self.assertEqual(lap.current_lap_num, 3)
        self.assertAlmostEqual(lap.lap_distance, 1520.5)
        self.assertFalse(lap.current_lap_invalid)

    def test_parse_session_data(self):
        header_bytes = self._create_mock_header(PACKET_ID_SESSION, player_idx=0)
        header = parse_header(header_bytes)

        session_bytes = header_bytes + struct.pack(
            SESSION_DATA_FORMAT,
            0,       # weather (clear)
            35,      # trackTemp
            26,      # airTemp
            20,      # totalLaps
            5793,    # trackLength (Monza)
            13,      # sessionType (Time Trial)
            11,      # trackId (Monza)
        )

        session = parse_session_data(session_bytes, header)
        self.assertIsNotNone(session)
        self.assertEqual(session.track_id, 11)
        self.assertIn("Monza", session.track_name)
        self.assertEqual(session.track_length, 5793)

    def test_circuits_mapping(self):
        monza = get_circuit_by_track_id(11)
        self.assertIsNotNone(monza)
        self.assertEqual(monza.name, "Autodromo Nazionale Monza")
        self.assertTrue(len(monza.corners) >= 6)


if __name__ == "__main__":
    unittest.main()
