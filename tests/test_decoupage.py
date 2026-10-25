"""Tests du decoupage en passages, sur de petits textes construits a la main.

Le vrai tokenizer de bge-m3 se telecharge : on le remplace par un tokenizer qui compte
un token par mot, ce qui suffit a tester les regles de decoupage sans reseau.
"""

from tokenizers import Tokenizer
from tokenizers.models import WordLevel
from tokenizers.pre_tokenizers import WhitespaceSplit

from src.config import Document
from src.decoupage import Decoupeur, decouper_en_blocs, retirer_lignes_sommaire

DOCUMENT = Document("guide", "Guide test", "socle", "https://exemple.fr", "2026-01-01", "0")


def tokenizer_un_mot_un_token() -> Tokenizer:
    tokenizer = Tokenizer(WordLevel({"[UNK]": 0}, unk_token="[UNK]"))
    tokenizer.pre_tokenizer = WhitespaceSplit()
    return tokenizer


def decoupeur(taille_max=40, taille_min_avant_titre=10, chevauchement_max=8) -> Decoupeur:
    return Decoupeur(
        tokenizer_un_mot_un_token(), taille_max, taille_min_avant_titre, chevauchement_max
    )


def test_blocs_titre_texte_tableau_separes():
    texte = "## Titre\nUn paragraphe.\n|Finalité|Durée|\n|---|---|\n|Paie|5 ans|"
    natures = [b.nature for b in decouper_en_blocs(texte, 1)]
    assert natures == ["titre", "texte", "tableau"]


def test_ligne_de_sommaire_retiree_et_texte_garde():
    texte = "1.2 Qu'est-ce que le principe ?........................ 4\nUn vrai paragraphe."
    nettoye, nb = retirer_lignes_sommaire(texte)
    assert nb == 1
    assert nettoye == "Un vrai paragraphe."


def test_aucun_passage_ne_depasse_la_taille_max():
    d = decoupeur()
    pages = [{"page": i, "texte": " ".join(["mot"] * 25) + "."} for i in range(1, 6)]
    passages = d.decouper_document(DOCUMENT, pages)
    assert len(passages) > 1
    assert all(d.nb_tokens(d.texte_indexe(DOCUMENT.titre, p)) <= 40 for p in passages)


def test_tableau_trop_long_coupe_avec_en_tete_repete():
    d = decoupeur()
    lignes = ["|Finalité|Durée|", "|---|---|"]
    lignes += [f"|Document numero {i} du personnel|{i} ans|" for i in range(12)]
    passages = d.decouper_document(DOCUMENT, [{"page": 3, "texte": "\n".join(lignes)}])
    assert len(passages) > 1
    for passage in passages:
        assert passage.contenu.startswith("|Finalité|Durée|\n|---|---|")


def test_un_titre_ouvre_un_nouveau_passage_et_donne_la_section():
    d = decoupeur()
    texte = (
        "## Première partie\n\n" + " ".join(["mot"] * 15) + ".\n\n"
        "## Deuxième partie\n\n" + " ".join(["mot"] * 15) + "."
    )
    passages = d.decouper_document(DOCUMENT, [{"page": 1, "texte": texte}])
    assert [p.section for p in passages] == ["Première partie", "Deuxième partie"]
    assert d.texte_indexe(DOCUMENT.titre, passages[1]).startswith("Guide test\nDeuxième partie")


def test_page_courte_recollee_a_la_suivante():
    d = decoupeur()
    pages = [{"page": 1, "texte": "Couverture."}, {"page": 2, "texte": "Contenu de la page."}]
    passages = d.decouper_document(DOCUMENT, pages)
    assert len(passages) == 1
    assert passages[0].pages == [1, 2]


def test_chevauchement_du_dernier_paragraphe_court():
    d = decoupeur()
    texte = " ".join(["long"] * 30) + ".\n\nPhrase courte reprise.\n\n" + " ".join(["fin"] * 20)
    passages = d.decouper_document(DOCUMENT, [{"page": 1, "texte": texte}])
    assert len(passages) == 2
    assert "Phrase courte reprise." in passages[0].contenu
    assert passages[1].contenu.startswith("Phrase courte reprise.")


def test_ligne_de_tableau_geante_coupee_entre_ses_phrases_en_tete_repete():
    d = decoupeur()
    phrases = " ".join(f"Phrase numero {i} de la cellule." for i in range(12))
    tableau = f"|Finalité|Durée|\n|---|---|\n|{phrases}|5 ans|"
    passages = d.decouper_document(DOCUMENT, [{"page": 2, "texte": tableau}])
    assert len(passages) > 1
    for passage in passages:
        assert passage.contenu.startswith("|Finalité|Durée|\n|---|---|")
    # Aucune phrase coupee en deux : chaque morceau finit sur une fin de phrase ou la ligne.
    texte_total = " ".join(p.contenu for p in passages)
    assert all(f"Phrase numero {i} de la cellule." in texte_total for i in range(12))
