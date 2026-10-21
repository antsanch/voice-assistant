#!/usr/bin/env python3
"""
Test Unitario para Audio Engine y Router: Fase 6
Verifica:
1. audio_engine.py: Modelo Vosk cargado, función de cálculo RMS de energía.
2. router.py: Coincidencias de Fast-Path Regex y clasificación semántica / corrección con Ollama.
"""

import unittest
from audio_engine import audio_engine, calculate_audio_energy
from router import router


class TestAudioEngineAndRouter(unittest.TestCase):

    def test_01_audio_engine_initialization(self):
        """Verifica que el modelo Vosk y los reconocedores estén listos."""
        self.assertIsNotNone(audio_engine.model)
        self.assertIsNotNone(audio_engine.wake_recognizer)
        self.assertIsNotNone(audio_engine.open_recognizer)

        # Probar cálculo RMS con silencio (buffer de ceros)
        silence = b"\x00" * 3200
        energy = calculate_audio_energy(silence)
        self.assertEqual(energy, 0.0)

    def test_02_router_fast_path(self):
        """Verifica el enrutamiento Regex sin latencia."""
        # Multimedia
        src, res = router.route("sube el volumen")
        self.assertEqual(src, "fast_path")
        self.assertEqual(res["intent"], "media")
        self.assertEqual(res["action"], "volume_up")

        # Ventanas
        src, res = router.route("cierra la ventana")
        self.assertEqual(src, "fast_path")
        self.assertEqual(res["intent"], "window")
        self.assertEqual(res["action"], "close")

        # Búsqueda Web
        src, res = router.route("busca en google brocas forstner")
        self.assertEqual(src, "fast_path")
        self.assertEqual(res["intent"], "web_search")
        self.assertEqual(res["text"], "brocas forstner")

        # Modo Dictado
        src, res = router.route("modo dictado")
        self.assertEqual(src, "fast_path")
        self.assertEqual(res["intent"], "dictate")
        self.assertEqual(res["action"], "start")

        # Escritura rápida
        src, res = router.route("escribe mesa de parota")
        self.assertEqual(src, "fast_path")
        self.assertEqual(res["intent"], "quick_type")
        self.assertEqual(res["text"], "mesa de parota")

    def test_03_router_semantic_ollama(self):
        """Verifica que frases no coincidentes se deriven a Ollama y devuelvan JSON estructurado."""
        src, res = router.route("¿cuántos milímetros son 3 cuartos de pulgada?")
        self.assertEqual(src, "semantic_llm")
        self.assertIn("intent", res)
        self.assertEqual(res["intent"], "assistant_answer")
        text_resp = res.get("text", "").lower()
        self.assertTrue(len(text_resp) > 0, "La respuesta no debe estar vacía")
        self.assertTrue(any(token in text_resp for token in ["mm", "milímetro", "milimetro", "19", "pulgada"]))

    def test_04_dictation_corrector_ollama(self):
        """Verifica la corrección ortográfica y de signos con Ollama."""
        raw = "hola coma cómo estás punto"
        corrected = router.correct_dictation_text(raw)
        self.assertIsInstance(corrected, str)
        # Debe contener la coma o el signo de puntuación correspondiente
        self.assertTrue("," in corrected or "¿" in corrected or "." in corrected)


if __name__ == "__main__":
    unittest.main()
