# Gestor de Descargas GTK4 + Aria2

Un gestor de descargas moderno, modular y nativo para Linux (GNOME) escrito en Python. 

Utiliza una arquitectura dividida en tres capas: **GTK4/Libadwaita** para una interfaz nativa hermosa, **yt-dlp** para extraer los enlaces reales de casi cualquier página web, y **aria2** corriendo en Docker como motor de descarga multiparte a través de JSON-RPC.

## Características Principales

* **Interfaz Nativa GNOME:** Construida con GTK4 y Libadwaita para integrarse perfectamente con el ecosistema de Linux moderno.
* **Descargas Multiparte:** Alimentado por `aria2`, divide los archivos en múltiples segmentos para maximizar el ancho de banda.
* **Extractor Inteligente (Router):** * Soporte "out-of-the-box" para más de 1000 sitios web (YouTube, Twitter, Vimeo, etc.) gracias a `yt-dlp`.
  * Arquitectura "Provider Rules" que permite programar scripts personalizados en Python para extraer vídeos de webs complejas o privadas.
* **Control Total:** Pausa, reanuda, cancela y reintenta descargas con un solo clic.
* **Monitorización en Vivo:** Tabla de datos con actualización asíncrona de progreso, velocidad y tiempo restante.
* **Sistema de Filtrado:** Barra lateral dinámica para separar descargas activas, completadas y erróneas.



## Arquitectura del Sistema

El proyecto se compone de tres piezas fundamentales que se comunican entre sí:

1. **La Interfaz (UI):** `main_ui.py` (Maneja GTK4 y bucles de monitorización).
2. **Las Reglas (Backend):** `extractor.py` (Traduce URLs de usuario a enlaces `.mp4` reales).
3. **El Motor:** Contenedor Docker de `aria2` (Hace el trabajo pesado de red).



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

### 1. Levantar el motor (aria2)
Antes de abrir la aplicación, asegúrate de tener tu archivo docker-compose.yml en el directorio. Este archivo levanta aria2 y expone el puerto RPC 6800.
```bash
docker-compose up -d
```
Las descargas se guardarán automáticamente en la carpeta descargas_prueba que creará Docker.

### 2. Iniciar la Aplicación
Una vez esté el motor encendidio, ejecuta la interfaz gráfica
```bash
python3 main_ui.py
```


## Cómo añadir nuevas páginas web (Provider Rules)
Si deseas añadir soporte para una página web que yt-dlp no soporta como páginas de streaming con reproductores incrustados oscuros deberás:
1. Abre `extractor.py`
2. Escribe una nueva función personalizada usando librerias como `BeautifulSoup` o `re` para escanear la web objetivo y obtener el enlace directo.
3. Añade la nueva regla al enrutador principal `resolver_url(url_usuario)`:
```Python
def resolver_url(url_usuario):
    if "mi-web-nueva.com" in url_usuario:
        return mi_extractor_nuevo(url_usuario)
    else:
        return extraer_enlace_real(url_usuario)
```