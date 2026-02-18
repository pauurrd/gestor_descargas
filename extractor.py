import yt_dlp
import requests
import json
import re

# --- 1. EXTRACTOR PRINCIPAL (yt-dlp) ---
def extraer_enlace_real(url_publica):
    print(f"[*] Analizando URL con yt-dlp: {url_publica}")
    
    # Opciones para intentar extraer lo máximo posible
    ydl_opts = {
        'format': 'best',
        'noplaylist': True,
        'quiet': True,
        # 'ignoreerrors': True, # Descomentar si quieres ignorar errores leves
    }
    
    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        try:
            # download=False es vital para solo obtener la URL sin bajar nada aquí
            info_dict = ydl.extract_info(url_publica, download=False)
            
            # Intentamos obtener la URL directa
            enlace_directo = info_dict.get('url', None)
            titulo = info_dict.get('title', 'video_descargado')
            ext = info_dict.get('ext', 'mp4')
            
            # Si yt-dlp devuelve una lista de formatos (a veces pasa), cogemos el primero
            if not enlace_directo and 'entries' in info_dict:
                enlace_directo = info_dict['entries'][0].get('url', None)
                titulo = info_dict['entries'][0].get('title', titulo)

            if not enlace_directo:
                return None, None

            # Sanitizamos el nombre del archivo
            nombre_final = f"{titulo}.{ext}".replace("/", "_").replace("\\", "_").replace(":", "-")
            
            return enlace_directo, nombre_final
            
        except Exception as e:
            print(f"[-] Error al extraer con yt-dlp: {e}")
            return None, None

# --- 2. EL ROUTER (Ahora limpio) ---
def resolver_url(url_usuario):
    # AQUÍ ES DONDE ANTES TENÍAS LA TRAMPA DE ANIMEFLV
    # Ahora la hemos quitado.
    
    # Si en el futuro escribes un scraper real para una web, lo pones aquí:
    # if "miwebprivada.com" in url_usuario:
    #     return mi_extractor_privado(url_usuario)
    
    # Por defecto, intentamos que yt-dlp lo resuelva todo
    return extraer_enlace_real(url_usuario)

# --- 3. COMUNICACIÓN CON ARIA2 (Igual que antes) ---
def enviar_a_aria2(enlace_directo, nombre_archivo):
    print(f"[*] Enviando {nombre_archivo} a aria2...")
    rpc_url = "http://localhost:6800/jsonrpc"
    
    payload = {
        "jsonrpc": "2.0",
        "id": "mi_gestor_gtk",
        "method": "aria2.addUri",
        "params": [
            [enlace_directo],
            {
                "out": nombre_archivo,
                "split": "4",
                "max-connection-per-server": "4"
            }
        ]
    }
    
    try:
        respuesta = requests.post(rpc_url, json=payload)
        return respuesta.json()
    except Exception as e:
        print(f"[-] Error conectando con aria2: {e}")
        return None

# --- 4. MONITORIZACIÓN (Igual que antes) ---
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