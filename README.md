# Gestor de Descargas Corporativo (GTK4 + Aria2 + Zero Trust)

Un gestor de descargas moderno, modular y nativo para Linux (GNOME) escrito en Python, diseñado específicamente para entornos empresariales con requisitos de máxima seguridad y **Confianza Cero (Zero Trust)**.

Utiliza una arquitectura dividida en tres capas: **GTK4/Libadwaita** para una interfaz nativa, un **Router Inteligente** en Python, y un motor **Aria2** corriendo dentro de un **Búnker de Red Docker** aislado perimetralmente.

## Características Principales

* **Interfaz Nativa GNOME:** Construida con GTK4 y Libadwaita para integrarse con el ecosistema de Linux moderno.
* **Descargas Multiparte Optimizadas:** Alimentado por `aria2`, soporta descargas HTTP/HTTPS y FTP dividiendo los archivos en múltiples conexiones simultáneas desde diferentes hosts.
* **Arquitectura Zero Trust y Cero Fugas:** El tráfico es secuestrado por un cortafuegos estricto (`iptables`) a nivel de contenedor. Si el túnel seguro falla, la red se corta físicamente (`Kill-Switch`). Incorpora un servidor DNS interno (`dnsmasq`) para evitar fugas de resolución (`DNS Leaks`) y fuerza el enrutamiento socks5h a través de un proxy transparente (`Privoxy`).
* **Importación por Lotes y Grupos (JSON):** Soporte para importar listas masivas de descargas simples o archivos divididos en partes lógicas. El sistema gestiona automáticamente múltiples fuentes (`espejos`) para un mismo archivo y omite descargas duplicadas.
* **Autenticación Nativa:** Soporte integrado para inyectar credenciales (`Basic Auth`) o Tokens de acceso (`Bearer Tokens`) en descargas protegidas a través del archivo JSON. Cada parte de un mismo archivo puede autenticarse contra un host diferente. El router de Python intercepta proactivamente las redirecciones 302 típicas de las APIs corporativas, pasarelas de seguridad o URLs temporales, asegurando que el motor de descarga reciba el enlace puro final sin romper firmas criptográficas.
* **Extractor Inteligente (Router):**
  * Filtro de extensiones empresariales clasificadas por tipología (`.zip`, `.pdf`, `.mp4`, `.iso`, etc.).
  * Soporte integrado para extraer vídeos corporativos usando `yt-dlp`.

## Arquitectura del Sistema

1. **La Interfaz (UI):** `main_ui.py` — Maneja la ventana GTK4, importación de JSON, validación de protocolos y los bucles de monitorización asíncrona.
2. **Las Reglas (Backend):** `extractor.py` —Estructura las peticiones, intercepta los redirects 302 de las pasarelas corporativas para proteger las firmas, y gestiona la comunicación RPC.
3. **El Búnker (Docker):** Contenedor Alpine bloqueado a nivel de Kernel.
4. **La Lambda de autenticación:** `lambda_auth.py` — Valida la cabecera `X-My-App-Auth` y genera URLs prefirmadas de S3 forzando el endpoint regional.

```text
[ Interfaz GTK4 ] <---(JSON / RPC)---> [ Router Python / Extractor ]
                                            |
                         (Intercepta 302 y extrae URL pura de S3)
                                            |
  [ Contenedor Docker (Búnker Zero Trust) ]------------------------------
  |                                                                     |
  |  [ Aria2c ] ---> (Consulta DNS)  ---> [ dnsmasq (Fake DNS) ]        |
  |             ---> (Petición HTTP) ---> [ Privoxy (Puerto 8118) ]     |
  |                                                  |                  |
  |  [ iptables (Kill-Switch) ] <---------------------                  |
  |  (Bloquea TODO el tráfico excepto IP del Proxy)                     |
  -----------------------------------------------------------------------
                                            |
                                  (SOCKS5h Encriptado)
                                            v
                                  [ Dante Proxy SOCKS5 ]
                                            |
                                            v
                           [ API Gateways / S3 (AWS Irlanda) ]
```

### Puertos Expuestos (Docker)

- **6800 (Aria2 RPC):** Puerto de control interno. Permite que la aplicación en Python envíe comandos de descarga y consulte el estado del progreso.
- **8118 (Privoxy):** Puerto de intercepción segura. Permite a Python usar el túnel estanco de Docker para comunicarse con APIs externas.


## Guía de Instalación para Nuevos Usuarios

Esta sección está dirigida a usuarios finales o al departamento de IT que instale la aplicación por primera vez en una máquina con **Debian 13.2** (GNOME, 8 GB RAM, 4 CPUs).

### Paso 1 — Configurar el proxy en el SO (IT)

**Este paso debe completarlo el departamento de IT antes de entregar la máquina al usuario**, o el propio usuario si tiene las credenciales del proxy.

1. Abre **Configuración del sistema** → **Red** → **Proxy de red**.
2. Activa el proxy y selecciona **Manual**.
3. En **SOCKS Host**, introduce la dirección y puerto del proxy corporativo.
4. Cierra la configuración. Los cambios se aplican de inmediato, sin reiniciar la aplicación.


### Paso 2 — Instalar dependencias del sistema

Abre una terminal y ejecuta:

