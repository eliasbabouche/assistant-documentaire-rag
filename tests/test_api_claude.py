"""Tests de l'appel a l'API Claude et du juge, sans reseau : le client est simule."""

import json
from types import SimpleNamespace

import pytest

from src import api_claude, config, generation, juge
from src.recherche import PassageTrouve


class FauxClient:
    """Imite client.messages.create : renvoie une reponse preparee et retient la requete."""

    def __init__(self, texte: str, stop_reason: str = "end_turn", modele: str | None = None):
        self.texte, self.stop_reason, self.modele = texte, stop_reason, modele
        self.requetes = []
        self.messages = SimpleNamespace(create=self.create)

    def create(self, **requete):
        self.requetes.append(requete)
        return SimpleNamespace(
            # Un bloc de reflexion precede le texte : seul le texte doit etre garde.
            content=[
                SimpleNamespace(type="thinking", thinking=""),
                SimpleNamespace(type="text", text=self.texte),
            ],
            stop_reason=self.stop_reason,
            model=self.modele or requete["model"],
            usage=SimpleNamespace(input_tokens=3000, output_tokens=200),
        )


@pytest.fixture
def faux_client(monkeypatch):
    def installer(texte: str, **options) -> FauxClient:
        faux = FauxClient(texte, **options)
        monkeypatch.setattr(api_claude, "client", lambda: faux)
        return faux

    return installer


def test_cout_calcule_depuis_les_tarifs():
    # 1 million de tokens en entree et autant en sortie : la somme des deux tarifs.
    entree, sortie = config.TARIFS_USD_PAR_MILLION[config.MODELE_CLAUDE]
    assert api_claude.cout_usd(config.MODELE_CLAUDE, 1_000_000, 1_000_000) == entree + sortie


def test_modeles_utilises_ont_un_tarif():
    assert {config.MODELE_CLAUDE, config.MODELE_JUGE} <= set(config.TARIFS_USD_PAR_MILLION)
    assert config.MODELE_JUGE != config.MODELE_CLAUDE  # le juge ne note pas ses reponses


def test_appel_garde_le_texte_les_tokens_et_le_cout(faux_client):
    faux = faux_client(" Deux ans [1]. ")
    appel = api_claude.appeler_claude(config.MODELE_CLAUDE, "consignes", "prompt", "low")
    assert appel.texte == "Deux ans [1]."
    assert (appel.tokens_entree, appel.tokens_sortie) == (3000, 200)
    assert appel.cout_usd == pytest.approx(3000 * 4 / 1e6 + 200 * 20 / 1e6)
    requete = faux.requetes[0]
    assert requete["system"] == "consignes"
    assert requete["output_config"] == {"effort": "low"}


@pytest.mark.parametrize("raison", ["max_tokens", "refusal"])
def test_reponse_interrompue_arrete_au_lieu_d_etre_notee(faux_client, raison):
    faux_client("texte coupé", stop_reason=raison)
    with pytest.raises(RuntimeError, match=raison):
        api_claude.appeler_claude(config.MODELE_CLAUDE, "consignes", "prompt", "low")


def test_autre_modele_que_celui_demande_arrete(faux_client):
    faux_client("réponse", modele="un-autre-modele")
    with pytest.raises(RuntimeError, match="un-autre-modele"):
        api_claude.appeler_claude(config.MODELE_CLAUDE, "consignes", "prompt", "low")


PASSAGES = [PassageTrouve("rh-003", "rh", "Référentiel RH", 2, 3, "", "Deux ans.", 0.7)]


def test_claude_recoit_le_meme_prompt_que_mistral(faux_client):
    faux = faux_client("Les CV sont conservés deux ans [1].")
    reponse = generation.repondre_claude("Combien de temps ?", passages=PASSAGES)
    requete = faux.requetes[0]
    assert requete["model"] == config.MODELE_CLAUDE
    assert requete["system"] == generation.CONSIGNES
    assert requete["messages"][0]["content"] == generation.construire_prompt(
        "Combien de temps ?", PASSAGES, generation.RAPPEL_REPONSE
    )
    assert not reponse.refus and reponse.cites == [1]
    assert reponse.modele == config.MODELE_CLAUDE and reponse.cout_usd > 0


def test_refus_de_claude_reconnu_et_sans_citation(faux_client):
    faux_client(config.PHRASE_REFUS)
    reponse = generation.repondre_claude("Question hors corpus ?", passages=PASSAGES)
    assert reponse.refus and reponse.cites == []


def test_mistral_utilise_les_passages_fournis_sans_refaire_la_recherche(monkeypatch):
    def recherche_interdite(*args, **kwargs):
        raise AssertionError("la recherche ne doit pas être relancée")

    monkeypatch.setattr(generation, "rechercher", recherche_interdite)
    monkeypatch.setattr(
        generation,
        "appeler_ollama",
        lambda prompt, nb_tokens_max=-1: {"message": {"content": "Deux ans [1]."}},
    )
    reponse = generation.repondre("Combien de temps ?", verifier=False, passages=PASSAGES)
    assert reponse.passages == PASSAGES and reponse.cout_usd == 0


def test_juge_lit_le_verdict_et_note_a_l_aveugle(faux_client):
    faux = faux_client(json.dumps({"justification": "Tout y est.", "verdict": "correcte"}))
    jugement = juge.juger("Combien de temps ?", "Deux ans.", "Deux ans [1].")
    assert jugement.verdict == "correcte" and jugement.justification == "Tout y est."
    requete = faux.requetes[0]
    assert requete["model"] == config.MODELE_JUGE
    assert requete["output_config"]["format"]["schema"] == juge.SCHEMA_JUGEMENT
    # A l'aveugle : rien dans la demande ne dit quel modele a ecrit la reponse.
    demande = requete["messages"][0]["content"].lower()
    assert "mistral" not in demande and "claude" not in demande


def test_verdict_hors_grille_refuse(faux_client):
    faux_client(json.dumps({"justification": "?", "verdict": "plutôt bien"}))
    with pytest.raises(ValueError, match="hors grille"):
        juge.juger("Question ?", "Référence.", "Réponse.")
