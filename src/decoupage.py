"""Decoupage des pages du corpus en passages a indexer.

Lancement depuis la racine du projet (apres src.extraction) :
    python -m src.decoupage

Produit :
- donnees/traite/passages.jsonl : un passage par ligne, avec ses metadonnees
  (document, pages, section) et le texte a indexer
- donnees/agrege/decoupage_resume.csv : nombre de passages et taille en tokens

Strategie « structure » (la premiere ; une seconde sera comparee en phase 6) :
1. chaque page est coupee en blocs : titres, paragraphes, tableaux ;
2. les blocs sont regroupes dans l'ordre du document jusqu'a TAILLE_MAX_TOKENS ;
3. un nouveau titre ouvre un nouveau passage (une partie = une idee) ;
4. un tableau trop long est coupe entre deux lignes, en-tete repete dans chaque morceau ;
5. chaque passage est precede du titre du document et de sa section : un passage sur
   « 5 ans » ne dit pas de quoi il parle, son contexte si.
"""

import json
import re
import statistics
from dataclasses import dataclass, field

import pandas as pd
from tokenizers import Tokenizer

from src import config

# 500 tokens bge-m3, soit 250 a 320 mots (mesure du 2026-10-09). Assez pour porter une
# regle et sa justification, assez court pour que 5 passages tiennent dans le contexte de
# Mistral avec les consignes. bge-m3 accepte 8 192 tokens, mais un passage long dilue son
# sens dans un seul vecteur : il ressemble a tout et a rien.
TAILLE_MAX_TOKENS = 500
# Un titre ouvre un nouveau passage, sauf si le passage en cours est encore trop court
# pour se suffire a lui-meme (un intertitre suivi de deux lignes).
TAILLE_MIN_AVANT_TITRE = 150
# Chevauchement : quand un passage est coupe parce qu'il est plein (et non sur un titre),
# son dernier paragraphe est repris en tete du suivant s'il fait au plus 100 tokens
# (20 % du passage). Une regle coupee en deux reste ainsi lisible des deux cotes.
CHEVAUCHEMENT_MAX_TOKENS = 100

# Ligne de sommaire : un intitule suivi d'une ligne de points et d'un numero de page
# (« 1.2 Qu'est-ce que... ........ 4 »). Ces lignes reprennent les mots de tous les
# titres du document et remonteraient en tete de la recherche sans rien apprendre.
MOTIF_LIGNE_SOMMAIRE = re.compile(r"\.{5,}\s*\d+\s*\|?\s*$")
# Fin de phrase : point, point d'exclamation ou d'interrogation, suivi d'une espace.
MOTIF_FIN_DE_PHRASE = re.compile(r"(?<=[.!?])\s+")


@dataclass
class Bloc:
    texte: str
    page: int
    nature: str  # "titre", "tableau" ou "texte"


@dataclass
class Passage:
    document: str
    blocs: list[Bloc] = field(default_factory=list)
    section: str = ""

    @property
    def contenu(self) -> str:
        return "\n\n".join(b.texte for b in self.blocs)

    @property
    def pages(self) -> list[int]:
        return sorted({b.page for b in self.blocs})


def est_ligne_de_tableau(ligne: str) -> bool:
    return ligne.lstrip().startswith("|")


def retirer_lignes_sommaire(texte: str) -> tuple[str, int]:
    """Retire les lignes de sommaire ; renvoie le texte et le nombre de lignes retirees."""
    lignes = texte.splitlines()
    gardees = [ligne for ligne in lignes if not MOTIF_LIGNE_SOMMAIRE.search(ligne)]
    return "\n".join(gardees), len(lignes) - len(gardees)


def decouper_en_blocs(texte: str, page: int) -> list[Bloc]:
    """Coupe une page en blocs : un titre, un paragraphe ou un tableau entier."""
    blocs = []
    for paragraphe in re.split(r"\n\s*\n", texte):
        lignes = [ligne for ligne in paragraphe.splitlines() if ligne.strip()]
        # Un titre colle au paragraphe suivant devient un bloc a part.
        while lignes and lignes[0].lstrip().startswith("#"):
            blocs.append(Bloc(lignes.pop(0).strip(), page, "titre"))
        if not lignes:
            continue
        # Un paragraphe peut melanger texte et tableau : on les separe.
        groupe, groupe_tableau = [], None
        for ligne in lignes:
            tableau = est_ligne_de_tableau(ligne)
            if groupe and tableau != groupe_tableau:
                nature = "tableau" if groupe_tableau else "texte"
                blocs.append(Bloc("\n".join(groupe), page, nature))
                groupe = []
            groupe.append(ligne)
            groupe_tableau = tableau
        blocs.append(Bloc("\n".join(groupe), page, "tableau" if groupe_tableau else "texte"))
    return blocs


