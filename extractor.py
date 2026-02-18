import yt_dlp
import requests
import json
import re

# --- 1. EXTRACTOR GENÉRICO (yt-dlp) ---
def extraer_enlace_real(url_publica):
    print(f"[*] Analizando URL con yt-dlp: {url_publica}")
    
    ydl_opts = {
        'format': 'best',
        'noplaylist': True,
        'quiet': True 
    }
    
    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        try:
            info_dict = ydl.extract_info(url_publica, download=False)
            enlace_directo = info_dict.get('url', None)
            titulo = info_dict.get('title', 'video_descargado')
            ext = info_dict.get('ext', 'mp4')
            # Sanitizamos el nombre para evitar problemas con caracteres raros
            nombre_final = f"{titulo}.{ext}".replace("/", "_").replace("\\", "_")
            return enlace_directo, nombre_final
        except Exception as e:
            print(f"[-] Error al extraer: {e}")
            return None, None

# --- 2. EXTRACTOR PERSONALIZADO (Ejemplo AnimeFLV) ---
def extractor_animeflv(url):
    print("[*] Usando regla personalizada para AnimeFLV...")
    # Aquí iría la lógica real de scraping con BeautifulSoup.
    # Para la prueba, devolvemos un vídeo de prueba de Google 
    # simulando que es el capítulo de Chainsaw Man.
    enlace_simulado = "http://commondatastorage.googleapis.com/gtv-videos-bucket/sample/ForBiggerBlazes.mp4"
    return enlace_simulado, "chainsaw-man-capitulo-prueba.mp4"

# --- 3. EL ROUTER (La función que le faltaba a tu archivo) ---
def resolver_url(url_usuario):
    # Si la URL contiene "animeflv", usamos nuestra regla personalizada
    if "animeflv.net" in url_usuario:
        return extractor_animeflv(url_usuario)
    
    # Para todo lo demás (YouTube, Twitter, etc.), usamos yt-dlp
    else:
        return extraer_enlace_real(url_usuario)

# --- 4. COMUNICACIÓN CON ARIA2 ---
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

def obtener_estado_aria2():
    # RPC para pedir las descargas activas
    # Pedimos: gid (id), totalLength (peso), completedLength (descargado), downloadSpeed (velocidad)
    payload = {
        "jsonrpc": "2.0",
        "id": "monitor_gtk",
        "method": "aria2.tellActive",
        "params": [
            ["gid", "totalLength", "completedLength", "downloadSpeed"]
        ]
    }
    
    try:
        respuesta = requests.post("http://localhost:6800/jsonrpc", json=payload)
        datos = respuesta.json()
        if 'result' in datos:
            return datos['result'] # Devuelve una lista de descargas activas
    except Exception:
        return [] # Si falla (aria2 apagado), devolvemos lista vacía
    return []

def formatear_tamano(bytes_str):
    # Convierte bytes (texto) a MB/GB legibles
    try:
        bytes_num = int(bytes_str)
        if bytes_num == 0: return "0 MB"
        
        for unidad in ['B', 'KB', 'MB', 'GB', 'TB']:
            if bytes_num < 1024.0:
                return f"{bytes_num:.2f} {unidad}"
            bytes_num /= 1024.0
    except:
        return "Unknown"

def obtener_info_gid(gid):
    payload = {
        "jsonrpc": "2.0",
        "id": "status_check",
        "method": "aria2.tellStatus",
        "params": [
            gid,
            ["gid", "status", "totalLength", "completedLength", "downloadSpeed", "errorCode"]
        ]
    }
    try:
        respuesta = requests.post("http://localhost:6800/jsonrpc", json=payload)
        datos = respuesta.json()
        if 'error' in datos:
            print(f"Error RPC: {datos['error']}")
            return None
        if 'result' in datos:
            return datos['result']
    except Exception as e:
        print(f"Excepcion RPC: {e}")
        return None
    return None