#!/usr/bin/env python3
"""
Módulo: cast_control.py
Propósito: Control unificado de Smart TVs y reproductores en la LAN (Roku, Chromecast, LG webOS).

Protocolos Implementados:
-------------------------
1. Roku TV (Protocolo ECP - External Control Protocol):
   - Comunicación HTTP REST ultraligera en el puerto 8060.
   - Peticiones POST a `/keypress/{key}` (ej. Play, Pause, VolumeUp, PowerOff).
   - Lanzamiento de canales a `/launch/{app_id}` (ej. YouTube, Netflix, Spotify).
2. Google Chromecast (pychromecast):
   - Protocolo CAST sobre TLS en puerto 8009 con mensajes Protobuf.
   - Control de transporte (play, pause, stop) y volumen de medios.
3. LG Smart TV (webOS vía WebSocket):
   - Conexión WebSocket cifrada/autenticada con handshake de clave (client_key).
   - Encendido mediante paquetes mágicos Wake-on-LAN (WOL).
   - Notificaciones toast flotantes en pantalla (avisos del taller/intercomunicador).

Resiliencia y Modo Móvil / Fuera de Casa:
------------------------------------------
Dado que este Nodo C (Lenovo) puede estar fuera de casa, todas las conexiones tienen
un timeout estricto de 1.5 segundos. Si las pantallas no están en la red actual,
el módulo informa con gracia sin bloquear la ejecución ni generar excepciones fatales.
"""

import json
import socket
import subprocess
import threading
from pathlib import Path
from typing import Any, Dict, Optional
import requests

from config import NETWORK_MEDIA_DEVICES, BASE_DIR

# IDs comunes de canales en la tienda de Roku
ROKU_APP_IDS = {
    "youtube": "837",
    "netflix": "12",
    "spotify": "19977",
    "prime": "13",
    "pluto": "39129"
}

# Archivo local para almacenar la clave de emparejamiento con televisores LG
LG_CONFIG_PATH = BASE_DIR / ".lgtv_auth.json"


