# Gestor de Descargas Corporativo (GTK4 + Aria2 + Tor)

Un gestor de descargas moderno, modular y nativo para Linux (GNOME) escrito en Python, diseñado específicamente para entornos empresariales y peticiones seguras.

Utiliza una arquitectura dividida en tres capas: **GTK4/Libadwaita** para una interfaz nativa hermosa, un **Router Inteligente** en Python, y un motor **Aria2** corriendo de forma aislada en Docker junto a **Tor** y **Privoxy** para maximizar el ancho de banda y enrutar el tráfico de forma segura y anónima.

## Características Principales

* **Interfaz Nativa GNOME:** Construida con GTK4 y Libadwaita para integrarse perfectamente con el ecosistema de Linux moderno.
* **Descargas Multiparte Optimizadas:** Alimentado por `aria2`, soporta descargas HTTP/HTTPS y FTP ultrarrápidas dividiendo los archivos en múltiples conexiones simultáneas.
* **Enrutamiento Corporativo Avanzado:** * Detección automática del proxy del SO (GNOME Settings o variables de entorno).
  * Opción manual y segura para "Forzar Descarga Directa" (ignorar proxy).
* **Red Tor Integrada:** Opción en las configuraciones avanzadas para enrutar todo el tráfico de descarga a través de la red Tor de forma transparente.
* **Importación por Lotes (JSON):** Soporte para importar listas masivas de descargas. El sistema gestiona automáticamente múltiples fuentes (espejos) para un mismo archivo y omite descargas duplicadas.
* **Autenticación Nativa:** Soporte integrado para inyectar credenciales (Basic Auth) o Tokens de acceso (Bearer Tokens) en descargas protegidas a través del archivo JSON.
* **Extractor Inteligente (Router):** * Filtro de extensiones empresariales (`.zip`, `.pdf`, `.mp4`, `.iso`, etc.).
  * Soporte integrado para extraer vídeos corporativos usando `yt-dlp`.

## Arquitectura del Sistema

El proyecto se compone de piezas fundamentales que se comunican entre sí aislando la lógica de la red:

1. **La Interfaz (UI):** `main_ui.py` (Maneja la ventana de GTK4, importación de JSON, validación de protocolos y los bucles de monitorización asíncrona).
2. **Las Reglas (Backend):** `extractor.py` (Filtra URLs, extrae enlaces directos, estructura las peticiones de autenticación y gestiona la comunicación RPC).
3. **El Motor Docker (Red):** Definido en `docker-compose.yml`, despliega un entorno aislado con tres servicios internos:
   * `aria2-rpc`: El músculo que realiza las descargas reales.
   * `tor`: Cliente SOCKS5 para enrutar tráfico a la red Onion.
   * `privoxy`: Traductor de red que convierte las peticiones HTTP puras de Aria2 al protocolo SOCKS5 que entiende Tor.

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
*(Nota: En entornos de producción modernos, se recomienda usar un entorno virtual venv).*



## Instalación y uso

### 1. Levantar el motor (Docker)
Antes de abrir la aplicación, asegúrate de levantar la infraestructura de red. Este comando enciende de forma aislada Aria2, Tor y Privoxy:
```bash
docker-compose up -d
```
Las descargas se guardarán automáticamente en la carpeta local `./Descargas` que el sistema creará en la raíz del proyecto.

### 2. Iniciar la Aplicación
Una vez el motor esté encendido y el puerto 6800 expuesto, ejecuta la interfaz gráfica:
```bash
python3 main_ui.py
```

## Formato de Importación JSON
El sistema permite importar un archivo .json con múltiples descargas. El gestor escogerá la fuente más rápida y aplicará la autenticación correspondiente si es necesaria.

**Ejemplo de estructura soportada:**
```json
[
  {
    "id_recurso": "archivo_publico_01",
    "nombre": "documento_abierto.pdf",
    "fuentes": [
      "https://servidor1.com/doc.pdf",
      "http://espejo2.com/doc.pdf"
    ],
    "auth": null
  },
  {
    "id_recurso": "archivo_restringido_basic",
    "nombre": "datos_internos.zip",
    "fuentes": ["http://intranet.empresa.local/datos.zip"],
    "auth": {
      "tipo": "basic",
      "user": "admin",
      "pass": "supersecreto123"
    }
  },
  {
    "id_recurso": "archivo_api_token",
    "nombre": "reporte_financiero.txt",
    "fuentes": ["http://api.empresa.com/v1/descargar/reporte"],
    "auth": {
      "tipo": "token",
      "token": "MI_TOKEN_BEARER_JWT"
    }
  }
]
```

