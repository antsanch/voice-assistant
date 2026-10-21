#!/usr/bin/env python3
"""
Módulo: intercom.py
Propósito: Servidor y cliente HTTP ultraligero para intercomunicación bidireccional en red local.

Arquitectura de Transporte Ligero:
----------------------------------
1. Sin Dependencias Pesadas ni Servicios Externos:
   Se utiliza el módulo estándar `http.server` de Python ejecutándose en un hilo secundario
   demonizado (`threading.Thread`) escuchando en el puerto 8765. No requiere instalar
   brokers MQTT ni servidores web complejos como Nginx o Apache.
2. Dos Modos de Comunicación:
   - Modo Voz Real (Walkie-Talkie / /audio):
     Transmite el búfer PCM/WAV grabado directamente en el micrófono. Al recibirlo,
     el otro nodo activa Audio Ducking, toca el tono armónico `intercom_chime.wav`
     y reproduce el audio con la voz original del interlocutor mediante `aplay`.
   - Modo Texto a Voz (/message):
     Transmite un JSON con el texto del mensaje. Al recibirlo, activa Audio Ducking,
     toca la campanilla y lee en voz alta con Piper TTS:
     "Mensaje del taller: [texto]".
3. Resiliencia Móvil:
   Si el equipo remoto está apagado o esta laptop se encuentra fuera de casa,
   las funciones de envío aplican un timeout suave de 2.0 segundos e informan
   al usuario sin colgar la aplicación.
"""

import io
import json
import socket
import subprocess
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
from typing import Optional
import wave
import requests

from config import INTERCOM_PORT, NETWORK_TIMEOUT_SECONDS, NODE_ROLE, PEER_IP, SOUNDS_DIR
from ducking import AudioDucker
from feedback import feedback


class IntercomRequestHandler(BaseHTTPRequestHandler):
    """
    Manejador de peticiones HTTP entrantes para el servicio de intercomunicador.
    """

    def do_POST(self):
        """Procesa mensajes de texto o transmisiones de audio entrantes."""
        path = self.path.rstrip("/")
        content_length = int(self.headers.get("Content-Length", 0))

        if path == "/message":
            self._handle_incoming_text_message(content_length)
        elif path == "/audio":
            self._handle_incoming_audio_message(content_length)
        else:
            self.send_response(404)
            self.end_headers()

    def _handle_incoming_text_message(self, content_length: int):
        """Recibe JSON: {"from": "taller", "text": "..."} y lo reproduce con TTS."""
        body = self.rfile.read(content_length)
        try:
            data = json.loads(body.decode("utf-8"))
            sender = data.get("from", "intercomunicador")
            text = data.get("text", "").strip()

            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(b'{"status": "ok"}')

            if text:
                print(f"\n[Intercomunicador] Mensaje recibido de '{sender}': \"{text}\"")

                def _play():
                    with AudioDucker(factor=0.20):
                        feedback.play_sound("intercom_chime.wav", blocking=True)
                        feedback.speak(f"Mensaje de {sender}: {text}", blocking=True)

                threading.Thread(target=_play, daemon=True).start()

        except Exception as e:
            import traceback
            traceback.print_exc()
            print(f"[IntercomHandler] Error procesando texto: {e}")
            self.send_response(400)
            self.end_headers()

    def _handle_incoming_audio_message(self, content_length: int):
        """Recibe archivo WAV binario en el cuerpo del POST y lo reproduce con aplay."""
        audio_data = self.rfile.read(content_length)
        sender = self.headers.get("X-Sender-Name", "intercomunicador")

        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        self.wfile.write(b'{"status": "ok"}')

        print(f"\n[Intercomunicador] Nota de voz recibida de '{sender}' ({len(audio_data)} bytes)")

        def _play_audio():
            # Guardar temporalmente en un archivo para que aplay lo lea
            temp_wav = Path("/tmp/incoming_intercom.wav")
            with open(temp_wav, "wb") as f:
                f.write(audio_data)

            with AudioDucker(factor=0.20):
                feedback.play_sound("intercom_chime.wav", blocking=True)
                subprocess.run(["aplay", "-q", str(temp_wav)], check=False)

        threading.Thread(target=_play_audio, daemon=True).start()

    def log_message(self, format, *args):
        """Silenciar logs estándar de acceso HTTP para no ensuciar la consola."""
        return


class IntercomService:
    """
    Servicio de servidor y cliente para la suite de intercomunicador.
    """

    def __init__(self, port: int = INTERCOM_PORT):
        self.port = port
        self.server: Optional[HTTPServer] = None
        self._server_thread: Optional[threading.Thread] = None

    def start_server(self):
        """Inicia el servidor HTTP en un hilo demonio secundario."""
        if self._server_thread is not None and self._server_thread.is_alive():
            return

        def _serve():
            try:
                # Permitir reuso rápido del socket al reiniciar
                server_address = ("0.0.0.0", self.port)
                self.server = HTTPServer(server_address, IntercomRequestHandler)
                print(f"[IntercomService] Servidor HTTP escuchando en el puerto {self.port}...")
                self.server.serve_forever()
            except Exception as e:
                print(f"[IntercomService] No se pudo iniciar el servidor en el puerto {self.port}: {e}")

        self._server_thread = threading.Thread(target=_serve, daemon=True, name="intercom_http")
        self._server_thread.start()

    def stop_server(self):
        """Detiene el servidor HTTP."""
        if self.server:
            self.server.shutdown()
            self.server.server_close()
            self.server = None

    def send_text_message(self, text: str, peer_ip: str = PEER_IP, sender: str = NODE_ROLE) -> bool:
        """
        Envía un mensaje de texto para que sea leído por voz en el nodo receptor.
        """
        url = f"http://{peer_ip}:{self.port}/message"
        payload = {"from": sender, "text": text}
        print(f"[IntercomService] Enviando mensaje de texto a {url}...")

        try:
            resp = requests.post(url, json=payload, timeout=NETWORK_TIMEOUT_SECONDS)
            if resp.status_code == 200:
                feedback.play_sound("sent.wav")
                return True
        except requests.RequestException:
            print(f"[IntercomService] El equipo en {peer_ip} no respondió (¿fuera de casa o apagado?).")
            feedback.speak("El otro equipo no está en línea.")

        return False

    def send_audio_file(self, wav_bytes: bytes, peer_ip: str = PEER_IP, sender: str = NODE_ROLE) -> bool:
        """
        Envía un búfer de audio WAV para que sea reproducido con la voz real en el otro nodo.
        """
        url = f"http://{peer_ip}:{self.port}/audio"
        headers = {
            "Content-Type": "audio/wav",
            "X-Sender-Name": sender
        }
        print(f"[IntercomService] Transmitiendo nota de voz a {url} ({len(wav_bytes)} bytes)...")

        try:
            resp = requests.post(url, data=wav_bytes, headers=headers, timeout=NETWORK_TIMEOUT_SECONDS + 2.0)
            if resp.status_code == 200:
                feedback.play_sound("sent.wav")
                return True
        except requests.RequestException:
            print(f"[IntercomService] Falló el envío de audio a {peer_ip}.")
            feedback.speak("No se pudo entregar el mensaje de voz.")

        return False


# Instancia singleton
intercom = IntercomService()


if __name__ == "__main__":
    import time
    print("Iniciando prueba local de intercom.py...")
    intercom.start_server()
    time.sleep(1.0)

    print("Enviando mensaje de prueba a localhost...")
    intercom.send_text_message("Hola, esta es una prueba local del intercomunicador.", peer_ip="127.0.0.1")
    time.sleep(3.0)
    print("Prueba completada.")
