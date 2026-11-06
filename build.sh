#!/bin/bash

# sudo apt install pyside6-tools qt6-tools-dev-tools python3-pyside6.qtcore python3-pyside6.qtgui python3-pyside6.qtwidgets

# Script de build pour PySide6

chemin="$(cd "$(dirname "$0")"; pwd)"
cd "${chemin}"

### Mise à jour des fichiers .ts depuis les fichiers sources
pyside6-lupdate ui_MKVExtractorQt6.ui MKVExtractorQt6.py -ts Languages/MKVExtractorQt6_fr_FR.ts \
    Languages/MKVExtractorQt6_cs_CZ.ts \
    Languages/MKVExtractorQt6_de_DE.ts \
    Languages/MKVExtractorQt6_es_ES.ts \
    Languages/MKVExtractorQt6_en_US.ts \
    Languages/MKVExtractorQt6_it_IT.ts \
    Languages/MKVExtractorQt6_tr_TR.ts

pyside6-lupdate QFileDialogCustom/QFileDialogCustom.py -ts QFileDialogCustom/QFileDialogCustom_fr_FR.ts \
    QFileDialogCustom/QFileDialogCustom_cs_CZ.ts \
    QFileDialogCustom/QFileDialogCustom_de_DE.ts \
    QFileDialogCustom/QFileDialogCustom_en_US.ts \
    QFileDialogCustom/QFileDialogCustom_es_ES.ts \
    QFileDialogCustom/QFileDialogCustom_it_IT.ts \
    QFileDialogCustom/QFileDialogCustom_tr_TR.ts


### Compilation des fichiers .ts en .qm
if [[ -e "/usr/lib/x86_64-linux-gnu/qt6/bin/lrelease" ]]; then
    /usr/lib/x86_64-linux-gnu/qt6/bin/lrelease Languages/*.ts QFileDialogCustom/*.ts

elif [[ -e "/usr/lib/i386-linux-gnu/qt6/bin/lrelease" ]]; then
    /usr/lib/i386-linux-gnu/qt6/bin/lrelease Languages/*.ts QFileDialogCustom/*.ts

elif [[ $(which pyside6-lrelease) ]] ; then
    pyside6-lrelease Languages/*.ts QFileDialogCustom/*.ts

else
    echo "cannot find 'lrelease' for Qt6"
    exit 1
fi

### Génération du fichier .qrc (ressources)
echo '<RCC>
  <qresource prefix="/">' > MKVRessources.qrc

for icon in img/*
do
    echo "    <file>${icon}</file>" >> MKVRessources.qrc
done

echo "    <file>icons/mkv-extractor-qt6.webp</file>" >> MKVRessources.qrc
echo '  </qresource>
</RCC>' >> MKVRessources.qrc

### Compilation des ressources Qt
pyside6-rcc MKVRessources.qrc -o MKVRessources_rc.py

### Compilation de l'interface Qt Designer
pyside6-uic ui_MKVExtractorQt6.ui -o ui_MKVExtractorQt6.py

### Ajout des icônes par défaut si absents du thème
for icon in img/*
do
    nom=${icon##*/}
    nom=${nom%.*}
    sed -i "s@QtGui.QIcon.fromTheme(\"${nom}\")@QtGui.QIcon.fromTheme(\"${nom}\", QtGui.QIcon(\":/${icon}\"))@" ui_MKVExtractorQt6.py
done

