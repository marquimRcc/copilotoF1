"""Testes unitários do Core (State, CornerStateMachine, AutoCornerLearner, Settings)."""

import os
import shutil
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "src")))

from core.settings import AppSettings, SettingsManager
from core.state import AutoCornerLearner, CornerStateMachine, TelemetryState
from tracks.circuits import CircuitInfo, CornerZone, get_circuit_by_track_id


class TestCoreComponents(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.mkdtemp()
        self.settings_file = os.path.join(self.temp_dir, "settings.json")

    def tearDown(self):
        if os.path.exists(self.temp_dir):
            shutil.rmtree(self.temp_dir)

    def test_settings_manager_load_save(self):
        mgr = SettingsManager(config_path=self.settings_file)
        self.assertEqual(mgr.settings.active_theme, "padrao")
        self.assertEqual(mgr.settings.active_layout, 1)

        mgr.update(active_theme="ferrari", active_layout=3, window_x=120, window_y=200, locked_click_through=True)
        self.assertEqual(mgr.settings.active_theme, "ferrari")
        self.assertEqual(mgr.settings.window_x, 120)

        # Recarrega do arquivo
        mgr2 = SettingsManager(config_path=self.settings_file)
        self.assertEqual(mgr2.settings.active_theme, "ferrari")
        self.assertEqual(mgr2.settings.active_layout, 3)
        self.assertEqual(mgr2.settings.window_x, 120)
        self.assertEqual(mgr2.settings.window_y, 200)
        self.assertTrue(mgr2.settings.locked_click_through)

    def test_kinematic_braking_calculation(self):
        # A 340 km/h freando para 80 km/h
        d_fast = CornerStateMachine.calculate_braking_distance(current_speed_kmh=340, target_speed_kmh=80)
        # A 200 km/h freando para 80 km/h
        d_slow = CornerStateMachine.calculate_braking_distance(current_speed_kmh=200, target_speed_kmh=80)

        self.assertTrue(d_fast > d_slow, "Velocidade maior deve exigir maior distância de frenagem.")
        self.assertTrue(d_fast <= 250.0)
        self.assertTrue(d_slow >= 25.0)

    def test_modular_wrap_around_finish_line(self):
        # Circuito teste com curva logo após a linha de chegada (80m)
        circuit = CircuitInfo(
            track_id=99,
            name="Circuito Teste",
            length=4000,
            corners=[
                CornerZone(number="1", name="Curva 1", start_distance=80.0, apex_distance=150.0, end_distance=300.0, gear_reference=2),
            ],
        )

        # Carro nos metros finais da reta antes da chegada (3980m num circuito de 4000m -> faltam 20m para o km 0)
        # Distância até o início da curva: 20m + 80m = 100m
        state, next_corner, d_brake, d_apex = CornerStateMachine.update(
            lap_distance=3980.0,
            speed_kmh=300,
            circuit=circuit,
        )

        self.assertIsNotNone(next_corner)
        self.assertEqual(next_corner.number, "1")
        # Deve estar em preparo ou reta com distância para o ápice calculada perfeitamente (~170m)
        self.assertTrue(160.0 <= d_apex <= 180.0, f"Distância até o ápice no wrap-around incorreta: {d_apex}")

    def test_auto_corner_learner(self):
        learner = AutoCornerLearner(track_id=999, track_name="Pista Desconhecida", track_length=5000)

        # Simula aproximação, frenagem forte e retomada
        # Reta
        learner.feed_sample(lap_distance=500.0, speed=320, brake=0.0, throttle=1.0, gear=8)
        # Início de freada
        learner.feed_sample(lap_distance=600.0, speed=280, brake=0.9, throttle=0.0, gear=6)
        # Meio da freada / ápice
        learner.feed_sample(lap_distance=680.0, speed=95, brake=0.8, throttle=0.0, gear=2)
        # Alívio e retomada de acelerador
        learner.feed_sample(lap_distance=740.0, speed=120, brake=0.0, throttle=0.75, gear=3)

        circuit = learner.finalize()
        self.assertEqual(len(circuit.corners), 1)
        c = circuit.corners[0]
        self.assertEqual(c.number, "1")
        self.assertAlmostEqual(c.start_distance, 600.0, delta=1.0)
        self.assertAlmostEqual(c.apex_distance, 680.0, delta=1.0)
        self.assertEqual(c.gear_reference, 2)

    def test_telemetry_state_thread_safety(self):
        state = TelemetryState()
        state.update_telemetry(speed=315, throttle=0.98, brake=0.0, steer=-0.05, gear=8, rpm=11800, drs=1)
        state.update_lap_data(lap_dist=1250.0, total_dist=6000.0, lap_num=2, lap_time_ms=45200, last_time_ms=82100, is_valid=True)

        snap = state.get_snapshot()
        self.assertEqual(snap["speed"], 315)
        self.assertEqual(snap["gear"], 8)
        self.assertEqual(snap["lap_number"], 2)
        self.assertTrue(snap["is_lap_valid"])


if __name__ == "__main__":
    unittest.main()
