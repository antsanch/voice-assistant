#!/usr/bin/env python3
"""
Test Unitario para Cast Control: Fase 7
Verifica:
1. Mapeo correcto de dispositivos Roku, Chromecast y LG webOS.
2. Formateo de comandos ECP de Roku.
3. Modo tolerante a fallos fuera de casa (Safe Mocking / Timeouts suaves).
"""

import unittest
from unittest.mock import patch, MagicMock

from cast_control import cast_control, ROKU_APP_IDS


class TestCastControl(unittest.TestCase):

    def test_01_device_registry(self):
        """Verifica que los dispositivos base estén configurados."""
        self.assertIn("tele_sala", cast_control.devices)
        self.assertIn("roku_cuarto", cast_control.devices)
        self.assertIn("chromecast_sala", cast_control.devices)
        self.assertIn("youtube", ROKU_APP_IDS)

    @patch("requests.post")
    def test_02_roku_command_dispatch(self, mock_post):
        """Verifica que execute_command envíe la petición HTTP REST ECP correcta."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_post.return_value = mock_response

        success = cast_control.execute_command("tele_sala", "pause")
        self.assertTrue(success)

        # Comprobar URL llamada
        expected_url = f"http://{cast_control.devices['tele_sala']['ip']}:8060/keypress/Pause"
        mock_post.assert_called_once_with(expected_url, timeout=1.5)

    def test_03_offline_safety_no_exceptions(self):
        """Verifica que al no estar en casa, el comando retorne False con gracia sin colgarse."""
        # Se asume que 192.168.254.254 no está presente actualmente
        fake_control = cast_control
        fake_control.devices["fake_tv"] = {"type": "roku", "ip": "192.168.254.254", "port": 8060}

        result = fake_control.execute_command("fake_tv", "play")
        self.assertFalse(result, "Debe retornar False al estar offline")


if __name__ == "__main__":
    unittest.main()
