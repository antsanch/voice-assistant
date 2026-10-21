#!/usr/bin/env python3
"""
Módulo: generate_sounds.py
Propósito: Pre-generación de archivos de audio WAV para confirmaciones instantáneas.

¿Por qué pre-generar sonidos en disco?
-------------------------------------
1. Latencia Cero (0 ms): La síntesis de voz en tiempo real (incluso en CPU rápida)
   requiere entre 200 ms y 600 ms de procesamiento. Para respuestas como "¿Sí?" o "Listo",
   esa latencia degrada la experiencia conversacional.
2. Cero Carga de CPU: Reproducir un archivo .wav estático mediante `aplay -q` consume
   menos del 0.1% de CPU, lo cual es vital para el hardware ligero (Core 2 Duo).
3. Confiabilidad: Si el motor TTS fallara temporalmente, los sonidos de estado del sistema
   seguirán funcionando ininterrumpidamente.
"""

import os
import subprocess
import sys
from pathlib import Path

from config import BASE_DIR, PIPER_BIN, PIPER_MODEL_FILE, PIPER_SPEAKER_ID, SOUNDS_DIR

# Diccionario de frases requeridas por la especificación
SOUND_PHRASES = {
    "wake.wav": "¿Sí, Doctor?",
    "ready.wav": "Listo Doctor.",
    "opening.wav": "Abriendo.",
    "searching.wav": "Buscando en internet.",
    "dictation_on.wav": "Dictado activo.",
    "dictation_off.wav": "Modo espera.",
    "sent.wav": "Mensaje enviado.",
}


def ensure_environment():
    """Valida la existencia del binario de Piper y del modelo de voz antes de generar."""
    if not PIPER_BIN.is_file():
        print(f"[ERROR] No se encontró el binario de Piper en: {PIPER_BIN}")
        sys.exit(1)
    if not PIPER_MODEL_FILE.is_file():
        print(f"[ERROR] No se encontró el modelo de voz en: {PIPER_MODEL_FILE}")
        sys.exit(1)
    SOUNDS_DIR.mkdir(parents=True, exist_ok=True)


def generate_speech_wav(text: str, output_file: Path):
    """
    Sintetiza una frase a archivo WAV utilizando Piper con la voz seleccionada.
    """
    print(f"  -> Generando [{output_file.name}]: \"{text}\"")
    cmd = [
        str(PIPER_BIN),
        "--model", str(PIPER_MODEL_FILE),
        "--output_file", str(output_file)
    ]
    if PIPER_SPEAKER_ID:
        cmd.extend(["--speaker", str(PIPER_SPEAKER_ID)])
    
    # Piper lee la entrada de texto por STDIN en codificación UTF-8
    process = subprocess.run(
        cmd,
        input=text.encode("utf-8"),
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE
    )
    
    if process.returncode != 0:
        print(f"[ERROR] Falló la síntesis de {output_file.name}: {process.stderr.decode()}")
        sys.exit(1)


def generate_chime_wav(output_file: Path):
    """
    Genera un tono armónico suave (chime de dos acordes: 587 Hz y 880 Hz)
    usando SoX para el aviso sonoro del intercomunicador.
    
    Esto produce un sonido limpio y no intrusivo sin necesidad de síntesis de voz.
    """
    print(f"  -> Generando tono de aviso [{output_file.name}] con SoX...")
    cmd = [
        "sox", "-n", "-r", "22050", "-c", "1", str(output_file),
        "synth", "0.25", "sin", "587.33", "fade", "h", "0.01", "0.25", "0.05",
        ":",
        "synth", "0.35", "sin", "880.00", "fade", "h", "0.01", "0.35", "0.10"
    ]
    subprocess.run(cmd, check=True)


def main():
    print("==========================================================")
    print("  Pre-generación de Confirmaciones Sonoras (.wav) ")
    print("==========================================================")
    ensure_environment()

    # 1. Generar frases habladas con Piper
    for filename, phrase in SOUND_PHRASES.items():
        wav_path = SOUNDS_DIR / filename
        generate_speech_wav(phrase, wav_path)

    # 2. Generar el chime del intercomunicador
    chime_path = SOUNDS_DIR / "intercom_chime.wav"
    generate_chime_wav(chime_path)

    print("\n[OK] Todos los sonidos han sido pre-generados exitosamente en:")
    print(f"     {SOUNDS_DIR}\n")


if __name__ == "__main__":
    main()
