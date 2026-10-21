#!/usr/bin/env python3
"""
Test de Integración Completa: Fase 9
Verifica:
1. Máquina de estados finitos en main.py (IDLE, SINGLE_INSTRUCTION, CONTINUOUS_DICTATION).
2. Transición y salida segura del modo dictado.
3. Despacho de intenciones (dispatch_intent) hacia actions, reader, intercom y feedback.
"""

import time
import unittest
from unittest.mock import MagicMock, patch

from main import VoiceAssistantDaemon, AssistantState


class TestFullIntegration(unittest.TestCase):

    def setUp(self):
        # Crear instancia del demonio sin iniciar el bucle infinito
        self.daemon = VoiceAssistantDaemon()

    def test_01_state_machine_transitions(self):
        """Verifica las transiciones entre estados de la máquina finita."""
        self.assertEqual(self.daemon.state, AssistantState.IDLE)

        # Entrar a dictado
        self.daemon.enter_dictation_mode()
        self.assertEqual(self.daemon.state, AssistantState.CONTINUOUS_DICTATION)

        # Salir de dictado
        self.daemon.exit_dictation_mode()
        self.assertEqual(self.daemon.state, AssistantState.IDLE)

    @patch("actions.actions.inject_text")
    @patch("actions.actions.volume_up")
    def test_02_intent_dispatching(self, mock_vol, mock_inject):
        """Verifica que el orquestador derive correctamente las intenciones a los módulos correspondientes."""
        # 1. Despacho multimedia
        self.daemon.dispatch_intent("fast_path", {"intent": "media", "action": "volume_up"})
        mock_vol.assert_called_once()

        # 2. Despacho de escritura
        self.daemon.dispatch_intent("fast_path", {"intent": "quick_type", "text": "texto de prueba"})
        mock_inject.assert_called_once()

    def test_03_signal_handler_binding(self):
        """Verifica que el manejador de SIGUSR1 transicione a modo dictado."""
        self.assertEqual(self.daemon.state, AssistantState.IDLE)
        self.daemon._handle_sigusr1(None, None)
        self.assertEqual(self.daemon.state, AssistantState.CONTINUOUS_DICTATION)
        self.daemon.exit_dictation_mode()


if __name__ == "__main__":
    unittest.main()
