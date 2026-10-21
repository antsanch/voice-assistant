# 🎙️ Voice Assistant, Smart Dictation & Local Intercom Suite

Suite modular de **Asistente de Voz, Dictado Inteligente e Intercomunicador Local** para Linux (Zorin OS / Ubuntu), diseñada con arquitectura desacoplada para operar en red local y en movilidad con alta eficiencia y cero dependencias de servicios en la nube.

---

## 🏛️ Arquitectura del Sistema

```text
voice-assistant/
├── docker-compose.yml       # Servicio Ollama con GPU Passthrough (NVIDIA GTX 1060)
├── install.sh               # Instalador unificado desatendido
├── generate_sounds.py       # Pre-generador de clips WAV para latencia 0 ms
├── config.py                # Centralización de configuración y roles
├── ducking.py               # Audio Ducking automático (playerctl / pactl)
├── feedback.py              # Piper TTS con Barge-in (<50ms) y audio en caché
├── audio_engine.py          # Captura PyAudio y Vosk (<3% CPU en Wake Word)
├── router.py                # Fast-Path Regex (0 ms) + Clasificador semántico Ollama
├── actions.py               # Inyección X11 (xdotool), historial deque y control de ventanas
├── reader.py                # Lectura de selección (xclip) y extracción web (trafilatura)
├── notifications.py         # Monitor D-Bus para mensajes de Telegram y WhatsApp Web
├── cast_control.py          # Control de Roku TV (ECP), Chromecast y LG webOS
├── intercom.py              # Servidor y cliente HTTP (:8765) de notas de voz y texto
├── send_intercom_cli.py     # CLI auxiliar para atajos de teclado y diálogos Zenity
├── main.py                  # Demonio orquestador (IDLE, SINGLE_INSTRUCTION, DICTATION)
└── voice-assistant.service  # Unidad systemd --user para arranque automático
```

---

## 🚀 Perfiles de Hardware Soportados

1. **Nodo C (Laptop Lenovo Móvil - Equipo Autónomo):**
   - Procesador Intel Core i7-7700HQ.
   - GPU NVIDIA GeForce GTX 1060 (6 GB VRAM).
   - Inferencia LLM local ultra-rápida mediante **Ollama en Docker** (`qwen2.5:1.5b-instruct-q8_0` fijado en VRAM con `keep_alive: -1`).
   - Autonomía completa dentro y fuera de casa.
2. **Nodo A (Taller de Carpintería - Hardware Ligero):**
   - Procesador Intel Core 2 Duo (sin instrucciones AVX/AVX2).
   - STT y Wake Word ultra-liviano mediante Vosk.
   - LLM remoto consumido desde el servidor local.
   - Supresión de ruido para maquinaria industrial y colectores de polvo.

---

## ⚡ Instalación Rápida

### 1. Clonar el repositorio
```bash
git clone https://github.com/antsanch/voice-assistant.git
cd voice-assistant
```

### 2. Ejecutar el instalador maestro
El script `install.sh` detecta la presencia de instrucciones AVX, instala paquetes apt necesarios, descarga Piper standalone, descarga el modelo Vosk en español, crea el entorno virtual `.venv` y pre-genera los sonidos:
```bash
chmod +x install.sh
./install.sh
```

### 3. Iniciar el contenedor de Ollama (Nodo C con GPU)
```bash
docker compose up -d
docker exec -it voice_assistant_ollama ollama pull qwen2.5:1.5b-instruct-q8_0
```

---

## 🎯 Modos de Operación

### 1. Estado `IDLE` (Escucha Ligera)
- Escucha continua de bajo consumo con Vosk.
- Palabra de activación: **"computadora"** o **"asistente"**.
- Al activarse, baja el volumen multimedia al 20% (*Audio Ducking*), responde *"¿Sí?"* y pasa a capturar la orden.

### 2. Estado `SINGLE_INSTRUCTION` (Fast-Path + Ollama)
- **Capa 1 (Fast-Path Regex - 0 ms):**
  - Control de volumen: *"sube el volumen"*, *"baja el volumen"*, *"silencio"*.
  - Multimedia: *"pausa"*, *"reproducir"*, *"siguiente canción"*.
  - Ventanas: *"cierra la ventana"*, *"maximizar"*, *"minimizar"*, *"cambiar ventana"*.
  - Búsqueda Web: *"busca en google tornillos autorroscantes"*.
  - Lectura: *"lee la selección"*, *"léeme esta página"*, *"resume esta página"*.
  - Notificaciones: *"activar lectura de mensajes"*, *"silenciar mensajes"*.
  - Intercomunicador: *"enviar audio"*, *"dile a la oficina que ya está listo"*.
- **Capa 2 (Semántica Ollama JSON):**
  - Consultas y conversiones de carpintería: *"¿cuántos milímetros son 3 cuartos de pulgada?"*.

### 3. Estado `CONTINUOUS_DICTATION` (Dictado Inteligente)
- Se activa diciendo *"modo dictado"* o pulsando el atajo global de teclado (`SIGUSR1`).
- Transcribe bloques continuos, corrigiendo automáticamente la puntuación y ortografía con Ollama e inyectándolos con `xdotool`.
- **Comandos en caliente (In-Band):**
  - *"borra eso"* / *"borrar última frase"*: Deshace la última frase exacta mediante cola `deque`.
  - *"nueva línea"* / *"punto y aparte"*: Salto de línea.
  - *"nuevo párrafo"*: Doble salto de línea.
  - *"enviar mensaje"*: Presiona Enter.
  - *"fin del dictado"*: Regresa al estado de espera.

---

## ⌨️ Atajos de Teclado Globales (Zorin OS / GNOME)

Configurar en **Configuración -> Teclado -> Atajos personalizados**:

| Función | Comando | Atajo sugerido |
| :--- | :--- | :--- |
| **Dictado Rápido** | `pkill -USR1 -f main.py` | `Super + D` |
| **Push-to-Talk (Intercom)** | `.venv/bin/python3 send_intercom_cli.py --audio` | `Super + I` |
| **Mensaje de Texto (Intercom)** | `.venv/bin/python3 send_intercom_cli.py --text` | `Super + Shift + I` |

---

## 🧪 Pruebas Automatizadas

Ejecutar la suite completa de pruebas:
```bash
.venv/bin/python3 -m unittest discover -s tests
```

---

## 📜 Licencia

Desarrollado bajo licencia MIT.
