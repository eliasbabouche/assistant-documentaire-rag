"""Tests de la lecture des reponses du modele, sans modele ni reseau."""

from src import config
from src.evaluation_recherche import contient_la_reponse
from src.generation import est_un_refus, extraire_citations
from src.recherche import PassageTrouve


def test_refus_reconnu_malgre_guillemets_et_ajout():
    assert est_un_refus(f"« {config.PHRASE_REFUS} »")
    assert est_un_refus("Je ne trouve pas cette information dans les documents fournis.")


def test_reponse_qui_n_est_pas_un_refus():
    assert not est_un_refus("Les CV sont conservés 2 ans [1].")


def test_citations_simples_groupees_et_numero_d_article_ignore():
    texte = "Deux ans [1]. Cinq ans [2][4]. Voir aussi [1, 55]."
    assert extraire_citations(texte, 5) == [1, 2, 4]


def test_passage_couvrant_la_page_source():
    passage = PassageTrouve("rh-003", "rh", "Titre", 2, 3, "", "texte", 0.7)
    assert contient_la_reponse(passage, [{"document": "rh", "pages": [3]}])
    assert not contient_la_reponse(passage, [{"document": "rh", "pages": [4]}])
    assert not contient_la_reponse(passage, [{"document": "autre", "pages": [3]}])


class FausseReponse:
    def __init__(self, code: int):
        self.status_code = code

    def raise_for_status(self):
        if self.status_code >= 400:
            raise RuntimeError(self.status_code)

    def json(self):
        return {"message": {"content": "OUI"}}


def test_ollama_reessaye_une_fois_apres_une_erreur_500(monkeypatch):
    from src import generation

    codes = iter([500, 200])
    appels = []

    def faux_post(*args, **kwargs):
        appels.append(1)
        return FausseReponse(next(codes))

    monkeypatch.setattr(generation.requests, "post", faux_post)
    monkeypatch.setattr(generation.time, "sleep", lambda s: None)
    assert generation.appeler_ollama("prompt")["message"]["content"] == "OUI"
    assert len(appels) == 2
