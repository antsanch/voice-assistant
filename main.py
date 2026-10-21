#!/usr/bin/env python3
"""
Módulo: main.py
Propósito: Demonio orquestador principal con máquina de estados finitos y manejo de señales.

Máquina de Estados del Asistente:
---------------------------------
1. Estado IDLE (Reposo y Escucha Ligera):
   - Escucha continua con Vosk mediante gramática restringida (<3% CPU).
   - Espera las palabras de activación: "computadora" o "asistente".
   - Al detectarla: activa Audio Ducking (20%), reproduce 'sounds/wake.wav' (0 ms)
     y transiciona inmediatamente a SINGLE_INSTRUCTION.
2. Estado SINGLE_INSTRUCTION (Captura y Enrutamiento):
   - Graba la frase hasta detectar 1.2 segundos de silencio.
   - Enruta mediante Fast-Path (0 ms) o Semántica con Ollama (Qwen 2.5).
   - Despacha a actions.py, reader.py, notifications.py, cast_control.py o intercom.py.
   - Al concluir, restaura el volumen y regresa a IDLE.
3. Estado CONTINUOUS_DICTATION (Dictado Inteligente Ininterrumpido):
   - Se activa por voz ("modo dictado") o por atajo de teclado vía señal `SIGUSR1`.
   - Escucha bloques continuos de voz.
   - Interpreta comandos en caliente (in-band): "borra eso", "nueva línea", "fin del dictado".
   - Corrige puntuación y ortografía con Ollama e inyecta con `xdotool`.
   - Timeout de seguridad de 60 segundos de inactividad para retornar a IDLE.

Manejo de Señales del Sistema (SIGUSR1):
----------------------------------------
Permite invocar el modo dictado desde un atajo de teclado global en Zorin OS
haciendo `pkill -USR1 -f main.py`.
"""

import enum
import os
import signal
import sys
import time
from typing import Optional

from actions import actions
from audio_engine import audio_engine
from cast_control import cast_control
from config import DUCKING_FACTOR, SILENCE_TIMEOUT_SECONDS
from ducking import AudioDucker
from feedback import feedback
from intercom import intercom
from notifications import notification_monitor
from reader import reader
from router import router


class AssistantState(enum.Enum):
    IDLE = 1
    SINGLE_INSTRUCTION = 2
    CONTINUOUS_DICTATION = 3


