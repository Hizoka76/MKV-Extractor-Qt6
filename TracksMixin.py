#!/usr/bin/python3
# -*- coding: utf-8 -*-
"""Mixin de gestion des pistes MKV (ComboModif, TracksLoad, TrackView, TrackModif, TrackSelectAll)."""

import json
from functools import partial
import state
from CodecListFile import CodecList
from PySide6.QtWidgets import QComboBox, QPushButton, QTableWidgetItem
from PySide6.QtCore import QFile, QFileInfo, QMimeDatabase, QMimeType, QStorageInfo, Qt, QUrl
from PySide6.QtGui import QDesktopServices, QIcon


class TracksMixin:
    # ========================================================================
    def ComboModif(self, x, index):
        """Fonction mettant à jour les dictionnaires des pistes du fichier MKV lors de l'utilisation des combobox du tableau."""

        # Récupérer le texte de la combo à partir de l'index
        value = self.ComboBoxes[x].itemText(index)

        ### Si x est une chaîne, c'est que ça traite un fichier AAC
        if isinstance(x, str):
            ## Récupération de la ligne
            x = int(x.split("-")[0])

            ## Mise à jour de variables
            if value != state.MKVDico[x][6]:
                state.MKVDico[x][6] = value
                if self.ui.mkv_tracks.item(x, 1).checkState() == Qt.Checked:
                    state.MKVDicoSelect[x][6] = value

        ### Pour les autres combobox
        elif value != state.MKVDico[x][5]:
            ## Mise à jour de variables
            state.MKVDico[x][5] = value
            if self.ui.mkv_tracks.item(x, 1).checkState() == Qt.Checked:
                state.MKVDicoSelect[x][5] = value

    # ========================================================================
    def TracksLoad(self):
        """Fonction de listage et d'affichage des pistes contenues dans le fichier MKV."""
        ### Curseur de chargement
        self.setCursor(Qt.WaitCursor)

        ### Mise à jour des variables
        state.TempValues.setValue("MKVLoaded", True)  # Fichier MKV chargé
        state.TempValues.setValue("AllTracks", False)  # Mode sélection all
        state.TempValues.setValue(
            "SuperBlockTemp", True
        )  # Sert à bloquer les signaux du tableau (impossible d'utiliser blocksignals)
        x = 0  # Sert à indiquer les numéros de lignes
        self.ComboBoxes = {}  # Dictionnaire listant les combobox
        state.MKVDico.clear()  # Mise au propre du dictionnaire

        ### Désactivation des différentes options qui pourraient être activés
        self.ui.mkv_execute.setEnabled(False)

        # Décoche et désactive les boutons
        for widget in [
            self.ui.option_reencapsulate,
            self.ui.option_subtitles,
            self.ui.option_audio,
        ]:
            widget.setChecked(False)
            widget.setEnabled(False)

        # Décoche les sous actions des boutons
        for widget in [
            state.Sup2Sub[1],
            state.Sup2Sub[2],
            state.Sup2Sub[3],
            state.Sub2Srt[1],
            state.Sub2Srt[2],
            self.option_ffmpeg,
            self.option_to_ac3,
            self.option_stereo,
            self.option_subtitles_open,
        ]:
            widget.setChecked(False)

        # Réinitialise les valeurs des conversions audio
        for nb in [128, 192, 224, 256, 320, 384, 448, 512, 576, 640]:
            state.QualityList[nb].setChecked(False)

        for nb in [2, 3, 4, 5]:
            state.PowerList[nb].setChecked(False)

        ### Activation des widgets qui attendaient un fichier MKV valide
        self.mkv_view.setEnabled(True)

        # Activation des actions si disponibles et cache les infos bulles d'aide
        for Location, Widget in (
            ("MKClean", self.mk_clean),
            ("MKVInfo", self.mkv_info),
            ("MKVToolNix", self.mkv_mkvtoolnix),
            ("MKValidator", self.mk_validator),
        ):

            if state.SoftExec[Location]:
                Widget.setEnabled(True)

        ### Affichage et nettoyage du tableau des pistes
        if self.ui.stackedMiddle.currentIndex() != 0:
            self.ui.stackedMiddle.setCurrentIndex(0)

        while self.ui.mkv_tracks.rowCount() != 0:
            self.ui.mkv_tracks.removeRow(0)

        ### Retours d'information
        self.SetInfo(self.Trad["WorkMerge"], "800080", True, True)

        ### Récupération du retour de MKVMerge
        # Vérification de la présence de mkvmerge
        if not state.SoftExec["MKVMerge"]:
            return

        JsonMKV = ""

        # Exécution de la commande
        for line in self.LittleProcess(
            state.Configs.value("Location/MKVMerge"), ["-J", state.Configs.value("InputFile")]
        ):
            JsonMKV += line

        # Conversion du json en un dictionnaire
        JsonMKV = json.loads(JsonMKV)

        ### Vérification des erreurs
        if JsonMKV["warnings"]:
            self.SetInfo(self.Trad["MKVMergeWarning"], "800080", True, True)
            self.SetInfo("\n".join(JsonMKV["warnings"]))

        if JsonMKV["errors"]:
            self.SetInfo(self.Trad["MKVMergeErrors"], "800080", True, True)
            self.SetInfo("\n".join(JsonMKV["errors"]))

            self.setCursor(Qt.ArrowCursor)
            return

        ### Blocage des signaux pour ne pas appeler TrackModif pour chaque ligne ajoutée
        self.ui.mkv_tracks.blockSignals(True)

        ### Traitement des données de Json
        # Titre du fichier MKV
        if "title" in JsonMKV["container"]["properties"]:
            # Si le titre existe
            state.TempValues.setValue(
                "TitleFile", JsonMKV["container"]["properties"]["title"]
            )

        else:
            # Sinon on utilise le nom du fichier
            state.TempValues.setValue(
                "TitleFile", QFileInfo(state.Configs.value("InputFile")).completeBaseName()
            )

        # Envoie de la valeur titre
        self.ui.mkv_title.setText(state.TempValues.value("TitleFile"))

        # Récupération de la durée du fichier MKV
        if "duration" in JsonMKV["container"]["properties"]:
            # Passage de nanosecondes à secondes 10 puissance 9 => il se plante d'un 0 ?!...
            state.TempValues.setValue(
                "DurationFile",
                int(JsonMKV["container"]["properties"]["duration"] / 10e8),
            )

        ### Boucle traitant les pistes du fichier MKV
        # Renvoie un truc du genre : 0 {"codec": "RealVideo", "id": 0, "properties": {... }}...
        for Track in JsonMKV["tracks"]:
            ID = Track["id"]  # Récupération de l'ID de la piste

            ## Récupération du codec de la piste
            if "codec_id" in Track["properties"]:
                codec = Track["properties"]["codec_id"]

                if codec in CodecList:
                    codecInfo = CodecList[codec][1]
                    codec = CodecList[codec][0]

                elif "codec" in Track:
                    codecInfo = codec
                    codec = Track["codec"]

                else:
                    codecInfo = ""
                    # [Claude] BUG : La variable était nommée 'code' au lieu de 'codec'.
                    # 'code' n'est pas défini ailleurs dans ce scope, ce qui aurait provoqué
                    # une NameError. L'intention évidente est d'assigner codec à lui-même
                    # (conservation de la valeur existante), ce qui est ici rendu explicite.
                    codec = codec  # conservation de la valeur existante

            elif "codec" in Track:
                codecInfo = ""
                codec = Track["codec"]

            else:
                codecInfo = ""
                codec = "Unknow"

            ## Traitement des videos
            if Track["type"] == "video":
                # Mise à jour des variables
                TrackTypeName = self.Trad["Video"]
                icone = "video-x-generic"

                # Récupération de l'info1
                if "track_name" in Track["properties"]:
                    info1 = Track["properties"]["track_name"]

                elif "display_dimensions" in Track["properties"]:
                    info1 = Track["properties"]["display_dimensions"]

                elif "pixel_dimensions" in Track["properties"]:
                    info1 = Track["properties"]["pixel_dimensions"]

                else:
                    info1 = ""

                # Liste normale des fps
                ComboItems = [
                    "23.976fps",
                    "25.000fps",
                    "30.000fps",
                    "48.000fps",
                    "50.000fps",
                    "60.000fps",
                ]

                # Récupération du fps de la piste
                if "default_duration" in Track["properties"]:
                    infoTemp = Track["properties"]["default_duration"]

                    FPSDico = {
                        40000000: "25.000fps",
                        40001000: "25.000fps",
                        41708000: "23.976fps",
                        41708333: "23.976fps",
                        33333000: "30.000fps",
                        20833333: "48.000fps",
                        20000000: "50.000fps",
                        16666666: "60.000fps",
                    }

                    if infoTemp in FPSDico:
                        info2 = FPSDico[infoTemp]

                    else:
                        cal = "%.3f" % float(1000000000 / infoTemp)
                        info2 = "{}fps".format(cal)
                        ComboItems.append(info2)  # Ajout de la valeur inconnue
                        ComboItems.sort()

                # Cas spécifique où l'info est manquante
                else:
                    info2 = ""

                # Texte à afficher
                Text = self.Trad["TrackVideo"]

            ## Traitement des audios et sous-titres
            elif Track["type"] in ["audio", "subtitles"]:
                # Variables spécifiques à l'audio
                if Track["type"] == "audio":
                    TrackTypeName = self.Trad["Audio"]
                    icone = "audio-x-generic"

                    # Récupération de l'info1
                    if "track_name" in Track["properties"]:
                        info1 = Track["properties"]["track_name"]

                    elif "audio_sampling_frequency" in Track["properties"]:
                        info1 = str(Track["properties"]["audio_sampling_frequency"])

                    else:
                        info1 = ""

                # Variables spécifiques aux sous titres
                else:
                    # Mise à jour des variables
                    TrackTypeName = self.Trad["Subtitles"]
                    icone = "text-x-generic"

                    # Récupération de l'info1
                    if "track_name" in Track["properties"]:
                        info1 = Track["properties"]["track_name"]

                    else:
                        info1 = ""

                # Variables communes
                # Récupération de la langue
                if "language" in Track["properties"]:
                    info2 = Track["properties"]["language"]

                else:
                    info2 = "und"

                # Item servant à remplir la combobox
                ComboItems = state.MKVLanguages

                # Texte à afficher
                Text = self.Trad["TrackAudio"]

            ## Création, remplissage d'une combobox qui est envoyée dans une nouvelle ligne du tableau
            self.ui.mkv_tracks.insertRow(x)
            self.ComboBoxes[x] = QComboBox()
            self.ui.mkv_tracks.setCellWidget(x, 4, self.ComboBoxes[x])
            self.ComboBoxes[x].addItems(ComboItems)
            self.ComboBoxes[x].setStatusTip(Text)

            ## Ajout de la piste au dico
            state.MKVDico[x] = [ID, "Track", icone, "unknown", info1, info2, codec]

            ## Envoie des informations dans le tableaux
            self.ui.mkv_tracks.setItem(x, 0, QTableWidgetItem(ID))  # Envoie de l'ID
            self.ui.mkv_tracks.setItem(
                x, 1, QTableWidgetItem("")
            )  # Texte bidon permettant d'envoyer la checkbox
            self.ui.mkv_tracks.item(x, 1).setCheckState(
                Qt.Unchecked
            )  # Envoie de la checkbox
            self.ui.mkv_tracks.item(x, 1).setStatusTip(
                self.Trad["TrackID1"].format(ID)
            )  # StatusTip
            self.ui.mkv_tracks.setItem(
                x,
                2,
                QTableWidgetItem(
                    QIcon.fromTheme(icone, QIcon(":/img/{}.png".format(icone))), ""
                ),
            )  # Envoie de l'icône
            self.ui.mkv_tracks.item(x, 2).setFlags(
                Qt.NoItemFlags | Qt.ItemIsEnabled
            )  # Blocage de la modification
            self.ui.mkv_tracks.item(x, 2).setStatusTip(
                self.Trad["TrackType"].format(TrackTypeName)
            )  # StatusTip
            self.ui.mkv_tracks.setItem(
                x, 3, QTableWidgetItem(info1)
            )  # Envoie de l'information
            self.ui.mkv_tracks.item(x, 3).setStatusTip(
                self.Trad["TrackRename"]
            )  # StatusTip

            ## Sélection de la valeur de la combobox
            self.ComboBoxes[x].setCurrentIndex(self.ComboBoxes[x].findText(str(info2)))

            ## Dans le cas de codec AAC
            if "aac" == codec:
                # Création d'une combobox, remplissage, mise à jour du statustip, connexion, sélection de la valeur et envoie de la combobox dans le tableau
                name = "{}-aac".format(x)
                self.ComboBoxes[name] = QComboBox()
                self.ui.mkv_tracks.setCellWidget(x, 5, self.ComboBoxes[name])
                self.ComboBoxes[name].addItems(["aac", "aac sbr"])
                self.ComboBoxes[name].setStatusTip(self.Trad["TrackAac"])
                self.ComboBoxes[name].currentIndexChanged.connect(
                    partial(self.ComboModif, name)
                )
                self.ComboBoxes[name].setCurrentIndex(
                    self.ComboBoxes[name].findText(codec)
                )

            ## Pour les autres audios
            else:
                self.ui.mkv_tracks.setItem(x, 5, QTableWidgetItem(codec))
                self.ui.mkv_tracks.item(x, 5).setFlags(
                    Qt.NoItemFlags | Qt.ItemIsEnabled
                )  # Blocage de la modification
                self.ui.mkv_tracks.item(x, 5).setStatusTip(codecInfo)

            ## Connexion de la combobox maintenant pour que setCurrentIndex ne lance pas la fonction
            self.ComboBoxes[x].currentIndexChanged.connect(partial(self.ComboModif, x))

            # Incrémentation du numéro de ligne
            x += 1

        ### Boucle traitant les chapitrages
        # Renvoie un truc du genre : 0 "num_entries": 15
        for Chapter in JsonMKV["chapters"]:
            ## Mise à jour des variables
            info1 = self.Trad["TrackChapters"]
            info2 = "{} {}".format(Chapter["num_entries"], info1)

            ## Mise à jour du dictionnaire des pistes du fichier MKV
            state.MKVDico[x] = [
                "NoID",
                "Chapters",
                "x-office-address-book",
                "document-preview",
                info1,
                info2,
                "Chapters",
            ]

            ## Création du bouton de visualisation
            Button = QPushButton(
                QIcon.fromTheme(
                    "x-office-address-book", QIcon(":/img/x-office-address-book.png")
                ),
                "",
            )
            Button.setFlat(True)
            Button.clicked.connect(partial(self.TrackView, x))
            Button.setStatusTip(self.Trad["TrackType2"].format(info1))

            ## Envoi des informations dans le tableaux
            self.ui.mkv_tracks.insertRow(x)  # Création de ligne
            self.ui.mkv_tracks.setItem(
                x, 0, QTableWidgetItem("chapters")
            )  # Remplissage des cellules
            self.ui.mkv_tracks.setItem(x, 1, QTableWidgetItem(""))
            self.ui.mkv_tracks.setCellWidget(x, 2, Button)  # Envoie du bouton
            self.ui.mkv_tracks.setItem(x, 3, QTableWidgetItem(info1))
            self.ui.mkv_tracks.setItem(x, 4, QTableWidgetItem(info2))
            self.ui.mkv_tracks.setItem(x, 5, QTableWidgetItem("text"))
            self.ui.mkv_tracks.item(x, 1).setStatusTip(
                self.Trad["TrackID3"].format(info1)
            )  # Envoie des StatusTip
            self.ui.mkv_tracks.item(x, 1).setCheckState(
                Qt.Unchecked
            )  # Envoie de la checkbox
            self.ui.mkv_tracks.item(x, 4).setFlags(Qt.NoItemFlags | Qt.ItemIsEnabled)
            self.ui.mkv_tracks.item(x, 5).setFlags(Qt.NoItemFlags | Qt.ItemIsEnabled)

            # Incrémentation du numéro de ligne
            x += 1

        ### Boucle traitant les tags
        # Renvoie un truc du genre : 0 "num_entries": 15
        for GlobalTag in JsonMKV["global_tags"]:
            ## Mise à jour des variables
            info1 = self.Trad["TrackTags"]
            info2 = "{} {}".format(GlobalTag["num_entries"], info1)

            ## Mise à jour du dictionnaire des pistes du fichier MKV
            state.MKVDico[x] = [
                "NoID",
                "Global tags",
                "text-html",
                "document-preview",
                info1,
                info2,
                "Tags",
            ]

            ## Création du bouton de visualisation
            Button = QPushButton(
                QIcon.fromTheme("text-html", QIcon(":/img/text-html.png")), ""
            )
            Button.setFlat(True)
            Button.clicked.connect(partial(self.TrackView, x))
            Button.setStatusTip(self.Trad["TrackType2"].format(info1))

            ## Envoi des informations dans le tableaux
            self.ui.mkv_tracks.insertRow(x)  # Création de ligne
            self.ui.mkv_tracks.setItem(
                x, 0, QTableWidgetItem("tags")
            )  # Remplissage des cellules
            self.ui.mkv_tracks.setItem(x, 1, QTableWidgetItem(""))
            self.ui.mkv_tracks.setCellWidget(x, 2, Button)  # Envoie du bouton
            self.ui.mkv_tracks.setItem(x, 3, QTableWidgetItem(info1))
            self.ui.mkv_tracks.setItem(x, 4, QTableWidgetItem(info2))
            self.ui.mkv_tracks.setItem(x, 5, QTableWidgetItem("xml"))
            self.ui.mkv_tracks.item(x, 1).setStatusTip(
                self.Trad["TrackID3"].format(info1)
            )  # Envoie des StatusTip
            self.ui.mkv_tracks.item(x, 1).setCheckState(
                Qt.Unchecked
            )  # Envoie de la checkbox
            self.ui.mkv_tracks.item(x, 4).setFlags(Qt.NoItemFlags | Qt.ItemIsEnabled)
            self.ui.mkv_tracks.item(x, 5).setFlags(Qt.NoItemFlags | Qt.ItemIsEnabled)

            # Incrémentation du numéro de ligne
            x += 1

        ### Boucle traitant les fichiers joints du fichier MKV
        # Renvoie un truc du genre : 0 "content_type": "text/html", "description": "", "file_name": "index.php"...
        for Attachment in JsonMKV["attachments"]:
            ## Mise à jour des variables
            ID = Attachment["id"]
            Item1 = ID
            info2 = "{} octets".format(Attachment["size"])
            typecodec = Attachment["content_type"]
            typetrack = typecodec.split("/")[0]

            ## Récupération de l'information 1
            if "description" in Attachment and Attachment["description"]:
                info1 = Attachment["description"]

            elif "file_name" in Attachment:
                info1 = Attachment["file_name"]

            else:
                info1 = "No info"

            ## Traitement des codecs
            if "/" in typecodec:
                typetrack = typecodec.split("/")[0]
                codec = typecodec.split("/")[1]

            else:
                typetrack = typecodec
                codec = typecodec

            ## Mise à jour du codec pour plus de lisibilité
            Codecs = {
                "x-truetype-font": "font",
                "vnd.ms-opentype": "font OpenType",
                "x-msdos-program": "application msdos",
                "plain": "text",
                "ogg": "audio",  # Il est reconnu en tant qu'application
                "ogm": "audio",  # Il est reconnu en tant qu'application
                "x-flac": "flac",
                "x-flv": "flv",
                "x-ms-bmp": "bmp",
            }

            codec = Codecs.get(codec, codec)

            ## Traitement des statustip
            StatusTip1 = self.Trad["TrackID2"].format(ID)
            StatusTip2 = self.Trad["TrackTypeAttachment"].format(typetrack)
            StatusTip3 = self.Trad["TrackAttachment"]

            ## Icône du type de piste
            machin = QMimeDatabase().mimeTypeForName(typecodec)
            icone = (
                QIcon()
                .fromTheme(
                    QMimeType(machin).iconName(),
                    QIcon().fromTheme(QMimeType(machin).genericIconName()),
                )
                .name()
            )

            ## Dans le cas où l'icône n'a pas été déterminée
            if not icone:
                Icones = {
                    "application": "system-run",
                    "image": "image-x-generic",
                    "text": "accessories-text-editor",
                    "media": "applications-multimedia",
                    "video": "applications-multimedia",
                    "audio": "applications-multimedia",
                    "web": "applications-internet",
                }

                icone = Icones.get(typetrack, "unknown")

            ## Mise à jour du dictionnaire des pistes du fichier MKV
            state.MKVDico[x] = [
                ID,
                "Attachment",
                icone,
                "document-preview",
                info1,
                info2,
                codec,
            ]

            ## Création du bouton de visualisation
            Button = QPushButton(
                QIcon.fromTheme(icone, QIcon(":/img/{}.png".format(icone))), ""
            )
            Button.setFlat(True)
            Button.clicked.connect(partial(self.TrackView, x))
            Button.setStatusTip(StatusTip2)

            ## Envoi des informations dans le tableau
            self.ui.mkv_tracks.insertRow(x)  # Création de ligne
            self.ui.mkv_tracks.setItem(
                x, 0, QTableWidgetItem(Item1)
            )  # Remplissage des cellules
            self.ui.mkv_tracks.setItem(x, 1, QTableWidgetItem(""))
            self.ui.mkv_tracks.setCellWidget(x, 2, Button)  # Envoi du bouton
            self.ui.mkv_tracks.setItem(x, 3, QTableWidgetItem(info1))
            self.ui.mkv_tracks.setItem(x, 4, QTableWidgetItem(info2))
            self.ui.mkv_tracks.setItem(x, 5, QTableWidgetItem(codec))
            self.ui.mkv_tracks.item(x, 1).setStatusTip(
                StatusTip1
            )  # Envoi des StatusTip
            self.ui.mkv_tracks.item(x, 3).setStatusTip(StatusTip3)
            self.ui.mkv_tracks.item(x, 1).setCheckState(
                Qt.Unchecked
            )  # Envoi de la checkbox
            self.ui.mkv_tracks.item(x, 4).setFlags(Qt.NoItemFlags | Qt.ItemIsEnabled)
            self.ui.mkv_tracks.item(x, 5).setFlags(Qt.NoItemFlags | Qt.ItemIsEnabled)

            ## Incrémentation du numéro de ligne
            x += 1

        ### Retours d'information
        if state.Configs.value("DebugMode"):
            self.SetInfo(self.Trad["WorkMerge"], "800080", True, True)

        ### Déblocage, curseur normal
        self.ui.mkv_tracks.blockSignals(False)
        state.TempValues.setValue(
            "SuperBlockTemp", False
        )  # Variable servant à bloquer les signaux du tableau (impossible autrement)
        self.setCursor(Qt.ArrowCursor)

    # ========================================================================
    def TrackView(self, x):
        """Fonction d'affichage des fichiers joints."""
        ### Vérification de la présence de mkvmerge
        if not state.SoftExec["MKVExtract"]:
            return

        ### Dans le cas d'un fichier de chapitrage
        if state.MKVDico[x][1] == "Chapters":
            ## Fichier de sortie
            ChaptersFileStr = state.TempValues.value("FolderTemp") + "/chapters.txt"
            state.TempValues.setValue("ChaptersFile", ChaptersFileStr)

            ## str => QFile
            ChaptersFile = QFile(ChaptersFileStr)

            ## Écriture du fichier
            ChaptersFile.open(QFile.WriteOnly)

            for line in self.LittleProcess(
                state.Configs.value("Location/MKVExtract"),
                ["chapters", state.Configs.value("InputFile"), "-s"],
            ):
                ChaptersFile.write((line + "\n").encode())

            ChaptersFile.close()

            ## Ouverture du fichier
            QDesktopServices.openUrl(QUrl.fromLocalFile(ChaptersFileStr))

        ### Dans le cas de global tags
        elif state.MKVDico[x][1] == "Global tags":
            ## Fichier de sortie
            TagsFileStr = state.TempValues.value("FolderTemp") + "/tags.xml"
            state.TempValues.setValue("TagsFile", TagsFileStr)

            ## str => QFile
            TagsFile = QFile(TagsFileStr)

            ## Écriture du fichier
            TagsFile.open(QFile.WriteOnly)

            for line in self.LittleProcess(
                state.Configs.value("Location/MKVExtract"),
                ["tags", state.Configs.value("InputFile")],
            ):
                TagsFile.write((line + "\n").encode())

            TagsFile.close()

            ## Ouverture du fichier
            QDesktopServices.openUrl(QUrl.fromLocalFile(TagsFileStr))

        ### Dans le cas de fichier joint
        elif state.MKVDico[x][1] == "Attachment":
            ## Test de la place disponible avant d'extraire
            FileSize = int(state.MKVDico[x][5].split(" ")[0])
            FreeSpaceDisk = QStorageInfo(
                state.TempValues.value("FolderTemp")
            ).bytesAvailable()

            ## Test de la place restante
            if self.CheckSize(
                "FolderTemp", FileSize, FreeSpaceDisk, self.Trad["ErrorSizeAttachement"]
            ):
                return

            ## Fichier de sortie
            Fichier = state.TempValues.value(
                "FolderTemp"
            ) + "/attachement_{0[0]}_{0[4]}".format(state.MKVDico[x])

            ## Extraction du fichier
            reply = self.LittleProcess(
                state.Configs.value("Location/MKVExtract"),
                [
                    "attachments",
                    state.Configs.value("InputFile"),
                    "{}:{}".format(state.MKVDico[x][0], Fichier),
                ],
            )

            ## Ouverture du fichier
            QDesktopServices.openUrl(QUrl.fromLocalFile(Fichier))

    # ========================================================================
    def TrackModif(self, info):
        """Fonction mettant à jour les dictionnaires des pistes du fichier MKV lors de l'édition des textes."""
        ### Blocage de la fonction pendant le chargement des pistes
        if state.TempValues.value("SuperBlockTemp"):
            return

        ### Récupération de la cellule modifiée
        x = self.ui.mkv_tracks.row(info)
        y = self.ui.mkv_tracks.column(info)

        ### Dans le cas de la modification d'une checkbox
        if y == 1:
            ## Mise au propre du tableau
            state.MKVDicoSelect.clear()  # Mise au propre du dictionnaire

            for x in range(
                self.ui.mkv_tracks.rowCount()
            ):  # Boucle traitant toutes les lignes du tableau
                if (
                    self.ui.mkv_tracks.item(x, 1).checkState() == Qt.Checked
                ):  # Teste si la ligne est cochée
                    state.MKVDicoSelect[x] = state.MKVDico[
                        x
                    ]  # mise à jour de la liste des pistes cochées

            ## Liste des widgets à possiblement (dé)bloquer
            Widgets = {
                self.ui.mkv_execute: False,
                self.mkv_execute_2: False,
                self.ui.option_audio: False,
                self.ui.option_subtitles: False,
                self.ui.option_reencapsulate: False,
                state.Sup2Sub[1]: False,
                state.Sup2Sub[2]: False,
                state.Sup2Sub[3]: False,
                state.Sub2Srt[1]: False,
                state.Sub2Srt[2]: False,
            }

            # Déblocage des options si besoin
            if state.MKVDicoSelect and state.Configs.value("OutputFolder"):
                # Déblocages des boutons
                if state.SoftExec["MKVExtract"]:
                    Widgets[self.ui.mkv_execute] = True
                    Widgets[self.mkv_execute_2] = True

                Widgets[self.ui.option_reencapsulate] = True

                # Boucle sur la liste des lignes
                for valeurs in state.MKVDicoSelect.values():
                    # Recherche la valeur audio dans les sous listes
                    if valeurs[2] == "audio-x-generic" and state.SoftExec["FFMpeg"]:
                        Widgets[self.ui.option_audio] = True

                    # Recherche la valeur vobsub dans les sous listes
                    elif valeurs[-1] == "sub" and state.SoftExec["Qtesseract5"]:
                        Widgets[self.ui.option_subtitles] = True
                        Widgets[state.Sub2Srt[1]] = True
                        Widgets[state.Sub2Srt[2]] = True

                    # Recherche la valeur sup/pgs dans les sous listes
                    elif valeurs[-1] in ("sup", "pgs") and (
                        state.SoftExec["BDSup2Sub"] or state.SoftExec["FFMpeg"]
                    ):
                        Widgets[self.ui.option_subtitles] = True

                        if state.SoftExec["BDSup2Sub"]:
                            Widgets[state.Sup2Sub[2]] = True
                            Widgets[state.Sup2Sub[3]] = True

                        if state.SoftExec["FFMpeg"]:
                            Widgets[state.Sup2Sub[1]] = True

                        # Active la conversion Qtesseract si disponible
                        if (
                            state.Sup2Sub[2].isChecked() or state.Sup2Sub[1].isChecked()
                        ) and state.SoftExec["Qtesseract5"]:
                            Widgets[state.Sub2Srt[1]] = True
                            Widgets[state.Sub2Srt[2]] = True

                    # Arrêt de la boucle si tout est activé
                    if (
                        Widgets[self.ui.option_subtitles]
                        and Widgets[state.Sub2Srt[1]]
                        and (Widgets[state.Sup2Sub[1]] or Widgets[state.Sup2Sub[2]])
                    ):
                        break

            # (Dé)blocage des widgets
            for Widget, State in Widgets.items():
                Widget.setEnabled(State)

                # Décoche les boutons s'ils sont grisés
                if (
                    Widget not in [self.ui.mkv_execute, self.mkv_execute_2]
                    and not State
                ):
                    Widget.setChecked(False)

        ### Dans le cas d'une modification de texte
        else:
            ## Mise à jour du texte dans le dico des pistes
            state.MKVDico[x][y] = self.ui.mkv_tracks.item(x, y).text()

            ## Mise à jour du texte dans le dico des pistes sélectionnées si la ligne est sélectionnée
            if self.ui.mkv_tracks.item(x, 1).checkState() == Qt.Checked:
                state.MKVDicoSelect[x][y] = state.MKVDico[x][y]

    # ========================================================================
    def TrackSelectAll(self, Value):
        """Fonction (dé)cochant toutes les pistes avec un clic sur le header. Value correspond à la colonne."""
        ### Ne traite que la colonne des coches soit la colonne num 1
        if Value == 1:
            ## Dans le cas où il faut tout cocher
            if not state.TempValues.value("AllTracks"):
                TempValue, CheckState = True, Qt.Checked

            ## Dans le cas où il faut tout décocher
            else:
                TempValue, CheckState = False, Qt.Unchecked

            ## Mise à jour de la valeur temporaire
            state.TempValues.setValue("AllTracks", TempValue)

            ## Boucle traitant toutes les lignes du tableau
            for x in range(self.ui.mkv_tracks.rowCount()):
                self.ui.mkv_tracks.item(x, 1).setCheckState(CheckState)
