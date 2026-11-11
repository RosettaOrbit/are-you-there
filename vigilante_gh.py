"""
Vigilante para GitHub Actions: hace UNA revisión y termina.
GitHub lo ejecuta cada 5 minutos y guarda el estado en estado.json entre ejecuciones.

Avisa al celular (con ntfy) cuando:
  - un juego de Roblox pasa de 0 jugadores a 1 o más
  - un canal de YouTube sube un video nuevo

Los ajustes NO van en este archivo (el repositorio es público).
Van como "secrets" del repositorio:
  NTFY_TOPIC        -> el tema de ntfy, ej. roblox-watch-k8f3q2
  ROBLOX_PLACE_IDS  -> números de los juegos, separados por comas
  YOUTUBE_CHANNELS  -> canales (ID UC... o @usuario), separados por comas
"""

import json
import os
import re
import urllib.request
import xml.etree.ElementTree as ET

NTFY_TOPIC = os.environ.get("NTFY_TOPIC", "").strip()
ROBLOX_PLACE_IDS = [p.strip() for p in os.environ.get("ROBLOX_PLACE_IDS", "").split(",") if p.strip()]
YOUTUBE_CHANNELS = [c.strip() for c in os.environ.get("YOUTUBE_CHANNELS", "").split(",") if c.strip()]
AVISAR_CUANDO_ROBLOX_SE_VACIA = os.environ.get("AVISAR_VACIO", "").lower() in ("1", "true", "si", "sí")

ARCHIVO_ESTADO = "estado.json"
HEADERS = {"User-Agent": "Mozilla/5.0 (vigilante personal)"}
NS = {"atom": "http://www.w3.org/2005/Atom", "yt": "http://www.youtube.com/xml/schemas/2015"}

# Los registros de un repositorio público los puede ver cualquiera,
# así que aquí no se imprimen nombres de juegos ni de canales.


def descargar(url):
    req = urllib.request.Request(url, headers=HEADERS)
    with urllib.request.urlopen(req, timeout=20) as resp:
        return resp.read()


def notificar(titulo, mensaje, enlace=None):
    if not NTFY_TOPIC:
        print("Falta el secret NTFY_TOPIC; no se envió la notificación.")
        return
    datos = {"topic": NTFY_TOPIC, "title": titulo, "message": mensaje, "tags": ["bell"]}
    if enlace:
        datos["click"] = enlace
    req = urllib.request.Request(
        "https://ntfy.sh/",
        data=json.dumps(datos).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        urllib.request.urlopen(req, timeout=15).close()
        print("Notificación enviada.")
    except Exception as e:
        print(f"No se pudo enviar la notificación ({type(e).__name__}).")


def cargar_estado():
    try:
        with open(ARCHIVO_ESTADO, encoding="utf-8") as f:
            estado = json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        estado = {}
    estado.setdefault("roblox", {})
    estado.setdefault("youtube", {})
    return estado


def guardar_estado(estado):
    with open(ARCHIVO_ESTADO, "w", encoding="utf-8") as f:
        json.dump(estado, f, ensure_ascii=False)


# ----------------------- ROBLOX -----------------------

def revisar_roblox(estado):
    for n, place in enumerate(ROBLOX_PLACE_IDS, 1):
        info = estado["roblox"].setdefault(place, {"anterior": 0})
        try:
            if "universe" not in info:
                data = json.loads(descargar(f"https://apis.roblox.com/universes/v1/places/{place}/universe"))
                info["universe"] = data["universeId"]
            data = json.loads(descargar(f"https://games.roblox.com/v1/games?universeIds={info['universe']}"))
            juego = data["data"][0]
            nombre, jugando = juego["name"], juego["playing"]
            enlace = f"https://www.roblox.com/games/{place}"
            if info["anterior"] == 0 and jugando > 0:
                notificar(f"{nombre} está activo", f"{jugando} jugador(es) en el juego ahora.", enlace)
            elif info["anterior"] > 0 and jugando == 0 and AVISAR_CUANDO_ROBLOX_SE_VACIA:
                notificar(f"{nombre} está vacío", "Ya no hay jugadores.", enlace)
            print(f"Roblox juego #{n}: revisado ({'con' if jugando else 'sin'} jugadores).")
            info["anterior"] = jugando
        except Exception as e:
            print(f"Roblox juego #{n}: error ({type(e).__name__}).")


# ----------------------- YOUTUBE -----------------------

def youtube_channel_id(texto):
    m = re.search(r"(UC[\w-]{22})", texto)
    if m:
        return m.group(1)
    m = re.search(r"@[\w.\-]+", texto)
    if not m:
        raise ValueError("canal no reconocido")
    html = descargar(f"https://www.youtube.com/{m.group(0)}").decode("utf-8", "ignore")
    for patron in (r'youtube\.com/channel/(UC[\w-]{22})', r'"externalId":"(UC[\w-]{22})"', r'"channelId":"(UC[\w-]{22})"'):
        m2 = re.search(patron, html)
        if m2:
            return m2.group(1)
    raise ValueError("no se encontró el ID del canal")


def youtube_videos(channel_id):
    raiz = ET.fromstring(descargar(f"https://www.youtube.com/feeds/videos.xml?channel_id={channel_id}"))
    nombre = raiz.findtext("atom:title", default="el canal", namespaces=NS)
    videos = []
    for entry in raiz.findall("atom:entry", NS):
        vid = entry.findtext("yt:videoId", namespaces=NS)
        titulo = entry.findtext("atom:title", default="(sin título)", namespaces=NS)
        videos.append((vid, titulo, f"https://www.youtube.com/watch?v={vid}"))
    return nombre, videos


def revisar_youtube(estado):
    for n, canal in enumerate(YOUTUBE_CHANNELS, 1):
        info = estado["youtube"].setdefault(canal, {})
        try:
            if "id" not in info:
                info["id"] = youtube_channel_id(canal)
            nombre, videos = youtube_videos(info["id"])
            ids = [v[0] for v in videos]
            if "vistos" not in info:
                # Primera vez: guardar los videos actuales sin avisar
                info["vistos"] = ids
                print(f"YouTube canal #{n}: primera revisión, {len(ids)} videos registrados.")
                continue
            nuevos = [v for v in videos if v[0] not in info["vistos"]]
            for vid, titulo, enlace in reversed(nuevos):
                notificar(f"Nuevo video de {nombre}", titulo, enlace)
            info["vistos"] = list(dict.fromkeys(ids + info["vistos"]))[:100]
            print(f"YouTube canal #{n}: revisado, {len(nuevos)} nuevo(s).")
        except Exception as e:
            print(f"YouTube canal #{n}: error ({type(e).__name__}).")


def main():
    estado = cargar_estado()
    if not ROBLOX_PLACE_IDS and not YOUTUBE_CHANNELS:
        print("No hay juegos ni canales configurados en los secrets.")
    revisar_roblox(estado)
    revisar_youtube(estado)
    guardar_estado(estado)


if __name__ == "__main__":
    main()
