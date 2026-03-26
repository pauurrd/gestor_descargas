import yt_dlp
import requests
import urllib.parse
import os
import base64

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

EXTENSIONES_EMPRESARIALES = {
    "Texto": [".txt", ".md", ".rtf"],
    "Ofimática": [".docx", ".xlsx", ".pptx", ".odt", ".ods", ".odp"],
    "Imagen": [".jpg", ".gif", ".bmp", ".png", ".heic", ".webp"],
    "Vídeo": [".avi", ".mov", ".mp4", ".mpeg", ".wmv"],
    "Ejecución del sistema": [".exe", ".bat", ".dll", ".sys"],
    "Audio": [".mp3", ".aac", ".ogg", ".wav", ".wma"],
    "Archivo comprimido": [".zip", ".rar", ".tar"],
    "Lectura": [".pdf", ".epub", ".azw", ".ibook"],
    "Imagen de disco": [".iso", ".mds", ".img"]
}   

def es_enlace_directo(url):
    url_limpia = url.strip().lower()    
    todas_las_extensiones = [ext for lista_ext in EXTENSIONES_EMPRESARIALES.values() for ext in lista_ext]
    
    for ext in todas_las_extensiones:
        if url_limpia.endswith(ext) or ext + "?" in url_limpia:
            nombre = url.split("/")[-1].split("?")[0]
            if not nombre:
                nombre = "archivo_descargado" + ext
            return True, nombre
            
    return False, ""

def resolver_url(url_usuario, proxy=None):
    url_usuario = url_usuario.strip()
    
    es_directo, nombre_archivo = es_enlace_directo(url_usuario)
    if es_directo:
        print(f"[*] Archivo empresarial detectado: {nombre_archivo}")
        return url_usuario, nombre_archivo
        
    print("[*] Enlace genérico/vídeo detectado. Delegando a yt-dlp...")
    return extraer_enlace_real(url_usuario, proxy)

def enviar_a_aria2(lista_urls, nombre_archivo, proxy=None, auth=None):
    rpc_url = "http://localhost:6800/jsonrpc"
    
    if isinstance(lista_urls, str):
        lista_urls = [lista_urls]

    opciones = {
        "out": nombre_archivo,
        "split": "4",                     
        "max-connection-per-server": "4", 
        "min-split-size": "5M",
        "uri-selector": "feedback",
        "timeout": "120",
        "connect-timeout": "60",
        "max-tries": "15",
        "retry-wait": "10",
        "continue": "true",
        "always-resume": "true",
        "max-file-not-found": "10"
    }

    if proxy:
        print(f"[*] 🛡️ Enrutando descarga a través del proxy: {proxy}")
        opciones["all-proxy"] = proxy
        opciones["disable-ipv6"] = "true"
    else:
        print("[*] ⚠️ ADVERTENCIA: Usando conexión directa (Sin Proxy)")
    
    if auth:
        tipo = auth.get('tipo', '').lower()
        if tipo == 'basic':
            user = auth.get('user')
            passwd = auth.get('pass')
            credenciales = base64.b64encode(f"{user}:{passwd}".encode('utf-8')).decode('utf-8')
            opciones["header"] = [f"X-My-App-Auth: Basic {credenciales}"]
        elif tipo == 'token':
            opciones["header"] = [f"X-My-App-Auth: Bearer {auth.get('token')}"]
    
    payload = {
        "jsonrpc": "2.0",
        "id": "batch_import",
        "method": "aria2.addUri",
        "params": [lista_urls, opciones]
    }
    
    try:
        respuesta = requests.post(rpc_url, json=payload)
        return respuesta.json()
    except Exception as e:
        print(f"[-] Error en batch: {e}")
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

def configurar_limite_descargas(max_concurrentes=2):
    payload = {
        "jsonrpc": "2.0",
        "id": "config_limit",
        "method": "aria2.changeGlobalOption",
        "params": [{"max-concurrent-downloads": str(max_concurrentes)}]
    }
    try:
        requests.post("http://localhost:6800/jsonrpc", json=payload)
    except Exception as e:
        print(f"[-] Error al configurar límite de colas: {e}")  