def texte_titre(bloc: Bloc) -> str:
    return bloc.texte.lstrip("#").strip()


class Decoupeur:
    """Regroupe les blocs d'un document en passages d'au plus `taille_max` tokens."""

    def __init__(
        self,
        tokenizer: Tokenizer,
        taille_max: int = TAILLE_MAX_TOKENS,
        taille_min_avant_titre: int = TAILLE_MIN_AVANT_TITRE,
        chevauchement_max: int = CHEVAUCHEMENT_MAX_TOKENS,
    ):
        self.tokenizer = tokenizer
        self.taille_max = taille_max
        self.taille_min_avant_titre = taille_min_avant_titre
        self.chevauchement_max = chevauchement_max

    def nb_tokens(self, texte: str) -> int:
        return len(self.tokenizer.encode(texte, add_special_tokens=False).ids)

    def entete(self, titre_document: str, section: str) -> str:
        return f"{titre_document}\n{section}".strip() + "\n\n"

    def texte_indexe(self, titre_document: str, passage: Passage) -> str:
        return self.entete(titre_document, passage.section) + passage.contenu

    def couper_bloc_trop_long(self, bloc: Bloc, budget: int) -> list[Bloc]:
        """Coupe un bloc qui ne tient pas seul dans un passage.

        Tableau : entre deux lignes, en repetant l'en-tete (ligne de titres + ligne de
        tirets) en tete de chaque morceau, sinon « 5 ans » n'a plus de colonne. Une ligne
        de tableau trop longue a elle seule est coupee entre deux phrases, en-tete repete.
        Texte : entre deux phrases.
        """
        if bloc.nature == "tableau":
            lignes = bloc.texte.splitlines()
            a_un_entete = len(lignes) > 2 and set(lignes[1].replace("|", "").strip()) <= set(
                "-: "
            )
            entete = "\n".join(lignes[:2]) + "\n" if a_un_entete else ""
            unites = lignes[2:] if a_un_entete else lignes
            morceaux = self.regrouper(unites, "\n", entete, budget)
        else:
            entete = ""
            morceaux = self.regrouper(MOTIF_FIN_DE_PHRASE.split(bloc.texte), " ", "", budget)

        resultat = []
        for morceau in morceaux:
            if self.nb_tokens(morceau) > budget and bloc.nature == "tableau":
                # Une seule ligne de tableau trop longue : coupee entre ses phrases.
                phrases = MOTIF_FIN_DE_PHRASE.split(morceau[len(entete) :])
                morceaux_ligne = self.regrouper(phrases, " ", entete, budget)
            else:
                morceaux_ligne = [morceau]
            for texte in morceaux_ligne:
                if self.nb_tokens(texte) <= budget:
                    resultat.append(Bloc(texte, bloc.page, bloc.nature))
                    continue
                # Une seule phrase plus longue que le passage : coupe au token pres, en
                # dernier recours.
                ids = self.tokenizer.encode(texte, add_special_tokens=False).ids
                for debut in range(0, len(ids), budget):
                    texte_coupe = self.tokenizer.decode(ids[debut : debut + budget])
                    resultat.append(Bloc(texte_coupe, bloc.page, bloc.nature))
        return resultat

    def regrouper(self, unites: list[str], separateur: str, prefixe: str, budget: int) -> list[str]:
        """Regroupe des unites (lignes, phrases) en morceaux d'au plus `budget` tokens,
        chacun precede de `prefixe` (l'en-tete d'un tableau, ou rien)."""
        morceaux, courant = [], []
        for unite in unites:
            candidat = prefixe + separateur.join(courant + [unite])
            if courant and self.nb_tokens(candidat) > budget:
                morceaux.append(prefixe + separateur.join(courant))
                courant = []
            courant.append(unite)
        if courant:
            morceaux.append(prefixe + separateur.join(courant))
        return morceaux

    def decouper_document(self, document: config.Document, pages: list[dict]) -> list[Passage]:
        blocs = []
        for page in pages:
            blocs.extend(decouper_en_blocs(page["texte"], page["page"]))

        passages: list[Passage] = []
        section = ""
        courant = Passage(document.identifiant, section=section)

        def taille(p: Passage) -> int:
            return self.nb_tokens(self.texte_indexe(document.titre, p))

        def clore(chevauchement: bool) -> Passage:
            nonlocal courant
            if not courant.blocs:
                return courant
            passages.append(courant)
            suivant = Passage(document.identifiant, section=section)
            dernier = courant.blocs[-1]
            if (
                chevauchement
                and dernier.nature == "texte"
                and self.nb_tokens(dernier.texte) <= self.chevauchement_max
            ):
                suivant.blocs.append(dernier)
            courant = suivant
            return courant

        for bloc in blocs:
            if bloc.nature == "titre":
                if taille(courant) >= self.taille_min_avant_titre:
                    clore(chevauchement=False)
                section = texte_titre(bloc)
                if not courant.blocs or all(b.nature == "titre" for b in courant.blocs):
                    courant.section = section

            budget = self.taille_max - self.nb_tokens(self.entete(document.titre, section)) - 4
            morceaux = [bloc] if self.nb_tokens(bloc.texte) <= budget else (
                self.couper_bloc_trop_long(bloc, budget)
            )
            for morceau in morceaux:
                courant.blocs.append(morceau)
                if taille(courant) > self.taille_max:
                    courant.blocs.pop()
                    clore(chevauchement=True)
                    courant.blocs.append(morceau)
                    if taille(courant) > self.taille_max:
                        # Le paragraphe repris en chevauchement ne laisse pas la place.
                        courant.blocs = [morceau]
        clore(chevauchement=False)
        return passages


