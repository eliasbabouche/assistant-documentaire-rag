"""Extraction des PDF du corpus en Markdown, page par page, avec l'entonnoir du nettoyage.

Lancement depuis la racine du projet (apres src.telechargement) :
    python -m src.extraction

Produit :
- donnees/traite/<identifiant>.jsonl : une ligne par page conservee
  {"document": ..., "page": ..., "texte": <Markdown nettoye>}
- donnees/agrege/entonnoir_extraction.csv : pages, caracteres et tokens a chaque etape
"""

import json
import re
from collections import Counter

import pandas as pd
import pymupdf4llm
from tokenizers import Tokenizer

from src import config

# Seules les pages VIDES sont ecartees. Un seuil de longueur (150 caracteres) a ete essaye
# puis abandonne : sur 29 pages ecartees, 3 portaient une information (date d'adoption
# sur une couverture, liste de references). Les pages courtes (couvertures, intercalaires)
# sont gardees : au decoupage, elles se recollent a la page suivante et lui donnent son
# titre de partie.
# Une ligne presente sur au moins la moitie des pages d'un document est un en-tete ou un
# pied de page (« CNIL. », « Passez a l'action | RGPD | 19 »).
# Une ligne presente sur au moins 30 % des pages est un en-tete ou un pied de page. Pas
# 50 % : les guides imprimes alternent pages paires et impaires (pied de page du guide
# TPE-PME sur 22 pages sur 54). Les intertitres recurrents restent sous 20 %.
PART_PAGES_LIGNE_REPETEE = 0.3
NB_PAGES_MIN_POUR_REPETITIONS = 4
# Seules les lignes en bordure de page (les 2 premieres et les 2 dernieres non vides)
# peuvent etre des en-tetes ou pieds de page. Sans ce critere de position, une ligne de
# contenu qui ne differe d'une page a l'autre que par un chiffre serait supprimee.
NB_LIGNES_BORDURE = 2


def nettoyer_balisage(texte: str) -> str:
    """Retire la mise en forme sans valeur pour le sens, en gardant la structure.

    Garde : titres (#), tableaux (|), listes. Retire : gras (**), barre (~~, que l'outil
    attribue a tort aux encadres), sauts de ligne de cellule (<br>, dus a l'etroitesse
    des colonnes du PDF).
    """
    # Remplacer par une espace et non par rien : « **5 ans**à compter » doit donner
    # « 5 ans à compter », pas « 5 ansà compter ».
    for balise in ("<br>", "**", "~~"):
        texte = texte.replace(balise, " ")
    # Balises HTML ajoutees par l'outil (souligne, exposant, surligne) : on garde le texte.
    texte = re.sub(r"</?(u|sup|mark)>", " ", texte)
    # Reperes autour du texte trouve dans les images : on garde le texte, pas les reperes.
    texte = re.sub(r"<!-- (Start|End) of picture text -->", "", texte)
    texte = re.sub(r"(?<=\S)[ \t]{2,}", " ", texte)  # espaces multiples (pas l'indentation)
    texte = re.sub(r" +([,.)])", r"\1", texte)  # « principe , » -> « principe, »
    texte = re.sub(r"[ \t]+\n", "\n", texte)  # espaces en fin de ligne
    texte = re.sub(r"\n{3,}", "\n\n", texte)  # lignes vides en serie
    return texte.strip()


def normaliser_ligne(ligne: str) -> str:
    """Forme comparable d'une ligne : les numeros de page ne doivent pas la distinguer."""
    return re.sub(r"\d+", "#", ligne.strip())


def positions_de_bordure(lignes: list[str]) -> set[int]:
    """Positions des premieres et dernieres lignes non vides, hors lignes de tableau.

    Les lignes de tableau sont exclues : l'en-tete d'un tableau repete sur chaque page
    est une information, pas un pied de page.
    """
    non_vides = [i for i, ligne in enumerate(lignes) if ligne.strip()]
    bordure = non_vides[:NB_LIGNES_BORDURE] + non_vides[-NB_LIGNES_BORDURE:]
    return {i for i in bordure if not lignes[i].lstrip().startswith("|")}


