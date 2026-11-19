"""Reponse a une question a partir des passages retrouves, avec citation des sources.

Lancement depuis la racine du projet (Ollama demarre, index construit) :
    python -m src.generation "Combien de temps garder les CV des candidats non retenus ?"
Meme question posee a l'API Claude (cle dans .env) :
    python -m src.generation --claude "Combien de temps garder les CV ?"

Le RAG en trois temps : 1. retrouver les passages proches de la question (src.recherche) ;
2. les donner au modele avec la consigne de n'utiliser qu'eux ; 3. renvoyer la reponse avec
les passages cites, pour que l'utilisateur puisse verifier.
"""

import re
import sys
import time
from dataclasses import dataclass

import requests

from src import config
from src.api_claude import appeler_claude
from src.recherche import PassageTrouve, rechercher

CONSIGNES = f"""Tu réponds à des questions sur les guides et recommandations de la CNIL.

Règles, à respecter strictement :
1. Réponds uniquement à partir des passages fournis, jamais avec tes propres connaissances.
2. Si les passages ne permettent pas de répondre, ta réponse entière est cette phrase, mot
   pour mot, sans rien ajouter : {config.PHRASE_REFUS}
3. Après chaque affirmation, cite le numéro du passage qui l'appuie, seul entre crochets :
   [2], ou [1][3] pour deux passages. Pas de numéro d'article ni de page dans les crochets.
4. Si la question affirme une règle que les passages contredisent, corrige-la en citant le
   passage.
5. Réponds en français, en trois phrases au plus."""

# Les consignes sont rappelees APRES les passages : un modele de 7 milliards de parametres
# suit mieux ce qu'il vient de lire que ce qu'il a lu 3 000 tokens plus tot.
# La reponse partielle est autorisee : sans elle, le modele refusait des questions dont les
# passages couvraient une partie (variante retenue parmi 5 essayees le 2026-10-25 :
# 8 refus a tort sur 32 au lieu de 9, autant de bons refus).
RAPPEL_REPONSE = (
    "Réponds à la question à partir de ces passages seulement, en citant leurs numéros. "
    "Si les passages ne répondent qu'à une partie de la question, réponds à cette partie "
    "et dis ce qui manque. Si aucun passage ne traite du sujet de la question, écris "
    f"seulement : {config.PHRASE_REFUS}"
)
# Garde-fou avant la reponse : une question fermee, a laquelle un petit modele repond
# mieux qu'a une consigne de refus noyee dans une demande de reponse.
QUESTION_VERIFICATION = (
    "Avant toute réponse : l'un des passages ci-dessus contient-il explicitement "
    "l'information demandée par la question ? Réponds uniquement par OUI ou par NON."
)


@dataclass
class Reponse:
    question: str
    texte: str
    refus: bool
    passages: list[PassageTrouve]
    cites: list[int]  # numeros (a partir de 1) des passages cites dans la reponse
    tokens_prompt: int
    tokens_reponse: int
    duree_s: float
    modele: str = config.MODELE_GENERATION
    cout_usd: float = 0.0  # modele local : aucun cout a l'appel


def construire_prompt(question: str, passages: list[PassageTrouve], consigne: str) -> str:
    blocs = [
        f"[{i}] {p.titre} ({p.pages})\n{p.texte}" for i, p in enumerate(passages, start=1)
    ]
    # Meme debut pour la verification et la reponse : Ollama reutilise alors le calcul
    # deja fait sur les passages, et le second appel ne relit pas 3 000 tokens.
    return "Passages :\n\n" + "\n\n".join(blocs) + f"\n\nQuestion : {question}\n\n{consigne}"


def est_un_refus(texte: str) -> bool:
    # Comparaison sans guillemets ni ponctuation finale : le modele les ajoute parfois.
    def normaliser(t: str) -> str:
        return re.sub(r"[«»\"'.\s]+", " ", t).strip().lower()

    return normaliser(config.PHRASE_REFUS) in normaliser(texte)


def extraire_citations(texte: str, nb_passages: int) -> list[int]:
    """Numeros des passages cites entre crochets, y compris groupes (« [1, 3] »).

    Un numero hors de la liste des passages (un numero d'article recopie) est ignore.
    """
    groupes = re.findall(r"\[([\d,\s]+)\]", texte)
    nombres = re.findall(r"\d+", " ".join(groupes))
    return sorted({int(n) for n in nombres if 1 <= int(n) <= nb_passages})


