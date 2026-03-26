# Gestor de Descargas Corporativo (GTK4 + Aria2 + Tor)

Un gestor de descargas moderno, modular y nativo para Linux (GNOME) escrito en Python, diseñado específicamente para entornos empresariales y peticiones seguras.

Utiliza una arquitectura dividida en tres capas: **GTK4/Libadwaita** para una interfaz nativa, un **Router Inteligente** en Python, y un motor **Aria2** corriendo de forma aislada en Docker junto a **Tor** y **Privoxy** para maximizar el ancho de banda y enrutar el tráfico de forma segura y anónima.

## Características Principales

* **Interfaz Nativa GNOME:** Construida con GTK4 y Libadwaita para integrarse perfectamente con el ecosistema de Linux moderno.
* **Descargas Multiparte Optimizadas:** Alimentado por `aria2`, soporta descargas HTTP/HTTPS y FTP ultrarrápidas dividiendo los archivos en múltiples conexiones simultáneas desde diferentes hosts.
* **Enrutamiento Corporativo Avanzado:**
  * Detección automática del proxy del SO (GNOME Settings o variables de entorno).
  * Opción manual y segura para "Forzar Descarga Directa" (ignorar proxy).
* **Red Tor Integrada:** Opción en las configuraciones avanzadas para enrutar todo el tráfico de descarga a través de la red Tor de forma transparente.
* **Importación por Lotes y Grupos (JSON):** Soporte para importar listas masivas de descargas simples o archivos divididos en partes lógicas. El sistema gestiona automáticamente múltiples fuentes (espejos) para un mismo archivo y omite descargas duplicadas.
* **Autenticación Nativa:** Soporte integrado para inyectar credenciales (Basic Auth) o Tokens de acceso (Bearer Tokens) en descargas protegidas a través del archivo JSON. Cada parte de un mismo archivo puede autenticarse contra un host diferente.
* **Extractor Inteligente (Router):**
  * Filtro de extensiones empresariales clasificadas por tipología (`.zip`, `.pdf`, `.mp4`, `.iso`, etc.).
  * Soporte integrado para extraer vídeos corporativos usando `yt-dlp`.

## Arquitectura del Sistema

El proyecto se compone de piezas fundamentales que se comunican entre sí aislando la lógica de la red. A continuación se muestra el flujo de la información:

1. **La Interfaz (UI):** `main_ui.py` — Maneja la ventana GTK4, importación de JSON, validación de protocolos y los bucles de monitorización asíncrona.
2. **Las Reglas (Backend):** `extractor.py` — Filtra URLs, extrae enlaces directos, estructura las peticiones de autenticación y gestiona la comunicación RPC con aria2.
3. **La Lambda de autenticación:** `lambda_auth.py` — Valida la cabecera `X-My-App-Auth` y genera URLs presignadas de S3 con firma V4.

```text
[ Interfaz GTK4 ] <---(JSON / RPC)---> [ Router Python / Extractor (yt-dlp) ]
                                                    |
                                         (Petición con X-My-App-Auth)
                                                    v
                                          [ Proxy Squid (EC2) ]
                                          /         |         \
                                         v          v          v
                               [ API Gateway 1 ] [ API Gateway 2 ] [ API Gateway 3 ]
                               Bearer token 1    Basic auth        Bearer token 2
                                         \          |          /
                                          v         v         v
                               [ Lambda 1 ]    [ Lambda 2 ]    [ Lambda 3 ]
                               valida auth     valida auth     valida auth
                               presigned URL   presigned URL   presigned URL
                                         \          |          /
                                          v         v         v
                               [ S3 bucket_a ] [ S3 bucket_b ] [ S3 bucket_c ]
                                  .7z.001         .7z.002         .7z.003
                                          \          |          /
                                           v         v         v
  [ Contenedor Docker (Red Aislada) ]------------------------------------------
  |                                                                            |
  |  [ Aria2c ] <---- datos binarios en paralelo desde los 3 buckets           |
  |      |                                                                     |
  |      +-------------> [ Privoxy ] ---> [ Tor SOCKS5 ] ---> (Red Onion)      |
  -----------------------------------------------------------------------------
```

### Puertos Expuestos (Docker)

El contenedor de red expone 3 puertos esenciales para el funcionamiento del sistema:

- **6800 (Aria2 RPC):** Puerto de control interno. Permite que la aplicación en Python envíe comandos de descarga y consulte el estado del progreso sin interactuar directamente con la consola.
- **8118 (Privoxy HTTP):** Traductor local. Aria2 no habla el protocolo nativo de Tor, por lo que envía sus peticiones HTTP a este puerto, y Privoxy se encarga de empaquetarlas hacia Tor.
- **9050 (Tor SOCKS5):** Puerto nativo de la red Tor. Se expone por si el usuario necesita enrutar el tráfico a través de la red Onion.

## Requisitos Previos

Asegúrate de tener un entorno **Debian/Ubuntu** con Docker instalado.

### 1. Dependencias del Sistema (Linux)

```bash
sudo apt update
sudo apt install python3-gi python3-gi-cairo gir1.2-gtk-4.0 gir1.2-adw-1 python3-pip docker.io docker-compose
```

### 2. Dependencias de Python

Se recomienda encarecidamente utilizar un entorno virtual para no interferir con los paquetes del sistema:

```bash
sudo apt install python3-venv
python3 -m venv venv
source venv/bin/activate
pip install yt-dlp requests
```

### 🛡️ Seguridad (Pre-commit)
Para evitar subir credenciales por error, es obligatorio activar el escáner local antes de hacer commits:
`pip3 install pre-commit && pre-commit install`

## Instalación y Uso

### 1. Levantar el motor (Docker)

Antes de abrir la aplicación, asegúrate de levantar la infraestructura de red:

```bash
docker-compose up -d
```

Las descargas se guardarán automáticamente en la carpeta local `./Descargas`.

### 2. Iniciar la Aplicación

```bash
python3 main_ui.py
```


## Formato de Importación JSON

El sistema permite importar listas de descargas utilizando un formato estructurado. Soporta tanto descargas simples como agrupaciones lógicas de archivos (por ejemplo, partes de un mismo backup alojadas en distintos servidores con autenticación diferente por parte).

```json
[
  {
    "id_recurso": "archivo_simple",
    "nombre": "documento_abierto.pdf",
    "fuentes": [
      "https://servidor1.com/doc.pdf",
      "http://espejo2.com/doc.pdf"
    ],
    "auth": null
  },
  {
    "id_recurso": "grupo_backup_semanal",
    "nombre_grupo": "Backup BD 2026",
    "auth": {
      "tipo": "basic",
      "user": "admin",
      "pass": "supersecreto123"
    },
    "archivos": [
      {
        "nombre": "datos.part1.rar",
        "fuentes": ["http://host1.com/datos.part1.rar", "http://host1.1.com/datos.part1.rar"]
      },
      {
        "nombre": "datos.part2.rar",
        "fuentes": ["http://host2.com/datos.part2.rar"]
      }
    ]
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

Cada vez que finaliza o falla una descarga, el sistema guarda un registro en el archivo local `historial_descargas.db`. Para visualizarlo:

```bash
sudo apt install sqlitebrowser
sqlitebrowser historial_descargas.db
```

En la pestaña **Browse Data** verás información de auditoría: fecha y hora, nombre del archivo, hash SHA-256, URL de origen y proxy usado.

## Cómo Añadir Nuevas Páginas Web (Provider Rules)

Si deseas añadir soporte para extraer enlaces desde una intranet corporativa o un proveedor de vídeo privado que yt-dlp no soporta:

1. Abrir `extractor.py`.
2. Escribir una nueva función personalizada usando `BeautifulSoup` o `re`.
3. Añadir la nueva regla al enrutador principal `resolver_url()`:

```python
def resolver_url(url_usuario, proxy=None):
    url_usuario = url_usuario.strip()
    if "mi-intranet-corporativa.com" in url_usuario:
        return mi_extractor_privado(url_usuario, proxy)
    es_directo, nombre_archivo = es_enlace_directo(url_usuario)
```

## Resolución de Problemas Frecuentes y Códigos de Error

* **Error "Aria2 rechazó el enlace" (❌ Rechazado):** El motor no pudo establecer la conexión inicial. Causas comunes: proxy caído o mal configurado, protocolo incorrecto (`socks5://` contra un puerto HTTP), o URL de S3 con firma caducada o región incorrecta.

* **Descargas congeladas en "Conectando...":** Ocurre en entornos corporativos al descargar desde la IP pública de la propia empresa a través del proxy interno (problema de "Hairpin NAT"). Solución: pedir al equipo de redes que habilite hairpinning o implemente Split DNS.

* **❌ Error (Código 1) — Conexión abortada:** La conexión fue cortada por un intermediario. Causas: proxy corporativo (Zscaler, Squid) con el método `CONNECT` bloqueado, o política de tamaño máximo de archivo activa. Contactar con el administrador de red.

