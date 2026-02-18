import sys
import threading
import gi

gi.require_version('Gtk', '4.0')
gi.require_version('Adw', '1') 
from gi.repository import Gtk, Adw, Gio, GLib, GObject

from extractor import resolver_url, enviar_a_aria2, obtener_estado_aria2, formatear_tamano, obtener_info_gid

class VentanaPrincipal(Adw.ApplicationWindow):
    def __init__(self, app):
        super().__init__(application=app, title="Gestor de Descargas GTK")
        self.set_default_size(1000, 650)
        
        # Variable para guardar qué estamos filtrando (0=Todas, 1=Descargando, etc.)
        self.filtro_actual_index = 0 

        # --- ESTRUCTURA DE LA VENTANA ---
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

        # 1. Sidebar (Izquierda)
        self.sidebar = Gtk.ListBox()
        self.sidebar.add_css_class("navigation-sidebar")
        
        # Conectamos el clic en el sidebar a nuestra función de filtrado
        self.sidebar.connect("row-selected", self.on_sidebar_selected) # <--- NUEVO

        for etiqueta in ["📥 Todas", "⏳ Descargando", "✅ Completadas", "❌ Errores"]:
            row = Gtk.ListBoxRow()
            lbl = Gtk.Label(label=etiqueta, xalign=0, margin_start=10, margin_top=10, margin_bottom=10)
            row.set_child(lbl)
            self.sidebar.append(row)
            
        # Seleccionamos la primera fila ("Todas") por defecto visualmente
        self.sidebar.select_row(self.sidebar.get_row_at_index(0))

        scroll_sidebar = Gtk.ScrolledWindow()
        scroll_sidebar.set_child(self.sidebar)
        scroll_sidebar.set_size_request(200, -1)
        self.paned_superior.set_start_child(scroll_sidebar)

        # 2. Zona Derecha
        caja_derecha = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=10)
        
        # Inputs
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

        # --- SISTEMA DE FILTRADO (LA MAGIA NUEVA) ---
        self.store = Gio.ListStore(item_type=DescargaItem)
        
        # 1. Creamos un filtro personalizado
        self.filtro = Gtk.CustomFilter.new(match_func=self.logica_de_filtrado)
        
        # 2. Creamos el modelo de filtrado que envuelve a nuestros datos (store)
        self.filter_model = Gtk.FilterListModel(model=self.store, filter=self.filtro)
        
        # 3. La selección ahora mira al modelo filtrado, no al store directo
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
        self.paned_superior.set_end_child(caja_derecha)
        self.paned_superior.set_position(300)

        # 3. Panel Log
        self.log_buffer = Gtk.TextBuffer()
        self.log_view = Gtk.TextView(buffer=self.log_buffer)
        self.log_view.set_editable(False)
        scroll_log = Gtk.ScrolledWindow()
        scroll_log.set_child(self.log_view)
        notebook = Gtk.Notebook()
        notebook.append_page(scroll_log, Gtk.Label(label="Registro"))
        self.paned_principal.set_end_child(notebook)

        self.log("Sistema iniciado.")
        GLib.timeout_add(1000, self.monitorizar_descargas)

    # --- LÓGICA DE FILTRADO ---
    def on_sidebar_selected(self, listbox, row):
        if row:
            # Guardamos qué botón se pulsó (0, 1, 2, 3)
            self.filtro_actual_index = row.get_index()
            # Avisamos al filtro que algo ha cambiado ("Change.DIFFERENT")
            self.filtro.changed(Gtk.FilterChange.DIFFERENT)

    def logica_de_filtrado(self, item, user_data=None):
        # Esta función se ejecuta para CADA fila de la tabla para decidir si se muestra
        
        # Caso 0: Todas
        if self.filtro_actual_index == 0:
            return True
        
        # Caso 1: Descargando
        if self.filtro_actual_index == 1:
            # Mostramos si pone "Descargando" o "Pendiente"
            return "Descargando" in item.estado or "Pendiente" in item.estado
        
        # Caso 2: Completadas
        if self.filtro_actual_index == 2:
            return "Completado" in item.estado
            
        # Caso 3: Errores
        if self.filtro_actual_index == 3:
            return "Error" in item.estado
            
        return True

    # --- RESTO DE MÉTODOS (IGUALES QUE ANTES) ---

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
        if url: 
            self.entrada_url.set_text("")
            threading.Thread(target=self.tarea_background, args=(url,)).start()

    def tarea_background(self, url):
        try:
            url_real, nombre = resolver_url(url)
            
            # Si nombre es None (falló), usamos la URL para que se vea en la tabla
            nombre_a_mostrar = nombre if nombre else url
            
            GLib.idle_add(self.actualizar_ui_tras_busqueda, url_real, nombre_a_mostrar)
        except Exception as e:
            GLib.idle_add(self.log, f"Error: {e}")

    def actualizar_ui_tras_busqueda(self, url_real, nombre):
        if url_real:
            # --- CASO ÉXITO: ENVIAMOS A ARIA2 ---
            self.log(f"Enviando a aria2: {nombre}")
            respuesta = enviar_a_aria2(url_real, nombre)
            gid = respuesta.get('result', None) if respuesta else None
            
            if gid:
                nuevo = DescargaItem(gid, nombre, "Pendiente...", "Calculando", "0%", "0 KB/s")
                self.store.append(nuevo)
                self.filtro.changed(Gtk.FilterChange.DIFFERENT)
        else:
            # --- CASO ERROR: NO SE PUDO RESOLVER ---
            self.log(f"⚠️ No se pudo obtener el video de: {nombre}")
            
            # Generamos un ID falso aleatorio para que la tabla no se queje
            import random
            fake_gid = f"error_{random.randint(1000, 9999)}"
            
            # Creamos la fila visualmente marcándola como Error
            # Fíjate que en estado ponemos "❌ Error" para que el filtro lo detecte
            nuevo_error = DescargaItem(fake_gid, nombre, "❌ Error (URL inválida)", "-", "Fallido", "-")
            
            self.store.append(nuevo_error)
            
            # Avisamos al filtro para que actualice la vista
            self.filtro.changed(Gtk.FilterChange.DIFFERENT)
            
        return False

    def monitorizar_descargas(self):
        try:
            lista_activos = obtener_estado_aria2()
            n_items = self.store.get_n_items()
            
            # --- NOTA IMPORTANTE PARA FILTROS ---
            # El bucle recorre self.store (TODOS los datos), no la tabla visible.
            # Así seguimos actualizando aunque la fila esté oculta por el filtro.
            
            hubo_cambios_de_estado = False # Flag para actualizar filtro

            for i in range(n_items):
                item_ui = self.store.get_item(i)
                
                if "Completado" in item_ui.estado or "Error" in item_ui.estado:
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
                
                # Si el estado cambió (ej: de Descargando -> Completado), 
                # avisamos para que el filtro oculte la fila si es necesario
                if item_ui.estado != antiguo_estado:
                    hubo_cambios_de_estado = True

            if hubo_cambios_de_estado:
                self.filtro.changed(Gtk.FilterChange.DIFFERENT)

        except Exception as e:
            print(f"ERROR BUCLE: {e}")

        return True

# --- CLASE DE DATOS ---
class DescargaItem(GObject.Object):
    gid = GObject.Property(type=str)
    nombre = GObject.Property(type=str)
    estado = GObject.Property(type=str)
    tamano = GObject.Property(type=str)
    progreso = GObject.Property(type=str)
    velocidad = GObject.Property(type=str)

    def __init__(self, gid, nombre, estado, tamano, progreso, velocidad):
        super().__init__()
        self.gid = gid
        self.nombre = nombre
        self.estado = estado
        self.tamano = tamano
        self.progreso = progreso
        self.velocidad = velocidad

class MiGestorApp(Adw.Application):
    def __init__(self):
        super().__init__(application_id="com.mi.gestor", flags=Gio.ApplicationFlags.FLAGS_NONE)
    def do_activate(self):
        win = VentanaPrincipal(self)
        win.present()

if __name__ == "__main__":
    app = MiGestorApp()
    app.run(sys.argv)