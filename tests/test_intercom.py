#!/usr/bin/env python3
"""
Test Unitario para Intercomunicador: Fase 8
Verifica:
1. Inicio del servidor HTTP en segundo plano.
2. Recepción de payload POST /message y respuesta JSON 200.
3. Cierre correcto del servidor HTTP.
"""

import time
import unittest
import requests

from intercom import IntercomService


class TestIntercom(unittest.TestCase):

    def test_01_http_message_reception(self):
        """Inicia un servidor de intercomunicador en puerto temporal y envía un mensaje local."""
        test_port = 8799
        service = IntercomService(port=test_port)
        service.start_server()
        time.sleep(0.5)

        try:
            url = f"http://127.0.0.1:{test_port}/message"
            payload = {"from": "test_suite", "text": "Verificación de intercomunicador"}
            resp = requests.post(url, json=payload, timeout=2.0)
            self.assertEqual(resp.status_code, 200)
            data = resp.json()
            self.assertEqual(data.get("status"), "ok")
        finally:
            service.stop_server()


if __name__ == "__main__":
    unittest.main()
