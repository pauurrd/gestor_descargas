import yt_dlp
import requests
import urllib.parse
import os

def extraer_enlace_real(url_publica, proxy=None):
    print(f"[*] Analizando URL con yt-dlp: {url_publica}")
    
    ydl_opts = {
        'format': 'best',
        'noplaylist': True,
        'quiet': True,
    }
    
    if proxy:
        ydl_opts['proxy'] = proxy
        print(f"[*] 🛡️ yt-dlp usando proxy: {proxy}")
    
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
    ruta = urllib.parse.urlparse(url).path
    nombre_archivo = os.path.basename(ruta)
    _, ext = os.path.splitext(nombre_archivo)
    
    extensiones_empresariales = [
        '.pdf', '.jpg', '.png', '.jpeg', 
        '.mp4', '.avi', '.mov', '.mkv',
        '.zip', '.rar', '.7z', '.tar', '.gz'
    ]

    if ext.lower() in extensiones_empresariales:
        if not nombre_archivo:
            nombre_archivo = "documento_empresarial" + ext
        return True, nombre_archivo
        
    return False, None

def resolver_url(url_usuario, proxy=None):
    url_usuario = url_usuario.strip()
    
    es_directo, nombre_archivo = es_enlace_directo(url_usuario)
    if es_directo:
        print(f"[*] Archivo empresarial detectado: {nombre_archivo}")
        return url_usuario, nombre_archivo
        
    print("[*] Enlace genérico/vídeo detectado. Delegando a yt-dlp...")
    return extraer_enlace_real(url_usuario, proxy)

def enviar_a_aria2(enlace_directo, nombre_archivo, proxy=None):
    print(f"[*] Enviando {nombre_archivo} a aria2...")
    rpc_url = "http://localhost:6800/jsonrpc"
    
    opciones = {
        "out": nombre_archivo,
        "split": "4",
        "max-connection-per-server": "4"
    }

    if proxy:
        print(f"[*] 🛡️ Enrutando descarga a través del proxy: {proxy}")
        opciones["all-proxy"] = proxy
    else:
        print("[*] ⚠️ ADVERTENCIA: Usando conexión directa (Sin Proxy)")
    
    payload = {
        "jsonrpc": "2.0",
        "id": "gestor_corporativo",
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