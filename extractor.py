import yt_dlp
import requests
import json
import re
import urllib.parse
import os

def extraer_enlace_real(url_publica, proxy=None):
    print(f"[*] Analizando UfRL con yt-dlp: {url_publica}")
    
    ydl_opts = {
        'format': 'best',
        'noplaylist': True,
        'quiet': True,
    }
    
    if proxy:
        ydl_opts['proxy'] = proxy
        print(f"[*] 🛡️ yt-dlp usando proxy manual: {proxy}")
    
    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        try:
            info_dict = ydl.extract_info(url_publica, download=False)
            
            enlace_directo = info_dict.get('url', None)
            titulo = info_dict.get('title', 'video_descargado')
            ext = info_dict.get('ext', 'mp4')
            
            if not enlace_directo and 'entries' in info_dict:
                enlace_directo = info_dict['entries'][0].get('url', None)
                titulo = info_dict['entries'][0].get('title', titulo)

            if not enlace_directo:
                return None, None

            nombre_final = f"{titulo}.{ext}".replace("/", "_").replace("\\", "_").replace(":", "-")
            return enlace_directo, nombre_final
            
        except Exception as e:
            print(f"[-] Error al extraer con yt-dlp: {e}")
            return None, None

def es_enlace_directo(url):
    if url.startswith("magnet:?"):
        return True, "Descarga_Torrent"

    if ".onion" in url:
        ruta = urllib.parse.urlparse(url).path
        nombre_archivo = os.path.basename(ruta)
        if not nombre_archivo: nombre_archivo = "archivo_tor_desconocido"
        return True, nombre_archivo

    ruta = urllib.parse.urlparse(url).path
    nombre_archivo = os.path.basename(ruta)
    _, ext = os.path.splitext(nombre_archivo)
    
    extensiones_comunes = [
        '.pdf', '.doc', '.docx', '.xls', '.xlsx', '.txt', '.csv',
        '.zip', '.rar', '.7z', '.tar', '.gz', '.xz', 
        '.jpg', '.png', '.gif', '.jpeg', '.webp',
        '.exe', '.iso', '.deb', '.apk', '.msi',
        '.mp4', '.mkv', '.avi', '.mov',
        '.mp3', '.ogg', '.wav', '.flac', '.torrent'
    ]

    if ext.lower() in extensiones_comunes:
        if not nombre_archivo:
            nombre_archivo = "archivo_descargado" + ext
        return True, nombre_archivo
        
    return False, None

def resolver_url(url_usuario, proxy=None):
    url_usuario = url_usuario.strip()
    
    if not url_usuario.startswith(('http://', 'https://', 'ftp://', 'magnet:')):
        if ".onion" in url_usuario:
            url_usuario = 'http://' + url_usuario
            print(f"[*] Auto-corrigiendo URL Onion: {url_usuario}")
        else:
            url_usuario = 'https://' + url_usuario
            print(f"[*] Auto-corrigiendo URL genérica: {url_usuario}")
    
    es_directo, nombre_archivo = es_enlace_directo(url_usuario)
    if es_directo:
        print(f"[*] Enlace directo o Torrent detectado: {nombre_archivo}")
        return url_usuario, nombre_archivo
        
    print("[*] Enlace genérico detectado. Delegando a yt-dlp...")
    return extraer_enlace_real(url_usuario, proxy)

def enviar_a_aria2(enlace_directo, nombre_archivo, proxy=None):
    print(f"[*] Enviando {nombre_archivo} a aria2...")
    rpc_url = "http://localhost:6800/jsonrpc"
    
    opciones = {
        "split": "4",
        "max-connection-per-server": "4"
    }

    if not enlace_directo.startswith("magnet:?") and ".onion" not in enlace_directo:
        opciones["out"] = nombre_archivo

    if proxy:
        proxy_aria = proxy.replace("127.0.0.1:8118", "poc-privoxy:8118").replace("localhost", "poc-privoxy")
        print(f"[*] 🛡️ Usando proxy manual para Aria2: {proxy_aria}")
        opciones["all-proxy"] = proxy_aria
    elif ".onion" in enlace_directo:
        print("[*] 🧅 Enlace .onion detectado. Enrutando a través de Privoxy -> Tor...")
        opciones["all-proxy"] = "http://poc-privoxy:8118"
    
    payload = {
        "jsonrpc": "2.0",
        "id": "mi_gestor_gtk",
        "method": "aria2.addUri",
        "params": [
            [enlace_directo],
            opciones
        ]
    }
    
    try:
        respuesta = requests.post(rpc_url, json=payload)
        datos = respuesta.json()
        if "error" in datos:
            print(f"[-] ARIA2 RECHAZÓ EL ENLACE: {datos['error'].get('message', 'Desconocido')}")
        return datos
    except Exception as e:
        print(f"[-] Error conectando con aria2: {e}")
        return None

def obtener_estado_aria2():
    payload = {
        "jsonrpc": "2.0",
        "id": "monitor_gtk",
        "method": "aria2.tellActive",
        "params": [["gid", "totalLength", "completedLength", "downloadSpeed"]]
    }
    try:
        respuesta = requests.post("http://localhost:6800/jsonrpc", json=payload)
        datos = respuesta.json()
        if 'result' in datos: return datos['result']
    except: return []
    return []

def formatear_tamano(bytes_str):
    try:
        bytes_num = int(bytes_str)
        if bytes_num == 0: return "0 MB"
        for unidad in ['B', 'KB', 'MB', 'GB', 'TB']:
            if bytes_num < 1024.0: return f"{bytes_num:.2f} {unidad}"
            bytes_num /= 1024.0
    except: return "Unknown"

def obtener_info_gid(gid):
    payload = {
        "jsonrpc": "2.0",
        "id": "status_check",
        "method": "aria2.tellStatus",
        "params": [gid, ["gid", "status", "totalLength", "completedLength", "downloadSpeed", "errorCode"]]
    }
    try:
        respuesta = requests.post("http://localhost:6800/jsonrpc", json=payload)
        datos = respuesta.json()
        if 'result' in datos: return datos['result']
    except: return None
    return None

def pausar_descarga_aria2(gid):
    try: requests.post("http://localhost:6800/jsonrpc", json={"jsonrpc": "2.0", "id": "pause", "method": "aria2.pause", "params": [gid]})
    except: pass

def reanudar_descarga_aria2(gid):
    try: requests.post("http://localhost:6800/jsonrpc", json={"jsonrpc": "2.0", "id": "unpause", "method": "aria2.unpause", "params": [gid]})
    except: pass

def cancelar_descarga_aria2(gid):
    try: requests.post("http://localhost:6800/jsonrpc", json={"jsonrpc": "2.0", "id": "remove", "method": "aria2.remove", "params": [gid]})
    except: pass