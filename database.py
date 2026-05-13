import os
import sqlite3
from datetime import datetime

HOME_DIR = os.path.expanduser("~")
DB_NAME = os.path.join(HOME_DIR, ".gestor_descargas_historial.db")

def init_db():
    """Crea la base de datos y la tabla si no existen."""
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()

    cursor.execute('''
        CREATE TABLE IF NOT EXISTS descargas (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            fecha_hora TEXT NOT NULL,
            nombre_asignado TEXT NOT NULL,
            nombre_original TEXT,
            hash_sha256 TEXT,
            url_origen TEXT NOT NULL,
            proxy_usado TEXT,
            estado TEXT NOT NULL
        )
    ''')

    cursor.execute('''
        CREATE TABLE IF NOT EXISTS files (
            uid TEXT PRIMARY KEY,
            nombre TEXT NOT NULL,
            tamano_esperado TEXT,
            has_esperado TEXT,
            fecha_creacion TEXT NOT NULL,
            estado TEXT DEFAULT 'nuevo'
        )
    ''')


    cursor.execute('''
        CREATE TABLE IF NOT EXISTS file_sources (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            file_uid TEXT NOT NULL,
            url TEXT NOT NULL UNIQUE,
            auth_tipo TEXT,
            auth_credencial TEXT,
            score INTEGER DEFAULT 0,
            estado TEXT DEFAULT 'pendiente',
            FOREIGN KEY(file_uid) REFERENCES files(uid)
        )
    ''')


    conn.commit()
    conn.close()

def registrar_descarga(nombre_asignado, nombre_original, hash_archivo, url_origen, proxy_usado, estado):
    """Guarda un nuevo registro en el historial."""
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    
    fecha_hora = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    proxy_str = proxy_usado if proxy_usado else "Directa (Sin Proxy)"
    
    cursor.execute('''
        INSERT INTO descargas (fecha_hora, nombre_asignado, nombre_original, hash_sha256, url_origen, proxy_usado, estado)
        VALUES (?, ?, ?, ?, ?, ?, ?)
    ''', (fecha_hora, nombre_asignado, nombre_original, hash_archivo, url_origen, proxy_str, estado))
    
    conn.commit()
    conn.close()


def normalizar_fecha(fecha_str):
    """Normaliza formatos de fecha a ISO 8601 (YYYY-MM-DD)."""
    if not fecha_str:
        return datetime.now().strftime("%Y-%m-%d")

    # Intenta parsear formatos comunes. Si falla, devuelve hoy.
    formatos = ["%Y/%m/%d", "%d-%m-%Y", "%Y-%m-%d %H:%M:%S", "%Y%m%d"]
    for fmt in formatos:
        try:
            return datetime.strptime(fecha_str, fmt).strftime("%Y-%m-%d")
        except ValueError:
            pass
    return datetime.now().strftime("%Y-%m-%d")

def upsert_entidad(item_dict):
    """Inserta un nuevo archivo o expande las fuentes si el UID ya existe.
    (Normalización y Expansión de Entidades).
    """
    print(f"\n[DEBUG] Entidad cruda recibida de Pydantic: {item_dict}")

    uid = item_dict.get('id_recurso') or item_dict.get('id') or item_dict.get('nombre')
    if not uid:
        print("[-] FALLO: No se encontró un identificador válido (UID) en el diccionario.")
        return False

    nombre = item_dict.get('nombre', f"descarga_{uid}")
    fecha_cruda = item_dict.get('fecha_creacion')
    fecha_norm = normalizar_fecha(fecha_cruda)
    fuentes = item_dict.get('fuentes', [])
    auth = item_dict.get('auth', {})

    auth_tipo = auth.get('tipo', None)
    auth_cred = auth.get('token', None) or auth.get('pass', None)

    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()

    try:
        # 1. Insertar el Archivo (IGNORA si el UID ya existe)
        cursor.execute('''
            INSERT OR IGNORE INTO files (uid, nombre, fecha_creacion, estado)
            VALUES (?, ?, ?, 'nuevo')
        ''', (uid, nombre, fecha_norm))

        # 2. Expansión de entidades: Insertar las nuevas fuentes (URLs) asociadas a ese UID
        for fuente in fuentes:
            url_limpia = str(fuente).strip()
            
            if not url_limpia:
                continue
            # Se usa INSERT OR IGNORE por el UNIQUE constraint de la URL. Si la URL ya existe, no la duplica.
            cursor.execute('''
                INSERT OR IGNORE INTO file_sources (file_uid, url, auth_tipo, auth_credencial)
                VALUES (?, ?, ?, ?)
            ''', (uid, url_limpia, auth_tipo, auth_cred))

            conn.commit()
            print(f"[+] ÉXITO: Entidad {uid} guardada correctamente en SQLite.")
            return True

    except Exception as e:
        print(f"[-] FALLO SQL al insertar {uid}: {str(e)}")
        return False
    finally:
        conn.close()