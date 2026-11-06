#!/bin/bash
#
# Génération des AppImage de MKV Extractor Qt6.
#
# Deux variantes sont produites :
#   - LÉGÈRE : ${APPNAME}-v${VERSION}-x86_64.AppImage
#       ~1 Mo, n'embarque que le code. Nécessite python3-pyside6 sur le système
#       cible (l'AppRun le vérifie au lancement).
#   - FULL   : ${APPNAME}-v${VERSION}-full-x86_64.AppImage
#       ~100 Mo, autonome : Python 3 et PySide6/Qt6 sont embarqués via PyInstaller.
#       Ne nécessite aucune installation Python côté utilisateur.
#
# Dans les deux cas, les outils externes appelés par le logiciel (mkvtoolnix,
# ffmpeg, etc.) restent à installer côté système.
#
# Usage :
#   ./appBuilder.sh           # construit les deux variantes (défaut)
#   ./appBuilder.sh light     # construit uniquement la variante légère
#   ./appBuilder.sh full      # construit uniquement la variante full

set -uo pipefail

### Emplacement du script (= dossier du projet)
chemin="$(cd "$(dirname "$0")"; pwd)"
cd "${chemin}"

### Variables communes
APPNAME="MKVExtractorQt6"
OUTPUT="${chemin}"
APPIMAGETOOL="${HOME}/.local/bin/appimagetool"

