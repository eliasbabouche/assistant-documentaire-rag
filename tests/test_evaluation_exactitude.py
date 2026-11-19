"""Tests du tableau de synthese de l'evaluation, sur un petit exemple compte a la main."""

import pandas as pd
import pytest

from src.evaluation_exactitude import a_juger, resumer, tirer_echantillon


def ligne(id_, avec_reponse, refus, rang=None, duree=2.0, cout=0.01):
    return {
        "configuration": "claude", "modele": "modele-test", "id": id_,
        "avec_reponse": avec_reponse, "rang_bon_passage": rang, "refus": refus,
        "tokens_entree": 3000, "tokens_sortie": 100, "duree_s": duree, "cout_usd": cout,
        "reponse": "texte",
    }


# 4 questions avec reponse (une refusee a tort, une sans bon passage) et 2 sans reponse
# (un bon refus, une reponse inventee).
REPONSES = pd.DataFrame(
    [
        ligne("Q01", True, False, rang=1, duree=1.0),
        ligne("Q02", True, False, rang=2, duree=2.0),
        ligne("Q03", True, False, rang=None, duree=3.0),
        ligne("Q04", True, True, rang=1, duree=4.0),
        ligne("Q05", False, True, duree=5.0),
        ligne("Q06", False, False, duree=60.0),
    ]
)
JUGEMENTS = pd.DataFrame(
    {
        "configuration": ["claude"] * 3,
        "id": ["Q01", "Q02", "Q03"],
        "verdict": ["correcte", "partielle", "incorrecte"],
        "justification": ["", "", ""],
        "tokens_entree": [500] * 3,
        "tokens_sortie": [100] * 3,
        "cout_usd": [0.002] * 3,
    }
)


def test_seules_les_reponses_donnees_a_une_question_avec_reponse_sont_jugees():
    assert list(a_juger(REPONSES)["id"]) == ["Q01", "Q02", "Q03"]


def test_resume_compte_a_la_main():
    r = resumer(REPONSES, JUGEMENTS).iloc[0]
    assert (r["questions_sans_reponse"], r["refus_corrects"]) == (2, 1)
    assert (r["questions_avec_reponse"], r["refus_a_tort"]) == (4, 1)
    assert (r["reponses_correctes"], r["reponses_partielles"], r["reponses_incorrectes"]) == (
        1, 1, 1,
    )
    # Le refus a tort compte au denominateur : 1 correcte sur 4, pas sur 3.
    assert r["exactitude"] == 0.25
    assert (r["questions_bon_passage"], r["correctes_bon_passage"]) == (3, 1)
    # Mediane et non moyenne : la reponse a 60 s ne la deplace pas.
    assert r["duree_mediane_s"] == 3.5
    assert r["cout_total_usd"] == pytest.approx(0.06)
    assert r["cout_juge_usd"] == pytest.approx(0.006)


def test_reponse_non_jugee_arrete_le_resume():
    with pytest.raises(ValueError, match="1 réponses n'ont pas été jugées"):
        resumer(REPONSES, JUGEMENTS.iloc[:2])


def test_colonne_manquante_arrete_le_resume():
    with pytest.raises(ValueError, match="duree_s"):
        resumer(REPONSES.drop(columns="duree_s"), JUGEMENTS)


def test_echantillon_reproductible_et_reparti_par_verdict():
    jugements = pd.DataFrame(
        {
            "id": [f"Q{i:02d}" for i in range(30)],
            "verdict": ["correcte"] * 20 + ["partielle"] * 8 + ["incorrecte"] * 2,
        }
    )
    echantillon = tirer_echantillon(jugements)
    assert echantillon["verdict"].value_counts().to_dict() == {
        "correcte": 4, "partielle": 3, "incorrecte": 2,
    }
    assert list(echantillon["id"]) == list(tirer_echantillon(jugements)["id"])
