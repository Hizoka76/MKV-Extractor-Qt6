#!/usr/bin/python3
# -*- coding: utf-8 -*-

"""Logiciel graphique d'extraction des pistes de fichiers MKV."""

###############################
### Importation des modules ###
###############################
try:
    import sys
    from functools import partial
    from os import execl

except ImportError as e:
    if "sys" in str(e):
        exit("Error: Impossible to find the sys module !")

    elif "functools" in str(e):
        exit("Error: Impossible to find partial from the functools module !")

    elif "os" in str(e):
        print(
            "Warning: Impossible to find execl from the os module ! Impossible to reboot with the right click on exit button."
        )


# Modules Qt
from PySide6.QtWidgets import (
    QApplication,
    QCheckBox,
    QDockWidget,
    QMainWindow,
    QMenu,
    QMessageBox,
    QPushButton,
    QStyleFactory,
    QSystemTrayIcon,
    QTableWidgetItem,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from PySide6.QtCore import (
    QCoreApplication,
    QDir,
    QFile,
    QFileInfo,
    QLibraryInfo,
    QLocale,
    QProcess,
    QSettings,
    Qt,
    QTemporaryDir,
    QTranslator,
    QUrl,
)

from PySide6.QtGui import (
    QDesktopServices,
    QFont,
    QIcon,
    QPixmap,
    QTextCursor,
    QGuiApplication,
    QAction,
    QActionGroup,
)

# Modules maisons
from QFileDialogCustom.QFileDialogCustom import (
    QFileDialogCustom,
)

# Version personnalisée de sélecteur de fichier
from WhatsUp.WhatsUp import WhatsUp

from ui_MKVExtractorQt6 import (
    Ui_mkv_extractor_qt6,
)

# Utilisé pour la fenêtre principale
from CodecListFile import CodecList  # Liste des codecs


# Import des fichiers locaux
import state

from CustomWidgets import (
    MultiVar,
    QActionCustom,
    QActionMenuCustom,
    QTextEditCustom,
    QuitButton,
)

from SoftwareMixin import SoftwareMixin
from MKVToolsMixin import MKVToolsMixin
from TracksMixin import TracksMixin
from CommandMixin import CommandMixin
from WorkMixin import WorkMixin

#############################################################################
# La classe hérite de toutes les classes locales
class MKVExtractorQt6(SoftwareMixin, MKVToolsMixin, TracksMixin, CommandMixin, WorkMixin, QMainWindow):
    """Fenêtre principale du logiciel."""

    def __init__(self, parent=None):
        """Fonction d'initialisation appelée au lancement de la classe."""

        ### Variables
        self.CloseMode = ""
        self.StartInProgress = True
        self.StopInProgress = False
        self.FinishState = ""

        ### Commandes à ne pas toucher
        super(MKVExtractorQt6, self).__init__(parent)
        self.ui = Ui_mkv_extractor_qt6()

        # Lance la fonction définissant tous les widgets du fichier UI
        self.ui.setupUi(self)  

        # Nom de la fenêtre
        self.setWindowTitle(f"{app.applicationName()} v{app.applicationVersion()}")  

        # Affichage de la fenêtre principale
        self.show()

        ### Création du QTextEditCustom affichant le retour avec un menu custom
        self.ui.reply_info = QTextEditCustom(self.ui.dockWidgetContents)
        self.ui.reply_info.setReadOnly(True)
        self.ui.reply_info.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOn)
        self.ui.reply_info.setLineWrapMode(QTextEdit.WidgetWidth)
        self.ui.reply_info.setTextInteractionFlags(
            Qt.TextSelectableByKeyboard | Qt.TextSelectableByMouse
        )
        self.ui.reply_info.resize(100, 150)
        self.ui.verticalLayout_8.addWidget(self.ui.reply_info)

        # [Claude] CORRECTION traduction au démarrage : OptionLanguage() est appelée AVANT
        # la création de reply_info, donc retranslate() ne peut pas y être déclenché.
        # On l'appelle ici, juste après la création, pour charger les textes dans la bonne
        # langue dès le premier affichage — sans attendre un changement de langue manuel.
        self.ui.reply_info.retranslate()

        ### Gestion de la fenêtre
        # Remet les widgets comme ils l'étaient
        if Configs.contains("WinState"):
            self.restoreState(Configs.value("WinState"))

        # Repositionne et donne la bonne taille à la fenêtre
        if Configs.value("WindowAspect") and Configs.contains("WinGeometry"):
            self.restoreGeometry(Configs.value("WinGeometry"))

        # Centrage de la fenêtre, en fonction de sa taille et de la taille de l'écran
        else:
            size_ecran = QGuiApplication.primaryScreen().geometry()  # Taille de l'écran
            self.move(
                int((size_ecran.width() - self.geometry().width()) / 2),
                int((size_ecran.height() - self.geometry().height()) / 2),
            )

        ### Modifications graphiques de boutons
        self.ui.mkv_stop.setVisible(False)  # Cache le bouton d'arrêt
        self.ui.mkv_pause.setVisible(False)  # Cache le bouton de pause

        # Grise le bouton pause si psutil n'est pas présent
        if not "psutil" in globals():
            self.ui.mkv_pause.setEnabled(False)

        ### Active les tooltips des actions dans les menus
        # [Claude] BUG MINEUR : self.ui.menuAide était listé deux fois, causant un appel
        # inutile en double sur le même widget. Le menu Options était également absent.
        for Widget in (
            self.ui.menuFichier,
            self.ui.menuActions,
            self.ui.menuLanguages,
            self.ui.menuOptions,
            self.ui.menuAide,
        ):
            Widget.setToolTipsVisible(True)

        ### Remplissage du menu des styles Qt disponibles
        self.ui.option_style.menuAction().setShortcut("Ctrl+S")
        ag = QActionGroup(self)  # Création d'un actiongroup

        for Style in QStyleFactory.keys():  # Styles disponibles
            QtStyleList[Style] = QAction(
                Style, self.ui.option_style, checkable=True
            )  # Création d'une action stockée dans le dico
            QtStyleList[Style].triggered.connect(
                partial(self.StyleChange, Style)
            )  # Action créée pour cet élément
            self.ui.option_style.addAction(
                ag.addAction(QtStyleList[Style])
            )  # Ajout de l'action à la liste

            # Si c'est le style actuel
            if Style.lower() == Configs.value("QtStyle").lower():
                QtStyleList[Style].setChecked(True)

        ### Mise en place du system tray
        menulist = QMenu()  # Création d'un menu
        icon = QIcon.fromTheme("application-exit", QIcon(":/img/application-exit.png"))
        self.SysTrayQuit = QAction(
            icon,
            "",
            self,
        )  # Création d'un item sans texte
        menulist.addAction(self.SysTrayQuit)  # Ajout de l'action à la liste

        self.SysTrayIcon = QSystemTrayIcon(
            QIcon.fromTheme(
                "mkv-extractor-qt6", QIcon(":/icons/mkv-extractor-qt6.webp")
            ),
            self,
        )
        self.SysTrayIcon.setContextMenu(menulist)

        if not Configs.value("SysTray"):
            self.ui.option_systray.setChecked(False)

        else:
            self.SysTrayIcon.show()

        ### Menu du bouton de conversion des sous titres
        menulist = QMenu(self.ui.option_subtitles)  # Création d'un menu
        menulist.setToolTipsVisible(True)  # Active les tooltips des actions

        ## SUP/PGS => SUB
        ag = QActionGroup(self)  # Création d'un actiongroup

        # Conversion FFMpeg
        Sup2Sub[1] = QActionMenuCustom(
            "", menulist, checkable=True
        )  # Création d'un item sans texte
        Sup2Sub[1].setIcon(QIcon.fromTheme("ffmpeg", QIcon(":/img/ffmpeg.png")))
        menulist.addAction(
            ag.addAction(Sup2Sub[1])
        )  # Ajout de l'item radio dans la sous liste

        # Conversion BDSup2Sub
        Sup2Sub[2] = QActionMenuCustom(
            "", menulist, checkable=True
        )  # Création d'un item sans texte
        Sup2Sub[2].setIcon(QIcon.fromTheme("BDSup2Sub", QIcon(":/img/BDSup2Sub.png")))
        menulist.addAction(
            ag.addAction(Sup2Sub[2])
        )  # Ajout de l'item radio dans la sous liste

        # Ouvrir BDSup2Sub lors de la conversion
        Sup2Sub[3] = QActionMenuCustom(
            "", menulist, checkable=True
        )  # Création d'un item sans texte
        Sup2Sub[3].setIcon(QIcon.fromTheme("BDSup2Sub", QIcon(":/img/BDSup2Sub.png")))
        menulist.addAction(
            ag.addAction(Sup2Sub[3])
        )  # Ajout de l'item radio dans la sous liste

        menulist.addSeparator()

        ## SUB => SRT
        ag = QActionGroup(self)  # Création d'un actiongroup

        # Conversion
        Sub2Srt[1] = QActionMenuCustom(
            "", menulist, checkable=True
        )  # Création d'un item sans texte
        Sub2Srt[1].setIcon(
            QIcon.fromTheme("Qtesseract5", QIcon(":/img/qtesseract5.png"))
        )
        menulist.addAction(
            ag.addAction(Sub2Srt[1])
        )  # Ajout de l'item radio dans la sous liste

        # Ouvrir Qtesseract5 lors de la conversion
        Sub2Srt[2] = QActionMenuCustom(
            "", menulist, checkable=True
        )  # Création d'un item sans texte
        Sub2Srt[2].setIcon(
            QIcon.fromTheme("Qtesseract5", QIcon(":/img/qtesseract5.png"))
        )
        menulist.addAction(
            ag.addAction(Sub2Srt[2])
        )  # Ajout de l'item radio dans la sous liste

        self.ui.option_subtitles.setMenu(menulist)  # Envoie de la liste dans le bouton

        ### Menu du bouton de conversion audio
        menulist = QMenu(self.ui.option_audio)  # Création d'un menu
        menulist.setToolTipsVisible(True)  # Active les tooltips des actions

        icon = QIcon.fromTheme("ffmpeg", QIcon(":/img/ffmpeg.png"))
        self.option_ffmpeg = QActionMenuCustom(
            icon, "", menulist, checkable=True
        )  # Création d'un item sans texte
        menulist.addAction(self.option_ffmpeg)  # Ajout de l'action à la liste

        icon = QIcon.fromTheme("audio-ac3", QIcon(":/img/audio-ac3.png"))
        self.option_to_ac3 = QActionMenuCustom(
            icon, "", menulist, checkable=True
        )  # Création d'un item sans texte
        menulist.addAction(self.option_to_ac3)  # Ajout de l'action à la liste

        icon = QIcon.fromTheme("stereo", QIcon(":/img/stereo.png"))
        self.option_stereo = QActionMenuCustom(
            icon, "", menulist, checkable=True
        )  # Création d'un item sans texte
        menulist.addAction(self.option_stereo)  # Ajout de l'action à la liste

        self.RatesMenu = QMenu(self)  # Création d'un sous menu
        ag = QActionGroup(self)  # Création d'un actiongroup

        for nb in [
            128,
            192,
            224,
            256,
            320,
            384,
            448,
            512,
            576,
            640,
        ]:  # Qualités utilisables
            QualityList[nb] = QActionMenuCustom(
                "", menulist, checkable=True
            )  # Création d'un item radio sans nom
            self.RatesMenu.addAction(
                ag.addAction(QualityList[nb])
            )  # Ajout de l'item radio dans la sous liste

        menulist.addMenu(self.RatesMenu)  # Ajout du sous menu dans le menu

        self.PowerMenu = QMenu(self)  # Création d'un sous menu
        ag = QActionGroup(self)  # Création d'un actiongroup

        for nb in [2, 3, 4, 5]:  # Puissances utilisables
            PowerList[nb] = QActionMenuCustom(
                "", menulist, checkable=True
            )  # Création d'un item radio sans nom
            self.PowerMenu.addAction(
                ag.addAction(PowerList[nb])
            )  # Ajout de l'item radio dans la sous liste

        menulist.addMenu(self.PowerMenu)  # Ajout du sous menu dans le menu

        self.ui.option_audio.setMenu(menulist)  # Envoie de la liste dans le bouton

        ### Menu du bouton de ré-encapsulage
        menulist = QMenu(self.ui.option_reencapsulate)  # Création d'un menu

        icon = QIcon.fromTheme("document-edit", QIcon(":/img/document-edit.png"))
        self.option_subtitles_open = QActionMenuCustom(
            icon, "", menulist, checkable=True
        )  # Création d'une action cochable sans texte
        menulist.addAction(self.option_subtitles_open)  # Ajout de l'action à la liste

        self.ui.option_reencapsulate.setMenu(
            menulist
        )  # Envoie de la liste dans le bouton

        ### Création des actions personnalisées
        self.mkv_info = QActionCustom(self.ui.menuActions)
        self.mkv_info.setEnabled(False)
        icon = QIcon.fromTheme("mkvinfo", QIcon(":/img/mkvinfo.png"))
        self.mkv_info.setIcon(icon)
        self.mkv_info.setShortcut("F5")
        self.mkv_info.setObjectName("mkv_info")
        self.ui.menuActions.addAction(self.mkv_info)

        self.mkv_mkvtoolnix = QActionCustom(self.ui.menuActions)
        self.mkv_mkvtoolnix.setEnabled(False)
        icon = QIcon.fromTheme("mkvmerge", QIcon(":/img/mkvmerge.png"))
        self.mkv_mkvtoolnix.setIcon(icon)
        self.mkv_mkvtoolnix.setShortcut("F6")
        self.mkv_mkvtoolnix.setObjectName("mkv_mkvtoolnix")
        self.ui.menuActions.addAction(self.mkv_mkvtoolnix)

        self.ui.menuActions.addSeparator()

        self.mk_validator = QActionCustom(self.ui.menuActions)
        self.mk_validator.setEnabled(False)
        icon = QIcon.fromTheme("dialog-ok", QIcon(":/img/dialog-ok.png"))
        self.mk_validator.setIcon(icon)
        self.mk_validator.setShortcut("F7")
        self.mk_validator.setObjectName("mk_validator")
        self.ui.menuActions.addAction(self.mk_validator)

        self.mk_clean = QActionCustom(self.ui.menuActions)
        self.mk_clean.setEnabled(False)
        icon = QIcon.fromTheme("draw-eraser", QIcon(":/img/draw-eraser.png"))
        self.mk_clean.setIcon(icon)
        self.mk_clean.setShortcut("F8")
        self.mk_clean.setObjectName("mk_clean")
        self.ui.menuActions.addAction(self.mk_clean)

        self.ui.menuActions.addSeparator()

        self.mkv_view = QActionCustom(self.ui.menuActions)
        self.mkv_view.setEnabled(False)
        icon = QIcon.fromTheme("document-preview", QIcon(":/img/document-preview.png"))
        self.mkv_view.setIcon(icon)
        self.mkv_view.setShortcut("F9")
        self.mkv_view.setObjectName("mkv_view")
        self.ui.menuActions.addAction(self.mkv_view)

        self.ui.menuActions.addSeparator()

        self.mkv_execute_2 = QActionCustom(self.ui.menuActions)
        self.mkv_execute_2.setEnabled(False)
        icon = QIcon.fromTheme("run-build", QIcon(":/img/run-build.png"))
        self.mkv_execute_2.setIcon(icon)
        self.mkv_execute_2.setShortcut("F4")
        self.mkv_execute_2.setObjectName("mkv_execute_2")
        self.ui.menuActions.addAction(self.mkv_execute_2)

        ### QProcess (permet de lancer les jobs en fond de taches)
        self.process = QProcess()  # Création du QProcess
        self.process.setProcessChannelMode(
            QProcess.ProcessChannelMode.MergedChannels
        )  # Unification des 2 sorties (normale + erreur) du QProcess

        ### Désactive le bouton whatsup s'il n'y a pas de changelog
        if not QFileInfo(
            "/usr/share/doc/mkv-extractor-qt6/changelog.Debian.gz"
        ).exists():
            self.ui.whatsup.setEnabled(False)

        ### Recherche ffmpeg et avconv qui font la même chose
        # Désactive les radiobutton et l'option de conversion
        if not SoftExec["FFMpeg"] and not SoftExec["AvConv"]:
            TempValues.setValue("FFMpeg", False)
            self.option_ffmpeg.setEnabled(False)
            self.ui.option_audio.setEnabled(False)

        # Sélection automatique ffmpeg
        elif SoftExec["FFMpeg"] and not SoftExec["AvConv"]:
            TempValues.setValue("FFMpeg", True)
            self.option_ffmpeg.setEnabled(False)

        # Sélection automatique avconv
        elif not SoftExec["FFMpeg"] and SoftExec["AvConv"]:
            TempValues.setValue("FFMpeg", False)
            self.option_ffmpeg.setEnabled(False)

        # Les deux sont dispo, utilisation de ffmpeg par défaut
        else:
            TempValues.setValue("FFMpeg", True)
            self.option_ffmpeg.setChecked(True)

        ### Activation et modifications des préférences
        if TempValues.value("AudioQuality") in [128, 192, 224, 256, 320, 384, 448, 512, 576, 640]:
            QualityList[TempValues.value("AudioQuality")].setChecked(
                True
            )  # Coche de la bonne valeur

        if TempValues.value("AudioBoost") in [2, 3, 4, 5]:
            PowerList[TempValues.value("AudioBoost")].setChecked(
                True
            )  # Coche de la bonne valeur

        if not Configs.value("RecentInfos"):
            self.ui.option_recent_infos.setChecked(True)

        if not Configs.value("WindowAspect"):
            self.ui.option_aspect.setChecked(False)

        if not Configs.value("DelTempFiles"):
            self.ui.option_del_temp_files.setChecked(False)

        if Configs.value("DebugMode"):
            self.ui.option_debug.setChecked(True)

        if Configs.value("SysTrayMinimise") and Configs.value("SysTray"):
            self.ui.option_minimise_systray.setChecked(True)

        if not Configs.value("Feedback"):
            self.ui.option_feedback.setChecked(False)
            self.ui.feedback_widget.hide()

        if Configs.value("FeedbackBlock"):
            self.ui.option_feedback_block.setChecked(True)
            self.ui.feedback_widget.setFeatures(QDockWidget.NoDockWidgetFeatures)

        ### Définition des liens location et widget
        self.WidgetsLocation = {
            "Location/BDSup2Sub": Sup2Sub[2],
            "Location/FFMpeg": self.option_ffmpeg,
            "Location/MKClean": self.mk_clean,
            "Location/MKVInfo": self.mkv_info,
            "Location/MKVToolNix": self.mkv_mkvtoolnix,
            "Location/MKValidator": self.mk_validator,
            "Location/Qtesseract5": Sub2Srt[1],
        }

        ### Gestion la traduction, le widget n'est pas encore connecté
        Langue = Configs.value("Language")[0:2].lower()
        if Langue in ("fr", "cs", "de", "es", "it", "tr"):
            Infos = {
                "fr": [self.ui.lang_fr, "fr_FR"],
                "cs": [self.ui.lang_cs, "cs_CZ"],
                "de": [self.ui.lang_de, "de_DE"],
                "es": [self.ui.lang_es, "es_ES"],
                "it": [self.ui.lang_it, "it_IT"],
                "tr": [self.ui.lang_tr, "tr_TR"],
            }

            # Sélection de la langue
            Infos[Langue][0].setChecked(True)
            self.OptionLanguage(Infos[Langue][1])

        # Force le chargement de traduction si c'est la langue anglaise (par défaut)
        else:
            self.OptionLanguage("en_US")

        ### Réinitialisation du dossier de sortie s'il n'existe pas
        if (
            not Configs.contains("OutputFolder")
            or not QFileInfo(Configs.value("OutputFolder")).isDir()
        ):
            Configs.setValue("OutputFolder", QDir.homePath())
            Configs.setValue("OutputSameFolder", True)

        ### Définition de la taille des colonnes du tableau des pistes
        largeur = int(
            (self.ui.mkv_tracks.size().width() - 75) / 3
        )  # Calcul pour définir la taille des colonnes
        self.ui.mkv_tracks.setMouseTracking(
            True
        )  # Nécessaire à l'affichage des statustip
        self.ui.mkv_tracks.hideColumn(0)  # Cache la 1ere colonne
        self.ui.mkv_tracks.setColumnWidth(1, 25)  # Définit la colonne 1 à 25px
        self.ui.mkv_tracks.setColumnWidth(2, 25)  # Définit la colonne 2 à 25px
        self.ui.mkv_tracks.setColumnWidth(3, largeur + 30)  # Définit la colonne 4
        self.ui.mkv_tracks.setColumnWidth(4, largeur + 15)  # Définit la colonne 5
        self.ui.mkv_tracks.horizontalHeader().setStretchLastSection(
            True
        )  # Définit la place restante à la dernière colonne

        ### Récupération du retour de MKVMerge
        for line in self.LittleProcess("mkvmerge", ["--list-languages"]):
            ## Exclue la ligne contenant les ---
            if line[0] != "-":
                try:
                    # Récupère la 2eme colonne, la langue en 3 lettres
                    line = line.split("|")[1].strip()

                    # Vérifie que le résultat est bien de 3 caractères puis ajoute la langue
                    if len(line) == 3:
                        MKVLanguages.append(line)

                except (IndexError, ValueError):
                    # [Claude] AMÉLIORATION : 'except:' nu remplacé par les exceptions pertinentes.
                    # Un bare except masque aussi KeyboardInterrupt et SystemExit, ce qui empêche
                    # l'arrêt propre du programme. Ici seuls IndexError et ValueError sont attendus.
                    pass

        # Range les langues dans l'ordre alphabétique
        MKVLanguages.sort()

        ### Connexions de la grande partie des widgets (les autres sont ci-dessus ou via le fichier UI)
        self.ConnectActions()

        ### Création du dossier temporaire
        if not self.FolderTempCreate():
            Configs.setValue("FolderParentTemp", DefaultValues["FolderParentTemp"])
            self.FolderTempCreate()

        ### Cache les boutons non fonctionnels
        if Configs.value("HideOptions"):
            self.ui.option_hide_options.setChecked(True)

        ### Fait manuellement pour éviter que la fonction soit appelée plusieurs fois
        self.SubtitlesSoftwareUpdate()

        ### Modifie la variable indiquant un démarrage en cours
        self.StartInProgress = False

        ### Dans le cas du lancement du logiciel avec ouverture de fichier
        # En cas d'argument simple
        if len(sys.argv) == 2:
            # Teste le fichier avant de l'utiliser
            if QFileInfo(sys.argv[1]).exists():
                Configs.setValue("InputFile", sys.argv[1])

            # En cas d'erreur
            else:
                QMessageBox(
                    QMessageBox.Critical,
                    self.Trad["ErrorArgTitle"],
                    self.Trad["ErrorArgExist"].format(sys.argv[1]),
                    QMessageBox.Close,
                    self,
                    Qt.WindowSystemMenuHint,
                ).exec()

        # En cas arguments multiples
        elif len(sys.argv) > 2:
            # Suppression du fichier d'entrée
            Configs.remove("InputFile")

            # Message d'erreur
            QMessageBox(
                QMessageBox.Critical,
                self.Trad["ErrorArgTitle"],
                self.Trad["ErrorArgNb"].format("<br/> - ".join(sys.argv[1:])),
                QMessageBox.Close,
                self,
                Qt.WindowSystemMenuHint,
            ).exec()

        # En cas de l'utilisation du dernier fichier ouvert
        elif Configs.value("InputFile") and Configs.value("LastFile"):
            # Si le fichier n'existe plus et qu'on ne cache pas le message, on affiche le message d'erreur
            if not QFileInfo(Configs.value("InputFile")).isFile() and not Configs.value(
                "ConfirmErrorLastFile"
            ):
                Configs.remove("InputFile")

                # Création d'une fenêtre de confirmation avec case à cocher pour se souvenir du choix
                dialog = QMessageBox(
                    QMessageBox.Warning,
                    self.Trad["ErrorLastFileTitle"],
                    self.Trad["ErrorLastFileText"],
                    QMessageBox.NoButton,
                    self,
                )
                CheckBox = QCheckBox(self.Trad["Convert5"])  # Reprise du même texte
                dialog.setCheckBox(CheckBox)
                dialog.setStandardButtons(QMessageBox.Close)
                dialog.setDefaultButton(QMessageBox.Close)
                dialog.exec()

                Configs.setValue(
                    "ConfirmErrorLastFile", CheckBox.isChecked()
                )  # Mise en mémoire de la case à cocher

        # Dans les autres cas, on vire le nom du fichier
        elif Configs.contains("InputFile"):
            Configs.remove("InputFile")

        QCoreApplication.processEvents()

        ### Ouverture du fichier indiqué en entrée
        if Configs.contains("InputFile"):
            QCoreApplication.processEvents()
            self.InputFile(Configs.value("InputFile"))

    # ========================================================================
    def ConnectActions(self):
        """Fonction faisant les connexions non faites par qtdesigner."""
        ### Connexions du menu File (au clic)
        self.ui.input_file.triggered.connect(self.InputFile)
        self.ui.output_folder.triggered.connect(self.OutputFolder)
        self.mkv_execute_2.triggered.connect(self.ui.mkv_execute.click)

        ### Connexions du menu Actions (au clic)
        self.mkv_info.triggered.connect(self.MKVInfoGui)
        self.mkv_mkvtoolnix.triggered.connect(self.MKVMergeGui)
        self.mk_validator.triggered.connect(self.MKValidator)
        self.mk_clean.triggered.connect(self.MKClean)
        self.mkv_view.triggered.connect(self.MKVView)

        ### Connexions du menu Options (au clic ou au coche)
        self.ui.option_recent_infos.toggled.connect(
            partial(self.OptionsValue, "RecentInfos")
        )
        self.ui.option_del_temp_files.toggled.connect(
            partial(self.OptionsValue, "DelTempFiles")
        )
        self.ui.option_configuration_table.triggered.connect(self.Configuration)
        self.ui.option_feedback.toggled.connect(partial(self.OptionsValue, "Feedback"))
        self.ui.option_feedback_block.toggled.connect(
            partial(self.OptionsValue, "FeedbackBlock")
        )
        self.ui.option_aspect.toggled.connect(
            partial(self.OptionsValue, "WindowAspect")
        )
        self.ui.option_hide_options.toggled.connect(
            partial(self.OptionsValue, "HideOptions")
        )
        self.ui.option_softwares_locations.triggered.connect(
            lambda: (self.ui.stackedMiddle.setCurrentIndex(2))
        )
        self.ui.lang_en.triggered.connect(partial(self.OptionLanguage, "en_US"))
        self.ui.lang_fr.triggered.connect(partial(self.OptionLanguage, "fr_FR"))
        self.ui.lang_cs.triggered.connect(partial(self.OptionLanguage, "cs_CZ"))
        self.ui.lang_de.triggered.connect(partial(self.OptionLanguage, "de_DE"))
        self.ui.lang_es.triggered.connect(partial(self.OptionLanguage, "es_ES"))
        self.ui.lang_it.triggered.connect(partial(self.OptionLanguage, "it_IT"))
        self.ui.lang_tr.triggered.connect(partial(self.OptionLanguage, "tr_TR"))

        ### Connexions du menu Help (au clic ou au coche)
        self.ui.option_debug.toggled.connect(partial(self.OptionsValue, "DebugMode"))
        self.ui.help_mkvextractorqt6.triggered.connect(self.HelpMKVExtractorQt6)
        self.ui.they_talk_about.triggered.connect(self.TheyTalkAbout)
        self.ui.about.triggered.connect(self.AboutMKVExtractorQt6)
        self.ui.about_qt.triggered.connect(
            lambda: QMessageBox.aboutQt(MKVExtractorQt6Class)
        )
        self.ui.mkvtoolnix.triggered.connect(
            lambda: QDesktopServices.openUrl(
                QUrl("https://mkvtoolnix.download/downloads.html")
            )
        )
        self.ui.whatsup.triggered.connect(
            lambda: WhatsUp(
                "/usr/share/doc/mkv-extractor-qt6/changelog.Debian.gz",
                "mkv-extractor-qt6",
                self.Trad["WhatsUpTitle"],
                self,
            )
        )

        ### Connexion du dockwidget
        self.ui.feedback_widget.visibilityChanged.connect(self.FeedbackWidget)

        ### Connexions des widgets de configuration (au clic ou changement de contenu)
        self.ui.configuration_table.itemChanged.connect(self.ConfigurationEdit)
        self.ui.configuration_close.clicked.connect(
            lambda: (self.ui.stackedMiddle.setCurrentIndex(0))
        )
        self.ui.configuration_reset.clicked.connect(self.ConfigurationReset)

        ### Connexions des widgets des locations de logiciels
        self.ui.locations_close.clicked.connect(
            lambda: (self.ui.stackedMiddle.setCurrentIndex(0))
        )
        self.ui.locations_reset.clicked.connect(partial(self.SoftwareFinding, True))
        self.ui.button_avconv.clicked.connect(
            partial(self.SoftwareSelector, "Location/AvConv", self.ui.location_avconv)
        )
        self.ui.button_bdsup2sub.clicked.connect(
            partial(
                self.SoftwareSelector, "Location/BDSup2Sub", self.ui.location_bdsup2sub
            )
        )
        self.ui.button_ffmpeg.clicked.connect(
            partial(self.SoftwareSelector, "Location/FFMpeg", self.ui.location_ffmpeg)
        )
        self.ui.button_mkclean.clicked.connect(
            partial(self.SoftwareSelector, "Location/MKClean", self.ui.location_mkclean)
        )
        self.ui.button_mkvextract.clicked.connect(
            partial(
                self.SoftwareSelector,
                "Location/MKVExtract",
                self.ui.location_mkvextract,
            )
        )
        self.ui.button_mkvinfo.clicked.connect(
            partial(self.SoftwareSelector, "Location/MKVInfo", self.ui.location_mkvinfo)
        )
        self.ui.button_mkvmerge.clicked.connect(
            partial(
                self.SoftwareSelector, "Location/MKVMerge", self.ui.location_mkvmerge
            )
        )
        self.ui.button_mkvtoolnix.clicked.connect(
            partial(
                self.SoftwareSelector,
                "Location/MKVToolNix",
                self.ui.location_mkvtoolnix,
            )
        )
        self.ui.button_mkvalidator.clicked.connect(
            partial(
                self.SoftwareSelector,
                "Location/MKValidator",
                self.ui.location_mkvalidator,
            )
        )
        self.ui.button_qtesseract5.clicked.connect(
            partial(
                self.SoftwareSelector,
                "Location/Qtesseract5",
                self.ui.location_qtesseract5,
            )
        )

        locations = {
            "Location/AvConv": self.ui.location_avconv,
            "Location/BDSup2Sub": self.ui.location_bdsup2sub,
            "Location/FFMpeg": self.ui.location_ffmpeg,
            "Location/MKVExtract": self.ui.location_mkvextract,
            "Location/MKClean": self.ui.location_mkclean,
            "Location/MKVInfo": self.ui.location_mkvinfo,
            "Location/MKVMerge": self.ui.location_mkvmerge,
            "Location/MKVToolNix": self.ui.location_mkvtoolnix,
            "Location/MKValidator": self.ui.location_mkvalidator,
            "Location/Qtesseract5": self.ui.location_qtesseract5,
        }

        for key, widget in locations.items():
            widget.textChanged.connect(
                partial(self.SoftwareChanged, key, Widget=widget)
            )

        ### Connexions du tableau listant les pistes du fichier mkv
        self.ui.mkv_tracks.itemChanged.connect(
            self.TrackModif
        )  # Au changement du contenu d'un item
        self.ui.mkv_tracks.itemSelectionChanged.connect(
            self.TrackModif
        )  # Au changement de sélection
        self.ui.mkv_tracks.horizontalHeader().sectionPressed.connect(
            self.TrackSelectAll
        )  # Au clic sur le header horizontal

        ### Connexions des options sur les pistes du fichier mkv (au clic)
        self.ui.option_reencapsulate.toggled.connect(
            partial(self.OptionsValue, "Reencapsulate")
        )
        self.ui.option_subtitles.toggled.connect(
            partial(self.OptionsValue, "SubtitlesConvert")
        )
        self.ui.option_audio.toggled.connect(partial(self.OptionsValue, "AudioConvert"))
        self.ui.option_systray.toggled.connect(partial(self.OptionsValue, "SysTray"))
        self.ui.option_minimise_systray.toggled.connect(
            partial(self.OptionsValue, "SysTrayMinimise")
        )
        self.option_stereo.toggled.connect(partial(self.OptionsValue, "AudioStereo"))
        self.option_to_ac3.toggled.connect(partial(self.OptionsValue, "AudioToAc3"))
        self.option_subtitles_open.toggled.connect(
            partial(self.OptionsValue, "SubtitlesOpen")
        )
        self.option_ffmpeg.toggled.connect(partial(self.OptionsValue, "FFMpeg"))

        Sub2Srt[1].triggered.connect(partial(self.OptionsValue, "Sub2Srt", 1))
        Sub2Srt[2].triggered.connect(partial(self.OptionsValue, "Sub2Srt", 2))
        Sup2Sub[1].triggered.connect(partial(self.OptionsValue, "Sup2Sub", 1))
        Sup2Sub[2].triggered.connect(partial(self.OptionsValue, "Sup2Sub", 2))
        Sup2Sub[3].triggered.connect(partial(self.OptionsValue, "Sup2Sub", 3))

        for nb in [128, 192, 224, 256, 320, 384, 448, 512, 576, 640]:
            QualityList[nb].triggered.connect(
                partial(self.OptionsValue, "AudioQuality", nb)
            )

        for nb in [2, 3, 4, 5]:
            PowerList[nb].triggered.connect(
                partial(self.OptionsValue, "AudioBoost", nb)
            )

        ### Connexions en lien avec le system tray
        self.SysTrayIcon.activated.connect(self.SysTrayClick)

        ### Connexions des boutons du bas (au clic)
        self.ui.mkv_stop.clicked.connect(partial(self.WorkStop, "Stop"))
        self.ui.mkv_pause.clicked.connect(self.WorkPause)
        self.ui.mkv_execute.clicked.connect(self.CommandCreate)
        self.ui.soft_quit.__class__ = QuitButton  # Utilisation de la classe QuitButton pour la prise en charge du clic droit

        ### Connexions du QProcess
        self.process.readyReadStandardOutput.connect(
            self.WorkReply
        )  # Retours du travail
        self.process.finished.connect(self.WorkFinished)  # Fin du travail
        self.process.errorOccurred.connect(self.WorkError)

        ### Boutons de fermeture de l'application'
        self.SysTrayQuit.triggered.connect(self.CloseButton)
        self.ui.soft_quit_2.triggered.connect(self.CloseButton)
        self.ui.soft_quit.clicked.connect(self.CloseButton)
        self.ui.soft_quit.signalReboot.connect(self.RebootButton)

    # ========================================================================
    def StyleChange(self, Value):
        """Fonction modifiant le style utilisé par Qt."""
        ### Enregistrement de la valeur
        Configs.setValue("QtStyle", Value)

        ### Applique le style graphique
        QApplication.setStyle(QStyleFactory.create(Value))

    # ========================================================================
    def OptionsValue(self, Option, Value):
        """Fonction de mise à jour des options."""
        ### Permet de décocher un radiobutton déjà actif
        # [Claude] CORRECTION : Ces options (AudioBoost, AudioQuality, Sup2Sub, Sub2Srt) sont
        # des valeurs de session -> lecture et ecriture dans TempValues, plus dans Configs.
        if Option in ("AudioBoost", "AudioQuality", "Sup2Sub", "Sub2Srt"):
            if TempValues.value(Option) == Value:
                if Option == "AudioBoost":
                    PowerList[Value].setChecked(False)

                elif Option == "AudioQuality":
                    QualityList[Value].setChecked(False)

                elif Option == "Sup2Sub":
                    Sup2Sub[Value].setChecked(False)

                    # Décoche si besoin l'utilisation de Qtesseract
                    if SoftExec["Qtesseract5"]:
                        State = False

                        # Boucle sur la liste des pistes cochées à la recherche de fichier sub
                        if MKVDicoSelect:
                            for valeurs in MKVDicoSelect.values():
                                if valeurs[-1] == "sub":
                                    # Ne désactive pas Qtesseract s'il y a un sub
                                    State = True
                                    break

                        if not State:
                            Sub2Srt[1].setEnabled(False)
                            Sub2Srt[1].setChecked(False)
                            Sub2Srt[2].setEnabled(False)
                            Sub2Srt[2].setChecked(False)

                elif Option == "Sub2Srt":
                    Sub2Srt[Value].setChecked(False)

                TempValues.setValue(Option, 0)

                return

        ### Mise à jour de la variable et envoi de l'info
        # [Claude] CORRECTION : Suite à la séparation de Configs et TempValues en deux
        # QSettings distincts, il faut écrire dans le bon objet selon la nature de l'option.
        # Les options de session (états temporaires de boutons) vont dans TempValues,
        # les préférences persistantes vont dans Configs.
        _TEMP_OPTIONS = {
            "Reencapsulate", "AudioConvert", "AudioBoost", "AudioQuality",
            "AudioStereo", "AudioToAc3", "Sub2Srt", "Sup2Sub", "SubtitlesConvert",
            "SubtitlesOpen", "FFMpeg", "BDSup2Sub", "AllTracks", "Command",
        }
        if Option in _TEMP_OPTIONS:
            TempValues.setValue(Option, Value)
        else:
            Configs.setValue(Option, Value)

        if Configs.value("DebugMode"):
            self.SetInfo(self.Trad["OptionUpdate"].format(Option, Value), newline=True)

        ### Dans le cas de certaines options, il faut faire plus
        # Si l'option OutputSameFolder est activée et qu'un fichier d'entrée est déjà connu
        if Option == "OutputSameFolder" and Value and Configs.contains("InputFile"):
            # Recherche de l'option OutputSameFolder
            x = self.ui.configuration_table.findItems(
                "OutputSameFolder", Qt.MatchExactly
            )[0].row()

            ## Il faut bloquer le signal pour éviter un cercle vicieux et modifier la valeur visuelle en directe
            self.ui.configuration_table.blockSignals(True)
            self.ui.configuration_table.item(x, 1).setText(Configs.value("InputFolder"))

            # Envoie de la nouvelle variable à la fonction de gestion des dossiers qui mettra à jour la variable
            self.OutputFolder(Configs.value("InputFolder"))

            # Déblocage des signaux
            self.ui.configuration_table.blockSignals(False)

        # En cas de modification du dossier de sorti
        elif Option == "OutputFolder":
            Configs.setValue(Option, Value)

            # Recherche de l'option OutputFolder
            x = self.ui.configuration_table.findItems(
                "OutputSameFolder", Qt.MatchExactly
            )[0].row()

            # Il faut bloquer le signal pour éviter un cercle vicieux et modifier la valeur visuelle en directe
            self.ui.configuration_table.blockSignals(True)
            self.ui.configuration_table.item(x, 1).setText("False")

            # Mise à jour de la variable
            Configs.setValue("OutputSameFolder", False)

            # Envoie de la nouvelle variable à la fonction de gestion des dossiers
            self.OutputFolder(Configs.value("OutputFolder"))

            # Déblocage des signaux
            self.ui.configuration_table.blockSignals(False)

        # Pour cacher ou afficher la box de retour d'informations
        elif Option == "Feedback":
            if Value:
                self.ui.feedback_widget.show()

            else:
                self.ui.feedback_widget.hide()

                # Décoche le fixe des retours
                if self.ui.option_feedback_block.isChecked():
                    self.ui.option_feedback_block.setChecked(False)

        # Pour bloquer ou débloquer la box de retour d'informations
        elif Option == "FeedbackBlock":
            if Value:
                # Coche l'affichage des retours
                if not self.ui.option_feedback.isChecked():
                    self.ui.option_feedback.setChecked(True)

                self.ui.feedback_widget.setFeatures(QDockWidget.NoDockWidgetFeatures)

            else:
                self.ui.feedback_widget.setFeatures(
                    QDockWidget.DockWidgetClosable
                    | QDockWidget.DockWidgetMovable
                    | QDockWidget.DockWidgetFloatable
                )

        # Pour cacher ou afficher l'icône du systray
        elif Option == "SysTray":
            ## Affichage de l'icône
            if Value:
                self.SysTrayIcon.show()

            ## Cache l'icône après avoir affiché la fenêtre principale
            else:
                self.show()
                self.activateWindow()
                self.SysTrayIcon.hide()

                # Décoche SysTrayMinimise
                if self.ui.option_minimise_systray.isChecked():
                    self.ui.option_minimise_systray.setChecked(False)

        # Pour cocher l'option systray
        elif Option == "SysTrayMinimise" and Value:
            if not self.ui.option_systray.isChecked():
                self.ui.option_systray.setChecked(True)

        # Activation des boutons Qtesseract si conversion Sup => Sub
        if Option == "Sup2Sub" and SoftExec["Qtesseract5"] and Value:
            # Si la conversion SUP => SUB est coché, on active les actions Qtesseract pour les fichiers SUP/PGS
            if Value:
                Sub2Srt[1].setEnabled(True)
                Sub2Srt[2].setEnabled(True)

            # Si la conversion SUP => SUB est décochée
            else:
                State = False

                # Boucle sur la liste des pistes cochées à la recherche de fichier sub
                if MKVDicoSelect:
                    for valeurs in MKVDicoSelect.values():
                        if valeurs[-1] == "sub":
                            # Ne désactive pas Qtesseract s'il y a un sub
                            State = True
                            break

                Sub2Srt[1].setEnabled(State)
                Sub2Srt[1].setChecked(Sub2Srt[1].isChecked())
                Sub2Srt[2].setEnabled(State)
                Sub2Srt[2].setChecked(Sub2Srt[2].isChecked())

        ## Pour cacher ou afficher les commandes indisponibles
        elif Option == "HideOptions":
            for Location, Widget in self.WidgetsLocation.items():
                # S'il faut les afficher
                if not Value:
                    Widget.setVisible(True)

                # S'il faut les cacher
                else:
                    if not SoftExec[Location.replace("Location/", "")]:
                        Widget.setVisible(False)

    # ========================================================================
    def SubtitlesTranslation(self, All=False):
        """Fonction de traduction des actions de conversion des sous-titres."""
        ### Retraduction complète
        if All:
            Sub2Srt[1].setText(self.Trad["QtesseractConvertText"])
            Sub2Srt[1].setStatusTip(self.Trad["QtesseractConvertStatusTip"])
            Sup2Sub[1].setText(self.Trad["FFMpegConvertText"])
            Sup2Sub[1].setStatusTip(self.Trad["FFMpegConvertStatusTip"])
            Sup2Sub[2].setText(self.Trad["BDSup2SubConvertText"])
            Sup2Sub[2].setStatusTip(self.Trad["BDSup2SubConvertStatusTip"])
            Sub2Srt[2].setText(self.Trad["QtesseractOpenText"])
            Sub2Srt[2].setStatusTip(self.Trad["QtesseractOpenStatusTip"])
            Sup2Sub[3].setText(self.Trad["BDSup2SubOpenText"])
            Sup2Sub[3].setStatusTip(self.Trad["BDSup2SubOpenStatusTip"])

        ### Gestion des bonnes info bulles
        if not QFileInfo(Configs.value("Location/Qtesseract5").split(" -")[0]).exists():
            Sub2Srt[1].setToolTip(self.Trad["QtesseractConvertToolTip1"])
            Sub2Srt[2].setToolTip(self.Trad["QtesseractOpenToolTip1"])

        elif not SoftExec["Qtesseract5"]:
            Sub2Srt[1].setToolTip(self.Trad["QtesseractConvertToolTip2"])
            Sub2Srt[2].setToolTip(self.Trad["QtesseractOpenToolTip2"])

        else:
            Sub2Srt[1].setToolTip(self.Trad["QtesseractConvertToolTip3"])
            Sub2Srt[2].setToolTip(self.Trad["QtesseractOpenToolTip3"])

        if not QFileInfo(Configs.value("Location/FFMpeg").split(" -")[0]).exists():
            Sup2Sub[1].setToolTip(self.Trad["FFMpegConvertToolTip1"])

        elif not SoftExec["FFMpeg"]:
            Sup2Sub[1].setToolTip(self.Trad["FFMpegConvertToolTip2"])

        else:
            Sup2Sub[1].setToolTip(self.Trad["FFMpegConvertToolTip3"])

        if not QFileInfo(Configs.value("Location/BDSup2Sub").split(" -")[0]).exists():
            Sup2Sub[2].setToolTip(self.Trad["BDSup2SubConvertToolTip1"])
            Sup2Sub[3].setToolTip(self.Trad["BDSup2SubOpenToolTip1"])

        elif not SoftExec["BDSup2Sub"]:
            Sup2Sub[2].setToolTip(self.Trad["BDSup2SubConvertToolTip2"])
            Sup2Sub[3].setToolTip(self.Trad["BDSup2SubOpenToolTip2"])

        else:
            Sup2Sub[2].setToolTip(self.Trad["BDSup2SubConvertToolTip3"])
            Sup2Sub[3].setToolTip(self.Trad["BDSup2SubOpenToolTip3"])

    # ========================================================================
    def OptionLanguage(self, value):
        """Fonction modifiant en temps réel la traduction."""
        ### Mise à jour de la variable de la langue
        Configs.setValue("Language", value)

        ### Chargement du fichier QM de traduction (anglais utile pour les textes singulier/pluriel)
        appTranslator = QTranslator()  # Création d'un QTranslator

        ### Dans le cas d'une langue autre que anglais et qui existe
        if Configs.value("Language") in ("fr_FR", "cs_CZ", "de_DE", "es_ES", "it_IT", "tr_TR"):
            find = appTranslator.load(
                "Languages/MKVExtractorQt6_{}".format(Configs.value("Language")),
                AppFolder,
            )

            # Si le fichier n'a pas été trouvé, affiche une erreur et utilise la version anglaise
            if not find:
                Texts = {
                    "fr_FR": [
                        "Erreur de traduction",
                        "Aucun fichier de traduction <b>française</b> trouvé.<br/>Utilisation de la langue <b>anglaise</b>.",
                    ],
                    "cs_CZ": [
                        "Chyba překladu",
                        "No translation file <b>Czech</b> found. Use <b>English</b> language. Soubor s překladem do <b>češtiny</b> nenalezen. Použít <b>anglický</b> jazyk.",
                    ],
                    "de_DE": [
                        "Übersetzungsfehler",
                        "Keine <b>deutsche</b> Übersetzungsdatei gefunden.<br/>Die <b>englische</b> Sprache wird verwendet.",
                    ],
                    "es_ES": [
                        "Error de traducción",
                        "No se han encontrado archivos de traducción al <b>español</b>.<br>El idioma <b>inglés</b> utilizado.",
                    ],
                    "it_IT": [
                        "Errore di traduzione",
                        "Nessun file di traduzione <b>italiano</b> trovato.<br/>Verrà utilizzata la lingua <b>inglese</b>.",
                    ],
                    "tr_TR": [
                        "Çeviri hatası",
                        "<b>Türkçe</b> çeviri dosyası bulunamadı.<br><b>İngilizce dilini</b> kullanma.",
                    ],
                }

                QMessageBox(
                    QMessageBox.Critical,
                    Texts[Configs.value("Language")][0],
                    Texts[Configs.value("Language")][1],
                    QMessageBox.Close,
                    self,
                    Qt.WindowSystemMenuHint,
                ).exec()
                self.ui.lang_en.setChecked(True)
                Configs.setValue("Language", "en_US")

            # Sinon, chargement de la traduction
            else:
                app.installTranslator(appTranslator)

        ### Mise à jour du fichier langage de Qt
        translator_qt = QTranslator()  # Création d'un QTranslator
        if translator_qt.load(
            "qt_" + Configs.value("Language"),
            QLibraryInfo.path(QLibraryInfo.TranslationsPath),
        ):
            app.installTranslator(translator_qt)

        # [Claude] CORRECTION traduction QTextEditCustom : On appelle retranslate() sur le
        # widget reply_info après chaque changement de traducteur, pour que les textes du
        # menu contextuel du QTextEdit soient bien mis à jour dans la nouvelle langue.
        # Le hasattr seul suffit : si reply_info n'existe pas encore, on ne fait rien
        # (le retranslate() au démarrage est géré directement après la création du widget).
        if hasattr(self.ui, 'reply_info'):
            self.ui.reply_info.retranslate()

        ### Mise à jour du dictionnaire des textes
        # 008000 : vert                 0000c0 : bleu                           800080 : violet
        effet = """<span style=" color:#000000;">@=====@</span>"""
        self.Trad = {
            "AboutTitle": QCoreApplication.translate(
                "About", "About MKV Extractor Qt6"
            ),
            "AboutText": QCoreApplication.translate(
                "About",
                """<html><head/><body><p align="center"><span style=" font-size:12pt; font-weight:600;">MKV Extractor Qt6 v{}</span></p><p><span style=" font-size:10pt;">GUI to extract/edit/remux the tracks of a matroska (MKV) file.</span></p><p><span style=" font-size:10pt;">This program follows several others that were coded in Bash and it codec in python3 + Qt6.</span></p><p><span style=" font-size:8pt;">This software is licensed under </span><span style=" font-size:8pt; font-weight:600;"><a href="{}">GNU GPL v3</a></span><span style=" font-size:8pt;">.</span></p><p>Software's page on <a href="https://github.com/Hizoka76/MKV-Extractor-Qt6"><span style=" text-decoration: underline; color:#0057ae;">github</span></a>.</p><p>ppa's page on <a href="https://launchpad.net/~hizo/+archive/ubuntu/mkv-extractor-gui"><span style=" text-decoration: underline; color:#0057ae;">launchpad</span></a>.</p><p align="right">Created by <span style=" font-weight:600;">Belleguic Terence</span> (Hizoka), May 2025</p></body></html>""",
            ),
            "TheyTalkAboutTitle": QCoreApplication.translate(
                "TheyTalkAbout", "They talk about MKV Extractor Gui"
            ),
            "TheyTalkAboutText": QCoreApplication.translate(
                "TheyTalkAbout",
                """<html><head/><body><p><a href="http://sysads.co.uk/2014/09/install-mkv-extractor-qt-5-1-4-ubuntu-14-04/"><span style=" text-decoration: underline; color:#0057ae;">sysads.co.uk</span></a> (English)</p><p><a href="http://www.softpedia.com/reviews/linux/mkv-extractor-qt-review-496919.shtml"><span style=" text-decoration: underline; color:#0057ae;">softpedia.com</span></a> (English)</p><p><a href="http://linux.softpedia.com/get/Multimedia/Video/MKV-Extractor-Qt-103555.shtml"><span style=" text-decoration: underline; color:#0057ae;">linux.softpedia.com</span></a> (English)</p><p><a href="http://zenway.ru/page/mkv-extractor-qt"><span style=" text-decoration: underline; color:#0057ae;">zenway.ru</span></a> (Russian)</p><p><a href="http://linuxg.net/how-to-install-mkv-extractor-qt-5-1-4-on-ubuntu-14-04-linux-mint-17-elementary-os-0-3-deepin-2014-and-other-ubuntu-14-04-derivatives/"><span style=" text-decoration: underline; color:#2980b9;">linuxg.net</span></a> (English)</p><p><a href="http://la-vache-libre.org/mkv-extractor-gui-virer-les-sous-titres-inutiles-de-vos-fichiers-mkv-et-plus-encore/"><span style=" text-decoration: underline; color:#2980b9;">la-vache-libre.org</span></a> (French)</p><p><a href="http://passionexubuntu.altervista.org/index.php/it/kubuntu/1152-mkv-extractor-qt-vs-5-1-3-kde.html"><span style=" text-decoration: underline; color:#2980b9;">passionexubuntu.altervista.org</span></a> (Italian)</p><p><a href="https://github.com/darealshinji/mkv-extractor-qt5"><span style=" text-decoration: underline; color:#2980b9;">an unofficial github </span></a>(English)</p><p><a href="https://gamblisfx.com/mkv-extractor-qt-5-2-1-extract-audio-and-video-from-mkv-files/"><span style=" text-decoration: underline; color:#2980b9;">gamblisfx.com</span></a><a href="https://github.com/darealshinji/mkv-extractor-qt5"><span style=" text-decoration: underline; color:#2980b9;"/></a>(English)</p><p><a href="https://aur.archlinux.org/packages/mkv-extractor-qt/"><span style=" text-decoration: underline; color:#2980b9;">An unofficial aur package</span></a></p><p><br/></p><p><br/></p><p><br/></p></body></html>""",
            ),
            "SysTrayQuit": QCoreApplication.translate("SysTray", "Quit"),
            "SysTrayFinishTitle": QCoreApplication.translate(
                "SysTray", "All commands have finished"
            ),
            "SysTrayStopTitle": QCoreApplication.translate(
                "SysTray", "All commands have canceled"
            ),
            "SysTrayErrorTitle": QCoreApplication.translate(
                "SysTray", "An error has occurred"
            ),
            "SysTrayFinishText": QCoreApplication.translate(
                "SysTray", "The <b>{}</b> command have finished its work."
            ),
            "SysTrayTotalFinishText": QCoreApplication.translate(
                "SysTray", "All commands have finished their work."
            ),
            "SysTrayTotalStopText": QCoreApplication.translate(
                "SysTray", "All commands have stopped their work."
            ),
            "SysTrayTotalErrorText": QCoreApplication.translate(
                "SysTray", "All commands have stopped their work due to an error."
            ),
            "WhatsUpTitle": QCoreApplication.translate(
                "WhatsUp", "MKV Extractor Qt6's changelog"
            ),
            "QTextEditStatusTip": QCoreApplication.translate(
                "Main", "Use the right click for view options."
            ),
            "LocationOK": QCoreApplication.translate("Main", "This location is valid."),
            "LocationKO": QCoreApplication.translate(
                "Main", "This location is not valid."
            ),
            "LocationNo": QCoreApplication.translate(
                "Main", "No location for this command."
            ),
            "LocationOKO": QCoreApplication.translate(
                "Main", "This location is valid but not executable."
            ),
            "LocationTitle": QCoreApplication.translate(
                "Main", "Please select the executable file"
            ),
            "AllFiles": QCoreApplication.translate("Main", "All compatible Files"),
            "MatroskaFiles": QCoreApplication.translate("Main", "Matroska Files"),
            "OtherFiles": QCoreApplication.translate(
                "Main", "Other files that need to be converted to mkv"
            ),
            "Convert0": QCoreApplication.translate("Main", "Do not ask again"),
            "Convert1": QCoreApplication.translate(
                "Main", "File needs to be converted"
            ),
            "Convert2": QCoreApplication.translate(
                "Main",
                "This file is not supported by MKVExtract.\nDo you want convert this file in mkv ?",
            ),
            "Convert3": QCoreApplication.translate("Main", "MKVMerge Warning"),
            "Convert4": QCoreApplication.translate(
                "Main",
                "A warning has occurred during the convertion of the file, read the feedback informations.",
            ),
            "Convert5": QCoreApplication.translate("Main", "Do not warn me"),
            "Convert6": QCoreApplication.translate(
                "Main", "Choose the out folder of the new mkv file"
            ),
            "FileExistsTitle": QCoreApplication.translate(
                "Main", "Already existing file"
            ),
            "FileExistsText": QCoreApplication.translate(
                "Main", "The <b>{}</b> is already existing, overwrite it?"
            ),
            "ErrorLastFileTitle": QCoreApplication.translate(
                "Errors", "The last file doesn't exist"
            ),
            "ErrorLastFileText": QCoreApplication.translate(
                "Errors",
                "You have checked the option who reload the last file to the launch of MKV Extractor Qt, but this last file doesn't exist anymore.",
            ),
            "ErrorArgTitle": QCoreApplication.translate("Errors", "Wrong arguments"),
            "ErrorArgExist": QCoreApplication.translate(
                "Errors", "The <b>{}</b> file given as argument does not exist."
            ),
            "ErrorArgNb": QCoreApplication.translate(
                "Errors", "<b>Too many arguments given:</b><br/> - {} "
            ),
            "ErrorConfigTitle": QCoreApplication.translate("Errors", "Wrong value"),
            "ErrorConfigText": QCoreApplication.translate(
                "Errors",
                "Wrong value for the <b>{}</b> option, MKV Extractor Qt will use the default value.",
            ),
            "ErrorConfigPath": QCoreApplication.translate(
                "Errors",
                "Wrong path for the <b>{}</b> option, MKV Extractor Qt will use the default path.",
            ),
            "ErrorQuoteTitle": QCoreApplication.translate(
                "Errors", "No way to open this file"
            ),
            "ErrorQuoteText": QCoreApplication.translate(
                "Errors",
                "The file to open contains quotes (\") in its name. It's impossible to open a file with this carac. Please rename it.",
            ),
            "ErrorSizeTitle": QCoreApplication.translate("Errors", "Space available"),
            "ErrorSize": QCoreApplication.translate(
                "Errors",
                "Not enough space available in the <b>{}</b> folder.<br/>It is advisable to have at least twice the size of free space on the disk file.<br>Free disk space: <b>{}</b>.<br>File size: <b>{}</b>.",
            ),
            "ErrorSizeAttachement": QCoreApplication.translate(
                "Errors",
                "Not enough space available in <b>{}</b> folder.<br/>Free space in the disk: <b>{}</b><br/>File size: <b>{}</b>.",
            ),
            "ErrorSizeButton1": QCoreApplication.translate(
                "Errors", "Change the directory"
            ),
            "ErrorSizeButton2": QCoreApplication.translate("Errors", "I don't care"),
            "ErrorSizeButton3": QCoreApplication.translate(
                "Errors", "I want stop this"
            ),
            "WaitWinTitle": QCoreApplication.translate(
                "WaitWindow", "Waiting for rework before re-encapsulation"
            ),
            "WaitWinText": QCoreApplication.translate(
                "WaitWindow",
                "The subtitle files are normally open.\nYou can make any changes you want to them.\nWhen finished, click on Continue.\n\nTo cancel the work and delete the created files, click on Stop.\n\nFile list:\n",
            ),
            "WaitWinButton1": QCoreApplication.translate("WaitWindow", "Continue"),
            "WaitWinButton2": QCoreApplication.translate("WaitWindow", "Stop"),
            "HelpTitle": QCoreApplication.translate("Help", "Help me!"),
            "HelpText": QCoreApplication.translate(
                "Help",
                """<html><head/><body><p align="center"><span style=" font-weight:600;">Are you lost? Do you need help? </span></p><p><span style=" font-weight:600;">Normally all necessary information is present: </span></p><p>- Read the informations in the status bar when moving the mouse on widgets </p><p>- Read the informations in some tooltips, wait 2-3 secondes on actions or buttons.</p><p><span style=" font-weight:600;">Though, if you need more information: </span></p><p>- Software's page on <a href="https://github.com/Hizoka76/MKV-Extractor-Qt6"><span style=" text-decoration: underline; color:#0057ae;">github</span></a>.</p><p> - ppa's page on <a href="https://launchpad.net/~hizo/+archive/ubuntu/mkv-extractor-gui"><span style=" text-decoration: underline; color:#0057ae;">launchpad</span></a>.</p><p>- Forum Ubuntu-fr.org: <a href="https://forum.ubuntu-fr.org/viewtopic.php?id=1508741"><span style=" text-decoration: underline; color:#0057ae;">topic</span></a></p><p>- My email address: <a href="mailto:hizo@free.fr"><span style=" text-decoration: underline; color:#0057ae;">hizo@free.fr </span></a></p><p><span style=" font-weight:600;">Thank you for your interest in this program.</span></p></body></html>""",
            ),
            "MKVMergeErrors": QCoreApplication.translate(
                "MKVMerge", "MKVMerge returns errors during the read of the MKV file."
            ),
            "MKVMergeWarning": QCoreApplication.translate(
                "MKVMerge", "MKVMerge returns warning during the read of the MKV file."
            ),
            "AlreadyExistsTest": QCoreApplication.translate(
                "Main", "Skip the existing file test."
            ),
            "AudioQuality": QCoreApplication.translate(
                "Main", "Quality of the ac3 file converted."
            ),
            "AudioBoost": QCoreApplication.translate(
                "Main", "Power of the ac3 file converted."
            ),
            "CheckSizeCheckbox": QCoreApplication.translate(
                "Main", "Skip the free space disk test."
            ),
            "DelTempFiles": QCoreApplication.translate(
                "Main", "Delete temporary files."
            ),
            "DebugMode": QCoreApplication.translate(
                "Main", "View more informations in feedback box."
            ),
            "ConfirmErrorLastFile": QCoreApplication.translate(
                "Main", "Remove the error message if the last file doesn't exist."
            ),
            "Feedback": QCoreApplication.translate(
                "Main", "Show or hide the information feedback box."
            ),
            "FeedbackBlock": QCoreApplication.translate(
                "Main", "Anchor or loose information feedback box."
            ),
            "FolderParentTemp": QCoreApplication.translate(
                "Main",
                "The folder to use for extract temporaly the attachements file to view them.",
            ),
            "FFMpeg": QCoreApplication.translate(
                "Main", "Use FFMpeg for the conversion."
            ),
            "LastFile": QCoreApplication.translate(
                "Main",
                "Keep in memory the last file opened for open it at the next launch of MKV Extractor Qt.",
            ),
            "HideOptions": QCoreApplication.translate(
                "Main", "Hide the disabled options."
            ),
            "MMGorMEQ": QCoreApplication.translate(
                "Main", "Software to use for just encapsulate."
            ),
            "MMGorMEQCheckbox": QCoreApplication.translate(
                "Main", "Skip the proposal to software to use."
            ),
            "ConfirmConvert": QCoreApplication.translate(
                "Main", "Skip the confirmation of the conversion."
            ),
            "ConfirmWarning": QCoreApplication.translate(
                "Main", "Hide the information of the conversion warning."
            ),
            "InputFolder": QCoreApplication.translate(
                "Main", "Folder of the MKV files."
            ),
            "OutputFolder": QCoreApplication.translate(
                "Main", "Output folder for the new MKV files."
            ),
            "Language": QCoreApplication.translate("Main", "Software language to use."),
            "RecentInfos": QCoreApplication.translate(
                "Main",
                "Remove the Qt file who keeps the list of the recent files for the window selection.",
            ),
            "OutputSameFolder": QCoreApplication.translate(
                "Main", "Use the same input and output folder."
            ),
            "RemuxRename": QCoreApplication.translate(
                "Main", "Automatically rename the output file name in MEG_FileName."
            ),
            "AudioStereo": QCoreApplication.translate(
                "Main", "Switch to stereo during conversion."
            ),
            "SubtitlesOpen": QCoreApplication.translate(
                "Main", "Opening subtitles before encapsulation."
            ),
            "SysTray": QCoreApplication.translate(
                "Main", "Display or hide the system tray icon."
            ),
            "SysTrayMinimise": QCoreApplication.translate(
                "Main",
                "Minimize the window when it closed with the X and when the systray is enabled.",
            ),
            "WindowAspect": QCoreApplication.translate(
                "Main",
                "Keep in memory the aspect and the position of the window for the next opened.",
            ),
            "QtStyle": QCoreApplication.translate("Main", "Qt decoration."),
            "OptionsDTStoAC31": QCoreApplication.translate("Options", "Convert in AC3"),
            "OptionsDTStoAC32": QCoreApplication.translate(
                "Options", "Convert audio tracks automatically to AC3."
            ),
            "OptionsFFMpeg": QCoreApplication.translate(
                "Options", "Use FFMpeg for the conversion."
            ),
            "OptionsFFMpegStatusTip": QCoreApplication.translate(
                "Options", "If FFMpeg and AvConv are installed, use FFMpeg."
            ),
            "OptionsPowerList": QCoreApplication.translate(
                "Options", "Increase the sound power"
            ),
            "OptionsPowerX": QCoreApplication.translate(
                "Options",
                "Multiplying audio power by {}. A click on item checked uncheck all.",
            ),
            "OptionsPowerY": QCoreApplication.translate("Options", "Power x {}"),
            "OptionsQuality": QCoreApplication.translate(
                "Options", "List of available flow rates of conversion"
            ),
            "OptionsQualityX": QCoreApplication.translate(
                "Options",
                "Convert the audio quality in {} kbits/s. A click on item checked uncheck all.",
            ),
            "OptionsQualityY": QCoreApplication.translate("Options", "{} kbits/s"),
            "OptionsStereo1": QCoreApplication.translate(
                "Options", "Switch to stereo during conversion"
            ),
            "OptionsStereo2": QCoreApplication.translate(
                "Options",
                "The audio will not use the same number of channels, the audio will be stereo (2 channels).",
            ),
            "OptionsSub1": QCoreApplication.translate(
                "Options", "Opening subtitles before encapsulation"
            ),
            "OptionsSub2": QCoreApplication.translate(
                "Options",
                "Auto opening of subtitle srt files for correction. The software will be paused.",
            ),
            "OptionUpdate": QCoreApplication.translate(
                "Options",
                'New value for <span style=" color:#0000c0;">{}</span> option: <span style=" color:#0000c0;">{}</span>',
            ),
            "OptionsStyles": QCoreApplication.translate("Options", "Use the {} style."),
            "MKVInfoText": QCoreApplication.translate(
                "Actions", "&View MKV information"
            ),
            "MKVInfoToolTip": QCoreApplication.translate(
                "Actions",
                '<html><head/><body><p><span style=" font-weight:600;">Why I can\'t use it?</span><br/>1) mkvtoolnix-gui needs to be install.<br/>2) Open a mkv file before execute command.</p></body></html>',
            ),
            "MKVInfoStatusTip": QCoreApplication.translate(
                "Actions", "Display information about the MKV file with mkvinfo."
            ),
            "MKVMergeText": QCoreApplication.translate("Actions", "&Edit MKV file"),
            "MKVMergeToolTip": QCoreApplication.translate(
                "Actions",
                '<html><head/><body><p><span style=" font-weight:600;">Why I can\'t use it?</span><br/>1) mkvtoolnix-gui needs to be install.<br/>2) Open a mkv file before execute command.</p></body></html>',
            ),
            "MKVMergeStatusTip": QCoreApplication.translate(
                "Actions", "Open the MKV file with mkvmerge GUI for more modifications."
            ),
            "MKValidatorText": QCoreApplication.translate("Actions", "&Check MKV file"),
            "MKValidatorToolTip": QCoreApplication.translate(
                "Actions",
                '<html><head/><body><p><span style=" font-weight:600;">Why I can\'t use it?</span><br/>1) mkvalidator needs to be install.<br/>2) Open a mkv file before execute command.</p></body></html>',
            ),
            "MKValidatorStatusTip": QCoreApplication.translate(
                "Actions",
                "Verify Matroska files for specification conformance with MKValidator.",
            ),
            "MKCleanText": QCoreApplication.translate("Actions", "&Optimize MKV file"),
            "MKCleanToolTip": QCoreApplication.translate(
                "Actions",
                '<html><head/><body><p><span style=" font-weight:600;">Why I can\'t use it?</span><br/>1) mkclean needs to be install.<br/>2) Open a mkv file before execute command.</p></body></html>',
            ),
            "MKCleanStatusTip": QCoreApplication.translate(
                "Actions", "Clean/Optimize Matroska files with MKClean."
            ),
            "MKViewText": QCoreApplication.translate("Actions", "&Play MKV file"),
            "MKViewToolTip": QCoreApplication.translate(
                "Actions",
                '<html><head/><body><p><span style=" font-weight:600;">Why I can\'t use it?</span><br/>1) Open a mkv file before execute command.</p></body></html>',
            ),
            "MKViewStatusTip": QCoreApplication.translate(
                "Actions", "Open the MKV file with the default application."
            ),
            "MKVExecute2Text": QCoreApplication.translate(
                "Actions", "&Start job queue"
            ),
            "MKVExecute2ToolTip": QCoreApplication.translate(
                "Actions",
                '<html><head/><body><p><span style=" font-weight:600;">Why I can\'t use it?</span><br/>1) Open a mkv file.<br/>2) Tick tracks before execute command.</p></body></html>',
            ),
            "MKVExecute2StatusTip": QCoreApplication.translate(
                "Actions", "Launch extract/convert/mux tracks."
            ),
            "PauseText": QCoreApplication.translate("Actions", "Pause"),
            "PauseStatusTip": QCoreApplication.translate(
                "Actions", "Press button to pause the jobs."
            ),
            "PauseErrorStatusTip": QCoreApplication.translate(
                "Actions", "The pause button needs python3 psutil2 module."
            ),
            "ResumeText": QCoreApplication.translate("Actions", "Resume"),
            "ResumeStatusTip": QCoreApplication.translate(
                "Actions", "Press button to resume the jobs."
            ),
            "SelectedFile": QCoreApplication.translate("Select", "Selected file: {}."),
            "SelectedFolder1": QCoreApplication.translate(
                "Select", "Selected folder: {}."
            ),
            "SelectedFolder2": QCoreApplication.translate(
                "Select",
                "Always use the same output folder as the input MKV file (automatically updated)",
            ),
            "SelectFileInCheckbox": QCoreApplication.translate(
                "Select",
                "Keep in memory the last file opened for open it at the next launch of MKV Extractor Qt (to use for tests)",
            ),
            "SelectFileIn": QCoreApplication.translate(
                "Select", "Select the input MKV File"
            ),
            "SelectFileOut": QCoreApplication.translate(
                "Select", "Select the output MKV file"
            ),
            "SelectFolder": QCoreApplication.translate(
                "Select", "Select the output folder"
            ),
            "UseMMGTitle": QCoreApplication.translate(
                "UseMMG", "MKV Merge Gui or MKV Extractor Qt ?"
            ),
            "UseMMGText": QCoreApplication.translate(
                "UseMMG",
                "You want extract and reencapsulate the tracks without use other options.\n\nIf you just need to make this, you should use MKVToolNix-Gui (previously mmg) who is more adapted for this job.\n\nWhat software do you want use ?\n",
            ),
            "RemuxRenameCheckBox": QCoreApplication.translate(
                "RemuxRename", "Always use the default file rename (MEG_FileName)"
            ),
            "RemuxRenameTitle": QCoreApplication.translate(
                "RemuxRename", "Choose the output file name"
            ),
            "Audio": QCoreApplication.translate("Track", "audio"),
            "Subtitles": QCoreApplication.translate("Track", "subtitles"),
            "Video": QCoreApplication.translate("Track", "video"),
            "TrackAac": QCoreApplication.translate(
                "Track", "If the remuxed file has reading problems, change this value."
            ),
            "TrackAudio": QCoreApplication.translate(
                "Track",
                "Change the language if it's not right. 'und' means 'Undetermined'.",
            ),
            "TrackAttachment": QCoreApplication.translate(
                "Track",
                "This track can be renamed and must contain an extension to avoid reading errors by clicking on the icon.",
            ),
            "TrackChapters": QCoreApplication.translate("Track", "chapters"),
            "TrackID1": QCoreApplication.translate(
                "Track", "Work with track number {}."
            ),  # Pour les pistes normales
            "TrackID2": QCoreApplication.translate(
                "Track", "Work with attachment number {}."
            ),  # Pour les fichiers joints
            "TrackID3": QCoreApplication.translate(
                "Track", "Work with {}."
            ),  # Pour les chapitres et les tags
            "TrackRename": QCoreApplication.translate(
                "Track", "This track can be renamed by doubleclicking."
            ),
            "TrackTags": QCoreApplication.translate("Track", "tags"),
            "TrackType": QCoreApplication.translate(
                "Track", "This track is a {} type and cannot be previewed."
            ),
            "TrackType2": QCoreApplication.translate(
                "Track", "This track is a {} type and can be previewed."
            ),
            "TrackTypeAttachment": QCoreApplication.translate(
                "Track",
                "This attachment file is a {} type, it can be extracted (speedy) and viewed by clicking.",
            ),
            "TrackVideo": QCoreApplication.translate(
                "Track",
                "Change the fps value if needed. Useful in case of audio lag. Normal : 23.976, 25.000 and 30.000.",
            ),
            "QtesseractConvertText": QCoreApplication.translate(
                "Qtesseract5", "Convert SUB files to SRT files"
            ),
            "QtesseractConvertStatusTip": QCoreApplication.translate(
                "Qtesseract5",
                "Convert the SUB files to SRT with Qtesseract5. A click on checked item uncheck it.",
            ),
            "QtesseractConvertToolTip1": QCoreApplication.translate(
                "Qtesseract5",
                "Qtesseract5 isn't installed, impossible to convert the SUB files.",
            ),
            "QtesseractConvertToolTip2": QCoreApplication.translate(
                "Qtesseract5",
                "Qtesseract5 isn't executable, impossible to convert the SUB files.",
            ),
            "QtesseractConvertToolTip3": QCoreApplication.translate(
                "Qtesseract5",
                "Convert the SUB files to SRT with Qtesseract5.\n A click on checked item uncheck it.",
            ),
            "QtesseractOpenText": QCoreApplication.translate(
                "Qtesseract5", "Open the SUB files in Qtesseract5"
            ),
            "QtesseractOpenStatusTip": QCoreApplication.translate(
                "Qtesseract5",
                "Open the SUB files in Qtesseract5. A click on checked item uncheck it.",
            ),
            "QtesseractOpenToolTip1": QCoreApplication.translate(
                "Qtesseract5",
                "Qtesseract5 isn't installed, impossible to open the SUB files with it.",
            ),
            "QtesseractOpenToolTip2": QCoreApplication.translate(
                "Qtesseract5",
                "Qtesseract5 isn't executable, impossible to open the SUB files with it.",
            ),
            "QtesseractOpenToolTip3": QCoreApplication.translate(
                "Qtesseract5",
                "Open the SUB files in Qtesseract5 gui for better configuration.\n A click on checked item uncheck it.",
            ),
            "QtesseractTitle": QCoreApplication.translate(
                "Qtesseract5", "Expected location of the SRT file"
            ),
            "QtesseractInfoText": QCoreApplication.translate(
                "Qtesseract5",
                "Since the SRT file is reused later, it must be saved under the address: {}",
            ),
            "FFMpegConvertText": QCoreApplication.translate(
                "FFMpeg", "Convert SUP/PGS files to SUB files"
            ),
            "FFMpegConvertStatusTip": QCoreApplication.translate(
                "FFMpeg",
                "Convert the SUP/PGS files to SUB files with FFMpeg. A click on checked item uncheck it.",
            ),
            "FFMpegConvertToolTip1": QCoreApplication.translate(
                "FFMpeg",
                "FFMpeg isn't installed, impossible to convert the SUP/PGS files with it.",
            ),
            "FFMpegConvertToolTip2": QCoreApplication.translate(
                "FFMpeg",
                "FFMpeg isn't executable, impossible to convert the SUP/PGS files with it.",
            ),
            "FFMpegConvertToolTip3": QCoreApplication.translate(
                "FFMpeg",
                "Convert the SUP/PGS files to SUB files with FFMpeg.\nA click on checked item uncheck it.",
            ),
            "BDSup2SubConvertText": QCoreApplication.translate(
                "BDSup2Sub", "Convert SUP/PGS files to SUB files"
            ),
            "BDSup2SubConvertStatusTip": QCoreApplication.translate(
                "BDSup2Sub",
                "Convert the SUP/PGS files to SUB files with BDSup2Sub. A click on checked item uncheck it.",
            ),
            "BDSup2SubConvertToolTip1": QCoreApplication.translate(
                "BDSup2Sub",
                "BDSup2Sub isn't installed, impossible to convert the SUP/PGS files with it.",
            ),
            "BDSup2SubConvertToolTip2": QCoreApplication.translate(
                "BDSup2Sub",
                "BDSup2Sub isn't executable, impossible to convert the SUP/PGS files with it.",
            ),
            "BDSup2SubConvertToolTip3": QCoreApplication.translate(
                "BDSup2Sub",
                "Convert the SUP/PGS files to SUB files with BDSup2Sub.\nA click on checked item uncheck it.",
            ),
            "BDSup2SubOpenText": QCoreApplication.translate(
                "BDSup2Sub", "Open the SUP/PGS files in BDSup2Sub"
            ),
            "BDSup2SubOpenStatusTip": QCoreApplication.translate(
                "BDSup2Sub",
                "Open SUP/PGS files in BDSup2Sub. A click on checked item uncheck it.",
            ),
            "BDSup2SubOpenToolTip1": QCoreApplication.translate(
                "BDSup2Sub",
                "BDSup2Sub isn't installed, impossible to open SUP/PGS files to SUB files.",
            ),
            "BDSup2SubOpenToolTip2": QCoreApplication.translate(
                "BDSup2Sub",
                "BDSup2Sub isn't executable, impossible to open SUP/PGS files to SUB files.",
            ),
            "BDSup2SubOpenToolTip3": QCoreApplication.translate(
                "BDSup2Sub",
                "Open the SUP/PGS files in BDSup2Sub gui for better configuration.\nA click on checked item uncheck it.",
            ),
            "BDSup2SubTitle": QCoreApplication.translate(
                "BDSup2Sub", "Expected location of the IDX file"
            ),
            "BDSup2SubInfoText": QCoreApplication.translate(
                "BDSup2Sub",
                "Since the IDX file is reused later, it must be saved under the address: {}",
            ),
            "Header1": QCoreApplication.translate(
                "Tracks", "Click here to (un)select all tracks."
            ),
            "Header2": QCoreApplication.translate(
                "Tracks",
                "Icon of the tracks, the attachments icons are clickable to view them.",
            ),
            "Header3": QCoreApplication.translate(
                "Tracks",
                "Name or information of the tracks. It's possible to edit them by double click.",
            ),
            "Header4": QCoreApplication.translate(
                "Tracks",
                "Audio and subtitles language or fps of the videos can be modified. Size of the attached files.",
            ),
            "Header5": QCoreApplication.translate(
                "Tracks",
                "Codec or extension of the tracks. Only codec AAC can be modified.",
            ),
            "TempFolderDeniedTitle": QCoreApplication.translate(
                "TempFolder", "Permission denied !"
            ),
            "TempFolderDeniedText": QCoreApplication.translate(
                "TempFolder",
                "Permission denied for the creation of the temporary folder !<br>You haven't the permission to create: <b>{}</b><br><br>Use of default value: <b>{}</b>",
            ),
            "TempFolderNoExistsTitle": QCoreApplication.translate(
                "TempFolder", "Folder no exists !"
            ),
            "TempFolderNoExistsText": QCoreApplication.translate(
                "TempFolder",
                "The folder to use as temp folder not exists !<br>The invalid folder: <b>{}</b><br><br>Use of default value: <b>{}</b>",
            ),
            "TempFolderErrorTitle": QCoreApplication.translate(
                "TempFolder", "Error while creating the temporary folder !"
            ),
            "TempFolderErrorText": QCoreApplication.translate(
                "TempFolder",
                "An error occurred while creating the temporary folder: <b>{}</b><br><br>Use of default value: <b>{}</b>",
            ),
            "WorkFileCheckTitle": QCoreApplication.translate("Work", "Files missing !"),
            "WorkFileCheckText": QCoreApplication.translate(
                "Work",
                "The following files are missing for the proper execution of the command:\n - {}",
            ),
            "WorkTestTitle": QCoreApplication.translate("Work", "{} problem !"),
            "WorkTestText": QCoreApplication.translate(
                "Work",
                "<b>{}</b> is the base of this software,<br>this command is <b>mandatory</b> !<br><br>To configure the command,<br>go to <b>Options > Softwares locations</b>.",
            ),
            "WorkCanceled": effet
            + QCoreApplication.translate("Work", " All commands were canceled ")
            + effet,
            "WorkCmd": QCoreApplication.translate(
                "Work", """Command execution: <span style=" color:#0000c0;">{}</span>"""
            ),
            "WorkError": effet
            + QCoreApplication.translate("Work", " The last command returned an error ")
            + effet,
            "WorkWarning": effet
            + QCoreApplication.translate(
                "Work", " The last command returned an warning "
            )
            + effet,
            "WorkFinished": effet
            + QCoreApplication.translate("Work", " {} execution is finished ")
            + effet,
            "WorkMerge": effet
            + QCoreApplication.translate("Work", " Load of MKV File Tracks ")
            + effet,
            "WorkProgress": effet
            + QCoreApplication.translate("Work", " {} execution in progress ")
            + effet,
        }

        ### Recharge les textes de l'application graphique du fichier ui.py
        self.ui.retranslateUi(self)

        ### Mise au propre du widget de retour d'info et envoie de langue
        if not TempValues.value(
            "FirstRun"
        ):  # Variable évitant l'envoie inutile d'info au démarrage
            self.ui.reply_info.clear()

            if Configs.value("DebugMode"):
                self.SetInfo(
                    self.Trad["OptionUpdate"].format("Language", value), newline=True
                )

        else:
            TempValues.setValue("FirstRun", False)

        ### Recharge le SysTrayQuit
        self.SysTrayQuit.setText(self.Trad["SysTrayQuit"])

        ### Message spécifique si le bouton pause n'est pas utilisable
        if not "psutil" in globals():
            self.ui.mkv_pause.setStatusTip(self.Trad["PauseErrorStatusTip"])

        ### Recharge les actions
        self.mkv_info.setText(self.Trad["MKVInfoText"])
        self.mkv_info.setToolTip(self.Trad["MKVInfoToolTip"])
        self.mkv_info.setStatusTip(self.Trad["MKVInfoStatusTip"])

        self.mkv_mkvtoolnix.setText(self.Trad["MKVMergeText"])
        self.mkv_mkvtoolnix.setToolTip(self.Trad["MKVMergeToolTip"])
        self.mkv_mkvtoolnix.setStatusTip(self.Trad["MKVMergeStatusTip"])

        self.mk_validator.setText(self.Trad["MKValidatorText"])
        self.mk_validator.setToolTip(self.Trad["MKValidatorToolTip"])
        self.mk_validator.setStatusTip(self.Trad["MKValidatorStatusTip"])

        self.mk_clean.setText(self.Trad["MKCleanText"])
        self.mk_clean.setToolTip(self.Trad["MKCleanToolTip"])
        self.mk_clean.setStatusTip(self.Trad["MKCleanStatusTip"])

        self.mkv_view.setText(self.Trad["MKViewText"])
        self.mkv_view.setToolTip(self.Trad["MKViewToolTip"])
        self.mkv_view.setStatusTip(self.Trad["MKViewStatusTip"])

        self.mkv_execute_2.setText(self.Trad["MKVExecute2Text"])
        self.mkv_execute_2.setToolTip(self.Trad["MKVExecute2ToolTip"])
        self.mkv_execute_2.setStatusTip(self.Trad["MKVExecute2StatusTip"])

        ### Recharger les statustip des headers
        self.ui.mkv_tracks.horizontalHeaderItem(1).setStatusTip(self.Trad["Header1"])
        self.ui.mkv_tracks.horizontalHeaderItem(2).setStatusTip(self.Trad["Header2"])
        self.ui.mkv_tracks.horizontalHeaderItem(3).setStatusTip(self.Trad["Header3"])
        self.ui.mkv_tracks.horizontalHeaderItem(4).setStatusTip(self.Trad["Header4"])
        self.ui.mkv_tracks.horizontalHeaderItem(5).setStatusTip(self.Trad["Header5"])

        ### Recharge les textes des toolbutton
        self.option_ffmpeg.setText(self.Trad["OptionsFFMpeg"])
        self.option_ffmpeg.setStatusTip(self.Trad["OptionsFFMpegStatusTip"])
        self.option_ffmpeg.setToolTip(self.Trad["OptionsFFMpegStatusTip"])
        self.option_to_ac3.setText(self.Trad["OptionsDTStoAC31"])
        self.option_to_ac3.setStatusTip(self.Trad["OptionsDTStoAC32"])
        self.option_stereo.setText(self.Trad["OptionsStereo1"])
        self.PowerMenu.setTitle(self.Trad["OptionsPowerList"])
        self.RatesMenu.setTitle(self.Trad["OptionsQuality"])
        self.option_subtitles_open.setText(self.Trad["OptionsSub1"])
        self.option_subtitles_open.setStatusTip(self.Trad["OptionsSub2"])
        self.option_stereo.setStatusTip(self.Trad["OptionsStereo2"])
        self.ui.reply_info.setStatusTip(self.Trad["QTextEditStatusTip"])

        for nb in [2, 3, 4, 5]:
            PowerList[nb].setText(self.Trad["OptionsPowerY"].format(nb))
            PowerList[nb].setStatusTip(self.Trad["OptionsPowerX"].format(nb))

        for nb in [128, 192, 224, 256, 320, 384, 448, 512, 576, 640]:
            QualityList[nb].setStatusTip(self.Trad["OptionsQualityX"].format(nb))
            QualityList[nb].setText(self.Trad["OptionsQualityY"].format(nb))

        for Style in QtStyleList.keys():
            QtStyleList[Style].setStatusTip(self.Trad["OptionsStyles"].format(Style))

        ### Recharge les emplacements des exécutables
        self.SoftwareFinding()

        ### Traduction des actions de conversion des sous titres
        self.SubtitlesTranslation(True)

        ### Si un dossier de sortie a déjà été sélectionné, mise à jour du statustip et affiche l'info
        if Configs.value("OutputFolder"):
            self.ui.output_folder.setStatusTip(
                self.Trad["SelectedFolder1"].format(Configs.value("OutputFolder"))
            )
            self.SetInfo(
                self.Trad["SelectedFolder1"].format(
                    '<span style=" color:#0000c0;">'
                    + Configs.value("OutputFolder")
                    + "</span>"
                ),
                newline=True,
            )

        ### Si un fichier mkv à déjà été chargé, relance le chargement du fichier pour tout traduire et remet en place les cases et boutons cochés
        if TempValues.value("MKVLoaded"):
            ## Crée la liste des boutons cochés
            WidgetsList = []
            for Widget in [
                self.ui.option_reencapsulate,
                self.ui.option_subtitles,
                self.ui.option_audio,
            ]:
                if Widget.isChecked():
                    WidgetsList.append(Widget)

            ## Relance le chargement du fichier mkv pour tout traduire
            self.InputFile(Configs.value("InputFile"))

            ## Recoche les pistes qui l'étaient, crée une liste car MKVDicoSelect sera modifié pendant la boucle
            for x in list(MKVDicoSelect.keys()):
                self.ui.mkv_tracks.item(x, 1).setCheckState(Qt.Checked)

            ## Recoche les boutons
            for Widget in WidgetsList:
                Widget.setChecked(True)

    # ========================================================================
    def SetInfo(self, text, color="000000", center=False, newline=False):
        """Fonction mettant en page les infos à afficher dans le widget d'information."""
        ### Saut de ligne à la demande si le widget n'est pas vide
        if newline and self.ui.reply_info.toPlainText() != "":
            self.ui.reply_info.append("")

        ### Envoie du nouveau texte avec mise en page
        if center:
            self.ui.reply_info.append(
                """<center><table><tr><td><span style=" color:#{};">{}</span></td></tr></table></center>""".format(
                    color, text
                )
            )

        else:
            self.ui.reply_info.append(
                """<span style=" color:#{};">{}</span>""".format(color, text)
            )

        ### Force l'affichage de la dernière ligne
        self.ui.reply_info.moveCursor(QTextCursor.End)

    # ========================================================================
    def Configuration(self):
        """Fonction affichant les options et leur valeurs."""
        ### Bloque la connexion pour éviter les messages d'erreur
        self.ui.configuration_table.blockSignals(True)

        ### Nécessaire à l'affichage des statustip
        self.ui.configuration_table.setMouseTracking(True)

        ### Affichage et nettoyage du tableau des pistes
        if self.ui.stackedMiddle.currentIndex() != 1:
            self.ui.stackedMiddle.setCurrentIndex(1)

        while self.ui.configuration_table.rowCount() != 0:
            self.ui.configuration_table.removeRow(0)

        ### Remplissage du tableau, chaque ligne renvoie (num_de_ligne, (Key, Value))
        for x, (Key, Value) in enumerate(DefaultValues.items()):
            # Création de la ligne
            self.ui.configuration_table.insertRow(x)

            # Remplissage de la ligne (nom, valeur, valeur par défaut)
            self.ui.configuration_table.setItem(x, 0, QTableWidgetItem(Key))

            # Valeur actuelle
            Item = QTableWidgetItem(str(Configs.value(Key)))

            # Mise en gras si la valeur actuelle diffère de celle par défaut
            if str(Value).lower() != str(Configs.value(Key)).lower():
                Font = QFont()
                Font.setBold(True)
                Item.setFont(Font)

            self.ui.configuration_table.setItem(x, 1, QTableWidgetItem(Item))
            self.ui.configuration_table.setItem(x, 2, QTableWidgetItem(str(Value)))

            # Blocage de la modification
            self.ui.configuration_table.item(x, 0).setFlags(
                Qt.NoItemFlags | Qt.ItemIsEnabled
            )
            self.ui.configuration_table.item(x, 2).setFlags(
                Qt.NoItemFlags | Qt.ItemIsEnabled
            )

            # Si c'est la variable d'un exécutable, on cache la ligne
            if Key[0:8] == "Location":
                self.ui.configuration_table.setRowHidden(x, True)

            # Sinon on envoie du statustip
            else:
                self.ui.configuration_table.item(x, 0).setStatusTip(self.Trad[Key])
                self.ui.configuration_table.item(x, 1).setStatusTip(self.Trad[Key])
                self.ui.configuration_table.item(x, 2).setStatusTip(self.Trad[Key])

        ### Visuel du tableau
        self.ui.configuration_table.sortItems(0)  # Rangement par ordre de nom d'option
        largeur = int(
            (self.ui.configuration_table.size().width() - 185) / 2
        )  # Calcul de la largeur
        self.ui.configuration_table.setColumnWidth(
            0, 160
        )  # Définition de la largeur de la colonne
        self.ui.configuration_table.setColumnWidth(
            1, largeur
        )  # Définition de la largeur de la colonne
        self.ui.configuration_table.setColumnWidth(
            2, largeur
        )  # Définition de la largeur de la colonne
        self.ui.configuration_table.setSortingEnabled(False)  # Blocage du rangement

        ### Débloque la connexion
        self.ui.configuration_table.blockSignals(False)

    # ========================================================================
    def ConfigurationEdit(self, Item):
        """Fonction de mise à jour de la configuration."""
        ### Récupération de la cellule modifiée et des valeurs
        x = self.ui.configuration_table.row(Item)
        Option = self.ui.configuration_table.item(x, 0).text()
        Value = self.ui.configuration_table.item(x, 1).text()

        ### Si la valeur est vide, on utilise celle par défaut
        if not Value:
            Value = self.ui.configuration_table.item(x, 2).text()
            self.ui.configuration_table.setItem(x, 1, QTableWidgetItem(Value))

        ### Vérifie la classe et corrige si besoin de la valeur
        ## En cas de type bool
        if isinstance(DefaultValues[Option], bool):
            # Pour gérer les vrai
            if Value.lower() == "true":
                self.OptionsValue(Option, True)

            # Pour gérer les faux
            elif Value.lower() == "false":
                self.OptionsValue(Option, False)

            # Si mauvaise valeur, on indique l'erreur et utilise la valeur par défaut
            else:
                # Message d'erreur
                QMessageBox(
                    QMessageBox.Critical,
                    self.Trad["ErrorConfigTitle"],
                    self.Trad["ErrorConfigText"].format(Option),
                    QMessageBox.Close,
                    self,
                    Qt.WindowSystemMenuHint,
                ).exec()

                # Modification du texte et donc de la valeur (ça relance cette fonction)
                self.ui.configuration_table.item(x, 1).setText(
                    str(DefaultValues[Option])
                )

        ## En cas de type int
        elif isinstance(DefaultValues[Option], int):
            # Essaie de convertir en int
            try:
                self.OptionsValue(Option, int(Value))

            # Si ça foire,  on indique l'erreur et utilise la valeur par défaut
            except (ValueError, TypeError, KeyError):
                # [Claude] AMÉLIORATION : bare except remplacé. ValueError/TypeError pour les
                # conversions de valeur échouées, KeyError si la clé Trad est absente.
                # Message d'erreur
                QMessageBox(
                    QMessageBox.Critical,
                    self.Trad["ErrorConfigTitle"],
                    self.Trad["ErrorConfigText"].format(Option),
                    QMessageBox.Close,
                    self,
                    Qt.WindowSystemMenuHint,
                ).exec()

                # Modification du texte et donc de la valeur (ça relance cette fonction)
                self.ui.configuration_table.item(x, 1).setText(
                    str(DefaultValues[Option])
                )

        ## En cas de type str
        else:
            # Si la valeur est une adresse existante, on converti en QFileInfo
            if QFileInfo(Value).exists():
                self.OptionsValue(Option, QFileInfo(Value))

            # En cas de modification du dossier temporaire
            if Option == "FolderParentTemp":
                self.OptionsValue(Option, Value)

                if not self.FolderTempCreate():
                    Item.setText(DefaultValues["FolderParentTemp"])

            # Sinon, c'est que c'est juste du texte
            else:
                # Si l'adresse est erronée
                if Option in ["OutputFolder", "InputFolder", "MKVConvertThisFolder"]:
                    # Message d'erreur
                    QMessageBox(
                        QMessageBox.Critical,
                        self.Trad["ErrorConfigTitle"],
                        self.Trad["ErrorConfigPath"].format(Option),
                        QMessageBox.Close,
                        self,
                        Qt.WindowSystemMenuHint,
                    ).exec()

                    # Modification du texte et donc de la valeur (ça relance cette fonction)
                    self.ui.configuration_table.item(x, 1).setText(
                        DefaultValues[Option]
                    )

                else:
                    self.OptionsValue(Option, str(Value))

        ### Mise en gras si la valeur actuelle diffère de celle par défaut
        Font = QFont()

        if str(Value) != str(DefaultValues[Option]):
            Font.setBold(True)

        else:
            Font.setBold(False)

        # setFont provoque un itemChanged et relance donc la fonction, il faut bloquer les signaux
        self.ui.configuration_table.blockSignals(True)
        Item.setFont(Font)
        self.ui.configuration_table.blockSignals(False)

    # ========================================================================
    def ConfigurationReset(self):
        """Fonction de réinitialisation des configs."""
        ### Utilisation de toutes les valeurs par défauts
        for Key, Value in DefaultValues.items():
            self.OptionsValue(Key, Value)

        ### Rechargement de la liste d'infos
        self.Configuration()

    # ========================================================================
    def FeedbackWidget(self, value):
        """Fonction appelée lors de l'ouverture et la fermeture du dockwidget."""
        ### Mise à jour de la variable
        Configs.setValue("Feedback", value)

        ### Mise à jour de la case à cocher
        self.ui.option_feedback.setChecked(value)

    # ========================================================================
    def HumanSize(self, Value):
        """Fonction rendant plus lisible les tailles."""
        ### Valeur finale
        HumanValue = ""

        ### Conversion dans une catégorie supérieure
        for count in ["Bytes", "KB", "MB", "GB"]:
            if Value > -1024.0 and Value < 1024.0:
                HumanValue = "%3.1f%s" % (Value, count)

            Value /= 1024.0

        if not HumanValue:
            HumanValue = "%3.1f%s" % (Value, "TB")

        ### Renvoie la valeur finale
        return HumanValue

    # ========================================================================
    def CheckSize(self, Folder, InputSize, OutputSize, Text):
        """Fonction vérifiant qu'il y a assez de place pour travailler."""
        ### Pas de test si valeur le demandant
        if Configs.value("CheckSizeCheckbox", False):
            return False

        ### Affiche un message s'il n'y a pas la double de la place
        if (InputSize * 2) > OutputSize:
            HumanInputSize = self.HumanSize(int(InputSize))
            HumanOutputSize = self.HumanSize(int(OutputSize))

            ## Création de la fenêtre d'information
            ChoiceBox = QMessageBox(
                QMessageBox.Warning,
                self.Trad["ErrorSizeTitle"],
                Text.format(TempValues.value(Folder), HumanOutputSize, HumanInputSize),
                QMessageBox.NoButton,
                self,
                Qt.WindowSystemMenuHint,
            )
            CheckBox = QCheckBox(self.Trad["Convert0"], ChoiceBox)
            Button1 = QPushButton(
                QIcon.fromTheme("folder-open", QIcon(":/img/folder-open.png")),
                self.Trad["ErrorSizeButton1"],
                ChoiceBox,
            )
            Button2 = QPushButton(
                QIcon.fromTheme("dialog-ok", QIcon(":/img/dialog-ok.png")),
                self.Trad["ErrorSizeButton2"],
                ChoiceBox,
            )
            Button3 = QPushButton(
                QIcon.fromTheme("process-stop", QIcon(":/img/process-stop.png")),
                self.Trad["ErrorSizeButton3"],
                ChoiceBox,
            )
            ChoiceBox.setCheckBox(CheckBox)  # Envoie de la checkbox
            ChoiceBox.addButton(Button3, QMessageBox.NoRole)  # Ajout du bouton
            ChoiceBox.addButton(Button2, QMessageBox.YesRole)  # Ajout du bouton
            ChoiceBox.addButton(Button1, QMessageBox.ApplyRole)  # Ajout du bouton
            Choice = ChoiceBox.exec()

            Configs.setValue("CheckSizeCheckbox", CheckBox.isChecked())

            ## Si on veut changer de répertoire
            if Choice == 2:
                # Affichage de la fenêtre
                FileDialogCustom = QFileDialogCustom(
                    self, self.Trad["SelectFolder"], TempValues.value(Folder)
                )
                OutputFolder = QFileInfo(
                    FileDialogCustom.createWindow(
                        "Folder",
                        "Open",
                        None,
                        Qt.Tool,
                        Language=Configs.value("Language"),
                    )
                )

                # Si un dossier a bien été indiqué
                if not OutputFolder.isDir():
                    return True

                else:
                    TempValues.setValue(Folder, OutputFolder.absoluteFilePath())

            ## Si on continue
            elif Choice == 1:
                return False

            ## Si on stoppe
            elif Choice == 0:
                return True

    # ========================================================================
    def FolderTempCreate(self):
        """Fonction créant le dossier temporaire."""
        ### Boucle permettant d'être sûr d'avoir un dossier de créé
        for x in range(0, 3):
            # Création du dossier temporaire
            self.FolderTempWidget = QTemporaryDir(
                Configs.value("FolderParentTemp") + "/mkv-extractor-qt6-"
            )

            # Suppression de l'auto suppression du dossier non adapté
            self.FolderTempWidget.setAutoRemove(False)

            # Si le dossier est valide, on l'enregistre et arrête la boucle
            if self.FolderTempWidget.isValid():
                TempValues.setValue(
                    "FolderTemp", self.FolderTempWidget.path()
                )  # Dossier temporaire
                return True

            elif self.FolderTempWidget.errorString() == "Permission denied":
                QMessageBox.critical(
                    self,
                    self.Trad["TempFolderDeniedTitle"],
                    self.Trad["TempFolderDeniedText"].format(
                        Configs.value("FolderParentTemp"),
                        DefaultValues["FolderParentTemp"],
                    ),
                )
                return False

            elif self.FolderTempWidget.errorString() == "No such file or directory":
                QMessageBox.critical(
                    self,
                    self.Trad["TempFolderNoExistsTitle"],
                    self.Trad["TempFolderNoExistsText"].format(
                        Configs.value("FolderParentTemp"),
                        DefaultValues["FolderParentTemp"],
                    ),
                )
                return False

        # Si on a pas réussi à créer le dossier temporaire
        QMessageBox.critical(
            self,
            self.Trad["TempFolderErrorTitle"],
            self.Trad["TempFolderErrorText"].format(
                Configs.value("FolderParentTemp"), DefaultValues["FolderParentTemp"]
            ),
        )
        return False

    # ========================================================================
    def AboutMKVExtractorQt6(self):
        """Fenêtre à propos de MKVExtractorQt6."""
        Win = QMessageBox(
            QMessageBox.NoIcon,
            self.Trad["AboutTitle"],
            self.Trad["AboutText"].format(
                app.applicationVersion(), "http://www.gnu.org/copyleft/gpl.html"
            ),
            QMessageBox.Close,
            self,
        )
        Win.setIconPixmap(
            QPixmap(
                QIcon()
                .fromTheme("mkv-extractor-qt6", QIcon(":/icons/mkv-extractor-qt6.webp"))
                .pixmap(128)
            )
        )
        Win.exec()

    # ========================================================================
    def HelpMKVExtractorQt6(self):
        """Fenêtre d'aide de MKVExtractorQt6."""
        Win = QMessageBox(
            QMessageBox.NoIcon,
            self.Trad["HelpTitle"],
            self.Trad["HelpText"],
            QMessageBox.Close,
            self,
        )
        Win.setIconPixmap(
            QPixmap(
                QIcon()
                .fromTheme("mkv-extractor-qt6", QIcon(":/icons/mkv-extractor-qt6.webp"))
                .pixmap(128)
            )
        )
        Win.exec()

    # ========================================================================
    def TheyTalkAbout(self):
        """Fenêtre "Ils en parlent" de MKVExtractorQt6."""
        Win = QMessageBox(
            QMessageBox.NoIcon,
            self.Trad["TheyTalkAboutTitle"],
            self.Trad["TheyTalkAboutText"],
            QMessageBox.Close,
            self,
        )
        Win.setIconPixmap(
            QPixmap(
                QIcon()
                .fromTheme("mkv-extractor-qt6", QIcon(":/icons/mkv-extractor-qt6.webp"))
                .pixmap(128)
            )
        )
        Win.exec()

    # ========================================================================
    def RemoveTempFiles(self):
        """Fonction supprimant les fichiers contenu dans la liste des fichiers temporaires."""
        ### Boucle supprimant les fichiers temporaires s'ils existent
        for Item in TempFiles:
            if QFileInfo(Item).exists() and QFileInfo(Item).isFile():
                QFile(Item).remove()

        ### Nettoyage de la liste des fichiers temporaires
        TempFiles.clear()

    # ========================================================================
    def RemoveAllTempFiles(self):
        """Fonction supprimant les fichiers contenu dans la liste des fichiers temporaires."""
        ### Boucle supprimant les fichiers temporaires s'ils existent
        for Item in AllTempFiles:
            if QFileInfo(Item).exists() and QFileInfo(Item).isFile():
                QFile(Item).remove()

        ### Nettoyage de la liste des fichiers temporaires
        AllTempFiles.clear()

    # ========================================================================
    def OutputFolder(self, OutputFolderTemp=None):
        """Fonction de sélection du dossier de sortie, est appelée via un clic ou via un glisser/déposer de dossier."""
        # OutputFolderTemp : Url au format texte

        if OutputFolderTemp == Configs.value("OutputFolder"):
            return

        ### En cas de lancement via l'interface graphique
        if not OutputFolderTemp:
            ## Création et coche si besoin de la checkbox
            CheckBox = QCheckBox(self.Trad["SelectedFolder2"])
            CheckBox.setChecked(Configs.value("OutputSameFolder"))

            ## Affichage de la fenêtre
            FileDialogCustom = QFileDialogCustom(
                self, self.Trad["SelectFolder"], Configs.value("OutputFolder")
            )
            OutputFolderTemp = FileDialogCustom.createWindow(
                "Folder", "Open", CheckBox, Qt.Tool, Language=Configs.value("Language")
            )

            ## Annulation du dialog (Échap ou fermeture) : ne rien modifier
            if not OutputFolderTemp:
                return

            ## Mise à jour de l'option
            Configs.setValue("OutputSameFolder", CheckBox.isChecked())

        ### Arrêt de la fonction si aucun fichier n'est sélectionné et qu'on n'utilise pas le même dossier de sorti
        if not QFileInfo(OutputFolderTemp).isDir() and not Configs.value(
            "OutputSameFolder"
        ):
            return

        ### Suite de la fonction
        # URL absolue au format texte
        OutputFolderTemp = QFileInfo(OutputFolderTemp).absoluteFilePath()

        # Mise à jour de la variable du dossier de sorti
        Configs.setValue("OutputFolder", OutputFolderTemp)

        # Mis à jour du statustip de l'item de changement de dossier
        self.ui.output_folder.setStatusTip(
            self.Trad["SelectedFolder1"].format(OutputFolderTemp)
        )

        # Envoie d'information en mode debug
        if Configs.value("DebugMode"):
            self.SetInfo(
                self.Trad["SelectedFolder1"].format(
                    '<span style=" color:#0000c0;">' + OutputFolderTemp + "</span>"
                ),
                newline=True,
            )

        ### Modifications graphiques
        # Cela n'a lieu que si un dossier et un fichier mkv sont choisis
        if TempValues.value("MKVLoaded") and MKVDicoSelect:
            self.ui.option_reencapsulate.setEnabled(True)  # Déblocage de widget
            self.ui.mkv_execute.setEnabled(True)  # Déblocage de widget
            self.mkv_execute_2.setEnabled(True)  # Déblocage de widget

            option_audio = False  # Blocage de widget
            option_subtitles = False  # Blocage de widget

            for valeurs in MKVDicoSelect.values():  # Boucle sur la liste des lignes
                # Recherche la valeur audio dans les sous listes
                if valeurs[2] == "audio-x-generic" and SoftExec["FFMpeg"]:
                    option_audio = True  # Déblocage de widget

                # Recherche la valeur vobsub dans les sous listes
                elif valeurs[-1] == "sub" and SoftExec["Qtesseract5"]:
                    option_subtitles = True  # Déblocage de widget

                elif valeurs[-1] in ("sup", "pgs") and (
                    SoftExec["BDSup2Sub"] or SoftExec["FFMpeg"]
                ):
                    option_subtitles = True  # Déblocage de widget

                # Arrêt de la boucle si on les 2 valeurs
                if option_audio and option_subtitles:
                    break

            # Mise à jour de l'état des widgets
            self.ui.option_audio.setEnabled(option_audio)
            self.ui.option_subtitles.setEnabled(option_subtitles)

    # ========================================================================
    def InputFile(self, MKVLinkTemp=None):
        """Fonction de sélection du fichier d'entrée."""
        # MKVLinkTemp : URL au format str

        ### Si aucun fichier n'est donné en argument
        if not MKVLinkTemp:
            ## Création du widget à ajouter à la boite
            BigWidget = QWidget()
            BigLayout = QVBoxLayout()
            CheckBox1 = QCheckBox(self.Trad["SelectFileInCheckbox"], BigWidget)
            CheckBox1.setChecked(Configs.value("LastFile"))
            BigLayout.addWidget(CheckBox1)
            BigWidget.setLayout(BigLayout)

            ## Affichage de la fenêtre
            FileDialogCustom = QFileDialogCustom(
                self,
                self.Trad["SelectFileIn"],
                Configs.value("InputFolder"),
                "{}(*.mk3d *.mka *.mks *.mkv *.webm *.webma *.webmv);; {}(*.avi *.m4a *.mp4 *.nut *.ogg *.ogm *.ogv);; {}(*.avi *.m4a *.mk3d *.mka *.mks *.mkv *.mp4 *.nut *.ogg *.ogm *.ogv *.webm *.webma *.webmv)".format(
                    self.Trad["MatroskaFiles"],
                    self.Trad["OtherFiles"],
                    self.Trad["AllFiles"],
                ),
            )
            MKVLinkTemp = FileDialogCustom.createWindow(
                "File", "Open", BigWidget, Qt.Tool, Language=Configs.value("Language")
            )

            ## Mise à jour de l'option
            Configs.setValue("LastFile", CheckBox1.isChecked())

        ### Transformation du type de la variable
        MKVLinkTemp = QFileInfo(MKVLinkTemp)

        ### Arrêt de la fonction si le fichier n'existe pas
        if not MKVLinkTemp.isFile():
            return

        ### Si le fichier nécessite une conversion en MKV
        if MKVLinkTemp.suffix().lower() in (
            "avi",
            "mp4",
            "m4a",
            "nut",
            "ogg",
            "ogm",
            "ogv",
        ):
            self.MKVConvert(
                MKVLinkTemp
            )  # Lancement de la conversion et la fonction sera relancée par WorkFinished

        ### Continuation de la fonction si un fichier est bien sélectionné
        else:
            # Mise à jour de variables
            Configs.setValue("InputFile", MKVLinkTemp.absoluteFilePath())
            Configs.setValue("InputFolder", MKVLinkTemp.absolutePath())

            # Envoie d'information quelque soit le mode de debug
            self.SetInfo(
                self.Trad["SelectedFile"].format(
                    '<span style=" color:#0000c0;">'
                    + Configs.value("InputFile")
                    + "</span>"
                )
            )

            # Mise à jour du statustip du menu d'ouverture d'un fichier MKV
            self.ui.input_file.setStatusTip(
                self.Trad["SelectedFile"].format(Configs.value("InputFile"))
            )

            # Dans le cas de l'utilisation de l'option SameFolder qui permet d'utiliser le même dossier en sorti qu'en entré
            if Configs.value("OutputSameFolder"):
                self.OutputFolder(Configs.value("InputFolder"))

            # Envoie d'information en mode debug de l'adresse du dossier de sortie s'il existe
            elif Configs.value("OutputFolder") and Configs.value("DebugMode"):
                self.SetInfo(
                    self.Trad["SelectedFolder1"].format(
                        '<span style=" color:#0000c0;">'
                        + Configs.value("OutputFolder")
                        + "</span>"
                    )
                )

            # Chargement du contenu du fichier MKV
            self.TracksLoad()

    # ========================================================================
    def SysTrayClick(self, event):
        """Fonction gérant les clics sur le system tray."""
        ### Si la fenêtre est cachée ou si elle n'a pas la main
        if not self.isVisible() or (not self.isActiveWindow() and self.isVisible()):
            self.show()
            self.activateWindow()

        ### Si la fenêtre est visible
        else:
            ## Blocage du widget des retours sinon, il se ferme
            self.ui.feedback_widget.blockSignals(True)
            self.hide()
            self.ui.feedback_widget.blockSignals(False)

    # ========================================================================
    def dragEnterEvent(self, event):
        """Fonction appelée à l'arrivée d'un fichier déposé sur la fenêtre."""
        # Impossible d'utiliser mimetypes car il ne reconnaît pas tous les fichiers...

        ### Récupération du nom du fichier
        try:
            Item = QFileInfo(event.mimeData().urls()[0].path())

        except (IndexError, Exception):
            # [Claude] AMÉLIORATION : bare except remplacé. IndexError si urls() est vide,
            # Exception générale pour les autres cas inattendus liés aux données MIME.
            event.ignore()
            return

        ### Acceptation de l'événement en cas de fichier et de fichier valide (pour le fichier d'entrée)
        if Item.isFile() and Item.suffix().lower() in (
            "m4a",
            "mk3d",
            "mka",
            "mks",
            "mkv",
            "mp4",
            "nut",
            "ogg",
            "ogm",
            "ogv",
            "webm",
            "webma",
            "webmv",
            "avi",
        ):
            event.accept()

        ### Acceptation de l'événement en cas de dossier (pour le dossier de sortie)
        elif Item.isDir():
            event.accept()

    # ========================================================================
    def dropEvent(self, event):
        """Fonction appelée à la dépose du fichier/dossier sur la fenêtre."""
        # Impossible d'utiliser mimetypes car il ne reconnaît pas tous les fichiers...

        ### Récupération du nom du fichier
        Item = QFileInfo(event.mimeData().urls()[0].path())

        ### En cas de fichier (pour le fichier d'entrée)
        if Item.isFile():
            ## Vérifie que l'extension fasse partie de la liste et lance la fonction d'ouverture du fichier MKV avec le nom du fichier
            if Item.suffix().lower() in (
                "mka",
                "mks",
                "mkv",
                "mk3d",
                "webm",
                "webmv",
                "webma",
            ):
                self.InputFile(Item.absoluteFilePath())

            ## Nécessite une conversion de la vidéo
            elif Item.suffix().lower() in ("avi", "mp4", "nut", "ogg"):
                self.MKVConvert(Item)

        ### Lancement de la fonction de gestion du dossier de sorti en cas de dossier (pour le dossier de sortie)
        elif Item.isDir():
            self.OutputFolder(Item.absoluteFilePath())

    # ========================================================================
    def resizeEvent(self, event):
        """Fonction qui resize le tableau à chaque modification de la taille de la fenêtre."""
        ### Resize de la liste des pistes
        largeur = int(
            (self.ui.mkv_tracks.size().width() - 50) / 3
        )  # Calcul pour définir la taille des colonnes
        self.ui.mkv_tracks.setColumnWidth(
            3, largeur + 30
        )  # Modification de la largeur des colonnes
        self.ui.mkv_tracks.setColumnWidth(
            4, largeur + 15
        )  # Modification de la largeur des colonnes

        ### Resize de la liste des options
        largeur = int(
            (self.ui.configuration_table.size().width() - 185) / 2
        )  # Calcul pour définir la taille des colonnes
        self.ui.configuration_table.setColumnWidth(
            0, 160
        )  # Modification de la largeur des colonnes
        self.ui.configuration_table.setColumnWidth(
            1, largeur
        )  # Modification de la largeur des colonnes
        self.ui.configuration_table.setColumnWidth(
            2, largeur
        )  # Modification de la largeur des colonnes

        ### Acceptation de l'événement
        event.accept()

    # ========================================================================
    def RebootButton(self):
        """Fonction appelée lors d'un clic droit sur le bouton quitter pour relancer le logiciel."""
        self.CloseMode = "Reboot"
        self.close()

    # ========================================================================
    def CloseButton(self):
        """Fonction appelée lors de la fermeture de la fenêtre par les boutons."""
        self.CloseMode = "Button"
        self.close()

    # ========================================================================
    def closeEvent(self, event):
        """Fonction exécutée à la fermeture de la fenêtre quelqu'en soit la méthode."""
        ### Mode minimise lors de la fermeture avec la croix et alt+F4
        if not self.CloseMode and Configs.value("SysTrayMinimise"):
            ## Blocage du widget des retours sinon, il se ferme
            self.ui.feedback_widget.blockSignals(True)
            self.hide()
            self.ui.feedback_widget.blockSignals(False)

            event.ignore()
            return

        ### Curseur de chargement
        self.setCursor(Qt.WaitCursor)

        ### Bloque les signaux sinon cela save toujours off
        self.ui.feedback_widget.blockSignals(True)

        ### Arrêt du travail en cours
        self.WorkStop("Close")

        ### Si l'option de suppression du fichier des fichiers et url récentes est activée, on l'efface
        if Configs.value("RecentInfos"):
            RecentFile = QFile(QDir.homePath() + "/.config/MKVExtractorQt6.pyrc")

            if RecentFile.exists():
                RecentFile.remove()

        ### Enregistrement de l'intérieur de la fenêtre (dockwidget)
        Configs.setValue("WinState", self.saveState())

        ### Si on a demandé à conserver l'aspect
        if Configs.value("WindowAspect"):
            Configs.setValue("WinGeometry", self.saveGeometry())

        ### Si on a rien demandé, on détruit la valeur
        elif Configs.contains("WinGeometry"):
            Configs.remove("WinGeometry")

        ### Suppression du dossier temporaire
        if self.FolderTempWidget.isValid():
            self.FolderTempWidget.remove()

        ### Acceptation de l'événement
        if self.CloseMode != "Reboot":
            event.accept()
            # [Claude] CORRECTION : Le setCursor(ArrowCursor) était placé APRÈS le bloc
            # if/else du reboot, ce qui le rendait inaccessible en mode Reboot puisque
            # execl() remplace le processus sans retour. Il est maintenant uniquement
            # appelé dans le chemin de fermeture normale (non-reboot).
            self.setCursor(Qt.ArrowCursor)

        ### Mode reboot
        else:
            python = sys.executable
            execl(python, python, *sys.argv)
            # Note : execl() remplace le processus courant, le code suivant n'est jamais atteint.


