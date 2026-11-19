"""Generation sur les 44 questions : Mistral (local) et Claude (API), memes passages.

Lancement depuis la racine du projet (Ollama demarre, index construit, cle dans .env) :
    python -m src.evaluation_generation --estimer          cout estime, sans rien generer
    python -m src.evaluation_generation --ids Q01 Q13 Q40  essai : affiche, n'ecrit rien
    python -m src.evaluation_generation                    les 44 questions

Produit : donnees/agrege/generation_reponses.csv (une ligne par question et par
configuration, avec la reponse complete, les tokens, la duree et le cout).

Les passages sont retrouves une seule fois par question, puis donnes tels quels aux trois
configurations : un ecart entre elles vient donc du modele, pas de la recherche.
L'exactitude des reponses est jugee ensuite, par src.evaluation_exactitude.
"""

import argparse

import pandas as pd

from src import config
from src.api_claude import client, cout_usd
from src.evaluation_recherche import lire_questions, rang_du_premier_bon
from src.generation import (
    CONSIGNES,
    RAPPEL_REPONSE,
    appeler_ollama,
    construire_prompt,
    repondre,
    repondre_claude,
)
from src.recherche import PassageTrouve, rechercher

FICHIER_REPONSES = config.DONNEES_AGREGE / "generation_reponses.csv"
CONFIGURATIONS = ("mistral", "mistral_garde_fou", "claude")

# Hypotheses de l'estimation, volontairement larges (la reflexion du modele est facturee
# en sortie, et ne se compte pas a l'avance). Le cout reel est dans les fichiers produits.
SORTIE_SUPPOSEE_GENERATION = 800
ENTREE_SUPPOSEE_JUGE = 1200
SORTIE_SUPPOSEE_JUGE = 800


def repondre_selon(configuration: str, question: str, passages: list[PassageTrouve]):
    if configuration == "claude":
        return repondre_claude(question, passages=passages)
    return repondre(
        question, verifier=(configuration == "mistral_garde_fou"), passages=passages
    )


def generer(questions: list[dict], bavard: bool = False) -> pd.DataFrame:
    # Toutes les recherches d'abord : le modele d'embedding et Ollama partagent la carte
    # graphique, et les passages sont ainsi figes avant la premiere reponse.
    passages = {q["id"]: rechercher(q["question"]) for q in questions}
    # Premier appel a vide : sans lui, la premiere question paierait le chargement de
    # Mistral en memoire, et sa duree n'aurait rien a voir avec les autres.
    appeler_ollama("Bonjour", nb_tokens_max=1)

    lignes = []
    # Une configuration apres l'autre, et non une question apres l'autre : Ollama garde en
    # memoire le dernier prompt, et le second appel sur les memes passages serait avantage.
    for configuration in CONFIGURATIONS:
        for q in questions:
            r = repondre_selon(configuration, q["question"], passages[q["id"]])
            avec_reponse = bool(q.get("sources"))
            rang = rang_du_premier_bon(r.passages, q["sources"]) if avec_reponse else None
            lignes.append(
                {
                    "configuration": configuration,
                    "modele": r.modele,
                    "id": q["id"],
                    "type": q["type"],
                    "avec_reponse": avec_reponse,
                    # Rang du premier passage qui couvre une page source (vide : aucun
                    # des 5). Separe les erreurs de recherche des erreurs de generation.
                    "rang_bon_passage": rang,
                    "refus": r.refus,
                    "passages_cites": " ".join(map(str, r.cites)),
                    "tokens_entree": r.tokens_prompt,
                    "tokens_sortie": r.tokens_reponse,
                    "duree_s": round(r.duree_s, 2),
                    "cout_usd": round(r.cout_usd, 6),
                    "reponse": r.texte.replace("\n", " "),
                }
            )
            print(
                f"  {configuration:<18} {q['id']} refus={r.refus!s:<5} "
                f"{r.duree_s:5.1f} s  {r.cout_usd:.4f} $",
                flush=True,
            )
            if bavard:
                print(f"      {r.texte}\n", flush=True)
    return pd.DataFrame(lignes)


def estimer(questions: list[dict]) -> float:
    """Cout estime du lancement complet, juge compris. Le comptage des tokens du prompt
    est exact (compteur de l'API, gratuit) ; les tokens de sortie sont une hypothese."""
    entree = 0
    for q in questions:
        prompt = construire_prompt(q["question"], rechercher(q["question"]), RAPPEL_REPONSE)
        entree += (
            client()
            .messages.count_tokens(
                model=config.MODELE_CLAUDE,
                system=CONSIGNES,
                messages=[{"role": "user", "content": prompt}],
            )
            .input_tokens
        )
    generation = cout_usd(
        config.MODELE_CLAUDE, entree, SORTIE_SUPPOSEE_GENERATION * len(questions)
    )
    # Au plus un jugement par question avec reponse et par configuration.
    nb_jugements = sum(bool(q.get("sources")) for q in questions) * len(CONFIGURATIONS)
    juge = cout_usd(
        config.MODELE_JUGE,
        ENTREE_SUPPOSEE_JUGE * nb_jugements,
        SORTIE_SUPPOSEE_JUGE * nb_jugements,
    )
    print(f"Génération {config.MODELE_CLAUDE} : {entree} tokens d'entrée comptés, "
          f"{SORTIE_SUPPOSEE_GENERATION} de sortie supposés par réponse : {generation:.2f} $")
    print(f"Juge {config.MODELE_JUGE} : {nb_jugements} jugements au plus : {juge:.2f} $")
    print(f"Total estimé : {generation + juge:.2f} $")
    return generation + juge


if __name__ == "__main__":
    analyseur = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    analyseur.add_argument("--estimer", action="store_true", help="estime le coût, sans générer")
    analyseur.add_argument("--ids", nargs="+", help="essai sur ces questions, sans rien écrire")
    arguments = analyseur.parse_args()

    questions = lire_questions()
    if arguments.estimer:
        estimer(questions)
    elif arguments.ids:
        essai = generer([q for q in questions if q["id"] in arguments.ids], bavard=True)
        print(f"Coût de l'essai : {essai['cout_usd'].sum():.4f} $")
    else:
        reponses = generer(questions)
        # Garde-fou avant l'export : une ligne par question et par configuration.
        assert len(reponses) == len(questions) * len(CONFIGURATIONS)
        reponses.to_csv(
            FICHIER_REPONSES,
            sep=config.SEPARATEUR_EXPORT,
            encoding=config.ENCODAGE_EXPORT,
            index=False,
        )
        print(f"\n{FICHIER_REPONSES.name} écrit. Coût : {reponses['cout_usd'].sum():.4f} $")
