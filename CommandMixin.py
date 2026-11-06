#!/usr/bin/python3
# -*- coding: utf-8 -*-
"""Mixin de création des commandes d'extraction/conversion MKV."""

import state
from PySide6.QtCore import QFile, QFileInfo, QStorageInfo, Qt, QThread
from PySide6.QtWidgets import QCheckBox, QMessageBox, QPushButton
from PySide6.QtGui import QIcon
from QFileDialogCustom.QFileDialogCustom import QFileDialogCustom


class CommandMixin:
    # ========================================================================
    def CommandCreate(self):
        """Fonction créant toutes les commandes : mkvextractor, ffmpeg, mkvmerge..."""
        ### Test de la place restante
        FileSize = QFileInfo(state.Configs.value("InputFile")).size()
        FreeSpaceDisk = QStorageInfo(state.Configs.value("OutputFolder")).bytesAvailable()

        if self.CheckSize(
            "OutputFolder", FileSize, FreeSpaceDisk, self.Trad["ErrorSize"]
        ):
            return

        ### Mise au propre et initialisation de variables
        state.TempFiles.clear()  # Fichiers temporaires à effacer
        state.AllTempFiles.clear()  # Fichiers à effacer en cas d'arrêt
        SubConvert = []  # Conversion des sub en srt
        SupConvert = []  # Conversion des sup/pgs en sub
        mkvextract_track = []  # Commande d'extraction des pistes normales
        mkvextract_joint = []  # Commande d'extraction des fichiers joints
        dts_ffmpeg = []  # Commande de conversion DTS vers AC3
        mkvmerge = []  # Commande de réencapsulage
        mkvmerge_files = [
            state.Configs.value("InputFile")
        ]  # Liste des fichiers nécessaires à mkvmerge
        SubToRemove = []  # Liste pour ne pas ouvrir les idx convertis

        state.CommandList.clear()  # Liste des commandes à exécuter à la suite
        # str : Nom de la commande
        # str : Commande
        # list : Arguments de la commande
        # list : Fichiers dont il faut vérifier l'existence avant le lancement de la commande

        ### Si on veut uniquement ré-encapsuler sans rien d'autre, on affiche un message conseillant d'utiliser MKVToolNix-Gui
        if (
            state.TempValues.value("Reencapsulate")
            and not state.TempValues.value("AudioConvert")
            and not state.TempValues.value("SubtitlesConvert")
            and not state.TempValues.value("SubtitlesOpen")
        ):
            if not state.Configs.value("MMGorMEQCheckbox"):
                ## Création de la fenêtre
                UseMMG = QMessageBox(
                    QMessageBox.Question,
                    self.Trad["UseMMGTitle"],
                    self.Trad["UseMMGText"],
                    QMessageBox.Cancel,
                    self,
                    Qt.WindowSystemMenuHint,
                )
                UseMMG.setWindowFlags(
                    Qt.WindowTitleHint
                    | Qt.Dialog
                    | Qt.WindowMaximizeButtonHint
                    | Qt.CustomizeWindowHint
                )  # Enlève le bouton de fermeture de la fenêtre

                # Création des widgets à y mettre
                CheckBox = QCheckBox(
                    self.Trad["Convert0"], UseMMG
                )  # Création de la checkbox
                MMG = QPushButton(
                    QIcon.fromTheme("mkvmerge", QIcon(":/img/mkvmerge.png")),
                    "MKVToolNix-Gui",
                    UseMMG,
                )  # Création du bouton MKVToolNix-Gui
                MEQ = QPushButton(
                    QIcon.fromTheme(
                        "mkv-extractor-qt6", QIcon(":/icons/mkv-extractor-qt6.webp")
                    ),
                    "MKV Extractor Qt 6",
                    UseMMG,
                )  # Création du bouton MKV Extractor Qt

                # Remplissage de la fenêtre
                UseMMG.setCheckBox(CheckBox)  # Envoie de la checkbox
                UseMMG.addButton(MMG, QMessageBox.YesRole)  # Ajout du bouton
                UseMMG.addButton(MEQ, QMessageBox.NoRole)  # Ajout du bouton
                UseMMG.setDefaultButton(MEQ)  # Bouton par défaut : MKV Extractor Qt

                # Lancement de la fenêtre
                UseMMG.exec()  # Message d'information

                # Mise à jour de la variable
                state.Configs.setValue("MMGorMEQCheckbox", CheckBox.isChecked())

                # Mise à jour de la variable du logiciel à utiliser
                clicked = UseMMG.clickedButton()

                if clicked == MMG:
                    state.Configs.setValue("MMGorMEQ", "MMG")

                elif clicked == MEQ:
                    state.Configs.setValue("MMGorMEQ", "MEQ")

                else:
                    return

            # Si on veut utiliser MMG, on arrête là
            if state.Configs.value("MMGorMEQ") == "MMG":
                self.MKVMergeGui()
                return

        ### Boucle traitant les pistes une à une
        for Select in state.MKVDicoSelect.values():
            # Select[0] : ID
            # Select[1] : Type de piste : Track, Attachment, Chapters, Global
            # Select[2] : Icône
            # Select[3] : Icône de visualisation
            # Select[4] : Nom de la piste
            # Select[5] : Info : fps, langue...
            # Select[6] : Info : codec

            ## Traitement des pistes vidéos, mise à jour de commandes
            if Select[2] == "video-x-generic":
                # Ajout du fichier à la liste
                FileWithoutSlash = "{}_video_{}.mkv".format(
                    Select[0], Select[4].replace("/", "-")
                )
                File = "{}/{}".format(state.Configs.value("OutputFolder"), FileWithoutSlash)
                state.AllTempFiles.append(File)
                mkvmerge_files.append(File)

                # Code d'extraction des pistes
                mkvextract_track.append("{0[0]}:{1}".format(Select, File))

                # Code d'encapsulage
                mkvmerge.extend(
                    [
                        "--track-name",
                        "0:{0[4]}".format(Select),
                        "--default-duration",
                        "0:{0[5]}".format(Select),
                        "--compression",
                        "0:none",
                        File,
                    ]
                )

            ## Traitement des pistes audios
            elif Select[2] == "audio-x-generic":
                # Ajout du fichier à la liste
                FileWithoutSlash = "{}_audio_{}".format(
                    Select[0], Select[4].replace("/", "-")
                )
                File = "{}/{}.{}".format(
                    state.Configs.value("OutputFolder"), FileWithoutSlash, Select[6]
                )
                state.AllTempFiles.append(File)

                # En cas de modification audio
                if state.TempValues.value("AudioConvert") and (
                    state.TempValues.value("AudioBoost")
                    or state.TempValues.value("AudioStereo")
                    or state.TempValues.value("AudioQuality")
                    # [Claude] CORRECTION : AudioToAc3 est une option de session -> state.TempValues
                    or state.TempValues.value("AudioToAc3")
                ):

                    # Indique la piste audio
                    dts_ffmpeg.extend(["-vn", "-map", "0:{}".format(Select[0])])

                    # En cas de boost
                    if state.TempValues.value("AudioBoost"):
                        dts_ffmpeg.extend(
                            ["-af", "volume={}".format(state.TempValues.value("AudioBoost"))]
                        )

                    # En cas de passage en stéréo
                    if state.TempValues.value("AudioStereo"):
                        dts_ffmpeg.extend(["-ac", "2"])

                    # En cas de modification de qualité
                    if state.TempValues.value("AudioQuality"):
                        dts_ffmpeg.extend(
                            [
                                "-ab",
                                "{0}k".format(state.TempValues.value("AudioQuality", 128)),
                            ]
                        )

                    # En cas de passage en ac3
                    # [Claude] CORRECTION : AudioToAc3 est une option de session -> state.TempValues
                    if state.TempValues.value("AudioToAc3"):
                        File = "{}/{}.ac3".format(
                            state.Configs.value("OutputFolder"), FileWithoutSlash
                        )
                        dts_ffmpeg.extend(["-f", "ac3"])

                    # Fichier de sortie
                    dts_ffmpeg.append(File)

                    # Ajout du fichier de sortie dans la liste
                    state.AllTempFiles.append(File)
                    mkvmerge_files.append(File)

                # Si pas de modification audio
                else:
                    # Code d'extraction des pistes
                    mkvmerge_files.append(File)
                    mkvextract_track.append("{0[0]}:{1}".format(Select, File))

                # Code d'encapsulage
                Temp = [
                    "--track-name",
                    "0:{0[4]}".format(Select),
                    "--language",
                    "0:{0[5]}".format(Select),
                    "--compression",
                    "0:none",
                ]

                # Dans le cas où il faut ré-encapsuler des fichiers AAC, il faut préciser si sbr ou non
                if "aac" in Select[6]:
                    aac_is_sbr = "0:1"

                    if Select[6] == "aac sbr":
                        aac_is_sbr = "0:0"

                    Temp.extend(["--aac-is-sbr", aac_is_sbr])

                Temp.append(File)
                mkvmerge.extend(Temp)

            ## Traitement des pistes sous titres
            elif Select[2] == "text-x-generic":
                FileWithoutSlash = "{}_subtitles_{}".format(
                    Select[0], Select[4].replace("/", "-")
                )

                # Dans le cas de sous titres de fichiers sub
                if Select[6] == "sub":
                    # Ajout des fichiers à la liste
                    SUB = "{0}/{1}.sub".format(
                        state.Configs.value("OutputFolder"), FileWithoutSlash
                    )
                    IDX = "{0}/{1}.idx".format(
                        state.Configs.value("OutputFolder"), FileWithoutSlash
                    )

                    state.AllTempFiles.append(SUB)
                    state.AllTempFiles.append(IDX)

                    # Code d'extraction des pistes
                    mkvextract_track.append("{0[0]}:{1}".format(Select, IDX))

                    # Dans le cas d'un conversion de sous titres sub => srt
                    if state.TempValues.value("SubtitlesConvert") and state.TempValues.value(
                        "Sub2Srt"
                    ):
                        # Ajout du fichier à la liste
                        SRT = "{0}/{1}.srt".format(
                            state.Configs.value("OutputFolder"), FileWithoutSlash
                        )
                        # state.TempFiles.append(SRT)
                        state.AllTempFiles.append(SRT)

                        state.TempFiles.append(SUB)
                        state.TempFiles.append(IDX)

                        # Code d'encapsulage
                        mkvmerge_files.append(SRT)
                        mkvmerge.extend(
                            [
                                "--track-name",
                                "0:{0[4]}".format(Select),
                                "--language",
                                "0:{0[5]}".format(Select),
                                "--compression",
                                "0:none",
                                SRT,
                            ]
                        )

                        # Différence de nom entre la langue de tesseract et celle de mkvalidator
                        SubConvert.append(
                            [Select[0], Select[4], Select[5].replace("fre", "fra")]
                        )

                    # Dans le cas ou il n'y a pas de conversion, maj de commande
                    else:
                        # Code d'encapsulage
                        mkvmerge_files.append(SUB)
                        mkvmerge_files.append(IDX)
                        File = "{0}/{1}.idx".format(
                            state.Configs.value("OutputFolder"), FileWithoutSlash
                        )
                        mkvmerge.extend(
                            [
                                "--track-name",
                                "0:{0[4]}".format(Select),
                                "--language",
                                "0:{0[5]}".format(Select),
                                "--compression",
                                "0:none",
                                "{1}".format(Select, File),
                            ]
                        )

                # Dans le cas de sous titres de fichiers sup ou pgs
                elif Select[6] in ("sup", "pgs"):
                    # Ajout du fichier à la liste
                    SUP = "{0}/{1}.{2[6]}".format(
                        state.Configs.value("OutputFolder"), FileWithoutSlash, Select
                    )
                    state.AllTempFiles.append(SUP)

                    # Code d'extraction des pistes
                    mkvextract_track.append("{0[0]}:{1}".format(Select, SUP))

                    # Si conversion du sous titre
                    if state.TempValues.value("SubtitlesConvert") and state.TempValues.value(
                        "Sup2Sub"
                    ):
                        state.TempFiles.append(SUP)

                        # Fichiers de conversion sup => sub
                        SUB = "{0}/{1}.sub".format(
                            state.Configs.value("OutputFolder"), FileWithoutSlash
                        )
                        IDX = "{0}/{1}.idx".format(
                            state.Configs.value("OutputFolder"), FileWithoutSlash
                        )

                        state.AllTempFiles.append(SUB)
                        state.AllTempFiles.append(IDX)

                        # Fichier de conversion sub => srt
                        if state.TempValues.value("Sub2Srt"):
                            SRT = "{0}/{1}.srt".format(
                                state.Configs.value("OutputFolder"), FileWithoutSlash
                            )
                            state.AllTempFiles.append(SRT)

                            state.TempFiles.append(SUB)
                            state.TempFiles.append(IDX)

                            # Code d'encapsulage du srt
                            mkvmerge.extend(
                                [
                                    "--track-name",
                                    "0:{0[4]}".format(Select),
                                    "--language",
                                    "0:{0[5]}".format(Select),
                                    "--compression",
                                    "0:none",
                                    SRT,
                                ]
                            )
                            mkvmerge_files.append(SRT)

                            # Différence de nom entre la langue de tesseract et celle de mkvalidator
                            SubConvert.append(
                                [Select[0], Select[4], Select[5].replace("fre", "fra")]
                            )

                        # Si pas de conversion srt
                        else:
                            mkvmerge_files.append(SUB)
                            mkvmerge_files.append(IDX)

                            # Code d'encapsulage
                            mkvmerge.extend(
                                [
                                    "--track-name",
                                    "0:{0[4]}".format(Select),
                                    "--language",
                                    "0:{0[5]}".format(Select),
                                    "--compression",
                                    "0:none",
                                    IDX,
                                ]
                            )

                        # Liste des sous titres à convertir
                        SupConvert.append(
                            [
                                Select[0],
                                Select[4],
                                "{0}/{1}.{2[6]}".format(
                                    state.Configs.value("OutputFolder"),
                                    FileWithoutSlash,
                                    Select,
                                ),
                            ]
                        )

                    # Dans le cas ou il n'y a pas de conversion, maj de commande
                    else:
                        # Code d'encapsulage
                        mkvmerge_files.append(SUP)
                        mkvmerge.extend(
                            [
                                "--track-name",
                                "0:{0[4]}".format(Select),
                                "--language",
                                "0:{0[5]}".format(Select),
                                "--compression",
                                "0:none",
                                SUP,
                            ]
                        )

                # Dans le cas de sous titres autre que de type sub, maj de commandes
                else:
                    # Ajout du fichier à la liste
                    File = "{0}/{1}.{2[6]}".format(
                        state.Configs.value("OutputFolder"), FileWithoutSlash, Select
                    )
                    state.AllTempFiles.append(File)

                    # Code d'extraction des pistes
                    mkvmerge_files.append(File)
                    mkvextract_track.append("{0[0]}:{1}".format(Select, File))

                    # Code d'encapsulage
                    mkvmerge.extend(
                        [
                            "--track-name",
                            "0:{0[4]}".format(Select),
                            "--language",
                            "0:{0[5]}".format(Select),
                            "--compression",
                            "0:none",
                            File,
                        ]
                    )

            ## Traitement des pistes chapitrage, maj de commandes
            elif Select[1] == "Chapters":
                # Ajout du fichier à la liste
                File = "{0}/chapters.txt".format(state.Configs.value("OutputFolder"))
                state.AllTempFiles.append(File)
                mkvmerge_files.append(File)

                # Code d'encapsulage
                mkvmerge.extend(["--chapters", File])

                # Variable temporaire
                state.TempValues.setValue("ChaptersFile", File)

                # Suppression du fichier s'il existe déjà
                if QFileInfo(state.TempValues.value("ChaptersFile")).exists():
                    QFile(state.TempValues.value("ChaptersFile")).remove()

                # Ajout de la commande d'extraction du chapitrage
                state.CommandList.append(
                    [
                        "MKVExtract Chapters",
                        state.Configs.value("Location/MKVExtract"),
                        ["chapters", state.Configs.value("InputFile"), "-s"],
                        [state.Configs.value("InputFile")],
                    ]
                )

            ## Traitement des pistes de tags, maj de commandes
            elif Select[1] == "Global tags":
                # Ajout du fichier à la liste
                File = "{0}/tags.xml".format(state.Configs.value("OutputFolder"))
                state.AllTempFiles.append(File)
                mkvmerge_files.append(File)

                # Code d'encapsulage
                mkvmerge.extend(["--global-tags", File])

                # Variable temporaire
                state.TempValues.setValue("TagsFile", File)

                # Suppression du fichier s'il existe déjà
                if QFileInfo(state.TempValues.value("TagsFile")).exists():
                    QFile(state.TempValues.value("TagsFile")).remove()

                # Ajout de la commande d'extraction des tags
                state.CommandList.append(
                    [
                        "MKVExtract Tags",
                        state.Configs.value("Location/MKVExtract"),
                        ["tags", state.Configs.value("InputFile")],
                        [state.Configs.value("InputFile")],
                    ]
                )

            ## Traitement des pistes jointes, maj de commandes
            else:
                # Ajout du fichier à la liste
                FileWithoutSlash = "{}_{}".format(
                    Select[0], Select[4].replace("/", "-")
                )
                File = "{}/{}".format(state.Configs.value("OutputFolder"), FileWithoutSlash)
                state.AllTempFiles.append(File)
                mkvmerge_files.append(File)

                # Code d'extraction des fichiers joints
                mkvextract_joint.append("{0[0]}:{1}".format(Select, File))

                # Code d'encapsulage
                mkvmerge.extend(["--attachment-name", Select[4], "--attach-file", File])

        ### Ajout de la commande mkvextract_track à la liste des commandes à exécuter
        if mkvextract_track:
            # Finalisation de la commande d'extraction des pistes
            mkvextract_track.insert(0, state.Configs.value("InputFile"))
            mkvextract_track.insert(0, "tracks")

            # Ajout de la commande d'extraction des pistes à la liste des commandes
            state.CommandList.append(
                [
                    "MKVExtract Tracks",
                    state.Configs.value("Location/MKVExtract"),
                    mkvextract_track,
                    [state.Configs.value("InputFile")],
                ]
            )

        ### Ajout de la commande mkvextract_joint à la liste des commandes à exécuter
        if mkvextract_joint:
            # Finalisation de la commande d'extraction des fichiers joints
            mkvextract_joint.insert(0, state.Configs.value("InputFile"))
            mkvextract_joint.insert(0, "attachments")

            # Ajout de la commande d'extraction des fichiers joints à la liste des commandes
            state.CommandList.append(
                [
                    "MKVExtract Attachments",
                    state.Configs.value("Location/MKVExtract"),
                    mkvextract_joint,
                    [state.Configs.value("InputFile")],
                ]
            )

        ### Ajout de la commande dts_ffmpeg à la liste des commandes à exécuter
        if dts_ffmpeg:
            # Finalisation de la commande de conversion audio
            if state.TempValues.value("FFMpeg"):
                ffconv = state.Configs.value("Location/FFMpeg")
                ffconvName = "FFMpeg"

            else:
                ffconv = state.Configs.value("Location/AvConv")
                ffconvName = "AvConv"

            dts_ffmpeg.insert(0, "-y")
            dts_ffmpeg.insert(0, state.Configs.value("InputFile"))
            dts_ffmpeg.insert(0, "-i")

            # Ajout de la commande de conversion audio à la liste des commandes
            state.CommandList.append(
                [ffconvName, ffconv, dts_ffmpeg, [state.Configs.value("InputFile")]]
            )

        ### Ajout des commandes de conversion des vobsub en srt
        if state.TempValues.value("SubtitlesConvert"):

            ## Pour chaque pgs/sup à convertir en sub
            for SupInfo in SupConvert:
                FileWithoutSlash = "{}_subtitles_{}".format(
                    SupInfo[0], SupInfo[1].replace("/", "-")
                )

                # Liste des fichiers sous titres
                IDX = "{}/{}.idx".format(
                    state.Configs.value("OutputFolder"), FileWithoutSlash
                )

                # Ajout de la commande de conversion des sous titres sup en sub à la liste des commandes
                if state.TempValues.value("Sup2Sub") == 3:
                    state.CommandList.append(
                        [
                            "Message",
                            "Information",
                            [
                                self.Trad["BDSup2SubTitle"],
                                self.Trad["BDSup2SubInfoText"].format(IDX),
                                IDX,
                            ],
                            [],
                        ]
                    )
                    state.CommandList.append(
                        [
                            "BDSup2Sub",
                            "java",
                            ["-jar", state.Configs.value("Location/BDSup2Sub"), SupInfo[2]],
                            [SupInfo[2]],
                        ]
                    )

                elif state.TempValues.value("Sup2Sub") == 2:
                    state.CommandList.append(
                        [
                            "BDSup2Sub",
                            "java",
                            [
                                "-jar",
                                state.Configs.value("Location/BDSup2Sub"),
                                "-o",
                                IDX,
                                SupInfo[2],
                            ],
                            [SupInfo[2]],
                        ]
                    )

                elif state.TempValues.value("Sup2Sub") == 1:
                    # Fichiers temporaires
                    MKS = "{}/{}.mks".format(
                        state.Configs.value("OutputFolder"), FileWithoutSlash
                    )
                    SUB = "{}/{}.sub".format(
                        state.Configs.value("OutputFolder"), FileWithoutSlash
                    )

                    state.AllTempFiles.append(MKS)
                    state.AllTempFiles.append(SUB)
                    state.TempFiles.append(MKS)

                    # Commande FFMpeg pour ne conserver que le sub dans un mks
                    state.CommandList.append(
                        [
                            "FFMpeg",
                            state.Configs.value("Location/FFMpeg"),
                            [
                                "-i",
                                SupInfo[2],
                                "-map",
                                "0:s:0",
                                "-c:s",
                                "dvdsub",
                                "-f",
                                "matroska",
                                MKS,
                            ],
                            [SupInfo[2]],
                        ]
                    )

                    # Commande mkvextract pour extraire le sub du mks
                    state.CommandList.append(
                        [
                            "MKVExtract",
                            state.Configs.value("Location/MKVExtract"),
                            [MKS, "tracks", "0:{}".format(SUB)],
                            [MKS],
                        ]
                    )

            ## Pour chaque sub à convertir en srt
            for SubInfo in SubConvert:
                FileWithoutSlash = "{}_subtitles_{}".format(
                    SubInfo[0], SubInfo[1].replace("/", "-")
                )

                # Liste des fichiers sous titres
                IDX = "{}/{}.idx".format(
                    state.Configs.value("OutputFolder"), FileWithoutSlash
                )
                SRT = "{}/{}.srt".format(
                    state.Configs.value("OutputFolder"), FileWithoutSlash
                )
                SubToRemove.append(IDX)

                # Finalisation de la commande Qtesseract5
                g = 1

                if state.TempValues.value("Sub2Srt") == 2:
                    state.CommandList.append(
                        [
                            "Message",
                            "Information",
                            [
                                self.Trad["QtesseractTitle"],
                                self.Trad["QtesseractInfoText"].format(SRT),
                                SRT,
                            ],
                            [],
                        ]
                    )
                    g = 2

                # Ajout de la commande de conversion de conversion des sous titres sub en srt à la liste des commandes
                state.CommandList.append(
                    [
                        "Qtesseract5",
                        state.Configs.value("Location/Qtesseract5"),
                        [
                            "-g", str(g),
                            "-v", "1",
                            "-r",
                            "-c", "0",
                            "-w",
                            "-t", str(QThread.idealThreadCount()),
                            "-l", SubInfo[2],
                            IDX,
                            SRT,
                        ],
                        [IDX],
                    ]
                )

        ### Ajout de la commande mkvmerge à la liste des commandes à exécuter
        if state.TempValues.value("Reencapsulate"):
            InputFileName = QFileInfo(state.Configs.value("InputFile")).fileName()

            ## Si l'option de renommage automatique n'est pas utilisée
            if not state.Configs.value("RemuxRename"):
                # Fenêtre de sélection de sortie du fichier mkv
                CheckBox = QCheckBox(self.Trad["RemuxRenameCheckBox"])

                FileDialogCustom = QFileDialogCustom(
                    self,
                    self.Trad["RemuxRenameTitle"],
                    state.Configs.value("OutputFolder"),
                    "{}(*.mka *.mks *.mkv *.mk3d *.webm *.webmv *.webma)".format(
                        self.Trad["MatroskaFiles"]
                    ),
                )

                # Choix du fichier de destination
                FileTemp = FileDialogCustom.createWindow(
                    "File",
                    "Save",
                    CheckBox,
                    Qt.Tool,
                    "MEG_{}".format(InputFileName),
                    AlreadyExistsTest=state.Configs.value("AlreadyExistsTest", False),
                    Language=state.Configs.value("Language"),
                    App=state.app,
                )

                # Si c'est vide, on utilise .
                if not FileTemp:
                    FileTemp = "."

                state.TempValues.setValue("OutputFile", FileTemp)
                state.Configs.setValue("RemuxRename", CheckBox.isChecked())

                # Mise à jour de la variable
                state.Configs.setValue("RemuxRename", CheckBox.isChecked())

                # Arrêt de la fonction si aucun fichier n'est choisi
                if state.TempValues.value("OutputFile") == ".":
                    return

            else:
                File = "{0}/MEG_{1}".format(
                    state.Configs.value("OutputFolder"), InputFileName
                )
                state.TempValues.setValue("OutputFile", File)

            ## Ajout des fichiers temporaires à la liste
            for Item in mkvmerge_files:
                if Item != state.Configs.value("InputFile"):
                    state.TempFiles.append(Item)

            ## Ajout du fichier mkv à la liste des fichiers
            state.AllTempFiles.append(state.TempValues.value("OutputFile"))

            ## Dans le cas où il faut ouvrir les fichiers srt avant leur encapsulage
            if state.TempValues.value("SubtitlesOpen"):
                state.SubtitlesFiles.clear()

                # Ajout des fichiers sous titres
                for Item in mkvmerge_files:
                    if QFileInfo(Item).suffix().lower() in ("srt", "ssa", "ass", "idx"):
                        state.SubtitlesFiles.append(Item)

                # Suppression des fichiers idx qui ont été convertis
                if SubToRemove:
                    for Item in SubToRemove:
                        state.SubtitlesFiles.remove(Item)

                # Echo bidon pour être sûr que la commande se termine bien
                if state.SubtitlesFiles:
                    state.CommandList.append(["Open Subtitles", "echo", [], []])

            ## Récupération du titre du fichier dans le cas où il faut réencapsuler,
            state.TempValues.setValue("TitleFile", self.ui.mkv_title.text())

            ## Si le titre est vide, il plante l'encapsulage
            if state.TempValues.value("TitleFile"):
                mkvmerge.insert(0, state.TempValues.value("TitleFile"))
                mkvmerge.insert(0, "--title")

            # Finalisation de la commande d'encapsulage
            mkvmerge.insert(0, state.TempValues.value("OutputFile"))
            mkvmerge.insert(0, "-o")

            # Ajout de la commande d'encapsulage à la liste des commandes
            state.CommandList.append(
                [
                    "MKVMerge",
                    state.Configs.value("Location/MKVMerge"),
                    mkvmerge,
                    mkvmerge_files,
                ]
            )

        ### Modifications graphiques
        self.WorkInProgress(True)  # Blocage des widgets

        ### Code à exécuter
        state.TempValues.setValue(
            "Command", state.CommandList.pop(0)
        )  # Récupération de la 1ere commande

        ### Envoie de textes
        self.SetInfo(
            self.Trad["WorkProgress"].format(state.TempValues.value("Command")[0]),
            "800080",
            True,
            True,
        )  # Nom de la commande
        self.SetInfo(
            self.Trad["WorkCmd"].format(
                state.TempValues.value("Command")[1]
                + " "
                + " ".join(state.TempValues.value("Command")[2])
            )
        )  # Envoie d'informations

        ### Lancement de la commande
        self.WorkStart()
