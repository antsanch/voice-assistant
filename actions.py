#!/usr/bin/env python3
"""
Módulo: actions.py
Propósito: Ejecución de comandos del sistema operativo, manipulación de ventanas e inyección de teclado.

Arquitectura y Herramientas Utilizadas:
---------------------------------------
1. Inyección de Texto y Teclado (xdotool):
   En entornos X11, `xdotool` simula eventos de hardware a nivel de protocolo X.
   - `xdotool type --delay 8`: Escribe caracteres simulando pulsaciones humanas con
     un retardo de 8 ms entre letras para evitar pérdida de caracteres en editores pesados.
   - Cola de Deshacer (`deque`): Almacena la longitud exacta de las últimas frases inyectadas.
     Cuando el usuario dice "borra eso" o "borrar última frase", se envía la cantidad exacta
     de eventos BackSpace (`xdotool key --repeat N BackSpace`).
2. Control de Ventanas (wmctrl):
   Interactúa con el gestor de ventanas EWMH/NetWM para cerrar (`-c :ACTIVE:`),
   maximizar (`-b toggle,maximized_vert,maximized_horz`) o cambiar de foco.
3. Control Multimedia y Volumen (playerctl / pactl):
   Gestiona la reproducción de música local de forma unificada.
4. Lanzamiento de Programas (xdg-open / subprocess):
   Abre URLs web y aplicaciones del escritorio.
"""

import collections
import subprocess
import urllib.parse
from typing import Deque

from config import APPLICATION_ALIASES


