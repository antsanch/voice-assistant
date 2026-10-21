#!/usr/bin/env bash
# ==============================================================================
# Script de Instalación Maestro: Suite Modular de Asistente de Voz e Intercomunicador
# Diseñado para ejecutarse tanto en el Nodo C (Lenovo i7 / GPU) como en el Nodo A (Core 2 Duo / Taller)
# ==============================================================================

set -e

BASE_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$BASE_DIR"

echo "=================================================================="
echo "    Instalación de Suite de Asistente de Voz e Intercomunicador   "
echo "=================================================================="

# 1. Detección de Arquitectura y Capacidades de CPU
echo -e "\n[1/7] Analizando arquitectura de la CPU..."
if grep -q "avx" /proc/cpuinfo; then
    echo "  -> CPU con soporte AVX/AVX2 detectada (Perfil Nodo B / Nodo C)."
    LOW_SPEC="false"
    DEFAULT_ROLE="nodo_c"
else
    echo "  -> CPU sin soporte AVX detectada (Core 2 Duo / Perfil Nodo A Taller)."
    LOW_SPEC="true"
    DEFAULT_ROLE="taller"
fi

# 2. Creación del archivo .env si no existe
if [ ! -f .env ]; then
    echo -e "\n[2/7] Generando archivo de configuración .env..."
    cat <<EOF > .env
NODE_ROLE=${DEFAULT_ROLE}
IS_MOBILE=true
IS_LOW_SPEC_CPU=${LOW_SPEC}
OLLAMA_URL=http://127.0.0.1:11434
MODEL_NAME=qwen2.5:1.5b-instruct-q8_0
PEER_IP=192.168.1.100
INTERCOM_PORT=8765
READ_NOTIFICATIONS=false
EOF
    echo "  -> Archivo .env creado con rol predeterminado: ${DEFAULT_ROLE}"
fi

# 3. Instalación de paquetes del sistema operativo
echo -e "\n[3/7] Instalando paquetes del sistema mediante apt..."
sudo apt-get update
sudo apt-get install -y \
    xdotool \
    wmctrl \
    playerctl \
    pulseaudio-utils \
    alsa-utils \
    sox \
    portaudio19-dev \
    libasound2-dev \
    python3-dev \
    python3-venv \
    zenity \
    libnotify-bin \
    xclip \
    wakeonlan \
    python3-gi \
    python3-dbus

# 4. Creación de subcarpetas requeridas
mkdir -p bin models sounds tests

# 5. Descarga de Piper standalone y modelos si no existen
echo -e "\n[4/7] Verificando modelos y binarios de voz..."
if [ ! -f bin/piper/piper ]; then
    echo "  -> Descargando Piper standalone x86_64..."
    curl -L -o piper.tar.gz https://github.com/rhasspy/piper/releases/download/2023.11.14-2/piper_linux_x86_64.tar.gz
    tar -xzf piper.tar.gz -C bin/
    rm piper.tar.gz
fi

if [ ! -f models/es_MX-ald-medium.onnx ]; then
    echo "  -> Descargando modelo de voz Piper es_MX-ald-medium..."
    curl -L -o models/es_MX-ald-medium.onnx https://huggingface.co/rhasspy/piper-voices/resolve/v1.0.0/es/es_MX/ald/medium/es_MX-ald-medium.onnx
    curl -L -o models/es_MX-ald-medium.onnx.json https://huggingface.co/rhasspy/piper-voices/resolve/v1.0.0/es/es_MX/ald/medium/es_MX-ald-medium.onnx.json
fi

if [ ! -d models/vosk-model-small-es-0.42 ]; then
    echo "  -> Descargando modelo de Vosk ligero en español..."
    curl -L -o vosk.zip https://alphacephei.com/vosk/models/vosk-model-small-es-0.42.zip
    unzip -q vosk.zip -d models/
    rm vosk.zip
fi

# 6. Creación del entorno virtual de Python
echo -e "\n[5/7] Configurando entorno virtual de Python (.venv)..."
if [ ! -d .venv ]; then
    python3 -m venv --system-site-packages .venv
fi

.venv/bin/pip install --upgrade pip
.venv/bin/pip install -r requirements.txt

# 7. Pre-generación de Sonidos WAV
echo -e "\n[6/7] Generando archivos de audio WAV para confirmaciones..."
.venv/bin/python3 generate_sounds.py

# 8. Instalación del servicio systemd de usuario
echo -e "\n[7/7] Configurando servicio systemd de usuario..."
mkdir -p ~/.config/systemd/user
cp voice-assistant.service ~/.config/systemd/user/voice-assistant.service
systemctl --user daemon-reload

echo -e "\n=================================================================="
echo "          ¡Instalación y Configuración Completada con Éxito!      "
echo "=================================================================="
echo "Comandos para gestionar el asistente:"
echo "  - Iniciar manualmente:   .venv/bin/python3 main.py"
echo "  - Activar servicio:      systemctl --user enable --now voice-assistant"
echo "  - Ver registros (logs):  journalctl --user -u voice-assistant -f"
echo "  - Atajo dictado rápido:  pkill -USR1 -f main.py"
echo "=================================================================="
EOF
chmod +x install.sh