```bash
sudo apt update
sudo apt install -y \
    python3-gi python3-gi-cairo \
    gir1.2-gtk-4.0 gir1.2-adw-1 \
    python3-pip \
    docker.io docker-compose \
    git
```

### Paso 3 — Clonar el repositorio

```bash
git clone https://github.com/pauurrd/gestor_descargas.git
cd gestor_descargas
```

### Paso 4 — Instalar dependencias de Python

```bash
pip3 install yt-dlp requests --break-system-packages
```

### Paso 5 — Añadir tu usuario al grupo Docker

Para poder ejecutar Docker sin `sudo`:

```bash
sudo usermod -aG docker $USER
```

Cierra sesión y vuelve a entrar para que el cambio tenga efecto.

### Paso 6 — Levantar el Búnker de Descargas (IT)

La aplicación aplica una política de Confianza Cero. Se debe inyectar la IP del proxy corporativo directamente en el contenedor Docker en el momento de levantarlo.

Desde la raíz del repositorio, inyecta tus variables de red corporativas:

```bash
PROXY_IP="IP_DEL_PROXY" PROXY_PORT="1080" docker-compose up -d --force-recreate
```

(El contenedor tardará entre 30 y 60 segundos en instalar las dependencias internas y bloquear el firewall).

### Paso 7 — Iniciar la aplicación

```bash
python3 main_ui.py
```

La aplicación está lista para usarse.

## Uso Básico

### Descarga por URL

Pega una URL directa en el campo de texto superior y pulsa `Descargar`. El router delegará la petición al búnker.

### Importación por JSON

Para descargar múltiples archivos o grupos de partes de un mismo fichero, pulsa **Importar JSON** y selecciona un archivo con el formato descrito más abajo. Es el método recomendado para descargas corporativas con autenticación.

### Panel de control

Selecciona cualquier descarga de la lista para activar los botones de acción:

* **Reintentar** — reintenta una descarga fallida con los mismos parámetros.
* **Pausar / Reanudar** — pausa o reanuda una descarga activa.
* **Cancelar** — cancela y elimina la tarea.
* **Abrir Carpeta** — abre el explorador de archivos en la carpeta `./Descargas`.



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

* **Error "Aria2 rechazó el enlace" (❌ Rechazado):** El motor no pudo establecer la conexión inicial. Causas comunes: proxy del SO caído o inaccesible, o URL de S3 con firma caducada o región incorrecta.

* **Descargas congeladas en "Conectando...":** Ocurre en entornos corporativos al descargar desde la IP pública de la propia empresa a través del proxy interno (problema de "Hairpin NAT"). Solución: pedir al equipo de redes que habilite hairpinning o implemente Split DNS.

* **Descargas congeladas en "0 KB/s" o "Fallo de red":** El Kill-Switch de iptables ha entrado en acción. Esto significa que el proxy corporativo (`PROXY_IP`) introducido en Docker está caído, o el puerto está cerrado. El sistema se ha bloqueado para evitar fugas de IP a internet abierto.

* **❌ Error (Código 1) — Conexión abortada:** La conexión fue cortada por un intermediario. Causas: proxy corporativo (Zscaler, Squid) con el método `CONNECT` bloqueado, o política de tamaño máximo de archivo activa. Contactar con el administrador de red.

* **❌ Error (Código 4) — Recurso no encontrado (HTTP 404):** La URL del API Gateway es correcta pero la ruta no existe. En la infraestructura de pruebas, asegurarse de que las rutas de los API Gateways están configuradas como `$default` y no como rutas específicas (`GET /download`).

* **❌ Error (Código 22) — Respuesta HTTP inesperada (HTTP 403/401):** El gestor recibió una respuesta de error en lugar de datos binarios. Causas comunes:
  * **Auth incorrecta:** Revisar el bloque `"auth"` del JSON. El valor de `X-My-App-Auth` debe coincidir exactamente con el `EXPECTED_AUTH` de la Lambda (incluyendo el prefijo `Bearer ` o `Basic `).
  * **Doble redirect en S3:** Si la Lambda genera URLs presignadas sin `endpoint_url` explícito, boto3 usa el endpoint global de S3 y éste hace un redirect interno al endpoint regional. La firma queda ligada al host original y el segundo request devuelve 403. Solución: instanciar el cliente S3 con `endpoint_url='https://s3.eu-west-1.amazonaws.com'` (ajustar la región según corresponda).
  * **Proxy corporativo inyectando HTML:** Si el recurso es público pero sigue fallando, la seguridad perimetral puede estar bloqueando la URL e inyectando una página de advertencia HTML.


## ☁️ Entorno de Pruebas en AWS (Terraform)

Este repositorio incluye `main.tf` y `lambda_auth.py` para levantar automáticamente una infraestructura de pruebas en AWS que valida el flujo completo de descarga multi-host con autenticación diferente por parte.

### Qué despliega

* **EC2 con Dante Proxy** — Actúa como el túnel SOCKS5. Protegido por Security Group atado a tu IP pública actual.
* **3 API Gateways HTTP y 3 Funciones Lambda** (`lambda_auth.py`) — Validan los tokens, interceptan autenticaciones y generan la firma V4 de S3, forzando la región para evitar corrupciones de firma 301/302.
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