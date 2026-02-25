# Gestor de Descargas Corporativo (GTK4 + Aria2)

Un gestor de descargas moderno, modular y nativo para Linux (GNOME) escrito en Python, diseñado específicamente para entornos empresariales.

Utiliza una arquitectura dividida en tres capas: **GTK4/Libadwaita** para una interfaz nativa hermosa, un **Router Inteligente** en Python (impulsado por `yt-dlp` y reglas de filtrado), y un motor **Aria2** corriendo de forma aislada en Docker para maximizar el ancho de banda y enrutar el tráfico de forma segura.

## Características Principales

* **Interfaz Nativa GNOME:** Construida con GTK4 y Libadwaita para integrarse perfectamente con el ecosistema de Linux moderno.
* **Descargas Multiparte Optimizadas:** Alimentado por `aria2`, soporta descargas HTTP/HTTPS y FTP ultrarrápidas dividiendo los archivos pesados en múltiples conexiones simultáneas.
* **Enrutamiento Corporativo (Proxy):** Soporte integrado para inyectar un Proxy corporativo obligatorio por defecto en todas las peticiones, con una opción manual y segura para "Forzar Descarga Directa" (ignorar proxy) en casos autorizados.
* **Validación Estricta:** El sistema rechaza enlaces malformados y exige protocolos válidos (`http://`, `https://`, `ftp://`) tanto para las descargas como para el proxy, evitando peticiones residuales o erróneas en la red local.
* **Extractor Inteligente (Router):** * Filtro estricto de extensiones de archivo empresariales en descargas directas (`.zip`, `.pdf`, `.mp4`, `.7z`, etc.).
  * Soporte integrado para extraer vídeos corporativos, conferencias o material de formación desde múltiples plataformas usando `yt-dlp`.
* **Control Total y UI Dinámica:** * Pausa, reanuda, cancela y reintenta descargas con un solo clic (ideal para retomar la descarga de archivos pesados).
  * Lanzamiento rápido de descargas pulsando la tecla *Enter*.
  * Botón de acceso directo para abrir la carpeta local de descargas.
* **Monitorización en Vivo:** Tabla de datos con actualización asíncrona de progreso, tamaño, velocidad y estados detallados de conexión.
* **Sistema de Filtrado:** Barra lateral dinámica para separar descargas activas, completadas y erróneas.

## Arquitectura del Sistema

El proyecto se compone de piezas fundamentales que se comunican entre sí aislando la lógica de la red:

1. **La Interfaz (UI):** `main_ui.py` (Maneja la ventana de GTK4, los eventos de teclado/ratón, la validación estricta de protocolos y los bucles de monitorización asíncrona).
2. **Las Reglas (Backend):** `extractor.py` (Filtra las URLs por extensión permitida, extrae enlaces directos de plataformas de vídeo y gestiona la inyección del proxy hacia el motor).
3. **El Motor Docker (Red):** Definido en `docker-compose.yml`, despliega un único contenedor ligero y seguro:
   * `aria2-rpc`: El músculo que realiza las descargas reales en segundo plano (estrictamente limitado a HTTP/FTP puro, con los protocolos P2P deshabilitados).

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
(Nota: En entornos de producción modernos, se recomienda usar un entorno virtual venv).



## Instalación y uso

### 1. Levantar el motor (Docker)
Antes de abrir la aplicación, asegúrate de levantar el motor de descargas. Este comando enciende de forma aislada el contenedor de Aria2:
```bash
docker-compose up -d
```
Las descargas se guardarán automáticamente en la carpeta local ./Descargas que el sistema creará en la raíz del proyecto.

### 2. Iniciar la Aplicación
Una vez el motor esté encendido y listo para recibir peticiones, ejecuta la interfaz gráfica:
```bash
python3 main_ui.py
```


## Cómo añadir nuevas páginas web (Provider Rules)
Si deseas añadir soporte para extraer enlaces desde una intranet corporativa o un proveedor de vídeo privado que yt-dlp no soporta por defecto, deberás:
1. Abrir `extractor.py`
2. Escribir una nueva función personalizada usando librerías como `BeautifulSoup` o `re` para escanear la web objetivo, manejar la autenticación si es necesaria, y obtener el enlace directo al archivo.
3. Añadir la nueva regla al enrutador principal `resolver_url(url_usuario, proxy=None)`:
```Python
def resolver_url(url_usuario, proxy=None):
    url_usuario = url_usuario.strip()
    if "mi-intranet-corporativa.com" in url_usuario:
        return mi_extractor_privado(url_usuario, proxy)
    es_directo, nombre_archivo = es_enlace_directo(url_usuario)
```