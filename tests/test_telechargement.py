"""Tests du telechargement, sans reseau : requests.get est remplace par une fausse
fonction (monkeypatch), et le dossier de donnees par un dossier temporaire."""

import hashlib

import pytest

from src import config, telechargement

CONTENU_FACTICE = b"%PDF-1.7 contenu factice"


class FausseReponse:
    def __init__(self, contenu):
        self.content = contenu

    def raise_for_status(self):
        pass


def document_factice(sha256):
    return config.Document(
        "test", "Titre", "socle", "https://exemple.fr/a.pdf", "2026-01-01", sha256
    )


@pytest.fixture
def dossier_temporaire(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "DONNEES_BRUT", tmp_path)
    return tmp_path


def simuler_reseau(monkeypatch, contenu):
    """Remplace requests.get et compte les appels."""
    appels = []

    def faux_get(url, **kwargs):
        appels.append(url)
        return FausseReponse(contenu)

    monkeypatch.setattr(telechargement.requests, "get", faux_get)
    return appels


def test_telecharge_et_ecrit_si_empreinte_correcte(dossier_temporaire, monkeypatch):
    simuler_reseau(monkeypatch, CONTENU_FACTICE)
    doc = document_factice(hashlib.sha256(CONTENU_FACTICE).hexdigest())

    assert telechargement.telecharger_document(doc) == "téléchargé"
    assert (dossier_temporaire / "test.pdf").read_bytes() == CONTENU_FACTICE


def test_refuse_et_n_ecrit_rien_si_empreinte_differente(dossier_temporaire, monkeypatch):
    simuler_reseau(monkeypatch, b"une autre edition du document")
    doc = document_factice(hashlib.sha256(CONTENU_FACTICE).hexdigest())

    with pytest.raises(telechargement.EmpreinteInvalide):
        telechargement.telecharger_document(doc)
    assert not (dossier_temporaire / "test.pdf").exists()


def test_ne_retelecharge_pas_un_fichier_present_et_valide(dossier_temporaire, monkeypatch):
    (dossier_temporaire / "test.pdf").write_bytes(CONTENU_FACTICE)
    appels = simuler_reseau(monkeypatch, CONTENU_FACTICE)
    doc = document_factice(hashlib.sha256(CONTENU_FACTICE).hexdigest())

    assert telechargement.telecharger_document(doc) == "déjà présent"
    assert appels == []


def test_detecte_un_fichier_local_corrompu(dossier_temporaire, monkeypatch):
    (dossier_temporaire / "test.pdf").write_bytes(b"fichier tronque")
    simuler_reseau(monkeypatch, CONTENU_FACTICE)
    doc = document_factice(hashlib.sha256(CONTENU_FACTICE).hexdigest())

    with pytest.raises(telechargement.EmpreinteInvalide):
        telechargement.telecharger_document(doc)
