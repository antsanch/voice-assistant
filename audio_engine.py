#!/usr/bin/env python3
"""
Módulo: audio_engine.py
Propósito: Captura de micrófono de baja latencia y reconocimiento de voz (Vosk) con supresión de ruido.

Principios Técnicos y Ahorro de Recursos:
-----------------------------------------
1. Entrada Predeterminada de PipeWire / PulseAudio:
   Se utiliza el dispositivo predeterminado del sistema operativo en lugar del hardware directo
   ALSA ('hw:0'). Esto permite que los filtros de supresión de ruido basados en RNNoise,
   puertas de ruido o ecualizadores del sistema limpien el audio de sierras, motores y
   colectores de polvo antes de que llegue a Python.
2. Reconocimiento de Doble Modo en Vosk (CPU Friendly):
   - Modo Wake Word: Se inicializa KaldiRecognizer con una gramática JSON restringida:
     '["computadora", "asistente", "[unk]"]'. Al limitar el árbol léxico a solo 3 nodos,
     el consumo de CPU desciende a menos del 3%, ideal para ejecución continua 24/7.
   - Modo Transcripción Abierta: Se utiliza el modelo en vocabulario libre para capturar
     la frase de la orden hasta detectar 1.2 segundos de silencio.
3. Detección de Silencio por Umbral de Energía (RMS):
   Calcula la raíz cuadrática media del búfer PCM de 16 bits para delimitar el final de una frase
   sin depender de llamadas pesadas al servidor.
"""

import json
import math
import struct
import time
from typing import Generator, Optional, Tuple

import pyaudio
from vosk import KaldiRecognizer, Model, SetLogLevel

from config import (
    AUDIO_CHANNELS,
    AUDIO_CHUNK_SIZE,
    AUDIO_SAMPLE_RATE,
    SILENCE_TIMEOUT_SECONDS,
    VOSK_MODEL_DIR,
    WAKE_WORDS,
)

# Silenciar los logs internos de depuración de Kaldi/Vosk
SetLogLevel(-1)


def calculate_audio_energy(data: bytes) -> float:
    """
    Calcula el valor RMS (Root Mean Square) del bloque de audio PCM 16-bit mono.
    Sirve para distinguir voz activa frente a silencio ambiental.
    """
    count = len(data) // 2
    if count == 0:
        return 0.0
    # Desempaquetar enteros con signo de 16 bits
    shorts = struct.unpack(f"{count}h", data)
    sum_squares = sum(s * s for s in shorts)
    return math.sqrt(sum_squares / count)


class AudioEngine:
    """
    Motor de captura de audio y reconocimiento con Vosk.
    """

    def __init__(self):
        print(f"[AudioEngine] Cargando modelo Vosk desde: {VOSK_MODEL_DIR}...")
        self.model = Model(str(VOSK_MODEL_DIR))

        # 1. Reconocedor ultra-ligero para Wake Word (gramática cerrada)
        wake_grammar = json.dumps(WAKE_WORDS + ["[unk]"])
        self.wake_recognizer = KaldiRecognizer(self.model, AUDIO_SAMPLE_RATE, wake_grammar)

        # 2. Reconocedor abierto para captura de órdenes y dictado
        self.open_recognizer = KaldiRecognizer(self.model, AUDIO_SAMPLE_RATE)
        self.open_recognizer.SetWords(True)

        self.audio = pyaudio.PyAudio()
        self.stream: Optional[pyaudio.Stream] = None
        print("[AudioEngine] Modelos cargados y motor de audio listo.")

    def start_stream(self):
        """Inicia el flujo de captura desde el micrófono predeterminado de PipeWire/PulseAudio."""
        if self.stream is None or not self.stream.is_active():
            self.stream = self.audio.open(
                format=pyaudio.paInt16,
                channels=AUDIO_CHANNELS,
                rate=AUDIO_SAMPLE_RATE,
                input=True,
                frames_per_buffer=AUDIO_CHUNK_SIZE
            )

    def stop_stream(self):
        """Pausa el flujo de captura."""
        if self.stream is not None:
            try:
                self.stream.stop_stream()
                self.stream.close()
            except Exception:
                pass
            self.stream = None

    def listen_for_wake_word(self) -> Optional[str]:
        """
        Bucle de escucha de bajo consumo. Retorna el nombre de la palabra detectada
        ('computadora' o 'asistente') o None si no hay coincidencia.
        """
        self.start_stream()
        if self.stream is None:
            return None

        try:
            data = self.stream.read(AUDIO_CHUNK_SIZE, exception_on_overflow=False)
            if len(data) == 0:
                return None

            if self.wake_recognizer.AcceptWaveform(data):
                res = json.loads(self.wake_recognizer.Result())
                text = res.get("text", "").lower().strip()
                for word in WAKE_WORDS:
                    if word in text:
                        return word
            else:
                partial = json.loads(self.wake_recognizer.PartialResult())
                p_text = partial.get("partial", "").lower().strip()
                for word in WAKE_WORDS:
                    if word in p_text:
                        # Reiniciar el reconocedor para no disparar dos veces
                        self.wake_recognizer.Reset()
                        return word
        except IOError:
            pass

        return None

    def capture_single_instruction(self, max_seconds: float = 10.0) -> str:
        """
        Captura una orden abierta después de la palabra de activación.
        Se detiene automáticamente tras detectar 1.2 segundos de silencio continuo.
        """
        self.start_stream()
        self.open_recognizer.Reset()

        print("[AudioEngine] Capturando orden...")
        last_voice_time = time.time()
        start_time = time.time()
        energy_threshold = 250.0  # Umbral RMS mínimo para considerar voz activa

        recognized_phrase = ""

        while True:
            current_time = time.time()
            if (current_time - start_time) > max_seconds:
                break

            data = self.stream.read(AUDIO_CHUNK_SIZE, exception_on_overflow=False)
            energy = calculate_audio_energy(data)

            if energy > energy_threshold:
                last_voice_time = current_time

            # Comprobar si el usuario guardó silencio por más de SILENCE_TIMEOUT_SECONDS
            if (current_time - last_voice_time) > SILENCE_TIMEOUT_SECONDS:
                # Silencio detectado, cerrar frase
                break

            if self.open_recognizer.AcceptWaveform(data):
                res = json.loads(self.open_recognizer.Result())
                text = res.get("text", "").strip()
                if text:
                    recognized_phrase += " " + text

        # Obtener el remanente final de Vosk
        final_res = json.loads(self.open_recognizer.FinalResult())
        final_text = final_res.get("text", "").strip()
        if final_text:
            recognized_phrase += " " + final_text

        clean_phrase = recognized_phrase.strip()
        print(f"[AudioEngine] Frase capturada: \"{clean_phrase}\"")
        return clean_phrase

    def record_raw_audio(self, duration_seconds: float = 6.0) -> bytes:
        """
        Graba un búfer de audio PCM en crudo (16 kHz 16-bit mono) durante N segundos.
        Utilizado para enviar notas de voz al intercomunicador.
        """
        self.start_stream()
        frames = []
        chunks_to_read = int(AUDIO_SAMPLE_RATE / AUDIO_CHUNK_SIZE * duration_seconds)

        print(f"[AudioEngine] Grabando nota de voz de {duration_seconds} segundos...")
        for _ in range(chunks_to_read):
            data = self.stream.read(AUDIO_CHUNK_SIZE, exception_on_overflow=False)
            frames.append(data)

        return b"".join(frames)


# Instancia singleton
audio_engine = AudioEngine()
