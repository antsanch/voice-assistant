#!/usr/bin/env python3
"""
Módulo: ducking.py
Propósito: Gestión automática de Audio Ducking (atenuación de volumen multimedia).

¿Qué es el Audio Ducking y por qué es fundamental?
--------------------------------------------------
El "Audio Ducking" es la técnica de atenuar automáticamente el volumen de la música
o contenido de fondo mientras otra fuente de audio (como la voz del usuario, el asistente
o un mensaje de intercomunicador) necesita prioridad auditiva.

Mecanismo de acción:
1. Prioridad MPRIS (playerctl): Controla reproductores multimedia que siguen el estándar
   MPRIS en Linux (Spotify, VLC, Chrome, Firefox). Es la vía más limpia porque baja
   el volumen del reproductor sin alterar el volumen maestro de la tarjeta de sonido.
2. Respaldo por Sink (pactl): Si no hay reproductores MPRIS activos o se desea asegurar
   el silencio en todo el sistema, atenúa el volumen de salida del sink predeterminado
   de PipeWire / PulseAudio al porcentaje definido (por defecto 20%).

Uso como Context Manager:
-------------------------
    with AudioDucker(factor=0.20):
        # Durante este bloque, la música está atenuada
        escuchar_al_usuario()
        responder_por_voz()
    # Al salir del bloque 'with', el volumen original se restaura con exactitud.
"""

import re
import subprocess
from typing import Optional


class AudioDucker:
    """
    Context manager de Python para reducir y restaurar el volumen del sistema.
    """

    def __init__(self, factor: float = 0.20):
        """
        :param factor: Nivel de atenuación deseado expresado entre 0.0 (silencio) y 1.0 (100%).
                       Por defecto 0.20 (20% del volumen).
        """
        self.factor = max(0.0, min(1.0, factor))
        self.previous_playerctl_volumes: dict[str, float] = {}
        self.previous_sink_volume: Optional[int] = None
        self.is_ducked = False

    def __enter__(self):
        self.duck()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.restore()

    def duck(self):
        """Aplica la atenuación de audio en reproductores activos y en el sink de PulseAudio."""
        if self.is_ducked:
            return

        # 1. Intentar atenuar mediante playerctl (MPRIS sobre D-Bus)
        self._duck_playerctl()

        # 2. Respaldo / Refuerzo con pactl (PipeWire / PulseAudio)
        self._duck_pactl()

        self.is_ducked = True

    def restore(self):
        """Restaura el volumen previo exacto que tenían los reproductores y el sink."""
        if not self.is_ducked:
            return

        # 1. Restaurar reproductores playerctl
        self._restore_playerctl()

        # 2. Restaurar sink de pactl
        self._restore_pactl()

        self.is_ducked = False

    # --------------------------------------------------------------------------
    # Métodos Internos: playerctl (MPRIS)
    # --------------------------------------------------------------------------
    def _duck_playerctl(self):
        """Consulta reproductores activos y reduce su volumen individualmente."""
        try:
            # Listar reproductores disponibles (ej: spotify, chromium, vlc)
            result = subprocess.run(
                ["playerctl", "-l"],
                stdout=subprocess.PIPE,
                stderr=subprocess.DEVNULL,
                text=True,
                check=False
            )
            players = [p.strip() for p in result.stdout.splitlines() if p.strip()]

            for player in players:
                # Obtener volumen actual del reproductor (flotante entre 0.0 y 1.0)
                vol_proc = subprocess.run(
                    ["playerctl", "-p", player, "volume"],
                    stdout=subprocess.PIPE,
                    stderr=subprocess.DEVNULL,
                    text=True,
                    check=False
                )
                try:
                    current_vol = float(vol_proc.stdout.strip())
                    self.previous_playerctl_volumes[player] = current_vol

                    # Reducir el volumen al factor objetivo o a una fracción de su volumen actual
                    target_vol = min(current_vol, self.factor)
                    subprocess.run(
                        ["playerctl", "-p", player, "volume", str(target_vol)],
                        stdout=subprocess.DEVNULL,
                        stderr=subprocess.DEVNULL,
                        check=False
                    )
                except ValueError:
                    continue
        except FileNotFoundError:
            # playerctl no está instalado en este entorno
            pass

    def _restore_playerctl(self):
        """Devuelve a cada reproductor su volumen previo."""
        for player, original_vol in self.previous_playerctl_volumes.items():
            try:
                subprocess.run(
                    ["playerctl", "-p", player, "volume", str(original_vol)],
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                    check=False
                )
            except Exception:
                pass
        self.previous_playerctl_volumes.clear()

    # --------------------------------------------------------------------------
    # Métodos Internos: pactl (PipeWire / PulseAudio)
    # --------------------------------------------------------------------------
    def _duck_pactl(self):
        """Consulta el volumen actual del sink predeterminado y lo atenúa."""
        try:
            # Obtener volumen actual del sink por defecto
            result = subprocess.run(
                ["pactl", "get-sink-volume", "@DEFAULT_SINK@"],
                stdout=subprocess.PIPE,
                stderr=subprocess.DEVNULL,
                text=True,
                check=False
            )
            if result.returncode == 0:
                # La salida suele ser del tipo: "Volumen: front-left: 65536 / 100% / -0.00 dB, ..."
                match = re.search(r"(\d+)%", result.stdout)
                if match:
                    current_percent = int(match.group(1))
                    self.previous_sink_volume = current_percent

                    # Calculamos el volumen atenuado (ej. si estaba al 80%, bajar al 20%)
                    target_percent = int(self.factor * 100)
                    if current_percent > target_percent:
                        subprocess.run(
                            ["pactl", "set-sink-volume", "@DEFAULT_SINK@", f"{target_percent}%"],
                            stdout=subprocess.DEVNULL,
                            stderr=subprocess.DEVNULL,
                            check=False
                        )
        except FileNotFoundError:
            pass

    def _restore_pactl(self):
        """Restaura el volumen previo del sink predeterminado."""
        if self.previous_sink_volume is not None:
            try:
                subprocess.run(
                    ["pactl", "set-sink-volume", "@DEFAULT_SINK@", f"{self.previous_sink_volume}%"],
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                    check=False
                )
            except Exception:
                pass
            self.previous_sink_volume = None


# ------------------------------------------------------------------------------
# Prueba Rápida Directa (si se ejecuta el script directamente)
# ------------------------------------------------------------------------------
if __name__ == "__main__":
    import time
    print("Probando AudioDucker: Atenuando volumen al 20% durante 3 segundos...")
    with AudioDucker(factor=0.20):
        print(" -> Volumen atenuado. Escuchando...")
        time.sleep(3)
    print(" -> Volumen restaurado con éxito.")
