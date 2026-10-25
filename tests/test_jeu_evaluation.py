"""Garde-fous du jeu d'evaluation : une reference fausse fausserait toute la mesure."""

import json

import pytest
import yaml

from src import config

FICHIER = config.RACINE / "evaluation" / "questions.yaml"
# Premisse fausse : la question affirme une regle que le corpus contredit ; la bonne
# reponse corrige la premisse, avec ses sources. Elle compte donc parmi les questions
# avec reponse.
TYPES_AVEC_REPONSE = {
    "factuelle", "tableau", "reformulee", "multi_documents", "couverture", "premisse_fausse"
}
TYPES_SANS_REPONSE = {"absente_hors_perimetre", "absente_proche"}

QUESTIONS = yaml.safe_load(FICHIER.read_text(encoding="utf-8"))


def test_composition_du_jeu():
    # 30 a 50 questions, dont environ un tiers sans reponse dans le corpus. Le plancher est
    # a 25 % depuis la correction du 2026-10-25 : Q37 et Q39, ecrites comme sans reponse,
    # en avaient une (12 sur 44, 27 %). On n'ajoute pas de question apres coup pour
    # remonter la part : elle aurait ete ecrite en connaissant le systeme.
    assert 30 <= len(QUESTIONS) <= 50
    part_sans_reponse = sum(q["type"] in TYPES_SANS_REPONSE for q in QUESTIONS) / len(QUESTIONS)
    assert 0.25 <= part_sans_reponse <= 0.40


def test_identifiants_uniques():
    ids = [q["id"] for q in QUESTIONS]
    assert len(ids) == len(set(ids))


@pytest.mark.parametrize("q", QUESTIONS, ids=lambda q: q["id"])
def test_structure_coherente_avec_le_type(q):
    assert q["type"] in TYPES_AVEC_REPONSE | TYPES_SANS_REPONSE
    if q["type"] in TYPES_AVEC_REPONSE:
        assert q["reponse_attendue"] and q["sources"] and q["citation"]
    else:
        assert q["reponse_attendue"] is None and not q.get("sources")


@pytest.mark.parametrize("q", QUESTIONS, ids=lambda q: q["id"])
def test_sources_dans_le_corpus(q):
    identifiants = {d.identifiant for d in config.CORPUS}
    for source in q.get("sources") or []:
        assert source["document"] in identifiants
        assert all(isinstance(p, int) and p >= 1 for p in source["pages"])


def textes_des_pages(document: str) -> dict[int, str]:
    chemin = config.DONNEES_TRAITE / f"{document}.jsonl"
    pages = (json.loads(ligne) for ligne in chemin.read_text(encoding="utf-8").splitlines())
    return {p["page"]: p["texte"] for p in pages}


@pytest.mark.parametrize("q", QUESTIONS, ids=lambda q: q["id"])
def test_citation_presente_mot_pour_mot(q):
    # Le texte extrait n'est pas versionne : ce test ne tourne qu'en local, apres
    # src.extraction (il est ignore dans la CI).
    if not q.get("citation"):
        pytest.skip("question sans reponse dans le corpus")
    if not config.DONNEES_TRAITE.exists() or not any(config.DONNEES_TRAITE.glob("*.jsonl")):
        pytest.skip("corpus extrait absent : lancer python -m src.extraction")
    textes = [
        textes_des_pages(s["document"]).get(page, "")
        for s in q["sources"]
        for page in s["pages"]
    ]
    # Une question a deux documents a une citation par document : chacune doit etre trouvee.
    citations = q["citation"] if isinstance(q["citation"], list) else [q["citation"]]
    for citation in citations:
        assert any(citation in texte for texte in textes), f"{q['id']} : introuvable : {citation}"


@pytest.mark.parametrize(
    "q", [q for q in QUESTIONS if q["type"] == "multi_documents"], ids=lambda q: q["id"]
)
def test_multi_documents_cite_bien_deux_documents(q):
    assert len({s["document"] for s in q["sources"]}) >= 2
    assert isinstance(q["citation"], list) and len(q["citation"]) >= 2
