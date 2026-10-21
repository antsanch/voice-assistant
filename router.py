#!/usr/bin/env python3
"""
Módulo: router.py
Propósito: Enrutamiento híbrido de intenciones en dos capas (Fast-Path Regex + Semántica Ollama).

Estrategia de Enrutamiento de Baja Latencia:
--------------------------------------------
1. Capa 1: Fast-Path Local (Regex - Latencia 0 ms):
   Evalúa la frase transcrita con expresiones regulares compiladas. Si coincide con
   órdenes comunes (control de volumen, ventanas, búsqueda web, lectura, atajos),
   se ejecuta inmediatamente sin tocar la GPU ni realizar peticiones HTTP.
2. Capa 2: Enrutador Semántico con LLM (Ollama JSON):
   Si la orden es ambigua, coloquial o requiere razonamiento (ej: dudas de carpintería,
   conversión de medidas, preguntas directas o envío de mensajes a otra persona),
   se envía a Qwen 2.5 en Ollama solicitando un esquema JSON estricto con 9 intenciones:
   - open_app
   - media
   - tv_cast_control
   - window
   - web_search
   - dictate
   - send_text_intercom
   - assistant_answer
   - web_summary
3. Corrector Ortográfico y de Puntuación para Dictado:
   Transforma palabras habladas como 'coma', 'punto' en signos reales (, .) y aplica
   mayúsculas y acentuación adecuada.
"""

import json
import re
from typing import Any, Dict, Optional, Tuple
import requests

from config import MODEL_NAME, OLLAMA_URL

# Esquema de System Prompt estricto para el enrutador semántico de Ollama
SEMANTIC_ROUTER_PROMPT = """Eres el clasificador de intenciones de un asistente de voz y taller en español.
Analiza la siguiente frase del usuario y clasifícala estrictamente en este esquema JSON:

{
  "intent": "open_app | media | tv_cast_control | window | web_search | dictate | send_text_intercom | assistant_answer | web_summary",
  "target": "identificador_app_dispositivo_o_nodo (ej: spotify, tele_sala, taller, chrome o null)",
  "action": "play | pause | volume_up | volume_down | power_off | launch_app | null",
  "text": "texto_corregido_o_respuesta_muy_breve_en_espanol"
}

Reglas obligatorias:
1. Si el usuario hace una pregunta directa de medidas, conversiones o carpintería (ej: 'cuántos mm son 3 cuartos de pulgada'), intent='assistant_answer' y en 'text' pon la respuesta concreta y muy corta (máximo 1 o 2 oraciones), escribiendo las unidades en palabras completas (ej: 'milímetros', 'centímetros') para síntesis de voz natural.
2. Si pide avisar o decir algo a alguien (ej: 'dile a mi esposa que ya terminé'), intent='send_text_intercom', target='taller' o 'oficina' y text='el mensaje a transmitir'.
3. Responde ÚNICAMENTE el bloque JSON válido, sin explicaciones ni markdown.
"""

# System Prompt para corrección ortográfica de dictado continuo
DICTATION_CORRECTOR_PROMPT = """Eres un corrector ortográfico y de puntuación especializado en transcripciones de voz en español.
Reglas:
1. Corrige la ortografía, acentuación y mayúsculas.
2. Convierte palabras de puntuación en signos correspondientes:
   - 'coma' -> ','
   - 'punto' o 'punto y seguido' -> '.'
   - 'punto y aparte' -> '\n'
   - 'dos puntos' -> ':'
   - 'abro interrogación' / 'cierro interrogación' -> '¿' / '?'
   - 'abro admiración' / 'cierro admiración' -> '¡' / '!'
3. Devuelve ÚNICAMENTE un JSON con el formato: {"text": "Texto corregido"} sin explicaciones adicionales.
"""


