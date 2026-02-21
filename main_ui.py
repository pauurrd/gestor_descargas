import sys
import threading
import gi
import random

gi.require_version('Gtk', '4.0')
gi.require_version('Adw', '1') 
from gi.repository import Gtk, Adw, Gio, GLib, GObject

from extractor import (resolver_url, enviar_a_aria2, obtener_estado_aria2, 
                       formatear_tamano, obtener_info_gid, 
                       pausar_descarga_aria2, reanudar_descarga_aria2, cancelar_descarga_aria2)

class VentanaPrincipal(Adw.ApplicationWindow):
    def __init__(self, app):
        super().__init__(application=app, title="Gestor de Descargas GTK")
        self.set_default_size(1000, 650)
        
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
        self.paned_principal.set_position(250)

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
        self.entrada_url.set_placeholder_text("Pega aquí el enlace...")
        btn_descargar = Gtk.Button(label="Descargar")
        btn_descargar.add_css_class("suggested-action")
        btn_descargar.connect("clicked", self.on_btn_descargar_clicked)
        caja_input.append(self.entrada_url)
        caja_input.append(btn_descargar)
        caja_derecha.append(caja_input)

        expander = Gtk.Expander(label="⚙️ Opciones Avanzadas (Proxy)")
        expander.set_margin_start(10)
        expander.set_margin_end(10)
        
        caja_avanzada = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=10)
        caja_avanzada.set_margin_top(10)
        caja_avanzada.set_margin_bottom(10)
        
        lbl_proxy = Gtk.Label(label="Servidor Proxy:")
        self.entrada_proxy = Gtk.Entry()
        self.entrada_proxy.set_hexpand(True)
        self.entrada_proxy.set_placeholder_text("Ej: http://127.0.0.1:8080 (Dejar en blanco para desactivar)")
        
        caja_avanzada.append(lbl_proxy)
        caja_avanzada.append(self.entrada_proxy)
        expander.set_child(caja_avanzada)
        caja_derecha.append(expander)

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
        
        self.btn_reintentar.add_css_class("suggested-action")
        self.btn_cancelar.add_css_class("destructive-action")
        
        self.btn_reintentar.connect("clicked", self.on_btn_reintentar_clicked)
        self.btn_pausar.connect("clicked", self.on_btn_pausar_clicked)
        self.btn_cancelar.connect("clicked", self.on_btn_cancelar_clicked)
        
        caja_acciones.append(self.btn_reintentar)
        caja_acciones.append(self.btn_pausar)
        caja_acciones.append(self.btn_cancelar)
        caja_derecha.append(caja_acciones)

        self.paned_superior.set_end_child(caja_derecha)
        self.paned_superior.set_position(300)

        self.log_buffer = Gtk.TextBuffer()
        self.log_view = Gtk.TextView(buffer=self.log_buffer)
        self.log_view.set_editable(False)
        scroll_log = Gtk.ScrolledWindow()
        scroll_log.set_child(self.log_view)
        notebook = Gtk.Notebook()
        notebook.append_page(scroll_log, Gtk.Label(label="Registro"))
        self.paned_principal.set_end_child(notebook)

        self.log("Sistema iniciado y listo.")
        self.sidebar.select_row(self.sidebar.get_row_at_index(0))
        GLib.timeout_add(1000, self.monitorizar_descargas)


    def on_btn_reintentar_clicked(self, btn):
        item = self.selection_model.get_selected_item()
        if not item: return
        
        if "Cancelado" in item.estado or "Error" in item.estado or "Rechazado" in item.estado:
            if not item.url: 
                self.log(f"⚠️ No hay un enlace válido guardado para reintentar {item.nombre}.")
                return
                
            self.log(f"🔄 Reintentando descarga: {item.nombre}")
            
            respuesta = enviar_a_aria2(item.url, item.nombre, item.proxy)
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

    def on_btn_descargar_clicked(self, btn):
        url = self.entrada_url.get_text()
        proxy = self.entrada_proxy.get_text().strip()
        
        if url: 
            self.entrada_url.set_text("")
            threading.Thread(target=self.tarea_background, args=(url, proxy)).start()

    def tarea_background(self, url, proxy):
        try:
            url_real, nombre = resolver_url(url, proxy)
            nombre_a_mostrar = nombre if nombre else url
            GLib.idle_add(self.actualizar_ui_tras_busqueda, url_real, nombre_a_mostrar, proxy)
        except Exception as e:
            GLib.idle_add(self.log, f"Error: {e}")

    def actualizar_ui_tras_busqueda(self, url_real, nombre, proxy):
        if url_real:
            self.log(f"Enviando a aria2: {nombre}")
            respuesta = enviar_a_aria2(url_real, nombre, proxy)
            gid = respuesta.get('result', None) if respuesta else None
            
            if gid:
                nuevo = DescargaItem(gid, nombre, "Pendiente...", "0 MB", "0%", "0 KB/s", url_real, proxy)
                self.store.append(nuevo)
                self.filtro.changed(Gtk.FilterChange.DIFFERENT)
            else:
                self.log(f"❌ Aria2 rechazó el enlace (¿URL inválida?): {nombre}")
                import random
                fake_gid = f"error_aria2_{random.randint(1000, 9999)}"
                nuevo_error = DescargaItem(fake_gid, nombre, "❌ Rechazado por Aria2", "-", "Fallido", "-", url_real, proxy)
                self.store.append(nuevo_error)
                self.filtro.changed(Gtk.FilterChange.DIFFERENT)
        else:
            self.log(f"⚠️ No se pudo obtener el video de: {nombre}")
            import random
            fake_gid = f"error_{random.randint(1000, 9999)}"
            nuevo_error = DescargaItem(fake_gid, nombre, "❌ Error (URL inválida)", "-", "Fallido", "-", "", proxy)
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
                
                if "Completado" in item_ui.estado or "Error" in item_ui.estado or "Cancelado" in item_ui.estado or "Pausado" in item_ui.estado or "Rechazado" in item_ui.estado:
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
                    item_ui.estado = "Descargando..."
                
                else:
                    info_final = obtener_info_gid(item_ui.gid)
                    if info_final:
                        estado_real = info_final.get('status', 'unknown')
                        error_code = info_final.get('errorCode', '0')
                        
                        if estado_real == 'complete':
                            if "Completado" not in item_ui.estado:
                                self.log(f"🎉 INSTALACIÓN COMPLETADA: {item_ui.nombre}")
                                item_ui.progreso = "100%"
                                item_ui.estado = "✅ Completado"
                                item_ui.velocidad = "-"
                                total = int(info_final.get('totalLength', 0))
                                item_ui.tamano = formatear_tamano(total)
                            
                        elif estado_real == 'error':
                            if "Error" not in item_ui.estado:
                                self.log(f"⚠️ ERROR en {item_ui.nombre}. Código: {error_code}")
                                item_ui.estado = f"❌ Error ({error_code})"
                                item_ui.velocidad = "-"
                                item_ui.progreso = "Fallido"
                        
                        elif estado_real == 'removed':
                            item_ui.estado = "🗑️ Eliminado"
                
                if item_ui.estado != antiguo_estado:
                    hubo_cambios_de_estado = True

            if hubo_cambios_de_estado:
                self.filtro.changed(Gtk.FilterChange.DIFFERENT)

        except Exception as e:
            pass

        return True

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
        super().__init__(application_id="com.mi.gestor", flags=Gio.ApplicationFlags.FLAGS_NONE)
    def do_activate(self):
        win = VentanaPrincipal(self)
        win.present()

if __name__ == "__main__":
    app = MiGestorApp()
    app.run(sys.argv)