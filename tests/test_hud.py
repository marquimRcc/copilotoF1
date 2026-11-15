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

    def test_interlagos_time_trial_and_grid_start(self):
        """Valida comportamento real do F1 25: Tomada de Tempo em Interlagos e Grid de Largada."""
        from tracks.circuits import get_circuit_by_track_id
        interlagos = get_circuit_by_track_id(16)
        self.hud.state.circuit = interlagos

        # 1. Spawn no Time Trial antes da reta (2833.4m em pista de 4309m com cronômetro em 0)
        self.hud.state.lap_distance = 2833.4
        self.hud.state.lap_time_ms = 0
        self.hud.state.driver_status = 1
        self.hud._update_corner_logic()
        self.assertEqual(self.hud.current_state, "lancamento")
        self.assertAlmostEqual(self.hud.dist_to_brake, 4309 - 2833.4, delta=0.5)
        self.assertEqual(self.hud.next_corner.name, "S do Senna")

        # 2. Carro acelerando na subida dos boxes (3800m, cronômetro ainda em 0)
        self.hud.state.lap_distance = 3800.0
        self.hud.state.lap_time_ms = 0
        self.hud._update_corner_logic()
        self.assertEqual(self.hud.current_state, "lancamento")
        self.assertAlmostEqual(self.hud.dist_to_brake, 509.0, delta=0.5)

        # 3. Cruzou a linha de largada! (lap_distance = 10m, lap_time_ms > 0)
        self.hud.state.lap_distance = 10.0
        self.hud.state.lap_time_ms = 150
        self.hud.state.speed = 280
        self.hud._update_corner_logic()
        self.assertEqual(self.hud.current_state, "reta")
        self.assertEqual(self.hud.next_corner.name, "S do Senna")

        # 4. Grid de Largada em corrida (carro parado na largada, dist = 0.0m, speed = 0, lap_time_ms = 0)
        self.hud.state.lap_distance = 0.0
        self.hud.state.speed = 0
        self.hud.state.lap_time_ms = 0
        self.hud._update_corner_logic()
        self.assertEqual(self.hud.current_state, "lancamento")
        self.assertEqual(self.hud.dist_to_brake, 0.0)

        # 5. Sequência completa de frenagem e contorno do S do Senna a 280 km/h
        # Aproximação / Preparação (150m da volta, antes do ápice de 380m)
        self.hud.state.lap_distance = 150.0
        self.hud.state.speed = 280
        self.hud.state.lap_time_ms = 2500
        self.hud._update_corner_logic()
        self.assertEqual(self.hud.current_state, "preparo", "Antes do ponto de freio deve estar em preparo, jamais acelera!")

        # Zona de Frenagem Máxima (240m da volta)
        self.hud.state.lap_distance = 240.0
        self.hud._update_corner_logic()
        self.assertEqual(self.hud.current_state, "freia", "No ponto de freada deve comandar freio imediato!")

        # Zona de Ápice (380m da volta)
        self.hud.state.lap_distance = 380.0
        self.hud._update_corner_logic()
        self.assertEqual(self.hud.current_state, "apice", "No ápice geométrico deve estar em ápice!")

        # Zona de Saída / Tração (480m da volta)
        self.hud.state.lap_distance = 480.0
        self.hud._update_corner_logic()
        self.assertEqual(self.hud.current_state, "acelera", "Na saída da curva deve comandar aceleração progressiva!")



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


    def test_best_session_lap_display(self):
        """Valida que o tempo da melhor volta da sessão é formatado e exibido permanentemente no topo."""
        # Sem voltas completas
        self.hud.state.best_session_lap_ms = None
        self.assertEqual(self.hud._format_lap_time(None), "BEST: --:--.---")
        self.assertEqual(self.hud._format_lap_time(0), "BEST: --:--.---")

        # Com melhor volta registrada (1m 12s 450ms = 72450 ms)
        self.hud.state.best_session_lap_ms = 72450
        formatted = self.hud._format_lap_time(72450)
        self.assertEqual(formatted, "BEST: 01:12.450")

        # Garante que os widgets de título central existem em todos os layouts
        self.assertIsNotNone(self.hud.l1_lbl_best)
        self.assertIsNotNone(self.hud.l2_lbl_best)
        self.assertIsNotNone(self.hud.l3_lbl_best)


if __name__ == "__main__":
    unittest.main()
