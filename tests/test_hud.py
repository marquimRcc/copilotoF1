"""Testes unitários da máquina de estados do HUD do Copiloto F1."""

import os
import sys
import unittest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "src")))

from tracks.circuits import get_circuit_by_track_id
from hud.overlay import F1HudOverlay


class TestHudStateMachine(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        # Instancia uma única janela HUD para a suíte de testes
        cls.hud = F1HudOverlay(port=29999, record_csv=False)

    @classmethod
    def tearDownClass(cls):
        cls.hud.on_close()

    def setUp(self):
        self.hud.track_id = 11  # Monza
        self.hud.circuit = get_circuit_by_track_id(11)
        self.hud.state.speed = 0

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



    def test_theme_and_layout_switching(self):
        from hud.overlay import THEMES
        for theme_key in THEMES:
            self.hud.set_theme(theme_key)
            self.assertEqual(self.hud.active_theme, theme_key)
        for layout_id in (1, 2, 3):
            self.hud.set_layout(layout_id)
            self.assertEqual(self.hud.active_layout, layout_id)



    def test_manual_track_selection(self):
        self.hud.set_track(16, manual=True)
        self.assertEqual(self.hud.track_id, 16)
        self.assertTrue(self.hud.manual_track_override)
        self.assertIn("Interlagos", self.hud.track_name)


if __name__ == "__main__":
    unittest.main()