class VoiceAssistantDaemon:
    """
    Demonio principal del asistente de voz e intercomunicador.
    """

    def __init__(self):
        self.state = AssistantState.IDLE
        self.ducker = AudioDucker(factor=DUCKING_FACTOR)
        self.running = True
        self.last_dictation_activity = time.time()

        # Registrar manejador para atajo de teclado global (SIGUSR1)
        signal.signal(signal.SIGUSR1, self._handle_sigusr1)
        signal.signal(signal.SIGINT, self._handle_shutdown)
        signal.signal(signal.SIGTERM, self._handle_shutdown)

    def _handle_sigusr1(self, signum, frame):
        """Atajo de teclado global: activa directamente el modo dictado."""
        print("\n[Señal SIGUSR1 Recibida] Activando modo dictado por atajo...")
        self.enter_dictation_mode()

    def _handle_shutdown(self, signum, frame):
        """Cierre ordenado del demonio."""
        print("\n[Apagando Demonio] Restaurando audio y cerrando servicios...")
        self.running = False
        self.ducker.restore()
        intercom.stop_server()
        sys.exit(0)

    def enter_dictation_mode(self):
        """Transiciona al estado CONTINUOUS_DICTATION."""
        self.state = AssistantState.CONTINUOUS_DICTATION
        self.last_dictation_activity = time.time()
        feedback.play_sound("dictation_on.wav", blocking=True)
        print("[Estado] CONTINUOUS_DICTATION activado.")

    def exit_dictation_mode(self):
        """Regresa al estado IDLE."""
        self.state = AssistantState.IDLE
        feedback.play_sound("dictation_off.wav", blocking=True)
        self.ducker.restore()
        print("[Estado] Regresando a IDLE.")

    # --------------------------------------------------------------------------
    # Ejecución de Intenciones
    # --------------------------------------------------------------------------
    def dispatch_intent(self, intent_type: str, data: dict):
        """Ejecuta la acción correspondiente según el resultado del enrutador."""
        intent = data.get("intent")
        action = data.get("action")
        target = data.get("target")
        text = data.get("text", "")

        print(f"[Dispatch] intent='{intent}', action='{action}', target='{target}', text='{text}'")

        # 1. Multimedia Local
        if intent == "media":
            if action == "volume_up":
                actions.volume_up()
            elif action == "volume_down":
                actions.volume_down()
            elif action == "mute":
                actions.volume_mute_toggle()
            elif action == "play_pause":
                actions.media_play_pause()
            elif action == "next":
                actions.media_next()
            elif action == "previous":
                actions.media_previous()

        # 2. Control de Ventanas
        elif intent == "window":
            if action == "close":
                actions.close_active_window()
            elif action == "maximize":
                actions.toggle_maximize_active_window()
            elif action == "minimize":
                actions.minimize_active_window()
            elif action == "switch":
                actions.switch_window()

        # 3. Búsqueda Web
        elif intent == "web_search":
            feedback.play_sound("searching.wav")
            actions.open_web_search(text)

        # 4. Lectura de Notificaciones y Web
        elif intent == "notifications":
            if action == "enable":
                notification_monitor.enable()
            elif action == "disable":
                notification_monitor.disable()

        elif intent == "reading":
            if action == "stop":
                feedback.stop_speaking()
            elif action == "read_selection":
                reader.read_selection()
            elif action == "read_page":
                reader.read_or_summarize_web_page(summarize=False)
            elif action == "summary_page":
                reader.read_or_summarize_web_page(summarize=True)

        # 5. Dictado y Escritura
        elif intent == "dictate":
            self.enter_dictation_mode()

        elif intent == "quick_type":
            # Corregir puntuación con Ollama antes de escribir
            corrected = router.correct_dictation_text(text)
            actions.inject_text(corrected)

        # 6. Intercomunicador
        elif intent == "intercom_audio":
            wav_bytes = audio_engine.record_raw_audio(duration_seconds=5.0)
            intercom.send_audio_file(wav_bytes)

        elif intent == "send_text_intercom":
            intercom.send_text_message(text)

        # 7. Control de Pantallas y Dispositivos Multimedia de Red (Roku/Cast/LG)
        elif intent == "tv_cast_control":
            cast_control.execute_command(target or "tele_sala", action or "play")

        # 8. Respuesta Semántica del Asistente (Cálculos de Taller / Consultas)
        elif intent == "assistant_answer":
            if text:
                feedback.speak(text)

    # --------------------------------------------------------------------------
    # Bucle Principal de la Máquina de Estados
    # --------------------------------------------------------------------------
    def run(self):
        print("==================================================================")
        print("   Suite Modular de Asistente de Voz e Intercomunicador Iniciada   ")
        print("==================================================================")
        print(" -> Modo actual: Nodo C (Móvil / Lenovo i7 / GPU GTX 1060)")
        print(" -> Di 'computadora' o 'asistente' para dar una orden.")
        print(" -> O pulsa el atajo global (pkill -USR1 -f main.py) para dictar.\n")

        # Iniciar servicios en segundo plano
        intercom.start_server()
        notification_monitor.start()

        while self.running:
            # ------------------------------------------------------------------
            # Estado 1: IDLE (Escucha continua de palabra clave)
            # ------------------------------------------------------------------
            if self.state == AssistantState.IDLE:
                wake_word = audio_engine.listen_for_wake_word()
                if wake_word:
                    print(f"\n[Wake Word Detectada]: '{wake_word}'")
                    # Activar Audio Ducking para escuchar la orden sin interferencias
                    self.ducker.duck()
                    # Sonido inmediato de confirmación
                    feedback.play_sound("wake.wav", blocking=True)
                    self.state = AssistantState.SINGLE_INSTRUCTION

            # ------------------------------------------------------------------
            # Estado 2: SINGLE_INSTRUCTION (Captura de frase y enrutamiento)
            # ------------------------------------------------------------------
            elif self.state == AssistantState.SINGLE_INSTRUCTION:
                phrase = audio_engine.capture_single_instruction(max_seconds=8.0)
                if phrase:
                    source, result = router.route(phrase)
                    self.dispatch_intent(source, result)

                # Si la acción no nos cambió al modo dictado, restaurar volumen y volver a IDLE
                if self.state != AssistantState.CONTINUOUS_DICTATION:
                    self.ducker.restore()
                    self.state = AssistantState.IDLE

            # ------------------------------------------------------------------
            # Estado 3: CONTINUOUS_DICTATION (Dictado continuo con comandos in-band)
            # ------------------------------------------------------------------
            elif self.state == AssistantState.CONTINUOUS_DICTATION:
                # Comprobar timeout de seguridad por inactividad (60 segundos)
                if (time.time() - self.last_dictation_activity) > 60.0:
                    print("[Dictado] 60 segundos de inactividad: saliendo a IDLE...")
                    self.exit_dictation_mode()
                    continue

                chunk = audio_engine.capture_single_instruction(max_seconds=5.0)
                if not chunk:
                    continue

                self.last_dictation_activity = time.time()
                clean_chunk = chunk.lower().strip()

                # Comandos In-Band en caliente:
                if clean_chunk in ("borrar última frase", "borra eso", "borra esto"):
                    actions.undo_last_sentence()
                elif clean_chunk in ("nueva línea", "punto y aparte"):
                    actions.new_line()
                elif clean_chunk in ("nuevo párrafo", "párrafo nuevo"):
                    actions.new_paragraph()
                elif clean_chunk in ("enviar mensaje", "presionar enter"):
                    actions.submit_or_enter()
                elif clean_chunk in ("terminar dictado", "fin del dictado", "salir de dictado"):
                    self.exit_dictation_mode()
                else:
                    # Corrección ortográfica y de signos con Ollama
                    corrected = router.correct_dictation_text(chunk)
                    actions.inject_text(corrected)


if __name__ == "__main__":
    daemon = VoiceAssistantDaemon()
    daemon.run()
