#!/usr/bin/env python3
"""
Módulo: config.py
Propósito: Centralizar la configuración, parámetros de hardware, rutas y alias del sistema.

Arquitectura y Roles:
---------------------
- Nodo A: Laptop Ligera (Taller) - Intel Core 2 Duo (sin AVX, LLM remoto).
- Nodo B: Servidor Casero / Oficina Fija.
- Nodo C: Laptop Lenovo Móvil (Equipo Actual) - Intel i7 / GPU GTX 1060 (Ollama Docker local).

Este archivo carga variables desde `.env` para facilitar el despliegue en cualquier nodo
sin necesidad de modificar el código fuente.
"""

import os
from pathlib import Path
from dotenv import load_dotenv

# ------------------------------------------------------------------------------
# 1. Rutas Base del Sistema
# ------------------------------------------------------------------------------
BASE_DIR = Path(__file__).resolve().parent

# Cargar variables de entorno desde el archivo .env si existe
ENV_FILE = BASE_DIR / ".env"
if ENV_FILE.is_file():
    load_dotenv(dotenv_path=ENV_FILE)

# Rutas a binarios, modelos y caché de audio
BIN_DIR = BASE_DIR / "bin"
PIPER_BIN = BIN_DIR / "piper" / "piper"

MODELS_DIR = BASE_DIR / "models"
VOSK_MODEL_DIR = MODELS_DIR / "vosk-model-small-es-0.42"

# Configuración de voz TTS Piper (Español Mexicano de alta calidad: es_MX-claude-high)
PIPER_MODEL_NAME = os.getenv("PIPER_MODEL_NAME", "es_MX-claude-high.onnx")
PIPER_SPEAKER_ID = os.getenv("PIPER_SPEAKER_ID", "")

PIPER_MODEL_FILE = MODELS_DIR / PIPER_MODEL_NAME
PIPER_CONFIG_FILE = MODELS_DIR / f"{PIPER_MODEL_NAME}.json"

SOUNDS_DIR = BASE_DIR / "sounds"

# ------------------------------------------------------------------------------
# 2. Identificación del Nodo y Hardware
# ------------------------------------------------------------------------------
# "nodo_c" representa la laptop Lenovo móvil actual.
NODE_ROLE = os.getenv("NODE_ROLE", "nodo_c")

# Indica si el nodo actual puede salir de la red local (movilidad)
IS_MOBILE = os.getenv("IS_MOBILE", "true").lower() == "true"

# Indica si la CPU carece de instrucciones AVX (True para Core 2 Duo, False para i7)
IS_LOW_SPEC_CPU = os.getenv("IS_LOW_SPEC_CPU", "false").lower() == "true"

# ------------------------------------------------------------------------------
# 3. Configuración de Inferencia LLM (Ollama)
# ------------------------------------------------------------------------------
# En el Nodo C móvil, apunta al contenedor Docker local en 127.0.0.1:11434
OLLAMA_URL = os.getenv("OLLAMA_URL", "http://127.0.0.1:11434")

# Modelo cuantizado optimizado para bajo consumo de VRAM y alta velocidad
MODEL_NAME = os.getenv("MODEL_NAME", "qwen2.5:1.5b-instruct-q8_0")

# ------------------------------------------------------------------------------
# 4. Intercomunicador y Red Local
# ------------------------------------------------------------------------------
# IP del otro nodo (por ejemplo, el taller o la oficina)
PEER_IP = os.getenv("PEER_IP", "192.168.1.100")

# Puerto HTTP en el que escucha el servicio de intercomunicación
INTERCOM_PORT = int(os.getenv("INTERCOM_PORT", "8765"))

# Timeout suave en segundos para no colgar el sistema si el peer no está disponible
NETWORK_TIMEOUT_SECONDS = 2.0

# ------------------------------------------------------------------------------
# 5. Parámetros de Audio y Reconocimiento de Voz
# ------------------------------------------------------------------------------
# Tasa de muestreo requerida por Vosk (16 kHz mono)
AUDIO_SAMPLE_RATE = 16000
AUDIO_CHANNELS = 1
AUDIO_CHUNK_SIZE = 4000

# Palabras clave para activar el asistente en modo Wake Word
WAKE_WORDS = ["computadora", "asistente"]

# Tiempo de silencio en segundos para considerar que el usuario terminó de hablar
SILENCE_TIMEOUT_SECONDS = 1.2

# Factor de atenuación de volumen multimedia durante la escucha o habla (20% del volumen original)
DUCKING_FACTOR = 0.20

# Activar lectura por voz de notificaciones entrantes de mensajería (D-Bus)
READ_NOTIFICATIONS = os.getenv("READ_NOTIFICATIONS", "false").lower() == "true"

# ------------------------------------------------------------------------------
# 6. Alias de Aplicaciones del Sistema (Fast-Path)
# ------------------------------------------------------------------------------
# Mapeo de nombres coloquiales a ejecutables del sistema operativo
APPLICATION_ALIASES = {
    "navegador": "google-chrome",
    "chrome": "google-chrome",
    "terminal": "x-terminal-emulator",
    "consola": "x-terminal-emulator",
    "archivos": "nautilus",
    "explorador": "nautilus",
    "calculadora": "gnome-calculator",
    "editor": "gedit",
    "spotify": "spotify",
}

# ------------------------------------------------------------------------------
# 7. Alias de Dispositivos Multimedia de Red (Roku, Chromecast, LG webOS)
# ------------------------------------------------------------------------------
# Configuración local de dispositivos de entretenimiento en el hogar
NETWORK_MEDIA_DEVICES = {
    "tele_sala": {
        "type": "roku",
        "ip": os.getenv("ROKU_SALA_IP", "192.168.1.110"),
        "port": 8060,
    },
    "roku_cuarto": {
        "type": "roku",
        "ip": os.getenv("ROKU_CUARTO_IP", "192.168.1.111"),
        "port": 8060,
    },
    "chromecast_sala": {
        "type": "chromecast",
        "ip": os.getenv("CHROMECAST_IP", "192.168.1.112"),
    },
    "tele_lg": {
        "type": "lg_webos",
        "ip": os.getenv("LG_TV_IP", "192.168.1.115"),
        "mac": os.getenv("LG_TV_MAC", "AA:BB:CC:DD:EE:FF"),
    }
}