# ===========================================================================
# Variante LÉGÈRE : code seul, s'appuie sur le PySide6 du système cible
# ===========================================================================
build_appimage_light() {
    local APPDIR="/tmp/${APPNAME}-light.AppDir"
    local APPIMAGE="${OUTPUT}/${APPNAME}-v${VERSION}-x86_64.AppImage"

    echo "==> Construction de la variante LÉGÈRE"

    rm -rf "${APPDIR}"
    mkdir -p "${APPDIR}/usr/share/mkv-extractor-qt6"
    mkdir -p "${APPDIR}/usr/share/icons/hicolor/256x256/apps"

    # Copie des fichiers de l'application
    cp ./*.py "${APPDIR}/usr/share/mkv-extractor-qt6/"
    cp -r Languages QFileDialogCustom icons img WhatsUp "${APPDIR}/usr/share/mkv-extractor-qt6/"

    # Icône
    cp icons/mkv-extractor-qt6.png "${APPDIR}/mkv-extractor-qt6.png"
    cp icons/mkv-extractor-qt6.png "${APPDIR}/usr/share/icons/hicolor/256x256/apps/mkv-extractor-qt6.png"

    # Fichier desktop (Icon sans chemin absolu, requis par AppImage)
    sed 's|^Icon=.*|Icon=mkv-extractor-qt6|' mkv-extractor-qt6.desktop > "${APPDIR}/mkv-extractor-qt6.desktop"

    # Script AppRun : utilise le python3 + PySide6 du système
    cat > "${APPDIR}/AppRun" << 'APPRUN'
#!/bin/bash
APPDIR="$(dirname "$(readlink -f "$0")")"
APPDATA="$APPDIR/usr/share/mkv-extractor-qt6"

check_dep() {
    python3 -c "import $1" 2>/dev/null || {
        echo "Erreur : le module Python '$1' n'est pas installé."
        echo "  Sur Ubuntu/Debian : sudo apt install python3-pyside6.qtcore python3-pyside6.qtgui python3-pyside6.qtwidgets"
        exit 1
    }
}

check_dep PySide6

if ! command -v mkvextract &>/dev/null; then
    echo "Avertissement : mkvtoolnix n'est pas installé. Installez-le avec : sudo apt install mkvtoolnix"
fi

exec python3 "$APPDATA/MKVExtractorQt6.py" "$@"
APPRUN
    chmod +x "${APPDIR}/AppRun"

    rm -f "${APPIMAGE}"
    ARCH=x86_64 APPIMAGE_EXTRACT_AND_RUN=1 "${APPIMAGETOOL}" "${APPDIR}" "${APPIMAGE}"

    if [[ -f "${APPIMAGE}" ]]; then
        echo "==> Variante LÉGÈRE générée : ${APPIMAGE} ($(du -sh "${APPIMAGE}" | cut -f1))"
    else
        echo "Échec de la génération de la variante légère" >&2
        return 1
    fi
}

# ===========================================================================
# Variante FULL : autonome (Python + PySide6/Qt6 embarqués via PyInstaller)
# ===========================================================================
build_appimage_full() {
    local APPDIR="/tmp/${APPNAME}-full.AppDir"
    local APPIMAGE="${OUTPUT}/${APPNAME}-v${VERSION}-full-x86_64.AppImage"
    local BUILDDIR="/tmp/${APPNAME}.build"             # travail PyInstaller
    local VENV="${HOME}/.cache/${APPNAME}-build-venv"  # venv de build (réutilisé)

    echo "==> Construction de la variante FULL (autonome)"

    # --- Environnement PyInstaller (PySide6 vu du système) ---------------
    if [[ ! -d "${VENV}" ]]; then
        # --system-site-packages : le venv voit le PySide6 installé via apt.
        python3 -m venv --system-site-packages "${VENV}"
    fi
    # shellcheck disable=SC1091
    source "${VENV}/bin/activate"
    python -m pip install --quiet --upgrade pip pyinstaller

    if ! python -c "import PySide6" 2>/dev/null; then
        echo "ERREUR : PySide6 introuvable dans le venv. Installez 'python3-pyside6'." >&2
        deactivate || true
        return 1
    fi

    # --- Empaquetage PyInstaller (mode onedir) --------------------------
    rm -rf "${BUILDDIR}"
    mkdir -p "${BUILDDIR}"

    # Modules Qt volumineux NON utilisés (seuls QtCore/QtGui/QtWidgets servent).
    local EXCLUDES=(
        PySide6.QtWebEngineCore PySide6.QtWebEngineWidgets PySide6.QtWebEngineQuick
        PySide6.QtWebChannel PySide6.QtWebSockets PySide6.QtWebView
        PySide6.QtQuick PySide6.QtQuick3D PySide6.QtQuickWidgets PySide6.QtQml
        PySide6.Qt3DCore PySide6.Qt3DRender PySide6.Qt3DInput PySide6.Qt3DLogic
        PySide6.Qt3DAnimation PySide6.Qt3DExtras
        PySide6.QtCharts PySide6.QtDataVisualization PySide6.QtGraphs
        PySide6.QtMultimedia PySide6.QtMultimediaWidgets PySide6.QtSpatialAudio
        PySide6.QtPdf PySide6.QtPdfWidgets PySide6.QtDesigner
        PySide6.QtLocation PySide6.QtPositioning PySide6.QtSensors
        PySide6.QtSerialPort PySide6.QtSerialBus PySide6.QtBluetooth PySide6.QtNfc
        PySide6.QtRemoteObjects PySide6.QtScxml PySide6.QtTest
    )
    local EXCLUDE_ARGS=()
    local m
    for m in "${EXCLUDES[@]}"; do
        EXCLUDE_ARGS+=(--exclude-module "${m}")
    done

    pyinstaller \
        --noconfirm \
        --clean \
        --name "${APPNAME}" \
        --distpath "${BUILDDIR}/dist" \
        --workpath "${BUILDDIR}/work" \
        --specpath "${BUILDDIR}" \
        --add-data "${chemin}/Languages:Languages" \
        --add-data "${chemin}/QFileDialogCustom:QFileDialogCustom" \
        "${EXCLUDE_ARGS[@]}" \
        "${chemin}/${APPNAME}.py"
    local PYI_RC=$?

    deactivate || true

    local DIST="${BUILDDIR}/dist/${APPNAME}"
    if [[ ${PYI_RC} -ne 0 || ! -x "${DIST}/${APPNAME}" ]]; then
        echo "ERREUR : échec de PyInstaller (exécutable ${DIST}/${APPNAME} absent)." >&2
        return 1
    fi

    # --- Assemblage de l'AppDir -----------------------------------------
    rm -rf "${APPDIR}"
    mkdir -p "${APPDIR}/usr/bin"
    mkdir -p "${APPDIR}/usr/share/icons/hicolor/256x256/apps"

    # Application empaquetée (exécutable + _internal/ : Python, Qt6, données)
    cp -r "${DIST}/." "${APPDIR}/usr/bin/"

    # Icône
    cp icons/mkv-extractor-qt6.png "${APPDIR}/mkv-extractor-qt6.png"
    cp icons/mkv-extractor-qt6.png "${APPDIR}/usr/share/icons/hicolor/256x256/apps/mkv-extractor-qt6.png"

    # Fichier desktop
    sed 's|^Icon=.*|Icon=mkv-extractor-qt6|' mkv-extractor-qt6.desktop > "${APPDIR}/mkv-extractor-qt6.desktop"

    # Script AppRun : lance directement l'exécutable autonome
    cat > "${APPDIR}/AppRun" << 'APPRUN'
#!/bin/bash
APPDIR="$(dirname "$(readlink -f "$0")")"

if ! command -v mkvextract &>/dev/null; then
    echo "Avertissement : mkvtoolnix n'est pas installé. Installez-le avec : sudo apt install mkvtoolnix"
fi

exec "$APPDIR/usr/bin/MKVExtractorQt6" "$@"
APPRUN
    chmod +x "${APPDIR}/AppRun"

    rm -f "${APPIMAGE}"
    ARCH=x86_64 APPIMAGE_EXTRACT_AND_RUN=1 "${APPIMAGETOOL}" "${APPDIR}" "${APPIMAGE}"

    if [[ -f "${APPIMAGE}" ]]; then
        echo "==> Variante FULL générée : ${APPIMAGE} ($(du -sh "${APPIMAGE}" | cut -f1))"
    else
        echo "Échec de la génération de la variante full" >&2
        return 1
    fi
}

# ===========================================================================
# Programme principal
# ===========================================================================
MODE="${1:-all}"   # all | light | full

case "${MODE}" in
    all|light|full) ;;
    *) echo "Usage : $0 [all|light|full]" >&2; exit 1 ;;
esac

### Étape commune 1 : génération des fichiers Qt dérivés (ui_*.py, ressources,
### traductions .qm). Indispensable pour les DEUX variantes, sinon l'AppImage
### embarque une application incomplète et non fonctionnelle.
echo "==> Génération des fichiers Qt (build.sh)"
bash "${chemin}/build.sh" || { echo "Échec de build.sh — génération annulée" >&2; exit 1; }

for f in "ui_${APPNAME}.py" "MKVRessources_rc.py"; do
    if [[ ! -f "${chemin}/${f}" ]]; then
        echo "ERREUR : ${f} manquant après build.sh." >&2
        exit 1
    fi
done

### Étape commune 2 : version + appimagetool
VERSION=$(grep -oP 'setApplicationVersion\("\K[^"]+' MKVExtractorQt6.py)
echo "==> MKV Extractor Qt6 v${VERSION}"

if [[ ! -x "${APPIMAGETOOL}" ]]; then
    echo "==> Téléchargement de appimagetool..."
    mkdir -p "${HOME}/.local/bin"
    curl -L -o "${APPIMAGETOOL}" \
        "https://github.com/AppImage/AppImageKit/releases/download/continuous/appimagetool-x86_64.AppImage"
    chmod +x "${APPIMAGETOOL}"
fi

### Étape commune 3 : construction des variantes demandées
RC=0
case "${MODE}" in
    light) build_appimage_light || RC=1 ;;
    full)  build_appimage_full  || RC=1 ;;
    all)
        build_appimage_light || RC=1
        build_appimage_full  || RC=1
        ;;
esac

exit "${RC}"