def lire_pages(identifiant: str) -> list[dict]:
    chemin = config.DONNEES_TRAITE / f"{identifiant}.jsonl"
    with chemin.open(encoding="utf-8") as f:
        return [json.loads(ligne) for ligne in f]


def decouper_corpus() -> pd.DataFrame:
    tokenizer = Tokenizer.from_pretrained(config.MODELE_EMBEDDING)
    decoupeur = Decoupeur(tokenizer)

    lignes_sortie, lignes_resume, nb_lignes_sommaire = [], [], 0
    for document in config.CORPUS:
        pages = []
        for page in lire_pages(document.identifiant):
            texte, retirees = retirer_lignes_sommaire(page["texte"])
            nb_lignes_sommaire += retirees
            pages.append({**page, "texte": texte})

        passages = decoupeur.decouper_document(document, pages)
        tailles = []
        for numero, passage in enumerate(passages, start=1):
            texte_indexe = decoupeur.texte_indexe(document.titre, passage)
            nb = decoupeur.nb_tokens(texte_indexe)
            tailles.append(nb)
            lignes_sortie.append(
                {
                    "id": f"{document.identifiant}-{numero:03d}",
                    "document": document.identifiant,
                    "titre": document.titre,
                    "theme": document.theme,
                    "page_debut": passage.pages[0],
                    "page_fin": passage.pages[-1],
                    "section": passage.section,
                    "contient_tableau": any(b.nature == "tableau" for b in passage.blocs),
                    "nb_tokens": nb,
                    "texte": passage.contenu,
                    "texte_indexe": texte_indexe,
                }
            )
        lignes_resume.append(
            {
                "document": document.identifiant,
                "pages": len(pages),
                "passages": len(passages),
                "tokens_median": int(statistics.median(tailles)),
                "tokens_max": max(tailles),
            }
        )
        nb_pages, nb_passages = len(pages), len(passages)
        print(f"  ✔ {document.identifiant:<30} {nb_pages:3d} pages -> {nb_passages:3d} passages")

    with (config.DONNEES_TRAITE / "passages.jsonl").open("w", encoding="utf-8", newline="\n") as f:
        for ligne in lignes_sortie:
            f.write(json.dumps(ligne, ensure_ascii=False) + "\n")

    resume = pd.DataFrame(lignes_resume)
    resume.to_csv(
        config.DONNEES_AGREGE / "decoupage_resume.csv",
        sep=config.SEPARATEUR_EXPORT,
        encoding=config.ENCODAGE_EXPORT,
        index=False,
    )
    tailles = [ligne["nb_tokens"] for ligne in lignes_sortie]
    print(
        f"\n{len(lignes_sortie)} passages, {sum(tailles)} tokens, "
        f"taille mediane {int(statistics.median(tailles))}, max {max(tailles)} ; "
        f"{sum(ligne['contient_tableau'] for ligne in lignes_sortie)} avec tableau ; "
        f"{nb_lignes_sommaire} lignes de sommaire retirees"
    )
    return resume


if __name__ == "__main__":
    decouper_corpus()
