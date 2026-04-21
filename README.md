# Gestor de Descargas Corporativo (GTK4 + Aria2)

Un gestor de descargas moderno, modular y nativo para Linux (GNOME) escrito en Python, diseñado específicamente para entornos empresariales y peticiones seguras.

Utiliza una arquitectura dividida en tres capas: **GTK4/Libadwaita** para una interfaz nativa, un **Router Inteligente** en Python, y un motor **Aria2** corriendo de forma aislada en Docker.

## Características Principales

* **Interfaz Nativa GNOME:** Construida con GTK4 y Libadwaita para integrarse con el ecosistema de Linux moderno.
* **Descargas Multiparte Optimizadas:** Alimentado por `aria2`, soporta descargas HTTP/HTTPS y FTP dividiendo los archivos en múltiples conexiones simultáneas desde diferentes hosts.
* **Enrutamiento Corporativo:** Detección automática del proxy del SO en cada descarga, leyendo directamente desde GNOME Settings. Cualquier cambio en la configuración de red del SO se aplica de forma inmediata sin reiniciar la aplicación.
* **Importación por Lotes y Grupos (JSON):** Soporte para importar listas masivas de descargas simples o archivos divididos en partes lógicas. El sistema gestiona automáticamente múltiples fuentes (espejos) para un mismo archivo y omite descargas duplicadas.
* **Autenticación Nativa:** Soporte integrado para inyectar credenciales (Basic Auth) o Tokens de acceso (Bearer Tokens) en descargas protegidas a través del archivo JSON. Cada parte de un mismo archivo puede autenticarse contra un host diferente.
* **Extractor Inteligente (Router):**
  * Filtro de extensiones empresariales clasificadas por tipología (`.zip`, `.pdf`, `.mp4`, `.iso`, etc.).
  * Soporte integrado para extraer vídeos corporativos usando `yt-dlp`.

## Arquitectura del Sistema

1. **La Interfaz (UI):** `main_ui.py` — Maneja la ventana GTK4, importación de JSON, validación de protocolos y los bucles de monitorización asíncrona.
2. **Las Reglas (Backend):** `extractor.py` — Filtra URLs, extrae enlaces directos, estructura las peticiones de autenticación y gestiona la comunicación RPC con aria2.
3. **La Lambda de autenticación:** `lambda_auth.py` — Valida la cabecera `X-My-App-Auth` y genera URLs presignadas de S3 con firma V4.

```text
[ Interfaz GTK4 ] <---(JSON / RPC)---> [ Router Python / Extractor (yt-dlp) ]
                                                    |
                                         (Petición con X-My-App-Auth)
                                                    v
                                          [ Proxy del SO ]
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
  [ Contenedor Docker ]--------------------------------------------------
  |                                                                     |
  |  [ Aria2c ] <---- datos binarios en paralelo desde los 3 buckets   |
  -----------------------------------------------------------------------
```

### Puertos Expuestos (Docker)

- **6800 (Aria2 RPC):** Puerto de control interno. Permite que la aplicación en Python envíe comandos de descarga y consulte el estado del progreso.

---

## Guía de Instalación para Nuevos Usuarios

Esta sección está dirigida a usuarios finales o al departamento de IT que instale la aplicación por primera vez en una máquina con **Debian 13.2** (GNOME, 8 GB RAM, 4 CPUs).

Hay dos métodos de instalación. El **método recomendado** es mediante el paquete `.deb`, que automatiza todos los pasos. El método manual se mantiene como alternativa para entornos de desarrollo.

---

### Método 1 — Instalación mediante paquete .deb (recomendado)

Este es el método pensado para el cliente final. No requiere clonar el repositorio ni instalar dependencias manualmente.

#### Paso 1 — Configurar el proxy corporativo (IT)

**Este paso debe completarlo el departamento de IT antes de entregar la máquina al usuario.**

La aplicación lee el proxy directamente desde GNOME Settings en cada descarga. No hay ningún campo en la interfaz para introducirlo — debe estar configurado a nivel de sistema operativo.

1. Abre **Configuración del sistema** → **Red** → **Proxy de red**.
2. Activa el proxy y selecciona **Manual**.
3. En **Proxy HTTP**, introduce la dirección y puerto del proxy corporativo.
4. Cierra la configuración. Los cambios se aplican de inmediato, sin reiniciar la aplicación.