* **❌ Error (Código 4) — Recurso no encontrado (HTTP 404):** La URL del API Gateway es correcta pero la ruta no existe. En la infraestructura de pruebas, asegurarse de que las rutas de los API Gateways están configuradas como `$default` y no como rutas específicas (`GET /download`).

* **❌ Error (Código 22) — Respuesta HTTP inesperada (HTTP 403/401):** El gestor recibió una respuesta de error en lugar de datos binarios. Causas comunes:
  * **Auth incorrecta:** Revisar el bloque `"auth"` del JSON. El valor de `X-My-App-Auth` debe coincidir exactamente con el `EXPECTED_AUTH` de la Lambda (incluyendo el prefijo `Bearer ` o `Basic `).
  * **Doble redirect en S3:** Si la Lambda genera URLs presignadas sin `endpoint_url` explícito, boto3 usa el endpoint global de S3 y éste hace un redirect interno al endpoint regional. La firma queda ligada al host original y el segundo request devuelve 403. Solución: instanciar el cliente S3 con `endpoint_url='https://s3.eu-west-1.amazonaws.com'` (ajustar la región según corresponda).
  * **Proxy corporativo inyectando HTML:** Si el recurso es público pero sigue fallando, la seguridad perimetral puede estar bloqueando la URL e inyectando una página de advertencia HTML.

## ☁️ Entorno de Pruebas en AWS (Terraform)

Este repositorio incluye `main.tf` y `lambda_auth.py` para levantar automáticamente una infraestructura de pruebas en AWS que valida el flujo completo de descarga multi-host con autenticación diferente por parte.

### Qué despliega

* **EC2 con Squid Proxy** — enruta el tráfico saliente de aria2. El Security Group se configura dinámicamente con tu IP pública en el momento del `apply`.
* **3 API Gateways HTTP** (uno por parte del archivo), cada uno con integración explícita `AWS_PROXY` y `payload_format_version = "2.0"` para garantizar que las cabeceras llegan a la Lambda como diccionario.
* **3 Funciones Lambda** (`lambda_auth.py`) — validan la cabecera `X-My-App-Auth` contra la variable de entorno `EXPECTED_AUTH` y generan una URL presignada S3 con firma V4. Usan `endpoint_url` regional explícito para evitar el doble redirect que invalidaría la firma.
* **3 Buckets S3 privados** — cada uno contiene una parte del archivo de prueba (`.7z.001`, `.7z.002`, `.7z.003`).

### Autenticación por Gateway

| Gateway | Método | Cabecera esperada |
|---------|--------|-------------------|
| API Gateway 1 | Bearer Token | `X-My-App-Auth: Bearer MI_TOKEN_SECRETO_123` |
| API Gateway 2 | Basic Auth | `X-My-App-Auth: Basic YWRtaW46c3VwZXJzZWNyZXRvMTIz` |
| API Gateway 3 | Bearer Token | `X-My-App-Auth: Bearer TOKEN_DEBIAN_3` |

### Preparar el archivo de prueba

El archivo de prueba debe dividirse en partes con 7-Zip antes del `terraform apply`. En Linux:

```bash
# Descargar una ISO de prueba
wget https://cdimage.debian.org/debian-cd/current/amd64/iso-cd/debian-12.5.0-amd64-netinst.iso

# Dividir en partes de 300 MB
7z a -v300m debian-split.7z debian-12.5.0-amd64-netinst.iso
# Genera: debian-split.7z.001, debian-split.7z.002, debian-split.7z.003 ...
```

En Windows con 7-Zip: botón derecho sobre el archivo → *Añadir al archivo* → en "Dividir en volúmenes de" escribir `300m`.

Coloca los archivos `.7z.001`, `.7z.002`, `.7z.003` en la misma carpeta que `main.tf` antes de aplicar.

### Despliegue

```bash
terraform init
terraform apply
```

Al terminar, el output mostrará la IP del proxy y las URLs de los tres API Gateways. Úsalas en tu JSON de importación.

### Ensamblado tras la descarga

Una vez descargadas las tres partes:

```bash
7z x debian-13.2.0-amd64-netinst.7z.001
# 7-Zip detecta automáticamente las partes .001, .002, .003 y reconstruye el archivo original
```

### Limpieza

```bash
terraform destroy
```

### Requisitos

* [Terraform](https://developer.hashicorp.com/terraform/downloads) instalado.
* [AWS CLI](https://aws.amazon.com/cli/) configurada con credenciales válidas.