## Historial de Descargas
Cada vez que finaliza o falla una descarga, el sistema guarda un registro en el archivo local **historial_descargas.db**. Para visualizar este historial cómodamente con una interfaz gráfica en tu sistema:
```bash
sudo apt install sqlitebrowser
sqlitebrowser historial_descargas.db
```
En la pestaña **Browse Data**, podrás visualizar cierta información relevante a las descargas que se han realizado (Fecha y hora de la descarga, nombre del archivo, hash, url, proxy usado...).

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

## Resolución de Problemas Frecuentes y Códigos de Error

El gestor está diseñado para capturar los fallos de red de Aria2 y mostrarlos en el registro de actividad o en la tabla principal. Aquí tienes los errores más comunes cuando se trabaja en entornos corporativos o proxies:

* **Error "Aria2 rechazó el enlace: Fallo de red" (al importar):** Si ves este error inmediato con el aspa roja (❌) en el registro, significa que Aria2 no ha podido ni siquiera iniciar la petición.
  * *Causas comunes:* El proxy configurado (Privoxy o corporativo) está caído, has introducido un protocolo incorrecto (`socks5://` en un proxy HTTP), o la URL de destino es rechazada instantáneamente por el servidor (ej. un Token de AWS S3 con la región equivocada).

* **Descargas congeladas en "Conectando...":** La tarea se añade a la cola pero nunca empieza a descargar ni a dar error.
  * *Causas comunes:* Suele ocurrir por bloqueos tipo "efecto boomerang" (Hairpinning) en firewalls y Security Groups (ej. AWS). Ocurre cuando el proxy intenta salir a internet para acceder a su propia IP pública, y el firewall bloquea la petición silenciosamente. *Solución: Usar `127.0.0.1` en el JSON si el archivo está alojado en el mismo servidor que el proxy.*

* **❌ Error (Código 1) - Conexión abortada:**
  Aria2 intentó descargar pero la conexión fue cortada abruptamente por el proxy.
  * *Causas comunes:* Ocurre muy a menudo al intentar descargar enlaces `https://` a través de proxies públicos o corporativos estrictos que tienen bloqueado el método `CONNECT` para el puerto 443. También puede ocurrir si el proxy corta la conexión al detectar un archivo demasiado grande.

* **❌ Error (Código 22) - Cabecera HTTP inesperada:**
  Aria2 esperaba recibir los bytes de un archivo (.zip, .pdf, etc.), pero en su lugar recibió código HTML de una página web de error.
  * *Causas comunes:* Problemas de Autenticación o Permisos. El servidor web de destino está devolviendo un error `401 Unauthorized` o `403 Forbidden` porque faltan las credenciales (Auth Basic) o el Token Bearer es incorrecto. También ocurre si la configuración interna del proxy (ej. Squid) está configurada en `deny all` y devuelve una página web de "Acceso Denegado".



## ☁️ Entorno de Pruebas en AWS (Terraform)

Para facilitar el desarrollo y la validación del gestor, este repositorio incluye un archivo `main.tf` que levanta automáticamente una infraestructura de pruebas segura en Amazon Web Services (AWS). 

Esta infraestructura despliega:
* Un servidor **EC2** con un Proxy configurado (`Squid`) y un servidor Web local (`Nginx`) preparado con rutas de Autenticación Básica y Token Bearer.
* Un **Bucket S3** con archivos públicos y privados de prueba.
* Un **Security Group dinámico** que detecta tu IP pública en el momento de la creación y bloquea el acceso a cualquier otra persona en el mundo.

### Requisitos
1. [Terraform](https://developer.hashicorp.com/terraform/downloads) instalado en tu sistema.
2. [AWS CLI](https://aws.amazon.com/cli/) instalada y configurada con tus credenciales.

### Instrucciones de Despliegue

1. Abre una terminal en el directorio donde se encuentra el archivo `main.tf`.
2. Inicializa el entorno de Terraform:
   ```bash
   terraform init
   ```
3. Aplica los cambios para construir la infraestructura:
   ```bash
   terraform apply
   ```
   *(Revisa el plan y escribe **yes** para confirmar).*
4. Al terminar (tardará un par de minutos), la consola imprimirá unos Outputs. Ahí verás la IP y el puerto de tu nuevo proxy, junto con las instrucciones y URLs necesarias para probar el archivo de importación JSON.

**Limpieza**
Para evitar cargos innecesarios en tu cuenta de AWS, recuerda destruir toda la infraestructura en cuanto termines de hacer tus pruebas de descarga:
```bash
terraform destroy
```
*(Escribe **yes** para confirmar y AWS eliminará todo el rastro).*