#############################################################################
if __name__ == "__main__":
    ### Informations sur l'application'
    app = QApplication(sys.argv)
    app.setApplicationVersion("26.10.18a")
    app.setApplicationName("MKV Extractor Qt6")

    ### Gestion de l'emplacement du logiciel
    # [Claude] Support PyInstaller : en mode "gelé" (sys.frozen), les données
    # embarquées (Languages/, QFileDialogCustom/) sont extraites dans sys._MEIPASS
    # et non à côté de sys.argv[0]. On utilise donc ce dossier comme racine.
    if getattr(sys, "frozen", False):
        AppFolder = sys._MEIPASS
    else:
        FileURL = QFileInfo(sys.argv[0])

        while FileURL.isSymLink():
            FileURL = QFileInfo(FileURL.symLinkTarget())

        AppFolder = FileURL.absolutePath()

    ### Création des dictionnaires et listes facilement modifiables partout
    # Dictionnaire qui contiendra toutes les pistes du fichier MKV
    MKVDico = {}  

    # Dictionnaire qui contiendra les sous titres à reconnaître manuellement
    MD5Dico = {}

    # Dictionnaire qui contiendra les pistes sélectionnées
    MKVDicoSelect = {}  

    # Liste qui contiendra et affichera dans les combobox les langues dispo (audio et sous titres)
    MKVLanguages = []

    # Dictionnaire qui contiendra les widgets de gestion de puissance de fichier AC3
    PowerList = {}

    # Dictionnaire qui contiendra les widgets de gestion de la qualité de fichier AC3
    QualityList = {}

    # Dictionnaire qui contiendra les styles possibles pour qt
    QtStyleList = {}  

     # Dictionnaire qui contiendra les widgets de conversion Sub en Srt
    Sub2Srt = {} 

    # Dictionnaire qui contiendra les widgets de conversion Sup en Sub
    Sup2Sub = {}  

    # Liste des fichiers temporaires pré ré-encapsulage ou conversion sous-titres
    TempFiles = []

    # Liste des fichiers créés en cas d'arrêt du travail
    AllTempFiles = []  

    # Liste des commandes à exécuter
    CommandList = []  

    # Adresse des fichiers sous titres à ouvrir avant l'encapsulage
    SubtitlesFiles = []  

    # Retour de mkvmerge en cas de warning
    WarningReply = []  

    # Pour éviter des appels multiples à SoftIsExec
    SoftExec = {}  

    # Mise à jour du dictionnaire des commandes exécutables
    for Soft in [
        "AvConv",
        "BDSup2Sub",
        "FFMpeg",
        "MKClean",
        "MKVExtract",
        "MKVInfo",
        "MKVMerge",
        "MKVToolNix",
        "MKValidator",
        "Qtesseract5",
    ]:
        SoftExec[Soft] = False

    ### Configs du logiciel
    # Valeurs par défaut des options générales, pas toutes (MMGorMEQ, les valeurs de la fenêtre, l'adresse du dernier fichier ouvert)
    DefaultValues = {
        "AlreadyExistsTest": False,  # Option ne signalant que le fichier existe déjà
        "CheckSizeCheckbox": False,  # Option ne signalant pas le manque de place
        "ConfirmErrorLastFile": False,  # Ne plus prévenir en cas d'absence de fichier au démarrage
        "DebugMode": False,  # Option affichant plus ou d'infos
        "DelTempFiles": True,  # Option de suppression des fichiers temporaires
        "Feedback": True,  # Option affichant ou non les infos de retours
        "FeedbackBlock": False,  # Option bloquant les infos de retours
        "FolderParentTemp": QDir.tempPath(),  # Dossier temporaire dans lequel extraire les pistes pour visualisation
        "HideOptions": False,  # Option cachant ou non les options inutilisables
        "LastFile": False,  # Option conservant en mémoire le dernier mkv ouvert
        "Location/AvConv": "",  # Adresses des logiciels
        "Location/BDSup2Sub": "",
        "Location/FFMpeg": "",
        "Location/MKClean": "",
        "Location/MKVInfo": "",
        "Location/MKVToolNix": "",
        "Location/MKVExtract": "",
        "Location/MKVMerge": "",
        "Location/MKValidator": "",
        "Location/Qtesseract5": "",
        "MMGorMEQ": "MEQ",  # Logiciel à utiliser entre MKVExtractorQt et mmg
        "MMGorMEQCheckbox": False,  # Valeur sautant la confirmation du choix de logiciel à utiliser
        "ConfirmConvert": False,  # Valeur sautant la confirmation de conversion
        "ConfirmWarning": False,  # Valeur sautant l'information du warning de conversion
        "InputFolder": QDir.homePath(),  # Dossier du fichier mkv d'entrée
        "OutputFolder": QDir.homePath(),  # Dossier de sortie
        "Language": QLocale.system().name(),  # Langue du système
        "RecentInfos": True,  # Option de suppression du fichier des fichiers et adresses récentes
        "RemuxRename": False,  # Renommer automatiquement le fichier de sorti remux
        "OutputSameFolder": True,  # Option d'utilisation du même dossier de sortie que celui du fichier mkv
        "SysTray": True,  # Option affichant l'icône du system tray
        "SysTrayMinimise": False,  # Option minimisant la fenêtre dans le systray lors de sa fermeture avec la croix
        "WindowAspect": True,  # Conserver la fenêtre et sa géométrie
        "QtStyle": QApplication.style().objectName(),  # Conserver la fenêtre et sa géométrie
    }

    ### Système de gestion des configurations QSettings
    # Création ou ouverture du fichier de config
    Configs = QSettings(
        QSettings.NativeFormat, QSettings.UserScope, "MKV Extractor Qt6"
    )

    # Gestion du bon type de variable
    # Boucle sur les valeurs par défaut
    for Key, Value in DefaultValues.items():
        # Si l'option n'existe pas, on l'ajoute au fichier avec la valeur de base
        if not Configs.contains(Key):
            Configs.setValue(Key, Value)

        # Si l'option existe, on la change dans le bon format
        else:
            try:
                KeyType = type(Value)

                # Si c'est censé ếtre un bool
                if KeyType is bool:
                    if Configs.value(Key).lower() == "true":
                        Configs.setValue(Key, True)

                    else:
                        Configs.setValue(Key, False)

                # Si ça doit être un int
                elif KeyType is int:
                    Configs.setValue(Key, int(Configs.value(Key)))

                # Si c'est un str diff de None et @Invalid()
                elif KeyType is str and Configs.value(Key).lower() not in (
                    "none",
                    "@invalid()",
                ):
                    Configs.setValue(Key, str(Configs.value(Key)))

                # Sinon, on réinitialise
                else:
                    Configs.setValue(Key, Value)

            # S'il y a un souci, la valeur est réinitialisée
            except (ValueError, AttributeError, TypeError):
                # [Claude] AMÉLIORATION : bare except remplacé par les exceptions pertinentes
                # lors de conversions de type (ValueError), accès sur None (AttributeError),
                # ou opération sur un type inattendu (TypeError).
                Configs.setValue(Key, Value)

    ### Valeurs temporaires
    # Valeurs par défaut des boutons et actions, pas toutes (MMGorMEQ, les valeurs de la fenêtre, l'adresse du dernier fichier ouvert)
    DefaultTempValues = {
        "AllTracks": False,
        "AudioConvert": False,
        "AudioBoost": 0,
        "AudioQuality": 0,
        "AudioStereo": False,
        "ChaptersFile": "",
        "Command": "",
        "DurationFile": 0,
        "FFMpeg": False,
        "FirstRun": True,
        "FolderTemp": "",
        "MKVLoaded": False,
        "OutputFile": "",
        "Qtesseract5Folder": "",
        "Sub2Srt": 0,
        "Sup2Sub": 0,
        "BDSup2Sub": False,
        "Reencapsulate": False,
        "SubtitlesConvert": False,
        "SubtitlesOpen": False,
        "SuperBlockTemp": False,
        "TagsFile": "",
        "TitleFile": "",
        # [Claude] BUG : Clé "SubtitlesConvert" dupliquée supprimée ici.
        # Python ne conserve que la dernière valeur d'une clé dupliquée dans un dict littéral,
        # la première occurrence était donc silencieusement ignorée.
        "WorkOldLine": "",
    }

    # [Claude] BUG : TempValues était instancié avec exactement les mêmes paramètres que Configs
    # (NativeFormat, UserScope, "MKV Extractor Qt6"), ce qui signifie qu'ils pointaient vers
    # le MÊME fichier de configuration sur disque. Les valeurs temporaires (états de session)
    # étaient donc mélangées et persistées avec les préférences utilisateur.
    # Correction : utiliser un nom d'application différent pour les valeurs temporaires,
    # ou mieux, utiliser un simple dictionnaire Python pour les données de session
    # qui n'ont pas besoin d'être persistées entre les lancements.
    # Solution retenue : nom distinct pour isoler les deux espaces de stockage.
    TempValues = QSettings(
        QSettings.NativeFormat, QSettings.UserScope, "MKV Extractor Qt6 Session"
    )

    # Chargement des valeurs par défaut
    for Key, Value in DefaultTempValues.items():
        TempValues.setValue(Key, Value)

    ### Lancement de l'application

    ### Remplissage du module state (partagé entre tous les mixins)
    state.app = app
    state.AppFolder = AppFolder
    state.Configs = Configs
    state.TempValues = TempValues
    state.MKVDico = MKVDico
    state.MKVDicoSelect = MKVDicoSelect
    state.MKVLanguages = MKVLanguages
    state.PowerList = PowerList
    state.QualityList = QualityList
    state.Sub2Srt = Sub2Srt
    state.Sup2Sub = Sup2Sub
    state.TempFiles = TempFiles
    state.AllTempFiles = AllTempFiles
    state.CommandList = CommandList
    state.SubtitlesFiles = SubtitlesFiles
    state.WarningReply = WarningReply
    state.SoftExec = SoftExec
    MKVExtractorQt6Class = MKVExtractorQt6()
    MKVExtractorQt6Class.setAttribute(Qt.WA_DeleteOnClose)
    sys.exit(app.exec())