class IntentRouter:
    """
    Enrutador híbrido de intenciones.
    """

    def __init__(self):
        self._compile_fast_path_regex()

    def _compile_fast_path_regex(self):
        """Compila patrones de expresiones regulares para máxima velocidad."""
        # 1. Volumen y Multimedia Local
        self.re_vol_up = re.compile(r"^(sube|subir|aumenta|aumentar)\s+(el\s+)?volumen", re.I)
        self.re_vol_down = re.compile(r"^(baja|bajar|reduce|reducir)\s+(el\s+)?volumen", re.I)
        self.re_mute = re.compile(r"^(silencio|silenciar|mutear|quitar sonido)$", re.I)
        self.re_play_pause = re.compile(r"^(pausa|pausar|reproducir|reanudar|play)$", re.I)
        self.re_next = re.compile(r"^(siguiente(\s+canci[oó]n|\s+pista)?|avanza)$", re.I)
        self.re_prev = re.compile(r"^(anterior(\s+canci[oó]n|\s+pista)?|regresa)$", re.I)

        # 2. Control de Ventanas
        self.re_win_close = re.compile(r"^(cierra|cerrar)(\s+la)?\s+ventana", re.I)
        self.re_win_max = re.compile(r"^(maximiza|maximizar)(\s+la\s+ventana)?", re.I)
        self.re_win_min = re.compile(r"^(minimiza|minimizar)(\s+la\s+ventana)?", re.I)
        self.re_win_switch = re.compile(r"^(cambia|cambiar|siguiente)\s+ventana", re.I)

        # 3. Búsqueda Web
        self.re_search = re.compile(r"^(busca|buscar|encuentra)\s+(en\s+internet|en\s+google)\s+(.+)", re.I)

        # 4. Lectura de Notificaciones y Web
        self.re_notif_enable = re.compile(r"^activar\s+lectura(\s+de\s+mensajes)?", re.I)
        self.re_notif_disable = re.compile(r"^(silenciar|desactivar)\s+(mensajes|notificaciones)", re.I)
        self.re_read_selection = re.compile(r"^lee\s+(la\s+selecci[oó]n|esto|el\s+texto)", re.I)
        self.re_read_page = re.compile(r"^l[eé]eme\s+(esta\s+p[aá]gina|la\s+web)", re.I)
        self.re_summary_page = re.compile(r"^resume\s+(esta\s+p[aá]gina|el\s+art[ií]culo)", re.I)
        self.re_stop_reading = re.compile(r"^(det[eé]n\s+la\s+lectura|c[aá]llate|para)$", re.I)

        # 5. Modos de Dictado y Escritura
        self.re_quick_type = re.compile(r"^(escribe|apunta)\s+(.+)", re.I)
        self.re_enter_dictation = re.compile(r"^(modo\s+dictado|dictado\s+continuo)$", re.I)

        # 6. Intercomunicador
        self.re_intercom_audio = re.compile(r"^(grabar\s+mensaje(\s+para)?|enviar\s+audio)(\s+(taller|oficina))?", re.I)
        self.re_intercom_say = re.compile(r"^(dile|avisa|av[ií]sale)\s+a\s+(.+?)\s+que\s+(.+)", re.I)

        # 7. Dispositivos Multimedia de Red (TVs)
        self.re_tv_cmd = re.compile(r"^(pausa|apaga|enciende|sube el volumen en|abre youtube en)\s+(la\s+tele|el\s+roku|el\s+chromecast)", re.I)

    def route_fast_path(self, phrase: str) -> Optional[Dict[str, Any]]:
        """
        Evalúa la frase en la Capa 1 (Fast-Path Regex).
        Retorna un diccionario de intención estructurado si hubo coincidencia, o None.
        """
        clean = phrase.strip().lower()

        # Multimedia
        if self.re_vol_up.match(clean):
            return {"intent": "media", "action": "volume_up"}
        if self.re_vol_down.match(clean):
            return {"intent": "media", "action": "volume_down"}
        if self.re_mute.match(clean):
            return {"intent": "media", "action": "mute"}
        if self.re_play_pause.match(clean):
            return {"intent": "media", "action": "play_pause"}
        if self.re_next.match(clean):
            return {"intent": "media", "action": "next"}
        if self.re_prev.match(clean):
            return {"intent": "media", "action": "previous"}

        # Ventanas
        if self.re_win_close.match(clean):
            return {"intent": "window", "action": "close"}
        if self.re_win_max.match(clean):
            return {"intent": "window", "action": "maximize"}
        if self.re_win_min.match(clean):
            return {"intent": "window", "action": "minimize"}
        if self.re_win_switch.match(clean):
            return {"intent": "window", "action": "switch"}

        # Búsqueda Web
        m_search = self.re_search.match(clean)
        if m_search:
            query = m_search.group(3).strip()
            return {"intent": "web_search", "text": query}

        # Notificaciones
        if self.re_notif_enable.match(clean):
            return {"intent": "notifications", "action": "enable"}
        if self.re_notif_disable.match(clean):
            return {"intent": "notifications", "action": "disable"}

        # Lectura
        if self.re_stop_reading.match(clean):
            return {"intent": "reading", "action": "stop"}
        if self.re_read_selection.match(clean):
            return {"intent": "reading", "action": "read_selection"}
        if self.re_read_page.match(clean):
            return {"intent": "reading", "action": "read_page"}
        if self.re_summary_page.match(clean):
            return {"intent": "reading", "action": "summary_page"}

        # Dictado y Escritura
        if self.re_enter_dictation.match(clean):
            return {"intent": "dictate", "action": "start"}
        m_type = self.re_quick_type.match(clean)
        if m_type:
            text_to_type = m_type.group(2).strip()
            return {"intent": "quick_type", "text": text_to_type}

        # Intercomunicador
        m_audio = self.re_intercom_audio.match(clean)
        if m_audio:
            target = m_audio.group(4) or "peer"
            return {"intent": "intercom_audio", "target": target}
        m_say = self.re_intercom_say.match(clean)
        if m_say:
            recipient = m_say.group(2).strip()
            message = m_say.group(3).strip()
            return {"intent": "send_text_intercom", "target": recipient, "text": message}

        return None

    def route_semantic_llm(self, phrase: str) -> Dict[str, Any]:
        """
        Evalúa la frase en la Capa 2 mediante consulta estructurada JSON a Ollama.
        """
        payload = {
            "model": MODEL_NAME,
            "prompt": f"{SEMANTIC_ROUTER_PROMPT}\n\nFrase del usuario: \"{phrase}\"",
            "format": "json",
            "temperature": 0.0,
            "stream": False,
            "keep_alive": -1
        }

        try:
            response = requests.post(f"{OLLAMA_URL}/api/generate", json=payload, timeout=8.0)
            if response.status_code == 200:
                raw_json = response.json().get("response", "{}")
                return json.loads(raw_json)
        except Exception as e:
            print(f"[IntentRouter] Error en enrutamiento semántico con Ollama: {e}")

        # Fallback genérico si el LLM estuviera temporalmente inaccesible
        return {
            "intent": "assistant_answer",
            "target": None,
            "action": None,
            "text": "No pude procesar la orden en este momento."
        }

    def correct_dictation_text(self, raw_text: str) -> str:
        """
        Aplica corrección ortográfica, signos de puntuación y capitalización con Ollama.
        """
        if not raw_text or not raw_text.strip():
            return ""

        payload = {
            "model": MODEL_NAME,
            "prompt": f"{DICTATION_CORRECTOR_PROMPT}\n\nTexto transcrito: \"{raw_text}\"",
            "format": "json",
            "temperature": 0.0,
            "stream": False,
            "keep_alive": -1
        }

        try:
            response = requests.post(f"{OLLAMA_URL}/api/generate", json=payload, timeout=6.0)
            if response.status_code == 200:
                raw_json = response.json().get("response", "{}")
                data = json.loads(raw_json)
                corrected = data.get("text", "").strip()
                if corrected:
                    return corrected
        except Exception:
            pass

        # Si falla Ollama, devolver el texto original con mayúscula inicial
        return raw_text.strip().capitalize()

    def route(self, phrase: str) -> Tuple[str, Dict[str, Any]]:
        """
        Punto de entrada universal: evalúa Fast-Path primero y, de no coincidir, delega a Ollama.
        Retorna ('fast_path' | 'semantic_llm', payload_resultado).
        """
        fast_result = self.route_fast_path(phrase)
        if fast_result is not None:
            return ("fast_path", fast_result)

        llm_result = self.route_semantic_llm(phrase)
        return ("semantic_llm", llm_result)


# Instancia singleton
router = IntentRouter()


if __name__ == "__main__":
    print("Probando IntentRouter...")
    test_phrases = [
        "sube el volumen",
        "cierra la ventana",
        "busca en google cómo afilar una gubia",
        "escribe nos vemos mañana a las diez",
        "¿cuántos milímetros son 3 cuartos de pulgada?"
    ]
    for p in test_phrases:
        source, res = router.route(p)
        print(f"[{source.upper()}] \"{p}\" -> {res}")