def appeler_ollama(prompt: str, nb_tokens_max: int = -1) -> dict:
    requete = {
        "model": config.MODELE_GENERATION,
        "messages": [
            {"role": "system", "content": CONSIGNES},
            {"role": "user", "content": prompt},
        ],
        "stream": False,
        # Temperature 0 : la meme question donne la meme reponse, condition pour evaluer.
        # num_ctx fixe : par defaut, Ollama tronque le prompt sans prevenir.
        "options": {
            "temperature": 0,
            "num_ctx": config.CONTEXTE_GENERATION,
            "num_predict": nb_tokens_max,
        },
    }
    for essai in range(2):
        reponse = requests.post(f"{config.URL_OLLAMA}/api/chat", json=requete, timeout=300)
        # Erreur 500 : le moteur d'Ollama s'est arrete (memoire GPU) et redemarre tout seul.
        # Un seul nouvel essai : au-dela, c'est un vrai probleme, qu'on laisse remonter.
        if reponse.status_code < 500 or essai == 1:
            break
        time.sleep(5)
    reponse.raise_for_status()
    return reponse.json()


def repondre(
    question: str,
    k: int = config.NB_PASSAGES,
    verifier: bool = True,
    passages: list[PassageTrouve] | None = None,
) -> Reponse:
    """Reponse de Mistral (Ollama). `passages` permet de fournir des passages deja
    retrouves : l'evaluation donne ainsi les memes aux deux modeles."""
    debut = time.perf_counter()
    if passages is None:
        passages = rechercher(question, k)
    tokens_prompt = tokens_reponse = 0

    if verifier:
        verification = appeler_ollama(
            construire_prompt(question, passages, QUESTION_VERIFICATION), nb_tokens_max=3
        )
        tokens_prompt += verification.get("prompt_eval_count", 0)
        tokens_reponse += verification.get("eval_count", 0)
        if verification["message"]["content"].strip().upper().startswith("NON"):
            return Reponse(
                question, config.PHRASE_REFUS, True, passages, [], tokens_prompt,
                tokens_reponse, time.perf_counter() - debut,
            )

    resultat = appeler_ollama(construire_prompt(question, passages, RAPPEL_REPONSE))
    texte = resultat["message"]["content"].strip()
    refus = est_un_refus(texte)
    cites = extraire_citations(texte, len(passages))
    return Reponse(
        question=question,
        texte=texte,
        refus=refus,
        passages=passages,
        cites=[] if refus else cites,
        # Compte reel renvoye par Ollama : la seule facon de verifier que le prompt tient
        # dans le contexte.
        tokens_prompt=tokens_prompt + resultat.get("prompt_eval_count", 0),
        tokens_reponse=tokens_reponse + resultat.get("eval_count", 0),
        duree_s=time.perf_counter() - debut,
    )


def repondre_claude(
    question: str, k: int = config.NB_PASSAGES, passages: list[PassageTrouve] | None = None
) -> Reponse:
    """Meme prompt que pour Mistral (consignes, passages, rappel), envoye a l'API Claude.

    Pas de garde-fou OUI/NON ici : il a ete ajoute pour aider un petit modele, et il
    doublerait le nombre d'appels factures.
    """
    debut = time.perf_counter()
    if passages is None:
        passages = rechercher(question, k)
    appel = appeler_claude(
        config.MODELE_CLAUDE,
        CONSIGNES,
        construire_prompt(question, passages, RAPPEL_REPONSE),
        config.EFFORT_CLAUDE,
    )
    refus = est_un_refus(appel.texte)
    return Reponse(
        question=question,
        texte=appel.texte,
        refus=refus,
        passages=passages,
        cites=[] if refus else extraire_citations(appel.texte, len(passages)),
        tokens_prompt=appel.tokens_entree,
        tokens_reponse=appel.tokens_sortie,
        duree_s=time.perf_counter() - debut,
        modele=config.MODELE_CLAUDE,
        cout_usd=appel.cout_usd,
    )


def afficher(reponse: Reponse) -> None:
    print(f"\nQuestion : {reponse.question}\n")
    print(reponse.texte)
    print("\nSources citées :" if reponse.cites else "\nAucune source citée.")
    for n in reponse.cites:
        p = reponse.passages[n - 1]
        print(f"  [{n}] {p.titre}, {p.pages} (similarité {p.score:.2f})")
    print("\nPassages retrouvés :")
    for n, p in enumerate(reponse.passages, start=1):
        print(f"  [{n}] {p.document}, {p.pages}, {p.score:.2f} : {p.section[:60]}")
    print(
        f"\n{reponse.modele} : {reponse.tokens_prompt} tokens de prompt, "
        f"{reponse.tokens_reponse} de réponse, {reponse.duree_s:.1f} s, "
        f"{reponse.cout_usd:.4f} $"
    )


if __name__ == "__main__":
    arguments = sys.argv[1:]
    avec_claude = "--claude" in arguments
    question = " ".join(a for a in arguments if a != "--claude")
    if not question:
        sys.exit('Usage : python -m src.generation [--claude] "votre question"')
    afficher(repondre_claude(question) if avec_claude else repondre(question))