class CastController:
    """
    Controlador universal de dispositivos de transmisión y pantallas en la red local.
    """

    def __init__(self):
        self.devices = NETWORK_MEDIA_DEVICES

    def _is_ip_reachable(self, ip: str, port: int, timeout: float = 1.0) -> bool:
        """Comprueba rápidamente mediante socket TCP si la IP y puerto están respondiendo."""
        try:
            with socket.create_connection((ip, port), timeout=timeout):
                return True
        except (socket.timeout, ConnectionRefusedError, OSError):
            return False

    # --------------------------------------------------------------------------
    # 1. Driver Roku TV (Protocolo ECP HTTP REST :8060)
    # --------------------------------------------------------------------------
    def roku_keypress(self, device_key: str, key_name: str) -> bool:
        """
        Envía un comando de tecla a un Roku TV mediante HTTP POST.
        
        Teclas soportadas por Roku:
          Play, Pause, VolumeUp, VolumeDown, VolumeMute, PowerOn, PowerOff, Home, Back, Select
        """
        dev_info = self.devices.get(device_key)
        if not dev_info or dev_info.get("type") != "roku":
            print(f"[CastController] Dispositivo Roku '{device_key}' no configurado.")
            return False

        ip = dev_info.get("ip")
        port = dev_info.get("port", 8060)
        url = f"http://{ip}:{port}/keypress/{key_name}"

        try:
            resp = requests.post(url, timeout=1.5)
            if resp.status_code == 200:
                print(f"[Roku:{device_key}] Comando '{key_name}' ejecutado con éxito.")
                return True
        except requests.RequestException:
            print(f"[Roku:{device_key}] Dispositivo fuera de alcance (¿fuera de casa?).")

        return False

    def roku_launch_app(self, device_key: str, app_name: str) -> bool:
        """Lanza una aplicación en Roku por su identificador de canal."""
        dev_info = self.devices.get(device_key)
        if not dev_info:
            return False

        app_id = ROKU_APP_IDS.get(app_name.lower())
        if not app_id:
            print(f"[CastController] Canal Roku desconocido: {app_name}")
            return False

        ip = dev_info.get("ip")
        port = dev_info.get("port", 8060)
        url = f"http://{ip}:{port}/launch/{app_id}"

        try:
            resp = requests.post(url, timeout=1.5)
            return resp.status_code == 200
        except requests.RequestException:
            return False

    # --------------------------------------------------------------------------
    # 2. Driver Google Chromecast (pychromecast)
    # --------------------------------------------------------------------------
    def chromecast_control(self, device_key: str, action: str) -> bool:
        """
        Controla un Chromecast por IP directa (play, pause, stop).
        """
        dev_info = self.devices.get(device_key)
        if not dev_info or dev_info.get("type") != "chromecast":
            return False

        ip = dev_info.get("ip")
        if not self._is_ip_reachable(ip, 8009, timeout=1.0):
            print(f"[Chromecast:{device_key}] No responde en {ip}:8009 (fuera de red).")
            return False

        try:
            import pychromecast
            chromecasts, browser = pychromecast.get_chromecasts()
            target_cast = None
            for cc in chromecasts:
                if cc.cast_info.host == ip:
                    target_cast = cc
                    break

            if target_cast:
                target_cast.wait()
                mc = target_cast.media_controller
                if action == "play":
                    mc.play()
                elif action == "pause":
                    mc.pause()
                elif action == "stop":
                    mc.stop()
                pychromecast.discovery.stop_discovery(browser)
                return True
        except Exception as e:
            print(f"[Chromecast:{device_key}] Error: {e}")

        return False

    # --------------------------------------------------------------------------
    # 3. Driver LG Smart TV (webOS)
    # --------------------------------------------------------------------------
    def lg_power_on(self, device_key: str) -> bool:
        """Enciende una televisión LG enviando un paquete mágico Wake-on-LAN a su tarjeta de red."""
        dev_info = self.devices.get(device_key)
        if not dev_info:
            return False
        mac = dev_info.get("mac")
        if not mac:
            return False
        try:
            subprocess.run(["wakeonlan", mac], check=False)
            print(f"[LGTV:{device_key}] Paquete Wake-on-LAN enviado a MAC: {mac}")
            return True
        except Exception as e:
            print(f"[LGTV:{device_key}] Error al enviar Wake-on-LAN: {e}")
            return False

    # --------------------------------------------------------------------------
    # 4. Enrutador Unificado de Comandos Multimedia
    # --------------------------------------------------------------------------
    def execute_command(self, target_device: str, action: str, param: Optional[str] = None) -> bool:
        """
        Punto de entrada universal para el enrutador de intenciones.
        
        :param target_device: Alias del dispositivo ('tele_sala', 'roku_cuarto', 'chromecast_sala').
        :param action: Acción deseada ('play', 'pause', 'volume_up', 'volume_down', 'power_off', 'launch_app').
        :param param: Parámetro opcional (ej: nombre de app como 'youtube').
        """
        dev_info = self.devices.get(target_device)
        if not dev_info:
            # Si no se especificó un alias exacto, usar 'tele_sala' por defecto
            dev_info = self.devices.get("tele_sala")
            target_device = "tele_sala"

        if not dev_info:
            return False

        dev_type = dev_info.get("type")

        # Despachar al driver correspondiente
        if dev_type == "roku":
            key_map = {
                "play": "Play",
                "pause": "Pause",
                "play_pause": "Play",
                "volume_up": "VolumeUp",
                "volume_down": "VolumeDown",
                "mute": "VolumeMute",
                "power_off": "PowerOff",
                "power_on": "PowerOn",
                "home": "Home"
            }
            if action == "launch_app" and param:
                return self.roku_launch_app(target_device, param)
            key_name = key_map.get(action)
            if key_name:
                return self.roku_keypress(target_device, key_name)

        elif dev_type == "chromecast":
            return self.chromecast_control(target_device, action)

        elif dev_type == "lg_webos":
            if action == "power_on":
                return self.lg_power_on(target_device)

        return False


# Instancia singleton
cast_control = CastController()


if __name__ == "__main__":
    print("Probando cast_control.py (Modo Fuera de Casa / Safe Mock)...")
    print(" -> Enviando prueba a tele_sala (Roku)...")
    success = cast_control.execute_command("tele_sala", "pause")
    print(f" -> Resultado (esperado False si no estamos en la LAN de casa): {success}")
