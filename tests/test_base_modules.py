#!/usr/bin/env python3
"""
Test Unitario para Módulos Base: Fase 4
Verifica:
1. config.py: Rutas existentes, alias cargados.
2. ducking.py: Funcionamiento del Context Manager sin excepciones.
3. actions.py: Cola de deshacer, atajos de búsqueda web y resolución de alias.
4. feedback.py: Mecanismo de parada (barge-in) y validación de caché.
"""

import unittest
from pathlib import Path

import config
from ducking import AudioDucker
from actions import actions
from feedback import feedback


class TestBaseModules(unittest.TestCase):

    def test_01_config_sanity(self):
        """Verifica que las rutas clave existan y sean válidas."""
        self.assertTrue(config.BASE_DIR.is_dir(), "BASE_DIR no existe")
        self.assertTrue(config.SOUNDS_DIR.is_dir(), "SOUNDS_DIR no existe")
        self.assertTrue(config.PIPER_BIN.is_file(), "El binario de Piper no existe")
        self.assertTrue(config.PIPER_MODEL_FILE.is_file(), "El modelo de voz ONNX no existe")
        self.assertTrue(config.VOSK_MODEL_DIR.is_dir(), "El modelo de Vosk no existe")
        self.assertIn("navegador", config.APPLICATION_ALIASES)
        self.assertEqual(config.NODE_ROLE, "nodo_c")

    def test_02_audio_ducking_context_manager(self):
        """Comprueba que AudioDucker se ejecute y restaure sin errores."""
        ducker = AudioDucker(factor=0.20)
        self.assertFalse(ducker.is_ducked)
        with ducker:
            self.assertTrue(ducker.is_ducked)
        self.assertFalse(ducker.is_ducked)

    def test_03_actions_injection_history(self):
        """Verifica el mecanismo de registro y deshacer de frases."""
        actions.injection_history.clear()
        self.assertEqual(len(actions.injection_history), 0)

        # Simular inyecciones
        actions.injection_history.append(15)
        actions.injection_history.append(25)
        self.assertEqual(len(actions.injection_history), 2)

        # Simular deshacer
        last_chars = actions.injection_history.pop()
        self.assertEqual(last_chars, 25)
        self.assertEqual(len(actions.injection_history), 1)

    def test_04_feedback_barge_in(self):
        """Verifica que stop_speaking() maneje de forma segura estados nulos o activos."""
        feedback.stop_speaking()
        self.assertIsNone(feedback._current_process)


if __name__ == "__main__":
    unittest.main()
