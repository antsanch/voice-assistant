#!/usr/bin/env python3
"""
Módulo: notifications.py
Propósito: Escucha pasiva en segundo plano de notificaciones D-Bus (WhatsApp, Telegram) y lectura por voz.

Arquitectura de Notificaciones en Linux (D-Bus):
------------------------------------------------
1. El Bus de Sesión (Session Bus):
   En entornos de escritorio Linux, las aplicaciones (Telegram, navegadores web, clientes de correo)
   envían llamadas RPC al bus `org.freedesktop.Notifications` llamando al método `Notify`.
2. Modo Monitor / Eavesdropping:
   Para no reemplazar ni romper el centro de notificaciones nativo del escritorio Zorin,
   nos conectamos como observadores pasivos mediante un filtro de captura D-Bus.
3. Filtrado Inteligente de Ruido:
   No todas las notificaciones deben leerse en voz alta (por ejemplo, cambios de brillo o batería).
   Filtramos exclusivamente las procedentes de mensajería relevante:
   - Telegram Desktop
   - WhatsApp Web / Chrome / Firefox
   - Thunderbird / Correo
4. Control de Estado por Voz:
   El usuario puede activar o silenciar esta función en cualquier momento diciendo:
   - "activar lectura de mensajes"
   - "silenciar mensajes"
"""

import threading
import time
from typing import Optional

import dbus
from dbus.mainloop.glib import DBusGMainLoop
from gi.repository import GLib

import config
from feedback import feedback
from ducking import AudioDucker

# Lista de identificadores de aplicaciones de mensajería para audición
ALLOWED_APP_NAMES = {
    "telegram", "telegramdesktop", "whatsapp", "google-chrome",
    "chromium", "firefox", "thunderbird", "slack"
}


class NotificationMonitor:
    """
    Monitor de eventos D-Bus para lectura de notificaciones en tiempo real.
    """

    def __init__(self):
        self.enabled = config.READ_NOTIFICATIONS
        self._thread: Optional[threading.Thread] = None
        self._loop: Optional[GLib.MainLoop] = None

    def enable(self):
        """Activa la lectura de mensajes por voz."""
        self.enabled = True
        print("[NotificationMonitor] Lectura de notificaciones ACTIVADA.")
        feedback.speak("Lectura de notificaciones activada.")

    def disable(self):
        """Silencia la lectura de mensajes."""
        self.enabled = False
        print("[NotificationMonitor] Lectura de notificaciones SILENCIADA.")
        feedback.speak("Lectura de notificaciones silenciada.")

    def toggle(self):
        """Alterna el estado de lectura."""
        if self.enabled:
            self.disable()
        else:
            self.enable()

    def _on_notification_message(self, bus, message):
        """
        Callback ejecutado por el bus D-Bus cada vez que una aplicación llama a 'Notify'.
        
        Firma estándar de org.freedesktop.Notifications.Notify:
          UINT32 Notify(
            STRING app_name,
            UINT32 replaces_id,
            STRING app_icon,
            STRING summary,
            STRING body,
            ARRAY actions,
            DICT hints,
            INT32 expire_timeout
          )
        """
        if not self.enabled:
            return

        # Verificar que sea una llamada al método Notify
        if message.get_interface() != "org.freedesktop.Notifications" or message.get_member() != "Notify":
            return

        args = message.get_args_list()
        if len(args) < 5:
            return

        app_name = str(args[0]).lower().strip()
        summary = str(args[3]).strip()  # Título / Remitente
        body = str(args[4]).strip()     # Texto del mensaje

        # Verificar si la aplicación remitente está en la lista permitida
        is_allowed = any(allowed in app_name for allowed in ALLOWED_APP_NAMES)
        if not is_allowed and not ("whatsapp" in summary.lower() or "telegram" in summary.lower()):
            return

        # Evitar notificaciones vacías
        if not summary and not body:
            return

        print(f"\n[Notificación Capturada]: [{app_name}] Remitente: '{summary}' | Cuerpo: '{body}'")

        def _announce():
            with AudioDucker(factor=0.20):
                feedback.play_sound("intercom_chime.wav", blocking=True)
                msg_to_read = f"Mensaje de {summary}: {body}" if summary and body else f"Mensaje: {summary or body}"
                feedback.speak(msg_to_read)

        # Despachar lectura en un hilo para no bloquear el bucle de eventos D-Bus
        threading.Thread(target=_announce, daemon=True).start()

    def start(self):
        """
        Inicializa el listener de D-Bus en un hilo secundario independiente (demonio).
        """
        if self._thread is not None and self._thread.is_alive():
            return

        def _run_loop():
            # Configurar el bucle principal GLib para D-Bus
            DBusGMainLoop(set_as_default=True)
            bus = dbus.SessionBus()

            # Agregar match rule para espiar las llamadas a Notify
            bus.add_match_string_non_blocking(
                "eavesdrop=true,type='method_call',interface='org.freedesktop.Notifications',member='Notify'"
            )
            bus.add_message_filter(self._on_notification_message)

            self._loop = GLib.MainLoop()
            try:
                self._loop.run()
            except Exception as e:
                print(f"[NotificationMonitor] Error en bucle D-Bus: {e}")

        self._thread = threading.Thread(target=_run_loop, daemon=True, name="dbus_notifications")
        self._thread.start()
        print("[NotificationMonitor] Monitor D-Bus iniciado en segundo plano.")


# Instancia singleton
notification_monitor = NotificationMonitor()


if __name__ == "__main__":
    print("Iniciando prueba de notification_monitor...")
    notification_monitor.enable()
    notification_monitor.start()
    print("Envía una notificación de prueba en tu terminal con:")
    print("  notify-send -a 'telegram' 'Juan Pérez' 'Hola, ¿está lista la mesa?'")
    print("Esperando 5 segundos...")
    time.sleep(5)
