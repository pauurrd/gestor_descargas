import sys
import threading
import gi
import os
import hashlib
import urllib.parse
import json
from schemas import RecursoImportacion
from pydantic import ValidationError
from database import init_db, registrar_descarga, upsert_entidad

os.environ['no_proxy'] = 'localhost,127.0.0.1,::1'

from database import init_db, registrar_descarga

gi.require_version('Gtk', '4.0')
gi.require_version('Adw', '1') 
from gi.repository import Gtk, Adw, Gio, GLib, GObject

from extractor import (resolver_url, enviar_a_aria2, obtener_estado_aria2, 
                       formatear_tamano, obtener_info_gid, 
                       pausar_descarga_aria2, reanudar_descarga_aria2, cancelar_descarga_aria2)

class VentanaPrincipal(Adw.ApplicationWindow):
    def __init__(self, app):
        super().__init__(application=app, title="Gestor de Descargas Corporativo")
        self.set_default_size(1200, 800)
        
        self.filtro_actual_index = 0 

        caja_main = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        header = Adw.HeaderBar()
        caja_main.append(header)
        
        self.paned_principal = Gtk.Paned(orientation=Gtk.Orientation.VERTICAL)
        self.paned_principal.set_vexpand(True)
        caja_main.append(self.paned_principal)
        self.set_content(caja_main)

        self.paned_superior = Gtk.Paned(orientation=Gtk.Orientation.HORIZONTAL)
        self.paned_principal.set_start_child(self.paned_superior)
        self.paned_principal.set_position(500)

        self.sidebar = Gtk.ListBox()
        self.sidebar.add_css_class("navigation-sidebar")
        self.sidebar.connect("row-selected", self.on_sidebar_selected)

        for etiqueta in ["📥 Todas", "⏳ Descargando", "✅ Completadas", "❌ Errores"]:
            row = Gtk.ListBoxRow()
            lbl = Gtk.Label(label=etiqueta, xalign=0, margin_start=10, margin_top=10, margin_bottom=10)
            row.set_child(lbl)
            self.sidebar.append(row)

        scroll_sidebar = Gtk.ScrolledWindow()
        scroll_sidebar.set_child(self.sidebar)
        scroll_sidebar.set_size_request(200, -1)
        self.paned_superior.set_start_child(scroll_sidebar)

        caja_derecha = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=10)
        
        caja_input = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=10)
        caja_input.set_margin_top(10)
        caja_input.set_margin_start(10)
        caja_input.set_margin_end(10)
        
        self.entrada_url = Gtk.Entry()
        self.entrada_url.set_hexpand(True)
        self.entrada_url.set_placeholder_text("Pega aquí el enlace del documento a descargar y pulsa Enter...")
        self.entrada_url.connect("activate", self.on_btn_descargar_clicked)
        
        btn_descargar = Gtk.Button(label="Descargar")
        btn_descargar.add_css_class("suggested-action")
        btn_descargar.connect("clicked", self.on_btn_descargar_clicked)
        
        btn_importar = Gtk.Button(label="📄 Importar JSON")
        btn_importar.connect("clicked", self.on_btn_importar_clicked)

        caja_input.append(self.entrada_url)
        caja_input.append(btn_descargar)
        caja_input.append(btn_importar)
        caja_derecha.append(caja_input)

        self.store = Gio.ListStore(item_type=DescargaItem)
        self.filtro = Gtk.CustomFilter.new(match_func=self.logica_de_filtrado)
        self.filter_model = Gtk.FilterListModel(model=self.store, filter=self.filtro)
        self.selection_model = Gtk.SingleSelection(model=self.filter_model)
        
        self.tabla = Gtk.ColumnView(model=self.selection_model)
        self.crear_columna("Nombre", "nombre")
        self.crear_columna("Estado", "estado")
        self.crear_columna("Tamaño", "tamano")   
        self.crear_columna("Progreso", "progreso")
        self.crear_columna("Velocidad", "velocidad") 
        
        scroll_tabla = Gtk.ScrolledWindow()
        scroll_tabla.set_child(self.tabla)
        scroll_tabla.set_vexpand(True)
        caja_derecha.append(scroll_tabla)

        caja_acciones = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=10)
        caja_acciones.set_margin_bottom(10)
        caja_acciones.set_margin_start(10)
        caja_acciones.set_margin_end(10)
        
        self.btn_reintentar = Gtk.Button(label="🔄 Reintentar")
        self.btn_pausar = Gtk.Button(label="⏸ Pausar / Reanudar")
        self.btn_cancelar = Gtk.Button(label="⏹ Cancelar")
        self.btn_abrir_carpeta = Gtk.Button(label="📁 Abrir Carpeta")
        self.btn_abrir_carpeta.connect("clicked", self.on_btn_abrir_carpeta_clicked)
        
        self.btn_reintentar.add_css_class("suggested-action")
        self.btn_cancelar.add_css_class("destructive-action")
        
        self.btn_reintentar.connect("clicked", self.on_btn_reintentar_clicked)
        self.btn_pausar.connect("clicked", self.on_btn_pausar_clicked)
        self.btn_cancelar.connect("clicked", self.on_btn_cancelar_clicked)
        
        caja_acciones.append(self.btn_reintentar)
        caja_acciones.append(self.btn_pausar)
        caja_acciones.append(self.btn_cancelar)
        caja_acciones.append(self.btn_abrir_carpeta)
        caja_derecha.append(caja_acciones)

        self.paned_superior.set_end_child(caja_derecha)
        self.paned_superior.set_position(300)

        self.log_buffer = Gtk.TextBuffer()
        self.log_view = Gtk.TextView(buffer=self.log_buffer)
        self.log_view.set_editable(False)
        scroll_log = Gtk.ScrolledWindow()
        scroll_log.set_child(self.log_view)
        notebook = Gtk.Notebook()
        notebook.append_page(scroll_log, Gtk.Label(label="Registro de Actividad"))
        self.paned_principal.set_end_child(notebook)

        self.log("Sistema iniciado y listo para uso corporativo.")
        init_db() 
        self.log("🗄️ Base de datos local conectada.")
        self.sidebar.select_row(self.sidebar.get_row_at_index(0))
        self.log("🔒 Entorno seguro activado: Tráfico gestionado por cortafuegos (Docker).")
        GLib.timeout_add(1000, self.monitorizar_descargas)

    def procesar_json_importado(self, datos_json):
        descargas_unicas = {}
        for item in datos_json:
            id_unico = item.get('id_recurso') or item['fuentes'][0]['url']
            
            if id_unico not in descargas_unicas:
                descargas_unicas[id_unico] = item
            else:
                self.log(f"♻️ Duplicado omitido: {id_unico}")

        for res_id, info in descargas_unicas.items():
            urls = [f['url'] for f in info['fuentes']]
            nombre = info.get('nombre', "archivo_descargado")
            auth = info.get('auth')
            
            threading.Thread(target=self.tarea_background_multiple, args=(urls, nombre, auth)).start()

    def on_btn_importar_clicked(self, btn):
        dialog = Gtk.FileDialog(title="Seleccionar lista de descargas (JSON)")
        filtros = Gio.ListStore.new(Gtk.FileFilter)
        f = Gtk.FileFilter()
        f.set_name("Archivos JSON")
        f.add_suffix("json")
        filtros.append(f)
        dialog.set_filters(filtros)

        dialog.open(self, None, self.al_seleccionar_archivo_json)

    def al_seleccionar_archivo_json(self, dialog, resultado):
        try:
            archivo = dialog.open_finish(resultado)
            if archivo:
                import ijson
                from schemas import RecursoImportacion
                from pydantic import ValidationError

                datos_validos = []
                errores = 0

                self.log("Leyendo JSON en modo streaming y validano...")

                with open(archivo.get_path(), 'rb') as f:
                    objetos_json = ijson.items(f, 'item')

                    for item in objetos_json:
                        try:
                            modelo_validado = RecursoImportacion(**item)
                            datos_validos.append(modelo_validado.model_dump(mode='json', exclude_none=True, by_alias=True))
                        except ValidationError:
                            errores += 1
                
                if datos_validos:
                    self.log(f"JSON procesado {len(datos_validos)} elementos válidos ({errores} descartados por formato).")
                    self.procesar_batch_json(datos_validos)
                else:
                    self.log("No se encontró ningún elemento válido en el JSON.")
            
        except Exception as e:
            if "Dismissed by user" in str(e):
                return
            self.log(f"❌ Error crítico al leer JSON: {str(e)}")

    def procesar_batch_json(self, datos):
        self.log(f"🛠️ Fase de Enriquecimiento: Normalizando {len(datos)} elementos...")
        nuevos_recursos = 0

        for item in datos:
            if "archivos" in item:
                id_grupo = item.get("id_recurso", "grupo_desconocido")
                auth_grupo = item.get('auth')

                for parte in item["archivos"]:
                    # Fabricamos un mini-diccionario temporal para el upsert
                    uid_parte = f"{id_grupo}_{parte.get('nombre', 'parte')}"
                    item_procesar = {
                        "id_recurso": uid_parte,
                        "nombre": f"[{item.get('nombre_grupo', id_grupo)}] {parte.get('nombre')}",
                        "fuentes": parte.get("fuentes", []),
                        "auth": parte.get('auth', auth_grupo)
                    }
                    if upsert_entidad(item_procesar):
                        nuevos_recursos += 1
                else:
                # Archivo simple
                if upsert_entidad(item):
                    nuevos_recursos += 1
            
        self.log(f"🗄️ {nuevos_recursos} entidades expandidas/guardadas en la base de datos (Estado: 'nuevo').")
        self.log("⏳ El Scheduler (pendiente de programar) decidirá el orden de descarga.")
                

    def al_seleccionar_archivo_json(self, dialog, resultado):
        try:
            archivo = dialog.open_finish(resultado)
            if archivo:
                with open(archivo.get_path(), 'r') as f:
                    datos_crudos = json.load(f)
                
                if not isinstance(datos_crudos, list):
                    self.log("❌ Error: El JSON debe contener una lista [].")
                    return
                
                datos_validados = []
                errores = 0
                
                # Pasamos cada elemento por el colador de Pydantic
                for i, item in enumerate(datos_crudos):
                    try:
                        recurso_seguro = RecursoImportacion(**item)
                        # by_alias=True es vital para que "pass" vuelva a ser "pass" y no "password"
                        datos_validados.append(recurso_seguro.model_dump(by_alias=True, exclude_none=True))
                    except ValidationError as e:
                        errores += 1
                        self.log(f"⚠️ Error de seguridad/formato en el elemento {i+1}. Ignorado.")
                        print(f"Detalle Pydantic: {e}")
                
                if datos_validados:
                    self.log(f"✅ JSON validado: {len(datos_validados)} elementos seguros ({errores} ignorados por fallos).")
                    self.procesar_batch_json(datos_validados)
                else:
                    self.log("❌ Ningún elemento del JSON pasó el filtro de seguridad (Pydantic).")
                    
        except Exception as e:
            self.log(f"❌ Error crítico al leer JSON: {str(e)}")
            

    def tarea_background_multiple(self, urls, nombre, auth=None):
        GLib.idle_add(self.log, f"Iniciando descarga múltiple: {nombre}")
        respuesta = enviar_a_aria2(urls, nombre, auth)
        gid = respuesta.get('result') if respuesta else None
        
        if gid:
            GLib.idle_add(self.registrar_descarga_ui, gid, nombre, urls[0])
        else:
            error_msg = respuesta.get('error', {}).get('message', 'Fallo desconocido o de conexión') if respuesta else 'Fallo de red'
            GLib.idle_add(self.log, f"❌ Aria2 rechazó el enlace '{nombre}': {error_msg}")

    def registrar_descarga_ui(self, gid, nombre, url_ref):
        nuevo = DescargaItem(gid, nombre, "Pendiente...", "0 MB", "0%", "0 KB/s", url_ref, "Protegido por Docker")
        self.store.append(nuevo)
        self.filtro.changed(Gtk.FilterChange.DIFFERENT)

    def on_btn_descargar_clicked(self, widget=None):
        url = self.entrada_url.get_text().strip()

        if not url:
            return

        if not url.startswith(('http://', 'https://', 'ftp://')):
            self.log(f"⚠️ ERROR: El enlace '{url}' es inválido. Debe empezar por http://, https:// o ftp://")
            return

        self.entrada_url.set_text("")
        threading.Thread(target=self.tarea_background, args=(url,)).start()

    def on_btn_reintentar_clicked(self, btn):
        item = self.selection_model.get_selected_item()
        if not item: return
        
        if "Cancelado" in item.estado or "Error" in item.estado or "Rechazado" in item.estado:
            if not item.url: 
                self.log(f"⚠️ No hay un enlace válido guardado para reintentar {item.nombre}.")
                return
                
            self.log(f"🔄 Reintentando descarga: {item.nombre}")
            respuesta = enviar_a_aria2(item.url, item.nombre, None)
            nuevo_gid = respuesta.get('result', None) if respuesta else None
            
            if nuevo_gid:
                item.gid = nuevo_gid
                item.estado = "Pendiente..."
                item.progreso = "0%"
                item.velocidad = "0 KB/s"
                item.tamano = "Calculando..."
                self.filtro.changed(Gtk.FilterChange.DIFFERENT)
            else:
                self.log(f"❌ Fallo al intentar reiniciar {item.nombre} en aria2.")

    def guardar_historial_background(self, nombre_json, url_origen, estado_final):
        ruta_url = urllib.parse.urlparse(url_origen).path
        nombre_original = os.path.basename(ruta_url)
        if not nombre_original:
            nombre_original = "Desconocido/Generado"

        hash_archivo = "-"
        if "Completado" in estado_final:
            ruta_local = os.path.join(os.path.abspath("./Descargas"), nombre_json)
            if os.path.exists(ruta_local):
                sha256 = hashlib.sha256()
                try:
                    with open(ruta_local, "rb") as f:
                        for bloque in iter(lambda: f.read(8192), b""):
                            sha256.update(bloque)
                    hash_archivo = sha256.hexdigest()
                except Exception as e:
                    hash_archivo = f"Error al leer: {e}"
        else:
            hash_archivo = "No aplicable (Fallido)"

        registrar_descarga(nombre_json, nombre_original, hash_archivo, url_origen, "Docker Firewall", estado_final)

    def on_btn_pausar_clicked(self, btn):
        item = self.selection_model.get_selected_item()
        if not item or item.gid.startswith("error_"): return

        if "Pausado" in item.estado:
            reanudar_descarga_aria2(item.gid)
            item.estado = "Descargando..."
            self.log(f"▶️ Reanudando: {item.nombre}")
        elif "Descargando" in item.estado or "Pendiente" in item.estado:
            pausar_descarga_aria2(item.gid)
            item.estado = "⏸ Pausado"
            item.velocidad = "0 KB/s"
            self.log(f"⏸ Pausando: {item.nombre}")
            
        self.filtro.changed(Gtk.FilterChange.DIFFERENT)

    def on_btn_cancelar_clicked(self, btn):
        item = self.selection_model.get_selected_item()
        if not item or item.gid.startswith("error_"): return

        if "Completado" not in item.estado and "Cancelado" not in item.estado:
            cancelar_descarga_aria2(item.gid)
            item.estado = "🗑️ Cancelado"
            item.progreso = "Cancelado"
            item.velocidad = "-"
            self.log(f"⏹ Descarga cancelada: {item.nombre}")
            self.filtro.changed(Gtk.FilterChange.DIFFERENT)

    def on_sidebar_selected(self, listbox, row):
        if row:
            self.filtro_actual_index = row.get_index()
            self.filtro.changed(Gtk.FilterChange.DIFFERENT)

    def logica_de_filtrado(self, item, user_data=None):
        if self.filtro_actual_index == 0:
            return True
        if self.filtro_actual_index == 1:
            return "Descargando" in item.estado or "Pendiente" in item.estado or "Pausado" in item.estado
        if self.filtro_actual_index == 2:
            return "Completado" in item.estado
        if self.filtro_actual_index == 3:
            return "Error" in item.estado or "Cancelado" in item.estado or "Rechazado" in item.estado
        return True

    def log(self, mensaje):
        self.log_buffer.insert(self.log_buffer.get_end_iter(), f"\n[*] {mensaje}")

    def crear_columna(self, titulo, atributo_obj):
        factory = Gtk.SignalListItemFactory()
        def on_setup(factory, item): item.set_child(Gtk.Label(xalign=0))
        def on_bind(factory, item): 
            lbl = item.get_child()
            obj = item.get_item()
            obj.bind_property(atributo_obj, lbl, "label", GObject.BindingFlags.SYNC_CREATE)
            
        factory.connect("setup", on_setup)
        factory.connect("bind", on_bind)
        columna = Gtk.ColumnViewColumn(title=titulo, factory=factory)
        self.tabla.append_column(columna)

    def tarea_background(self, url):
        try:
            url_real, nombre = resolver_url(url, None)
            nombre_a_mostrar = nombre if nombre else url
            GLib.idle_add(self.actualizar_ui_tras_busqueda, url_real, nombre_a_mostrar)
        except Exception as e:
            GLib.idle_add(self.log, f"Error: {e}")

    def actualizar_ui_tras_busqueda(self, url_real, nombre):
        if url_real:
            self.log(f"Enviando a aria2: {nombre}")
            respuesta = enviar_a_aria2(url_real, nombre, None)
            gid = respuesta.get('result', None) if respuesta else None
            
            if gid:
                nuevo = DescargaItem(gid, nombre, "Pendiente...", "0 MB", "0%", "0 KB/s", url_real, "Protegido por Docker")
                self.store.append(nuevo)
                self.filtro.changed(Gtk.FilterChange.DIFFERENT)
            else:
                self.log(f"❌ Aria2 rechazó el enlace: {nombre}")
                import random
                fake_gid = f"error_aria2_{random.randint(1000, 9999)}"
                nuevo_error = DescargaItem(fake_gid, nombre, "❌ Rechazado", "-", "Fallido", "-", url_real, "Protegido por Docker")
                self.store.append(nuevo_error)
                self.filtro.changed(Gtk.FilterChange.DIFFERENT)
        else:
            self.log(f"⚠️ No se pudo obtener enlace válido de: {nombre}")
            import random
            fake_gid = f"error_{random.randint(1000, 9999)}"
            nuevo_error = DescargaItem(fake_gid, nombre, "❌ Error (URL inválida)", "-", "Fallido", "-", "", "Protegido por Docker")
            self.store.append(nuevo_error)
            self.filtro.changed(Gtk.FilterChange.DIFFERENT)
            
        return False

    def monitorizar_descargas(self):
        try:
            lista_activos = obtener_estado_aria2()
            n_items = self.store.get_n_items()
            hubo_cambios_de_estado = False 

            for i in range(n_items):
                item_ui = self.store.get_item(i)
                
                if "Completado" in item_ui.estado or "Error" in item_ui.estado or "Cancelado" in item_ui.estado or "Rechazado" in item_ui.estado:
                    continue

                datos_aria = next((x for x in lista_activos if x['gid'] == item_ui.gid), None)
                antiguo_estado = item_ui.estado

                if datos_aria:
                    total = int(datos_aria.get('totalLength', 0))
                    completado = int(datos_aria.get('completedLength', 0))
                    velocidad = int(datos_aria.get('downloadSpeed', 0))
                    
                    if total > 0:
                        porcentaje = (completado / total) * 100
                        item_ui.progreso = f"{porcentaje:.1f}%"
                        item_ui.tamano = formatear_tamano(total)

                    item_ui.velocidad = f"{formatear_tamano(velocidad)}/s"
                    
                    if velocidad == 0 and completado == 0:
                        item_ui.estado = "Conectando..."
                    else:
                        item_ui.estado = "Descargando..."
                
                else:
                    info_final = obtener_info_gid(item_ui.gid)
                    if info_final:
                        estado_real = info_final.get('status', 'unknown')
                        error_code = info_final.get('errorCode', '0')
                        
                        if estado_real == 'complete':
                            if "Completado" not in item_ui.estado:
                                self.log(f"🎉 DESCARGA COMPLETADA: {item_ui.nombre}")
                                item_ui.progreso = "100%"
                                item_ui.estado = "✅ Completado"
                                item_ui.velocidad = "-"
                                total = int(info_final.get('totalLength', 0))
                                item_ui.tamano = formatear_tamano(total)
                            
                                threading.Thread(
                                    target=self.guardar_historial_background, 
                                    args=(item_ui.nombre, item_ui.url, "Completado")
                                ).start()
                                
                        elif estado_real == 'error':
                            if "Error" not in item_ui.estado:
                                self.log(f"⚠️ ERROR definitivo en {item_ui.nombre}. Código: {error_code}")
                                item_ui.estado = f"❌ Error ({error_code})"
                                item_ui.velocidad = "-"
                                item_ui.progreso = "Fallido"
                        
                                threading.Thread(
                                    target=self.guardar_historial_background, 
                                    args=(item_ui.nombre, item_ui.url, f"Error ({error_code})")
                                ).start()
                        
                        elif estado_real == 'removed':
                            item_ui.estado = "🗑️ Eliminado"
                
                if item_ui.estado != antiguo_estado:
                    hubo_cambios_de_estado = True

            if hubo_cambios_de_estado:
                self.filtro.changed(Gtk.FilterChange.DIFFERENT)

        except Exception as e:
            pass

        return True

    def on_btn_abrir_carpeta_clicked(self, btn):
        import subprocess
        import os
        
        ruta_descargas = os.path.abspath("./Descargas") 
        if not os.path.exists(ruta_descargas):
            os.makedirs(ruta_descargas)
            
        try:
            subprocess.Popen(["xdg-open", ruta_descargas])
            self.log("📁 Abriendo carpeta de descargas...")
        except Exception as e:
            self.log(f"⚠️ Error al abrir la carpeta: {e}")

class DescargaItem(GObject.Object):
    gid = GObject.Property(type=str)
    nombre = GObject.Property(type=str)
    estado = GObject.Property(type=str)
    tamano = GObject.Property(type=str)
    progreso = GObject.Property(type=str)
    velocidad = GObject.Property(type=str)
    url = GObject.Property(type=str) 
    proxy = GObject.Property(type=str)

    def __init__(self, gid, nombre, estado, tamano, progreso, velocidad, url, proxy):
        super().__init__()
        self.gid = gid
        self.nombre = nombre
        self.estado = estado
        self.tamano = tamano
        self.progreso = progreso
        self.velocidad = velocidad
        self.url = url 
        self.proxy = proxy

class MiGestorApp(Adw.Application):
    def __init__(self):
        super().__init__(application_id="com.mi.gestor.corporativo", flags=Gio.ApplicationFlags.FLAGS_NONE)
    def do_activate(self):
        win = VentanaPrincipal(self)
        win.present()

if __name__ == "__main__":
    app = MiGestorApp()
    app.run(sys.argv)