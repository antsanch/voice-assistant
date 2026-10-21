#!/usr/bin/env python3
"""
Test Unitario para Reader y Notifications: Fase 5
Verifica:
1. reader.py: Extracción con trafilatura y conexión con Ollama para resúmenes.
2. notifications.py: Control de estados (enable/disable), filtrado de aplicaciones permitidas.
"""

import unittest
from unittest.mock import MagicMock, patch

import trafilatura
from reader import reader
from notifications import notification_monitor, ALLOWED_APP_NAMES


class TestReaderAndNotifications(unittest.TestCase):

    def test_01_trafilatura_extraction(self):
        """Verifica que trafilatura extraiga correctamente el contenido de un artículo."""
        sample_html = """
        <html>
            <head><title>Título de Prueba</title></head>
            <body>
                <nav><a href="#">Inicio</a><a href="#">Contacto</a></nav>
                <article>
                    <h1>Guía de Ensambles de Madera</h1>
                    <p>El ensamble de caja y espiga es uno de los métodos más resistentes en carpintería tradicional.</p>
                </article>
                <footer>Derechos Reservados 2026</footer>
            </body>
        </html>
        """
        extracted = trafilatura.extract(sample_html)
        self.assertIsNotNone(extracted)
        self.assertIn("caja y espiga", extracted)
        # Asegurarse de que el menú y pie de página fueron limpiados
        self.assertNotIn("Inicio", extracted)
        self.assertNotIn("Contacto", extracted)

    def test_02_ollama_summarization(self):
        """Verifica que el generador de resúmenes conecte con el Ollama en Docker."""
        sample_text = (
            "El roble blanco es una madera dura ampliamente utilizada en ebanistería fina "
            "debido a su grano cerrado y su resistencia natural a la humedad y hongos. "
            "Es ideal para muebles de exterior y pisos de alto tránsito."
        )
        summary = reader.summarize_text_with_llm(sample_text)
        self.assertIsInstance(summary, str)
        self.assertTrue(len(summary) > 0, "El resumen de Ollama no debe estar vacío")

    def test_03_notification_monitor_toggle(self):
        """Verifica la activación y desactivación de la lectura de notificaciones."""
        notification_monitor.enable()
        self.assertTrue(notification_monitor.enabled)

        notification_monitor.disable()
        self.assertFalse(notification_monitor.enabled)

        notification_monitor.toggle()
        self.assertTrue(notification_monitor.enabled)

    def test_04_notification_app_filter(self):
        """Verifica que las aplicaciones clave estén contempladas en el filtro."""
        self.assertIn("telegram", ALLOWED_APP_NAMES)
        self.assertIn("whatsapp", ALLOWED_APP_NAMES)
        self.assertIn("firefox", ALLOWED_APP_NAMES)


if __name__ == "__main__":
    unittest.main()