> Si el proxy cambia en el futuro, basta con actualizar este valor en GNOME Settings. La aplicación lo detectará automáticamente en la siguiente descarga.

#### Paso 2 — Instalar el paquete

```bash
sudo dpkg -i gestor-descargas_1.0.0_amd64_systemd.deb
sudo apt-get install -f   # resuelve dependencias si falta alguna
```

El instalador se encarga automáticamente de instalar las dependencias de Python, levantar el motor de descargas y registrar la aplicación en el menú de GNOME.

#### Paso 3 — Iniciar la aplicación

Busca **Gestor de Descargas** en el menú de aplicaciones de GNOME, o desde terminal:

```bash
gestor-descargas
```

---

### Método 2 — Instalación manual desde el repositorio (desarrollo)

Este método está pensado para el equipo de desarrollo.

#### Paso 1 — Configurar el proxy corporativo (IT)

Igual que en el Método 1 — ver instrucciones arriba.

#### Paso 2 — Instalar dependencias del sistema

```bash
sudo apt update
sudo apt install -y \
    python3-gi python3-gi-cairo \
    gir1.2-gtk-4.0 gir1.2-adw-1 \
    python3-pip \
    docker.io docker-compose \
    git
```

#### Paso 3 — Clonar el repositorio

```bash
git clone https://github.com/pauurrd/gestor_descargas.git
cd gestor_descargas
```

#### Paso 4 — Instalar dependencias de Python

```bash
pip3 install yt-dlp requests --break-system-packages
```

#### Paso 5 — Añadir tu usuario al grupo Docker

```bash
sudo usermod -aG docker $USER
```

Cierra sesión y vuelve a entrar para que el cambio tenga efecto. Verifica con:

```bash
docker ps
```

#### Paso 6 — Levantar el motor de descargas

```bash
docker-compose up -d
```

Con `restart: unless-stopped` el contenedor arrancará automáticamente con el sistema en sucesivos reinicios. Verifica que está corriendo:

```bash
docker ps
# Debe aparecer 'poc-aria2-backend' con estado 'Up'
```

#### Paso 7 — Iniciar la aplicación

```bash
python3 main_ui.py
```

> **Nota para entornos VirtualBox:** GTK4 puede congelarse en un bucle infinito al intentar usar aceleración 3D con la tarjeta gráfica simulada, lanzando el error `MESA: error: Failed to attach to x11 shm`. Para evitarlo, fuerza el renderizado por software (CPU) arrancando la app así:
> ```bash
> GSK_RENDERER=cairo python3 main_ui.py
> ```

---

## Generación del Paquete .deb (desarrolladores)

El repositorio incluye dos scripts para generar el paquete `.deb` según el motor de descargas elegido. Ambos se ejecutan desde la raíz del repositorio y generan el instalador en `dist/`.

### Generar el instalador

aria2 se instala como binario nativo y corre como servicio del SO. No requiere Docker en la máquina del cliente.

```bash
chmod +x build_deb_systemd.sh
./build_deb_systemd.sh
# Genera: dist/gestor-descargas_1.0.0_amd64_systemd.deb
```

### Estructura de archivos de packaging

```
packaging/
├── DEBIAN/
│   ├── control              ← metadatos y dependencias del paquete
│   ├── postinst             ← pip install + systemctl enable/start
│   └── prerm                ← systemctl stop antes de desinstalar
├── lib/systemd/system/
│   └── aria2-rpc.service    ← unidad systemd de aria2
└── usr/
    ├── bin/
    │   └── gestor-descargas      ← script lanzador
    └── share/applications/
        └── gestor-descargas.desktop ← entrada menú GNOME
```

---

## Uso Básico

### Descarga por URL

Pega una URL directa en el campo de texto superior y pulsa **Descargar** o la tecla `Enter`. La aplicación detectará automáticamente el tipo de archivo y lo enviará al motor de descarga.

### Importación por JSON

Para descargar múltiples archivos o grupos de partes de un mismo fichero, pulsa **Importar JSON** y selecciona un archivo con el formato descrito más abajo. Es el método recomendado para descargas corporativas con autenticación.

