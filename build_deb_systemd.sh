#!/bin/bash
# =============================================================================
# build_deb_systemd.sh
# Genera gestor-descargas_1.0.0_amd64.deb
# Uso: ./build_deb_systemd.sh
# =============================================================================
set -e

APP_NAME="gestor-descargas"
VERSION="1.0.0"
ARCH="amd64"
PKG_DIR="$(pwd)/dist/${APP_NAME}_${VERSION}_${ARCH}_systemd"
SRC_DIR="$(pwd)"

echo "==> Limpiando build anterior..."
rm -rf "$PKG_DIR"

echo "==> Creando estructura de directorios..."
mkdir -p "$PKG_DIR/DEBIAN"
mkdir -p "$PKG_DIR/usr/share/$APP_NAME"
mkdir -p "$PKG_DIR/usr/bin"
mkdir -p "$PKG_DIR/lib/systemd/system"
mkdir -p "$PKG_DIR/usr/share/applications"

echo "==> Copiando archivos de la aplicación..."
cp "$SRC_DIR/main_ui.py"    "$PKG_DIR/usr/share/$APP_NAME/"
cp "$SRC_DIR/extractor.py"  "$PKG_DIR/usr/share/$APP_NAME/"
cp "$SRC_DIR/database.py"   "$PKG_DIR/usr/share/$APP_NAME/"

echo "==> Copiando archivos de empaquetado..."
cp "$SRC_DIR/packaging/DEBIAN/control"  "$PKG_DIR/DEBIAN/control"
cp "$SRC_DIR/packaging/DEBIAN/postinst" "$PKG_DIR/DEBIAN/postinst"
cp "$SRC_DIR/packaging/DEBIAN/prerm"    "$PKG_DIR/DEBIAN/prerm"
cp "$SRC_DIR/packaging/lib/systemd/system/aria2-rpc.service" \
   "$PKG_DIR/lib/systemd/system/aria2-rpc.service"
cp "$SRC_DIR/packaging/usr/bin/gestor-descargas" \
   "$PKG_DIR/usr/bin/gestor-descargas"
cp "$SRC_DIR/packaging/usr/share/applications/gestor-descargas.desktop" \
   "$PKG_DIR/usr/share/applications/gestor-descargas.desktop"

echo "==> Ajustando permisos..."
chmod 755 "$PKG_DIR/DEBIAN/postinst"
chmod 755 "$PKG_DIR/DEBIAN/prerm"
chmod 755 "$PKG_DIR/usr/bin/gestor-descargas"
chmod 755 "$PKG_DIR/usr/share/$APP_NAME"
chmod 644 "$PKG_DIR/usr/share/$APP_NAME/main_ui.py"
chmod 644 "$PKG_DIR/usr/share/$APP_NAME/extractor.py"
chmod 644 "$PKG_DIR/usr/share/$APP_NAME/database.py"

echo "==> Construyendo el paquete .deb..."
dpkg-deb --build --root-owner-group "$PKG_DIR"

OUTPUT_DEB="dist/${APP_NAME}_${VERSION}_${ARCH}_systemd.deb"
# mv "${PKG_DIR}.deb" "$OUTPUT_DEB"

echo ""
echo "✅ Paquete generado: $OUTPUT_DEB"
echo ""
echo "Para instalar en la máquina del cliente:"
echo "  sudo dpkg -i $OUTPUT_DEB"
echo "  sudo apt-get install -f   # resuelve dependencias si falta alguna"
