"""Telechargement du corpus CNIL, avec verification de l'empreinte de chaque fichier.

Lancement depuis la racine du projet :
    python -m src.telechargement

Un fichier n'est ecrit sur le disque qu'apres verification de son empreinte : un PDF
d'une autre edition (ou corrompu) n'arrive jamais dans donnees/brut/.
"""

import hashlib
from pathlib import Path

import requests

from src import config

# On s'annonce honnetement plutot que de se faire passer pour un navigateur.
EN_TETES = {"User-Agent": "assistant-documentaire-rag/0.1 (projet open source)"}
DELAI_MAX_SECONDES = 60


class EmpreinteInvalide(Exception):
    """Le fichier recu n'est pas l'edition figee dans config.CORPUS."""


def empreinte_sha256(contenu: bytes) -> str:
    return hashlib.sha256(contenu).hexdigest()


def chemin_local(document: config.Document) -> Path:
    return config.DONNEES_BRUT / f"{document.identifiant}.pdf"


def telecharger_document(document: config.Document) -> str:
    """Rapatrie un document s'il manque, et verifie son empreinte dans tous les cas.

    Renvoie « deja present » ou « telecharge ». Leve EmpreinteInvalide si le contenu
    ne correspond pas a l'edition attendue.
    """
    chemin = chemin_local(document)
    if chemin.exists():
        contenu = chemin.read_bytes()
        statut = "déjà présent"
    else:
        reponse = requests.get(document.url, headers=EN_TETES, timeout=DELAI_MAX_SECONDES)
        reponse.raise_for_status()
        contenu = reponse.content
        statut = "téléchargé"

    empreinte = empreinte_sha256(contenu)
    if empreinte != document.sha256:
        raise EmpreinteInvalide(
            f"{document.identifiant} : empreinte {empreinte[:12]}… au lieu de "
            f"{document.sha256[:12]}…. La CNIL a peut-être publié une nouvelle édition : "
            "vérifier le document, puis mettre à jour config.CORPUS."
        )

    if statut == "téléchargé":
        chemin.write_bytes(contenu)
    return statut


def telecharger_corpus() -> None:
    config.creer_dossiers()
    for document in config.CORPUS:
        statut = telecharger_document(document)
        print(f"  ✔ {document.identifiant:<30} {statut}")

    taille_totale = sum(chemin_local(d).stat().st_size for d in config.CORPUS)
    print(f"\n{len(config.CORPUS)} documents vérifiés, {taille_totale / 1e6:.1f} Mo")
    print(f"Dossier : {config.DONNEES_BRUT}")


if __name__ == "__main__":
    telecharger_corpus()
