#!/usr/bin/env python3
"""
Módulo: reader.py
Propósito: Lectura por voz de texto seleccionado en pantalla y extracción limpia de páginas web.

Herramientas y Principios:
--------------------------
1. xclip para Selección de Texto X11:
   - Buffer primario (`-selection primary`): Captura cualquier texto que el usuario haya
     resaltado con el ratón sin necesidad de pulsar Ctrl+C.
   - Buffer de portapapeles (`-selection clipboard`): Captura lo copiado con Ctrl+C (ej. una URL).
2. Trafilatura para Extracción Web:
   - Las páginas web modernas contienen entre 60% y 80% de código irrelevante para lectura
     (scripts, publicidad, menús de navegación, avisos de cookies).
   - Trafilatura procesa el árbol DOM HTML y extrae exclusivamente el contenido del artículo
     en texto plano y limpio.
3. Resúmenes Inteligentes con Ollama:
   - Si el artículo es extenso, se puede solicitar a Qwen 2.5 que genere un resumen
     conciso de 2 párrafos enfocado en las ideas principales antes de leerlo.
"""

import json
import subprocess
from typing import Optional
import urllib.parse
import requests

import trafilatura
from config import OLLAMA_URL, MODEL_NAME
from feedback import feedback
from ducking import AudioDucker


class ContentReader:
    """
    Gestor de extracción de contenidos y lectura por voz.
    """

    def get_selected_text(self) -> str:
        """
        Obtiene el texto actualmente seleccionado con el ratón en la interfaz gráfica (X11 Primary).
        """
        try:
            result = subprocess.run(
                ["xclip", "-o", "-selection", "primary"],
                stdout=subprocess.PIPE,
                stderr=subprocess.DEVNULL,
                text=True,
                check=False
            )
            return result.stdout.strip()
        except FileNotFoundError:
            print("[ContentReader] xclip no está disponible.")
            return ""

    def get_clipboard_text(self) -> str:
        """
        Obtiene el contenido actual del portapapeles (Ctrl+C).
        """
        try:
            result = subprocess.run(
                ["xclip", "-o", "-selection", "clipboard"],
                stdout=subprocess.PIPE,
                stderr=subprocess.DEVNULL,
                text=True,
                check=False
            )
            return result.stdout.strip()
        except FileNotFoundError:
            return ""

    def read_selection(self):
        """
        Comando: "lee la selección" o "lee esto".
        Extrae la selección activa y la sintetiza por voz aplicando ducking.
        """
        text = self.get_selected_text()
        if not text:
            # Si el buffer primario está vacío, probar el portapapeles
            text = self.get_clipboard_text()

        if not text:
            feedback.speak("No encontré ningún texto seleccionado para leer.")
            return

        print(f"[ContentReader] Leyendo selección ({len(text)} caracteres)...")
        with AudioDucker(factor=0.20):
            feedback.speak(text)

    def extract_web_article(self, url: str) -> Optional[str]:
        """
        Descarga una página web y extrae el cuerpo principal del texto usando Trafilatura.
        """
        if not url:
            return None

        # Asegurar prefijo de protocolo HTTP/HTTPS
        if not url.startswith("http://") and not url.startswith("https://"):
            url = "https://" + url

        try:
            downloaded = trafilatura.fetch_url(url)
            if not downloaded:
                return None
            article_text = trafilatura.extract(downloaded, include_comments=False, include_tables=False)
            return article_text
        except Exception as e:
            print(f"[ContentReader] Error extrayendo URL {url}: {e}")
            return None

    def summarize_text_with_llm(self, text: str) -> str:
        """
        Envía el texto del artículo a Ollama para sintetizarlo en un resumen breve de 2 párrafos.
        """
        prompt = (
            "Resume el siguiente texto en exactamente dos párrafos claros y directos en español, "
            "ideales para ser leídos en voz alta:\n\n"
            f"{text[:4000]}"  # Truncar a ~4000 caracteres para respuesta rápida
        )

        try:
            response = requests.post(
                f"{OLLAMA_URL}/api/generate",
                json={
                    "model": MODEL_NAME,
                    "prompt": prompt,
                    "stream": False,
                    "keep_alive": -1
                },
                timeout=15.0
            )
            if response.status_code == 200:
                data = response.json()
                return data.get("response", "").strip()
        except Exception as e:
            print(f"[ContentReader] Error en resumen con Ollama: {e}")

        # Fallback si falla Ollama: devolver los primeros 300 caracteres del artículo
        return text[:300] + "..."

    def read_or_summarize_web_page(self, summarize: bool = False, url: Optional[str] = None):
        """
        Comando: "léeme esta página" o "resume esta página".
        """
        target_url = url or self.get_clipboard_text()
        if not target_url or not ("." in target_url and "/" in target_url):
            feedback.speak("No encontré una dirección web válida en el portapapeles.")
            return

        feedback.play_sound("searching.wav")
        article = self.extract_web_article(target_url)

        if not article:
            feedback.speak("No pude extraer el contenido legible de esa página.")
            return

        if summarize:
            feedback.speak("Generando resumen...")
            summary = self.summarize_text_with_llm(article)
            with AudioDucker(factor=0.20):
                feedback.speak(summary)
        else:
            with AudioDucker(factor=0.20):
                feedback.speak(article[:1500])


# Instancia singleton
reader = ContentReader()


if __name__ == "__main__":
    print("Probando reader.py...")
    print(" -> Texto en selección primaria:", repr(reader.get_selected_text()))
    print(" -> Texto en portapapeles:", repr(reader.get_clipboard_text()))
