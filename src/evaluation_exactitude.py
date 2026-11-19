"""Exactitude des reponses, jugee contre les reponses de reference, et tableau de synthese.

Lancement depuis la racine du projet, apres src.evaluation_generation (cle dans .env) :
    python -m src.evaluation_exactitude            juge les reponses, puis ecrit le resume
    python -m src.evaluation_exactitude --resume   recalcule le resume seul (aucun appel)

Produit :
- donnees/agrege/generation_jugements.csv : un verdict par reponse jugee, avec sa raison
- donnees/agrege/generation_resume.csv : le tableau comparatif, une ligne par configuration

Qui est juge : seulement les reponses donnees a une question qui a une reponse. Un refus
ne passe pas devant le juge : il est compte a part (refus a tort, ou refus correct).
L'exactitude est le nombre de reponses « correcte » rapporte a TOUTES les questions qui
ont une reponse : un refus a tort compte donc comme une question ratee.
"""

import argparse

import pandas as pd

from src import config
from src.evaluation_generation import FICHIER_REPONSES
from src.evaluation_recherche import lire_questions
from src.juge import VERDICTS, juger

FICHIER_JUGEMENTS = config.DONNEES_AGREGE / "generation_jugements.csv"
FICHIER_RESUME = config.DONNEES_AGREGE / "generation_resume.csv"
COLONNES_REPONSES = {
    "configuration", "modele", "id", "avec_reponse", "rang_bon_passage", "refus",
    "tokens_entree", "tokens_sortie", "duree_s", "cout_usd", "reponse",
}


def lire(fichier) -> pd.DataFrame:
    return pd.read_csv(fichier, sep=config.SEPARATEUR_EXPORT, encoding=config.ENCODAGE_EXPORT)


def ecrire(tableau: pd.DataFrame, fichier) -> None:
    tableau.to_csv(
        fichier, sep=config.SEPARATEUR_EXPORT, encoding=config.ENCODAGE_EXPORT, index=False
    )


def a_juger(reponses: pd.DataFrame) -> pd.DataFrame:
    return reponses[reponses["avec_reponse"] & ~reponses["refus"]]


def juger_reponses(reponses: pd.DataFrame, questions: list[dict]) -> pd.DataFrame:
    par_id = {q["id"]: q for q in questions}
    lignes = []
    for r in a_juger(reponses).itertuples():
        q = par_id[r.id]
        j = juger(q["question"], q["reponse_attendue"], r.reponse)
        lignes.append(
            {
                "configuration": r.configuration,
                "id": r.id,
                "verdict": j.verdict,
                "justification": j.justification,
                "tokens_entree": j.tokens_entree,
                "tokens_sortie": j.tokens_sortie,
                "cout_usd": round(j.cout_usd, 6),
            }
        )
        print(f"  {r.configuration:<18} {r.id} {j.verdict}", flush=True)
    return pd.DataFrame(lignes)


def resumer(reponses: pd.DataFrame, jugements: pd.DataFrame) -> pd.DataFrame:
    """Une ligne par configuration : refus, exactitude, latence, cout."""
    manquantes = COLONNES_REPONSES - set(reponses.columns)
    if manquantes:
        raise ValueError(f"Colonnes absentes du fichier des réponses : {sorted(manquantes)}")
    juge = reponses.merge(jugements, on=["configuration", "id"], how="left", suffixes=("", "_juge"))
    # Garde-fou : toute reponse a juger doit avoir son verdict, et un verdict de la grille.
    sans_verdict = a_juger(juge)["verdict"].isna().sum()
    if sans_verdict:
        raise ValueError(f"{sans_verdict} réponses n'ont pas été jugées")
    hors_grille = set(jugements["verdict"]) - set(VERDICTS)
    if hors_grille:
        raise ValueError(f"Verdicts hors grille : {hors_grille}")

    lignes = []
    for configuration, groupe in juge.groupby("configuration", sort=False):
        avec = groupe[groupe["avec_reponse"]]
        sans = groupe[~groupe["avec_reponse"]]
        bon_passage = avec[avec["rang_bon_passage"].notna()]
        ligne = {
            "configuration": configuration,
            "modele": groupe["modele"].iloc[0],
            "questions_sans_reponse": len(sans),
            "refus_corrects": int(sans["refus"].sum()),
            "questions_avec_reponse": len(avec),
            "refus_a_tort": int(avec["refus"].sum()),
        }
        for verdict in VERDICTS:
            ligne[f"reponses_{verdict}s"] = int((avec["verdict"] == verdict).sum())
        ligne["exactitude"] = round(ligne["reponses_correctes"] / len(avec), 3)
        # Meme mesure, restreinte aux questions dont le bon passage a ete retrouve :
        # c'est la part qui revient a la generation seule.
        ligne["questions_bon_passage"] = len(bon_passage)
        ligne["correctes_bon_passage"] = int((bon_passage["verdict"] == "correcte").sum())
        ligne["duree_mediane_s"] = round(float(groupe["duree_s"].median()), 2)
        ligne["tokens_entree_moyens"] = round(float(groupe["tokens_entree"].mean()))
        ligne["tokens_sortie_moyens"] = round(float(groupe["tokens_sortie"].mean()))
        ligne["cout_total_usd"] = round(float(groupe["cout_usd"].sum()), 4)
        ligne["cout_par_question_usd"] = round(float(groupe["cout_usd"].mean()), 5)
        ligne["cout_juge_usd"] = round(float(groupe["cout_usd_juge"].sum()), 4)
        lignes.append(ligne)
    return pd.DataFrame(lignes)


def tirer_echantillon(jugements: pd.DataFrame, graine: int = 19) -> pd.DataFrame:
    """10 jugements a relire a la main : 4 « correcte », 3 « partielle », 3 « incorrecte »
    (ou moins s'il n'y en a pas assez), tires au sort avec une graine fixe. Sans cette
    repartition, l'echantillon ne contiendrait presque que des « correcte »."""
    parts = []
    for verdict, nombre in zip(VERDICTS, (4, 3, 3)):
        groupe = jugements[jugements["verdict"] == verdict]
        parts.append(groupe.sample(n=min(nombre, len(groupe)), random_state=graine))
    return pd.concat(parts)


if __name__ == "__main__":
    analyseur = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    analyseur.add_argument("--resume", action="store_true", help="résumé seul, sans juger")
    arguments = analyseur.parse_args()

    reponses = lire(FICHIER_REPONSES)
    if arguments.resume:
        jugements = lire(FICHIER_JUGEMENTS)
    else:
        jugements = juger_reponses(reponses, lire_questions())
        ecrire(jugements, FICHIER_JUGEMENTS)
        print(f"\nCoût du juge : {jugements['cout_usd'].sum():.4f} $")
    resume = resumer(reponses, jugements)
    ecrire(resume, FICHIER_RESUME)
    print()
    print(resume.set_index("configuration").T.to_string())
