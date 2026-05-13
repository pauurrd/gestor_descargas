import sqlite3
import requests
import os

HOME_DIR = os.path.expanduser("~")
DB_NAME = os.path.join(HOME_DIR, ".gestor_descargas_historial.db")

def obtener_fuentes_pendientes():
    """Busca en la base de datos las URLs que aún no han sido enriquecidas."""
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute('''
        SELECT id, url, auth_tipo, auth_credencial 
        FROM file_sources 
        WHERE estado = 'pendiente'
    ''')
    fuentes = cursor.fetchall()
    conn.close()
    return fuentes

def actualizar_capacidades_fuente(id_fuente, estado_red, soporta_pausa, tamano_bytes):
    """Guarda los resultados del explorador en la base de datos."""
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    
    # Marcamos como 'analizado' o 'error_red' dependiendo del código HTTP
    nuevo_estado = 'analizado' if estado_red == 200 else f'error_{estado_red}'

    score = 0
    if estado_red == 200:
        score += 50
    if soporta_pausa:
        score += 50
    
    try:
        cursor.execute('''
            UPDATE file_sources 
            SET estado = ?, score = ?
            WHERE id = ?
        ''', (nuevo_estado, score, id_fuente))
        conn.commit()
        print(f"[+] Fuente {id_fuente} actualizada: HTTP {estado_red} | Pausa: {soporta_pausa} | Tamaño: {tamano_bytes}B | Score: {score}/100")
    
    except sqlite3.OperationalError as e:
        print(f"[-] Error DB: {e}")
    finally:
        conn.close()

def analizar_capacidades_url(url, auth_tipo, auth_credencial):
    """
    Hace una petición HEAD para descubrir las capacidades del servidor 
    sin descargar el archivo completo.
    """
    headers = {}
    if auth_tipo == 'basic' and auth_credencial:
        headers["X-My-App-Auth"] = f"Basic {auth_credencial}"
    elif auth_tipo == 'token' and auth_credencial:
        headers["X-My-App-Auth"] = f"Bearer {auth_credencial}"

    # Usamos el proxy del sistema que configurasteis para AWS
    proxies = None

    try:
        # Petición HEAD: Solo pide las cabeceras, no el cuerpo del archivo. ¡Muy rápido!
        respuesta = requests.head(url, headers=headers, proxies=proxies, timeout=10, allow_redirects=True)
        
        estado_red = respuesta.status_code
        # Comprobamos si el servidor acepta 'Range' (vital para pausar/reanudar en Aria2)
        soporta_pausa = respuesta.headers.get('Accept-Ranges', '').lower() == 'bytes'
        tamano_bytes = respuesta.headers.get('Content-Length', '0')
        
        return estado_red, soporta_pausa, tamano_bytes

    except requests.RequestException as e:
        print(f"[-] Error de red al analizar {url}: {e}")
        return 0, False, "0"

def ejecutar_fase_enriquecimiento():
    """Función principal que orquesta el enriquecimiento de todas las fuentes pendientes."""
    print("🚀 Iniciando Fase de Enriquecimiento (Tarea #25)...")
    fuentes = obtener_fuentes_pendientes()
    
    if not fuentes:
        print("✅ No hay fuentes pendientes de analizar en la base de datos.")
        return

    for id_fuente, url, auth_tipo, auth_cred in fuentes:
        print(f"[*] Analizando capacidades de: {url}")
        estado, pausa, tamano = analizar_capacidades_url(url, auth_tipo, auth_cred)
        actualizar_capacidades_fuente(id_fuente, estado, pausa, tamano)
        
    print("🏁 Fase de enriquecimiento finalizada.")

if __name__ == "__main__":
    # Si ejecutas este archivo directamente, hará un barrido de la base de datos
    ejecutar_fase_enriquecimiento()