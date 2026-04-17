import threading
import json
from schemas import RecursoImportacion
from pydantic import ValidationError
from extractor import enviar_a_aria2

class GestorDescargasCore:
    def __init__(self, log_callback, ui_callback):
        # Callbacks para avisar a la UI sin depender de GTK
        self.log = log_callback
        self.registrar_descarga_ui = ui_callback

    def procesar_archivo_json(self, ruta_archivo, proxy_actual):
        try:
            with open(ruta_archivo, 'r') as f:
                datos_crudos = json.load(f)
            
            if not isinstance(datos_crudos, list):
                self.log("❌ Error: El JSON debe contener una lista [].")
                return False
            
            datos_validados = []
            errores = 0
            
            # Pasamos cada elemento por el colador de Pydantic
            for i, item in enumerate(datos_crudos):
                try:
                    recurso_seguro = RecursoImportacion(**item)
                    datos_validados.append(recurso_seguro.model_dump(by_alias=True, exclude_none=True))
                except ValidationError as e:
                    errores += 1
                    self.log(f"⚠️ Error de seguridad/formato en el elemento {i+1}. Ignorado.")
                    print(f"Detalle Pydantic: {e}")
            
            if datos_validados:
                self.log(f"✅ JSON validado: {len(datos_validados)} elementos seguros ({errores} ignorados por fallos).")
                self.procesar_batch_json(datos_validados, proxy_actual)
                return True
            else:
                self.log("❌ Ningún elemento del JSON pasó el filtro de seguridad (Pydantic).")
                return False
                
        except Exception as e:
            self.log(f"❌ Error crítico al leer JSON: {str(e)}")
            return False

    def procesar_batch_json(self, datos, proxy_actual):
        procesados = set()

        for item in datos:
            auth_grupo = item.get('auth')
            
            if "archivos" in item:
                id_grupo = item.get("id_recurso", "grupo_desconocido")
                nombre_grupo = item.get("nombre_grupo", id_grupo)
                
                if id_grupo in procesados:
                    continue
                procesados.add(id_grupo)
                
                self.log(f"📦 Detectado grupo: {nombre_grupo} ({len(item['archivos'])} partes)")
                
                for parte in item["archivos"]:
                    urls = parte.get("fuentes", [])
                    nombre_parte = parte.get("nombre", "parte_desconocida")
                    auth_parte = parte.get('auth', auth_grupo) 
                    
                    if not urls:
                        continue
                    
                    nombre_visual = f"[{nombre_grupo}] {nombre_parte}"
                    threading.Thread(
                        target=self.tarea_background_multiple, 
                        args=(urls, nombre_visual, proxy_actual, auth_parte)
                    ).start()
                    
            else:
                id_unico = item.get('id_recurso') or item.get('nombre')
                urls = item.get('fuentes', [])
                
                if not urls or id_unico in procesados:
                    continue
                procesados.add(id_unico)

                nombre_archivo = item.get('nombre', f"descarga_{id_unico}")
                
                threading.Thread(
                    target=self.tarea_background_multiple, 
                    args=(urls, nombre_archivo, proxy_actual, auth_grupo)
                ).start()

    def tarea_background_multiple(self, urls, nombre, proxy, auth):
        self.log(f"Iniciando descarga múltiple: {nombre}")
        respuesta = enviar_a_aria2(urls, nombre, proxy, auth)
        gid = respuesta.get('result') if respuesta else None
        
        if gid:
            self.registrar_descarga_ui(gid, nombre, urls[0], proxy)
        else:
            error_msg = respuesta.get('error', {}).get('message', 'Fallo desconocido o de conexión') if respuesta else 'Fallo de red'
            self.log(f"❌ Aria2 rechazó el enlace '{nombre}': {error_msg}")