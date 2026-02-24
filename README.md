# Gestor de Descargas GTK4 + Aria2 + Tor

Un gestor de descargas moderno, modular y nativo para Linux (GNOME) escrito en Python. 

Utiliza una arquitectura dividida en tres capas: **GTK4/Libadwaita** para una interfaz nativa hermosa, un **Router Inteligente** en Python (impulsado por `yt-dlp`), y un motor **Aria2** corriendo en Docker respaldado por una red **Tor/Privoxy** para descargas seguras y acceso a la Deep Web.

## Características Principales

* **Interfaz Nativa GNOME:** Construida con GTK4 y Libadwaita para integrarse perfectamente con el ecosistema de Linux moderno.
* **Descargas Multiparte y BitTorrent:** Alimentado por `aria2`, soporta descargas HTTP ultra-rápidas, enlaces Magnet y archivos `.torrent` de forma nativa.
* **Acceso a la Deep Web (Tor):** Soporte integrado para descargar archivos desde dominios `.onion` a través de un circuito Tor automatizado.
* **Extractor Inteligente (Router):** * Soporte "out-of-the-box" para extraer vídeos de cientos de sitios web (YouTube, Twitter, Vimeo, etc.) gracias a `yt-dlp`.
  * Detección automática de protocolos (HTTP, Magnet, Onion) para enrutar el tráfico al proxy adecuado.
* **Sistema P2P Inteligente:** Detección automática de atascos en la red DHT (cancela automáticamente los enlaces Magnet muertos o sin pares después de 30 segundos para liberar recursos).
* **Control Total y UI Dinámica:** * Pausa, reanuda, cancela y reintenta descargas con un solo clic.
  * Opciones avanzadas para inyectar un Proxy manual por cada descarga.
  * Botón de acceso directo para abrir la carpeta local de descargas.
* **Monitorización en Vivo:** Tabla de datos con actualización asíncrona de progreso, velocidad y estados detallados (ej. "Buscando pares (DHT)...").
* **Sistema de Filtrado:** Barra lateral dinámica para separar descargas activas, completadas y erróneas.

## Arquitectura del Sistema

El proyecto se compone de piezas fundamentales que se comunican entre sí aislando la lógica de la red:

1. **La Interfaz (UI):** `main_ui.py` (Maneja GTK4, eventos de usuario y bucles de monitorización asíncrona).
2. **Las Reglas (Backend):** `extractor.py` (Traduce URLs, extrae directos y decide si inyectar tráfico P2P o Tor).
3. **El Motor Docker (Red):** Definido en `docker-compose.yml`, orquesta tres contenedores:
   * `aria2-rpc`: El músculo que realiza las descargas reales.
   * `tor-proxy`: Puerta de entrada a la red Tor (SOCKS5).
   * `privoxy`: Traductor HTTP a SOCKS5t que enruta de forma transparente las peticiones `.onion` de Aria2 hacia Tor.

## Requisitos Previos

Asegúrate de tener un entorno **Debian/Ubuntu** con Docker instalado.

### 1. Dependencias del Sistema (Linux)
Instala los componentes de GTK4 y Docker ejecutando:
```bash
sudo apt update
sudo apt install python3-gi python3-gi-cairo gir1.2-gtk-4.0 gir1.2-adw-1 python3-pip docker.io docker-compose
```

### 2. Dependencias de python
Instala las librerías necesarias para el backend de extracción y comunicación:
```bash
pip3 install yt-dlp requests --break-system-packages
```
(Nota: En entornos de producción, se recomienda usar un entorno virtual venv).



## Instalación y uso

### 1. Levantar el motor (Docker)
Antes de abrir la aplicación, asegúrate de levantar la infraestructura de red. Este comando enciende Aria2, Privoxy y el nodo de Tor:
```bash
docker-compose up -d
```
Las descargas se guardarán automáticamente en la carpeta local ./descargas_prueba que creará el sistema.

### 2. Iniciar la Aplicación
Una vez el motor esté encendido y la red Tor conectada, ejecuta la interfaz gráfica:
```bash
python3 main_ui.py
```


## Cómo añadir nuevas páginas web (Provider Rules)
Si deseas añadir soporte para una página web que yt-dlp no soporta (como páginas de streaming pirata) deberás:
1. Abrir `extractor.py`
2. Escribir una nueva función personalizada usando librerías como `BeautifulSoup` o `re` para escanear la web objetivo y obtener el enlace directo.
3. Añade la nueva regla al enrutador principal `resolver_url(url_usuario)`:
```Python
def resolver_url(url_usuario):
    if "mi-web-pirata.com" in url_usuario:
        return mi_extractor_nuevo(url_usuario)
    else:
        return extraer_enlace_real(url_usuario)
```