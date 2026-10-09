"""Test minimal, presente surtout pour que la CI demarre au vert des le premier commit.

A remplacer par de vrais tests du code metier : en priorite ceux qui verifient le
format des exports (colonnes attendues, encodage, separateur) et le comportement
sur donnees d'entree degradees.
"""

from src import config


def test_racine_contient_le_readme():
    assert (config.RACINE / "README.md").exists()


def test_corpus_fige_et_coherent():
    # 23 documents, identifiants uniques (ils deviennent des noms de fichiers),
    # adresses cnil.fr en https, empreintes SHA-256 completes (64 caracteres hexa).
    assert len(config.CORPUS) == 23
    assert len({d.identifiant for d in config.CORPUS}) == len(config.CORPUS)
    for doc in config.CORPUS:
        assert doc.url.startswith("https://www.cnil.fr/") and doc.url.endswith(".pdf")
        assert len(doc.sha256) == 64 and all(c in "0123456789abcdef" for c in doc.sha256)
        assert doc.theme in {"socle", "securite", "rh", "numerique", "ia"}


def test_parametres_export_explicites():
    # Un separateur ou un encodage laisse implicite casse l'import en aval.
    assert config.SEPARATEUR_EXPORT in (";", ",", "\t")
    assert config.ENCODAGE_EXPORT.startswith("utf-8")
