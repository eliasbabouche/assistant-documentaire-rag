"""Premiere mesure de la recherche, seule, sur le jeu d'evaluation.

Lancement depuis la racine du projet (apres src.indexation) :
    python -m src.evaluation_recherche

Produit :
- donnees/agrege/recherche_questions.csv : rang du premier bon passage, question par question
- donnees/agrege/recherche_resume.csv : hit rate a 1, 3, 5, 10 et MRR

On mesure la recherche avant la generation : si le bon passage n'est pas retrouve, le
meilleur modele du monde ne peut pas repondre juste.
"""

import pandas as pd
import yaml

from src import config
from src.recherche import PassageTrouve, rechercher

K_MAX = 10
VALEURS_K = (1, 3, 5, 10)


def lire_questions() -> list[dict]:
    with (config.DOSSIER_EVALUATION / "questions.yaml").open(encoding="utf-8") as f:
        return yaml.safe_load(f)


def contient_la_reponse(passage: PassageTrouve, sources: list[dict]) -> bool:
    """Un passage est bon s'il vient d'un document source et couvre l'une de ses pages."""
    return any(
        passage.document == source["document"]
        and any(passage.page_debut <= page <= passage.page_fin for page in source["pages"])
        for source in sources
    )


def rang_du_premier_bon(passages: list[PassageTrouve], sources: list[dict]) -> int | None:
    for rang, passage in enumerate(passages, start=1):
        if contient_la_reponse(passage, sources):
            return rang
    return None


def evaluer_recherche() -> tuple[pd.DataFrame, pd.DataFrame]:
    lignes = []
    for q in lire_questions():
        passages = rechercher(q["question"], K_MAX)
        avec_reponse = bool(q.get("sources"))
        rang = rang_du_premier_bon(passages, q["sources"]) if avec_reponse else None
        lignes.append(
            {
                "id": q["id"],
                "type": q["type"],
                "avec_reponse": avec_reponse,
                "rang_premier_bon": rang,
                "score_premier_passage": round(passages[0].score, 3),
                "premier_passage": f"{passages[0].document} {passages[0].pages}",
            }
        )
    detail = pd.DataFrame(lignes)
    detail.to_csv(
        config.DONNEES_AGREGE / "recherche_questions.csv",
        sep=config.SEPARATEUR_EXPORT,
        encoding=config.ENCODAGE_EXPORT,
        index=False,
    )

    rangs = detail.loc[detail["avec_reponse"], "rang_premier_bon"]
    resume = {"collection": config.COLLECTION, "questions_avec_reponse": len(rangs)}
    for k in VALEURS_K:
        resume[f"hit_rate_{k}"] = round(float((rangs <= k).mean()), 3)
    # MRR : moyenne de 1 / rang du premier bon passage (0 s'il n'est pas dans les 10).
    resume["mrr_10"] = round(float((1 / rangs).fillna(0).mean()), 3)
    scores = detail.groupby("avec_reponse")["score_premier_passage"].median()
    resume["score_median_avec_reponse"] = scores.get(True)
    resume["score_median_sans_reponse"] = scores.get(False)
    resume_df = pd.DataFrame([resume])
    resume_df.to_csv(
        config.DONNEES_AGREGE / "recherche_resume.csv",
        sep=config.SEPARATEUR_EXPORT,
        encoding=config.ENCODAGE_EXPORT,
        index=False,
    )
    return detail, resume_df


if __name__ == "__main__":
    detail, resume = evaluer_recherche()
    print(detail.to_string(index=False))
    print()
    print(resume.T.to_string(header=False))
