"""Premier essai de la generation : refus et citations sur les 44 questions.

Lancement depuis la racine du projet (Ollama demarre, index construit) :
    python -m src.evaluation_refus

Produit : donnees/agrege/refus_premier_essai.csv (une ligne par question et par
configuration, avec la reponse complete).

Ce n'est pas encore l'evaluation de la phase 5 : on ne juge pas ici si la reponse est
juste, seulement si le systeme refuse quand il le faut, et seulement dans ce cas.
"""

import pandas as pd

from src import config
from src.evaluation_recherche import lire_questions
from src.generation import repondre


def essayer_refus() -> pd.DataFrame:
    lignes = []
    for verifier in (False, True):
        for q in lire_questions():
            r = repondre(q["question"], verifier=verifier)
            lignes.append(
                {
                    "garde_fou": verifier,
                    "id": q["id"],
                    "type": q["type"],
                    "avec_reponse": bool(q.get("sources")),
                    "refus": r.refus,
                    "passages_cites": " ".join(map(str, r.cites)),
                    "tokens_prompt": r.tokens_prompt,
                    "duree_s": round(r.duree_s, 2),
                    "reponse": r.texte.replace("\n", " "),
                }
            )
            print(f"  garde-fou={verifier!s:<5} {q['id']} refus={r.refus}", flush=True)
    resultat = pd.DataFrame(lignes)
    resultat.to_csv(
        config.DONNEES_AGREGE / "refus_premier_essai.csv",
        sep=config.SEPARATEUR_EXPORT,
        encoding=config.ENCODAGE_EXPORT,
        index=False,
    )
    return resultat


if __name__ == "__main__":
    resultat = essayer_refus()
    print()
    print(
        resultat.groupby(["garde_fou", "avec_reponse"])
        .agg(questions=("id", "size"), refus=("refus", "sum"), duree_mediane=("duree_s", "median"))
        .to_string()
    )
