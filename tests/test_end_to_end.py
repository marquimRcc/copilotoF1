"""Teste de ponta a ponta: emissão UDP simulada -> gravação CSV -> análise prática."""

import glob
import os
import shutil
import sys
import threading
import time
import unittest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "src")))

from recorder import F1TelemetryRecorder
from analyzer import LapAnalyzer, load_telemetry_csv
from tests.mock_sender import send_simulated_lap


class TestEndToEndPipeline(unittest.TestCase):
    def setUp(self):
        self.test_output_dir = os.path.join(os.path.dirname(__file__), "test_data")
        os.makedirs(self.test_output_dir, exist_ok=True)
        # Limpa dados anteriores
        for f in glob.glob(os.path.join(self.test_output_dir, "*.csv")):
            os.remove(f)

    def tearDown(self):
        if os.path.exists(self.test_output_dir):
            shutil.rmtree(self.test_output_dir)

    def test_record_and_analyze(self):
        test_port = 20788
        recorder = F1TelemetryRecorder(host="127.0.0.1", port=test_port, output_dir=self.test_output_dir)

        # Inicia o gravador em uma thread separada
        recorder_thread = threading.Thread(target=recorder.start, daemon=True)
        recorder_thread.start()
        time.sleep(0.2)  # Aguarda socket abrir

        # Emite os dados simulados na porta dedicada de teste
        send_simulated_lap(port=test_port)
        time.sleep(0.5)  # Aguarda salvar

        # Para o gravador
        recorder.close()

        # Verifica se o arquivo CSV foi gerado
        csv_files = glob.glob(os.path.join(self.test_output_dir, "*.csv"))
        self.assertTrue(len(csv_files) >= 1, "Deveria ter gerado pelo menos 1 arquivo CSV de volta.")

        generated_csv = csv_files[0]
        points = load_telemetry_csv(generated_csv)
        self.assertTrue(len(points) >= 50, f"Deveria ter registrado amostras suficientes. Total: {len(points)}")

        # Executa o motor de análise
        analyzer = LapAnalyzer(track_id=11)  # Monza
        report = analyzer.compare_laps(points)

        self.assertIn("MONZA", report)
        self.assertIn("Variante del Rettifilo", report)
        self.assertIn("Ponto de Frenagem", report)


if __name__ == "__main__":
    unittest.main()
