"""Recherche des passages les plus proches d'une question dans l'index ChromaDB."""

from dataclasses import dataclass
from functools import lru_cache

from src import config, indexation


@dataclass
class PassageTrouve:
    id: str
    document: str
    titre: str
    page_debut: int
    page_fin: int
    section: str
    texte: str
    score: float  # similarite cosinus entre la question et le passage (1 = identique)

    @property
    def pages(self) -> str:
        if self.page_debut == self.page_fin:
            return f"p. {self.page_debut}"
        return f"p. {self.page_debut}-{self.page_fin}"


@lru_cache(maxsize=1)
def modele():
    return indexation.charger_modele()


@lru_cache(maxsize=1)
def collection():
    return indexation.ouvrir_collection()


def rechercher(question: str, k: int = config.NB_PASSAGES) -> list[PassageTrouve]:
    """La question est encodee par le meme modele que les passages, puis ChromaDB renvoie
    les k vecteurs les plus proches : c'est une recherche par le sens, pas par les mots."""
    vecteur = indexation.encoder(modele(), [question])
    resultat = collection().query(
        query_embeddings=vecteur,
        n_results=k,
        include=["documents", "metadatas", "distances"],
    )
    return [
        PassageTrouve(
            id=identifiant,
            document=meta["document"],
            titre=meta["titre"],
            page_debut=meta["page_debut"],
            page_fin=meta["page_fin"],
            section=meta["section"],
            texte=texte,
            score=1 - distance,
        )
        for identifiant, texte, meta, distance in zip(
            resultat["ids"][0],
            resultat["documents"][0],
            resultat["metadatas"][0],
            resultat["distances"][0],
        )
    ]
