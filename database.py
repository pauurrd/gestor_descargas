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