#!/usr/bin/env python3
"""
Módulo: feedback.py
Propósito: Retroalimentación sonora instantánea, síntesis Piper TTS y gestión de Barge-in.

Conceptos Clave de Audio y Latencia:
------------------------------------
1. Confirmaciones Caché (.wav):
   Archivos de audio pregrabados reproducidos mediante `aplay -q`. No consumen CPU ni
   generan retraso alguno (0 ms de overhead).
2. Síntesis Piper en Streaming:
   Para respuestas dinámicas o lectura de texto, se utiliza un pipeline directo de Linux:
     [Piper genera audio RAW] ---> [Tubería PIPE] ---> [aplay reproduce de inmediato]
   Esto evita escribir archivos temporales en el disco y permite escuchar las primeras
   palabras casi de inmediato.
3. Mecanismo de Barge-in (Interrupción):
   Si el usuario habla, dice "silencio" o envía una nueva orden mientras el asistente
   está hablando, la función `stop_speaking()` envía una señal SIGKILL al proceso de audio,
   deteniendo la reproducción en menos de 50 milisegundos.
"""

import os
import signal
import subprocess
import threading
from pathlib import Path
from typing import Optional

from config import PIPER_BIN, PIPER_MODEL_FILE, PIPER_SPEAKER_ID, SOUNDS_DIR


class FeedbackManager:
    """
    Gestor centralizado de audio de salida para confirmaciones sonoras y síntesis de voz.
    """

    def __init__(self):
        self._current_process: Optional[subprocess.Popen] = None
        self._lock = threading.Lock()

    def play_sound(self, sound_name: str, blocking: bool = False):
        """
        Reproduce un archivo .wav de la carpeta sounds/ usando aplay.
        
        :param sound_name: Nombre del archivo (ej. 'wake.wav', 'ready.wav').
        :param blocking: Si es True, espera a que termine el sonido antes de retornar.
        """
        wav_path = SOUNDS_DIR / sound_name
        if not wav_path.is_file():
            print(f"[FeedbackManager] Archivo de sonido no encontrado: {wav_path}")
            return

        # Detener cualquier reproducción previa
        self.stop_speaking()

        cmd = ["aplay", "-q", str(wav_path)]

        if blocking:
            subprocess.run(cmd, check=False)
        else:
            with self._lock:
                self._current_process = subprocess.Popen(
                    cmd,
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL
                )

    def speak(self, text: str, blocking: bool = False):
        """
        Sintetiza texto hablado usando Piper TTS a través de un pipeline hacia aplay.
        
        :param text: Texto en español para ser leído por voz.
        :param blocking: Si es True, bloquea la ejecución hasta finalizar el habla.
        """
        if not text or not text.strip():
            return

        text = text.strip()
        print(f"[Asistente Habla]: \"{text}\"")

        # Barge-in: Si ya estaba hablando, silenciarlo primero
        self.stop_speaking()

        if not PIPER_BIN.is_file() or not PIPER_MODEL_FILE.is_file():
            print("[FeedbackManager] Error: Piper o el modelo no están disponibles.")
            return

        def _synthesize_and_play():
            with self._lock:
                # 1. Proceso de Piper (Genera audio raw en PCM 16-bit 22050Hz)
                piper_cmd = [
                    str(PIPER_BIN),
                    "--model", str(PIPER_MODEL_FILE),
                    "--output-raw"
                ]
                if PIPER_SPEAKER_ID:
                    piper_cmd.extend(["--speaker", str(PIPER_SPEAKER_ID)])

                piper_proc = subprocess.Popen(
                    piper_cmd,
                    stdin=subprocess.PIPE,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.DEVNULL
                )

                # 2. Proceso de aplay (Consume el stream raw directamente sin escribir a disco)
                aplay_proc = subprocess.Popen(
                    [
                        "aplay",
                        "-r", "22050",
                        "-f", "S16_LE",
                        "-t", "raw",
                        "-q"
                    ],
                    stdin=piper_proc.stdout,
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL
                )

                # Permitir que piper_proc reciba SIGPIPE si aplay sale
                if piper_proc.stdout:
                    piper_proc.stdout.close()

                self._current_process = aplay_proc

            # Inyectar texto al STDIN de Piper y cerrar el flujo de entrada
            try:
                if piper_proc.stdin:
                    piper_proc.stdin.write(text.encode("utf-8"))
                    piper_proc.stdin.close()
            except (BrokenPipeError, OSError):
                pass

            # Esperar a que aplay termine de reproducir
            aplay_proc.wait()

            with self._lock:
                if self._current_process == aplay_proc:
                    self._current_process = None

        if blocking:
            _synthesize_and_play()
        else:
            # Ejecutar en un hilo separado para no congelar el bucle principal
            thread = threading.Thread(target=_synthesize_and_play, daemon=True)
            thread.start()

    def stop_speaking(self):
        """
        Implementa el Barge-in: Detiene inmediatamente cualquier reproducción de audio activa.
        """
        with self._lock:
            if self._current_process is not None:
                try:
                    # Enviar señal SIGKILL para corte instantáneo sin buffer residual
                    self._current_process.kill()
                    self._current_process.wait(timeout=0.1)
                except Exception:
                    pass
                finally:
                    self._current_process = None


# Instancia singleton para ser importada y utilizada en toda la aplicación
feedback = FeedbackManager()


# ------------------------------------------------------------------------------
# Prueba Directa
# ------------------------------------------------------------------------------
if __name__ == "__main__":
    import time
    print("Probando feedback.py...")
    print("1. Reproduciendo sonido wake.wav (bloqueante)...")
    feedback.play_sound("wake.wav", blocking=True)

    print("2. Sintetizando frase con Piper...")
    feedback.speak("Sistema de audio y síntesis inicializado correctamente.", blocking=True)

    print("3. Probando Barge-in (interrupción a medio hablar)...")
    feedback.speak("Esta es una frase muy larga que debería ser interrumpida casi de inmediato...")
    time.sleep(1.0)
    print(" -> Enviando señal de interrupción (Barge-in)...")
    feedback.stop_speaking()
    print(" -> Interrupción completada.")