class ActionManager:
    """
    Gestor de acciones del sistema operativo X11.
    """

    def __init__(self):
        # Registro histórico de las últimas 10 frases inyectadas (guarda el número de caracteres)
        self.injection_history: Deque[int] = collections.deque(maxlen=10)

    # --------------------------------------------------------------------------
    # 1. Inyección y Manipulación de Texto (Dictado Inteligente)
    # --------------------------------------------------------------------------
    def inject_text(self, text: str):
        """
        Inyecta texto directamente en la ventana enfocada actualmente mediante xdotool.
        Registra la longitud del texto escrito en la cola de historial para permitir deshacer.
        """
        if not text:
            return

        # Asegurar espacio al final si no lo tiene, para concatenar dictados continuos
        text_to_type = text if text.endswith(" ") else text + " "

        try:
            # --clearmodifiers evita que teclas como Shift o Alt interfieran con la escritura
            subprocess.run(
                ["xdotool", "type", "--delay", "8", "--clearmodifiers", text_to_type],
                check=False
            )
            # Guardamos la longitud para poder borrarla si se solicita
            self.injection_history.append(len(text_to_type))
        except FileNotFoundError:
            print("[ActionManager] xdotool no encontrado en el sistema.")

    def undo_last_sentence(self):
        """
        Comando reservado: "borrar última frase" / "borra eso".
        Envía N pulsaciones de la tecla BackSpace correspondientes a la última frase escrita.
        """
        if not self.injection_history:
            print("[ActionManager] No hay historial de texto previo para borrar.")
            return

        char_count = self.injection_history.pop()
        print(f"[ActionManager] Deshaciendo última frase: enviando {char_count} BackSpaces.")

        try:
            subprocess.run(
                ["xdotool", "key", "--repeat", str(char_count), "BackSpace"],
                check=False
            )
        except Exception as e:
            print(f"[ActionManager] Error al ejecutar BackSpace: {e}")

    def press_key(self, key_name: str, repeat: int = 1):
        """Envía una tecla especial (ej: 'Return', 'BackSpace', 'Escape')."""
        try:
            cmd = ["xdotool", "key"]
            if repeat > 1:
                cmd.extend(["--repeat", str(repeat)])
            cmd.append(key_name)
            subprocess.run(cmd, check=False)
        except Exception as e:
            print(f"[ActionManager] Error enviando tecla {key_name}: {e}")

    def new_line(self):
        """Comando reservado: "nueva línea" o "punto y aparte"."""
        self.press_key("Return", repeat=1)

    def new_paragraph(self):
        """Comando reservado: "nuevo párrafo"."""
        self.press_key("Return", repeat=2)

    def submit_or_enter(self):
        """Comando reservado: "enviar mensaje" o "presionar enter"."""
        self.press_key("Return", repeat=1)

    # --------------------------------------------------------------------------
    # 2. Control de Ventanas (wmctrl / xdotool)
    # --------------------------------------------------------------------------
    def close_active_window(self):
        """Cierra la ventana activa con elegancia mediante el protocolo ICCCM de X11."""
        try:
            subprocess.run(["wmctrl", "-c", ":ACTIVE:"], check=False)
        except Exception:
            pass

    def toggle_maximize_active_window(self):
        """Alterna entre maximizar y restaurar la ventana activa."""
        try:
            subprocess.run(
                ["wmctrl", "-r", ":ACTIVE:", "-b", "toggle,maximized_vert,maximized_horz"],
                check=False
            )
        except Exception:
            pass

    def minimize_active_window(self):
        """Minimiza la ventana activa."""
        try:
            subprocess.run(
                ["xdotool", "getactivewindow", "windowminimize"],
                check=False
            )
        except Exception:
            pass

    def switch_window(self):
        """Cambia a la siguiente ventana activa (simula Alt+Tab)."""
        try:
            subprocess.run(["xdotool", "key", "Alt+Tab"], check=False)
        except Exception:
            pass

    # --------------------------------------------------------------------------
    # 3. Control Multimedia y Volumen
    # --------------------------------------------------------------------------
    def volume_up(self, step: str = "5%"):
        """Sube el volumen del sink predeterminado."""
        try:
            subprocess.run(["pactl", "set-sink-volume", "@DEFAULT_SINK@", f"+{step}"], check=False)
        except Exception:
            pass

    def volume_down(self, step: str = "5%"):
        """Baja el volumen del sink predeterminado."""
        try:
            subprocess.run(["pactl", "set-sink-volume", "@DEFAULT_SINK@", f"-{step}"], check=False)
        except Exception:
            pass

    def volume_mute_toggle(self):
        """Alterna el silencio (mute/unmute)."""
        try:
            subprocess.run(["pactl", "set-sink-mute", "@DEFAULT_SINK@", "toggle"], check=False)
        except Exception:
            pass

    def media_play_pause(self):
        """Alterna reproducir/pausar en cualquier reproductor MPRIS activo."""
        try:
            subprocess.run(["playerctl", "play-pause"], check=False)
        except Exception:
            pass

    def media_next(self):
        """Siguiente pista musical."""
        try:
            subprocess.run(["playerctl", "next"], check=False)
        except Exception:
            pass

    def media_previous(self):
        """Pista musical anterior."""
        try:
            subprocess.run(["playerctl", "previous"], check=False)
        except Exception:
            pass

    # --------------------------------------------------------------------------
    # 4. Búsqueda Web y Aplicaciones
    # --------------------------------------------------------------------------
    def open_web_search(self, query: str):
        """
        Abre el navegador web predeterminado con una consulta en Google.
        """
        if not query:
            return
        encoded_query = urllib.parse.quote_plus(query.strip())
        url = f"https://www.google.com/search?q={encoded_query}"
        try:
            subprocess.Popen(["xdg-open", url], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        except Exception as e:
            print(f"[ActionManager] Error abriendo búsqueda web: {e}")

    def open_url(self, url: str):
        """Abre cualquier URL en el navegador."""
        try:
            subprocess.Popen(["xdg-open", url], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        except Exception as e:
            print(f"[ActionManager] Error abriendo URL: {e}")

    def launch_app_by_alias(self, alias_or_name: str) -> bool:
        """
        Lanza una aplicación usando el diccionario de alias o su nombre de ejecutable.
        """
        clean_name = alias_or_name.lower().strip()
        binary = APPLICATION_ALIASES.get(clean_name, clean_name)
        try:
            subprocess.Popen([binary], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            return True
        except Exception as e:
            print(f"[ActionManager] No se pudo lanzar la aplicación '{binary}': {e}")
            return False


# Instancia singleton para uso en toda la suite
actions = ActionManager()


# ------------------------------------------------------------------------------
# Prueba Rápida
# ------------------------------------------------------------------------------
if __name__ == "__main__":
    print("Probando actions.py...")
    print(" -> Registrando inyección simulada...")
    actions.injection_history.append(10)
    print(f" -> Historial actual: {list(actions.injection_history)}")
    print(" -> Acciones inicializadas correctamente.")