def lignes_de_bordure(texte: str) -> list[str]:
    lignes = texte.splitlines()
    return [lignes[i] for i in sorted(positions_de_bordure(lignes))]


def lignes_repetees(pages: list[str]) -> set[str]:
    """Lignes de bordure presentes sur au moins la moitie des pages du document."""
    if len(pages) < NB_PAGES_MIN_POUR_REPETITIONS:
        return set()
    presence = Counter()
    for texte in pages:
        presence.update({normaliser_ligne(ligne) for ligne in lignes_de_bordure(texte)})
    seuil = PART_PAGES_LIGNE_REPETEE * len(pages)
    return {ligne for ligne, nb in presence.items() if nb >= seuil}


def retirer_lignes(texte: str, a_retirer: set[str]) -> str:
    """Retire les lignes repetees, uniquement quand elles sont en bordure de page."""
    lignes = texte.splitlines()
    bordure = positions_de_bordure(lignes)
    gardees = [
        ligne
        for i, ligne in enumerate(lignes)
        if not (i in bordure and normaliser_ligne(ligne) in a_retirer)
    ]
    return "\n".join(gardees).strip()


def extraire_document(document: config.Document) -> dict[str, list[dict]]:
    """Renvoie l'etat des pages a chaque etape du nettoyage (pour l'entonnoir)."""
    chemin = config.DONNEES_BRUT / f"{document.identifiant}.pdf"
    brut = pymupdf4llm.to_markdown(str(chemin), page_chunks=True, show_progress=False)
    pages = [
        {"document": document.identifiant, "page": p["metadata"]["page_number"], "texte": p["text"]}
        for p in brut
    ]

    balisage = [{**p, "texte": nettoyer_balisage(p["texte"])} for p in pages]

    repetees = lignes_repetees([p["texte"] for p in balisage])
    sans_repetitions = [{**p, "texte": retirer_lignes(p["texte"], repetees)} for p in balisage]

    gardees = [p for p in sans_repetitions if p["texte"]]

    return {
        "1. Pages extraites (Markdown brut)": pages,
        "2. Balisage retiré (gras, barré, <br>)": balisage,
        "3. En-têtes et pieds de page retirés": sans_repetitions,
        "4. Pages vides écartées": gardees,
    }


def ecrire_jsonl(pages: list[dict], identifiant: str) -> None:
    chemin = config.DONNEES_TRAITE / f"{identifiant}.jsonl"
    with chemin.open("w", encoding="utf-8") as f:
        for page in pages:
            f.write(json.dumps(page, ensure_ascii=False) + "\n")


def extraire_corpus() -> pd.DataFrame:
    config.creer_dossiers()
    tokenizer = Tokenizer.from_pretrained(config.MODELE_EMBEDDING)

    def nb_tokens(texte: str) -> int:
        return len(tokenizer.encode(texte, add_special_tokens=False).ids)

    totaux: dict[str, dict[str, int]] = {}
    for document in config.CORPUS:
        etapes = extraire_document(document)
        for etape, pages in etapes.items():
            t = totaux.setdefault(etape, {"pages": 0, "caracteres": 0, "tokens_bge_m3": 0})
            t["pages"] += len(pages)
            t["caracteres"] += sum(len(p["texte"]) for p in pages)
            t["tokens_bge_m3"] += sum(nb_tokens(p["texte"]) for p in pages)
        pages_finales = list(etapes.values())[-1]
        ecrire_jsonl(pages_finales, document.identifiant)
        nb_depart = len(list(etapes.values())[0])
        print(f"  ✔ {document.identifiant:<30} {len(pages_finales):3d} / {nb_depart:3d} pages")

    entonnoir = pd.DataFrame.from_dict(totaux, orient="index").rename_axis("etape").reset_index()
    entonnoir.to_csv(
        config.DONNEES_AGREGE / "entonnoir_extraction.csv",
        sep=config.SEPARATEUR_EXPORT,
        encoding=config.ENCODAGE_EXPORT,
        index=False,
    )
    return entonnoir


if __name__ == "__main__":
    resultat = extraire_corpus()
    print()
    print(resultat.to_string(index=False))
