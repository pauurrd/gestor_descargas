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
        
        caja_main = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        header = Adw.HeaderBar()
        caja_main.append(header)
        
        self.paned_principal = Gtk.Paned(orientation=Gtk.Orientation.VERTICAL)
        self.paned_principal.set_vexpand(True)
        caja_main.append(self.paned_principal)
        self.set_content(caja_main)

        self.paned_superior = Gtk.Paned(orientation=Gtk.Orientation.HORIZONTAL)
        self.paned_principal.set_start_child(self.paned_superior)
        self.paned_principal.set_position(250) # Ajustado un poco el sidebar

        # 1. Sidebar
        self.sidebar = Gtk.ListBox()
        self.sidebar.add_css_class("navigation-sidebar")
        for etiqueta in ["📥 Todas", "⏳ Descargando", "✅ Completadas", "❌ Errores"]:
            row = Gtk.ListBoxRow()
            lbl = Gtk.Label(label=etiqueta, xalign=0, margin_start=10, margin_top=10, margin_bottom=10)
            row.set_child(lbl)
            self.sidebar.append(row)
        scroll_sidebar = Gtk.ScrolledWindow()
        scroll_sidebar.set_child(self.sidebar)
        scroll_sidebar.set_size_request(200, -1)
        self.paned_superior.set_start_child(scroll_sidebar)

        # 2. Zona Derecha
        caja_derecha = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=10)
        
        caja_input = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=10)
        caja_input.set_margin_top(10)
        caja_input.set_margin_start(10)
        caja_input.set_margin_end(10)
        self.entrada_url = Gtk.Entry()
        self.entrada_url.set_hexpand(True)
        btn_descargar = Gtk.Button(label="Descargar")
        btn_descargar.add_css_class("suggested-action")
        btn_descargar.connect("clicked", self.on_btn_descargar_clicked)
        caja_input.append(self.entrada_url)
        caja_input.append(btn_descargar)
        caja_derecha.append(caja_input)

        # --- TABLA Y COLUMNAS ---
        self.store = Gio.ListStore(item_type=DescargaItem)
        self.selection_model = Gtk.SingleSelection(model=self.store)
        self.tabla = Gtk.ColumnView(model=self.selection_model)
        
        self.crear_columna("Nombre", "nombre")
        self.crear_columna("Estado", "estado")       # <--- CORREGIDO: Faltaba esta columna visual
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
            GLib.idle_add(self.actualizar_ui_tras_busqueda, url_real, nombre)
        except Exception as e:
            GLib.idle_add(self.log, f"Error: {e}")

    def actualizar_ui_tras_busqueda(self, url_real, nombre):
        if url_real:
            self.log(f"Enviando a aria2: {nombre}")
            respuesta = enviar_a_aria2(url_real, nombre)
            gid = respuesta.get('result', None) if respuesta else None
            
            if gid:
                # CORREGIDO: Añadimos el estado "Pendiente" al crear el objeto
                nuevo = DescargaItem(gid, nombre, "Pendiente...", "0 MB", "0%", "0 KB/s")
                self.store.append(nuevo)
        else:
            self.log("No se pudo resolver la URL.")
        return False

    def monitorizar_descargas(self):
        try:
            lista_activos = obtener_estado_aria2()
            n_items = self.store.get_n_items()
            
            for i in range(n_items):
                item_ui = self.store.get_item(i)
                
                # Ahora sí funcionará porque 'estado' existe
                if item_ui.progreso == "100%" or "Error" in item_ui.estado:
                    continue

                datos_aria = next((x for x in lista_activos if x['gid'] == item_ui.gid), None)
                
                if datos_aria:
                    total = int(datos_aria.get('totalLength', 0))
                    completado = int(datos_aria.get('completedLength', 0))
                    velocidad = int(datos_aria.get('downloadSpeed', 0))
                    
                    if total > 0:
                        porcentaje = (completado / total) * 100
                        item_ui.progreso = f"{porcentaje:.1f}%"
                    
                    item_ui.tamano = formatear_tamano(total)
                    item_ui.velocidad = f"{formatear_tamano(velocidad)}/s"
                    item_ui.estado = "Descargando..." # Ahora sí funcionará
                
                else:
                    info_final = obtener_info_gid(item_ui.gid)
                    if info_final:
                        estado_real = info_final.get('status', 'unknown')
                        error_code = info_final.get('errorCode', '0')
                        
                        if estado_real == 'complete':
                            item_ui.progreso = "100%"
                            item_ui.estado = "✅ Completado"
                            item_ui.velocidad = "-"
                            total = int(info_final.get('totalLength', 0))
                            item_ui.tamano = formatear_tamano(total)
                            
                        elif estado_real == 'error':
                            item_ui.estado = f"❌ Error ({error_code})"
                            item_ui.velocidad = "-"
                            item_ui.progreso = "Fallido"
                        
                        elif estado_real == 'removed':
                            item_ui.estado = "🗑️ Eliminado"
                        
                        elif estado_real == 'paused':
                            item_ui.estado = "⏸ Pausado"

        except Exception as e:
            print(f"🔥 ERROR CRÍTICO EN EL BUCLE: {e}")
            import traceback
            traceback.print_exc()

        return True

# --- CLASE DE DATOS CORREGIDA ---
class DescargaItem(GObject.Object):
    gid = GObject.Property(type=str)
    nombre = GObject.Property(type=str)
    estado = GObject.Property(type=str) # <--- CORREGIDO: AÑADIDA PROPIEDAD
    tamano = GObject.Property(type=str)
    progreso = GObject.Property(type=str)
    velocidad = GObject.Property(type=str)

    # <--- CORREGIDO: AÑADIDO 'estado' AL INIT
    def __init__(self, gid, nombre, estado, tamano, progreso, velocidad):
        super().__init__()
        self.gid = gid
        self.nombre = nombre
        self.estado = estado # <--- CORREGIDO
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