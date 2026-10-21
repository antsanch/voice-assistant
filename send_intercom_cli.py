#!/usr/bin/env python3
"""
Módulo: send_intercom_cli.py
Propósito: Script auxiliar de línea de comandos para enviar notas de voz o texto vía atajos de teclado.

Casos de Uso:
-------------
1. Atajo Global de Nota de Voz (Push-to-Talk):
   Vincular una tecla de acceso rápido en el entorno gráfico (ej. Super+I) para ejecutar:
     /home/antsanch/voice-assistant/.venv/bin/python3 /home/antsanch/voice-assistant/send_intercom_cli.py --audio
   Esto graba 5 segundos del micrófono y los transmite inmediatamente al otro nodo.
2. Atajo Global de Texto Rápido (Zenity Dialog):
   Vincular un atajo (ej. Super+Shift+I) para ejecutar:
     /home/antsanch/voice-assistant/.venv/bin/python3 /home/antsanch/voice-assistant/send_intercom_cli.py --text
   Abre una pequeña ventana gráfica emergente con `zenity` para escribir una orden o aviso.
"""

import argparse
import io
import subprocess
import sys
import wave

from config import AUDIO_CHANNELS, AUDIO_SAMPLE_RATE, NODE_ROLE, PEER_IP
from feedback import feedback
from intercom import intercom


def send_quick_text():
    """Abre un cuadro de diálogo con Zenity para escribir un mensaje."""
    try:
        proc = subprocess.run(
            [
                "zenity",
                "--entry",
                "--title=Intercomunicador Local",
                "--text=Escribe el mensaje para la otra laptop:"
            ],
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            text=True,
            check=False
        )
        message = proc.stdout.strip()
        if message:
            print(f"[send_intercom_cli] Enviando texto: \"{message}\"")
            intercom.send_text_message(message, peer_ip=PEER_IP, sender=NODE_ROLE)
    except FileNotFoundError:
        print("[send_intercom_cli] Zenity no está instalado.")


def send_voice_note(duration_seconds: float = 5.0):
    """Graba audio del micrófono durante N segundos y lo transmite al peer."""
    feedback.play_sound("wake.wav", blocking=True)
    print(f"[send_intercom_cli] Grabando nota de voz de {duration_seconds} segundos...")

    # Grabar con arecord a 16 kHz 16-bit mono
    try:
        proc = subprocess.run(
            [
                "arecord",
                "-q",
                "-r", str(AUDIO_SAMPLE_RATE),
                "-c", str(AUDIO_CHANNELS),
                "-f", "S16_LE",
                "-t", "wav",
                "-d", str(int(duration_seconds))
            ],
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            check=False
        )
        wav_bytes = proc.stdout
        if wav_bytes:
            intercom.send_audio_file(wav_bytes, peer_ip=PEER_IP, sender=NODE_ROLE)
    except Exception as e:
        print(f"[send_intercom_cli] Error grabando audio: {e}")


def main():
    parser = argparse.ArgumentParser(description="Envío rápido por intercomunicador.")
    parser.add_argument("--text", action="store_true", help="Abrir ventana Zenity para enviar texto.")
    parser.add_argument("--audio", action="store_true", help="Grabar nota de voz y enviarla de inmediato.")
    parser.add_argument("--duration", type=float, default=5.0, help="Duración de la nota de voz en segundos.")
    args = parser.parse_args()

    if args.text:
        send_quick_text()
    elif args.audio:
        send_voice_note(duration_seconds=args.duration)
    else:
        # Por defecto abre la entrada de texto
        send_quick_text()


if __name__ == "__main__":
    main()