### Panel de control

Selecciona cualquier descarga de la lista para activar los botones de acción:

* **Reintentar** — reintenta una descarga fallida con los mismos parámetros.
* **Pausar / Reanudar** — pausa o reanuda una descarga activa.
* **Cancelar** — cancela y elimina la tarea.
* **Abrir Carpeta** — abre el explorador de archivos en la carpeta de descargas.

---

## Formato de Importación JSON

Soporta descargas simples, espejos (múltiples fuentes para el mismo archivo) y grupos de partes con autenticación diferente por parte.

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

---

## Historial de Descargas

Cada vez que finaliza o falla una descarga, el sistema guarda un registro en `historial_descargas.db`. Para visualizarlo:

```bash
sudo apt install sqlitebrowser
sqlitebrowser historial_descargas.db
```

En la pestaña **Browse Data** verás: fecha y hora, nombre del archivo, hash SHA-256, URL de origen y proxy usado.

---

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

---

## Resolución de Problemas Frecuentes y Códigos de Error

* **La app se congela al arrancar en VirtualBox** (`MESA: error: Failed to attach to x11 shm`): GTK4 intenta usar aceleración 3D con la tarjeta gráfica simulada de VirtualBox y falla. Solución: forzar renderizado por software con `GSK_RENDERER=cairo python3 main_ui.py`.

* **Error "Aria2 rechazó el enlace" (❌ Rechazado):** El motor no pudo establecer la conexión inicial. Causas comunes: proxy del SO caído o inaccesible, o URL de S3 con firma caducada o región incorrecta.

* **Descargas congeladas en "Conectando...":** Ocurre en entornos corporativos al descargar desde la IP pública de la propia empresa a través del proxy interno (problema de "Hairpin NAT"). Solución: pedir al equipo de redes que habilite hairpinning o implemente Split DNS.

* **❌ Error (Código 1) — Conexión abortada:** La conexión fue cortada por un intermediario. Causas: proxy corporativo (Zscaler, Squid) con el método `CONNECT` bloqueado, o política de tamaño máximo de archivo activa. Contactar con el administrador de red.

* **❌ Error (Código 4) — Recurso no encontrado (HTTP 404):** La URL del API Gateway es correcta pero la ruta no existe. En la infraestructura de pruebas, asegurarse de que las rutas de los API Gateways están configuradas como `$default` y no como rutas específicas (`GET /download`).

* **❌ Error (Código 22) — Respuesta HTTP inesperada (HTTP 403/401):** El gestor recibió una respuesta de error en lugar de datos binarios. Causas comunes:
  * **Auth incorrecta:** Revisar el bloque `"auth"` del JSON. El valor de `X-My-App-Auth` debe coincidir exactamente con el `EXPECTED_AUTH` de la Lambda (incluyendo el prefijo `Bearer ` o `Basic `).
  * **Doble redirect en S3:** Si la Lambda genera URLs presignadas sin `endpoint_url` explícito, boto3 usa el endpoint global de S3 y éste hace un redirect interno al endpoint regional. La firma queda ligada al host original y el segundo request devuelve 403. Solución: instanciar el cliente S3 con `endpoint_url='https://s3.eu-west-1.amazonaws.com'` (ajustar la región según corresponda).
  * **Proxy corporativo inyectando HTML:** Si el recurso es público pero sigue fallando, la seguridad perimetral puede estar bloqueando la URL e inyectando una página de advertencia HTML.

---

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

En Linux:

```bash
wget https://cdimage.debian.org/debian-cd/current/amd64/iso-cd/debian-12.5.0-amd64-netinst.iso
7z a -v300m debian-split.7z debian-12.5.0-amd64-netinst.iso
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

```bash
7z x debian-13.2.0-amd64-netinst.7z.001
```

7-Zip detecta automáticamente las partes `.001`, `.002`, `.003` y reconstruye el archivo original.

### Limpieza

```bash
terraform destroy
```

### Requisitos

* [Terraform](https://developer.hashicorp.com/terraform/downloads) instalado.
* [AWS CLI](https://aws.amazon.com/cli/) configurada con credenciales válidas.