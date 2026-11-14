"""Testes unitários da máquina de estados do HUD do Copiloto F1."""

import os
import sys
import unittest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "src")))

from tracks.circuits import get_circuit_by_track_id
from hud.overlay import F1HudOverlay


class TestHudStateMachine(unittest.TestCase):
    def setUp(self):
        # Instancia o HUD com gravação desativada para teste
        self.hud = F1HudOverlay(port=29999, record_csv=False)
        self.hud.track_id = 11  # Monza
        self.hud.circuit = get_circuit_by_track_id(11)

    def tearDown(self):
        self.hud.on_close()

    def test_corner_state_machine_monza(self):
        # 1. Reta dos Boxes (distância = 200m, C1 começa aos 420m)
        self.hud.lap_distance = 200.0
        self.hud._update_corner_logic()
        self.assertEqual(self.hud.current_state, "reta")
        self.assertAlmostEqual(self.hud.dist_to_brake, 220.0, delta=1.0)

        # 2. Zona de Preparação (a 45m do freio: 375m)
        self.hud.lap_distance = 375.0
        self.hud._update_corner_logic()
        self.assertEqual(self.hud.current_state, "preparo")

        # 3. Ponto de Frenagem (430m)
        self.hud.lap_distance = 430.0
        self.hud._update_corner_logic()
        self.assertEqual(self.hud.current_state, "freia")

        # 4. Ápice da Curva 1 (620m)
        self.hud.lap_distance = 620.0
        self.hud._update_corner_logic()
        self.assertEqual(self.hud.current_state, "apice")

        # 5. Saída e Aceleração (830m)
        self.hud.lap_distance = 830.0
        self.hud._update_corner_logic()
        self.assertEqual(self.hud.current_state, "acelera")

        # 6. Volta à reta / Curva Grande (1000m)
        self.hud.lap_distance = 1000.0
        self.hud._update_corner_logic()
        self.assertEqual(self.hud.current_state, "reta")


if __name__ == "__main__":
    unittest.main()
