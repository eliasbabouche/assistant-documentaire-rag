"""Embeddings des passages avec bge-m3 et index vectoriel ChromaDB.

Lancement depuis la racine du projet (apres src.decoupage) :
    python -m src.indexation

Produit : donnees/index/ (base ChromaDB sur disque, non versionnee).

Un embedding est un vecteur de 1 024 nombres qui resume le sens d'un texte : deux textes
qui disent la meme chose avec des mots differents ont des vecteurs proches. L'index
vectoriel range ces vecteurs pour retrouver vite les plus proches d'une question.
"""

import json
import time

from src import config

# Seuls les fichiers utiles a sentence-transformers sont telecharges (2,3 Go). Le depot
# contient aussi une version ONNX du modele (2,3 Go de plus) et des images du README.
FICHIERS_MODELE = [
    "*.json",
    "pytorch_model.bin",
    "sentencepiece.bpe.model",
    "1_Pooling/*",
]
FICHIERS_IGNORES = ["onnx/*", "imgs/*"]
# Les passages font au plus 500 tokens : inutile de laisser le modele preparer 8 192.
LONGUEUR_MAX_MODELE = 512
TAILLE_LOT = 32


def charger_modele():
    """Charge bge-m3 sur le GPU s'il y en a un, en demi-precision (deux fois moins de
    memoire et de calcul qu'en precision simple)."""
    import torch
    from huggingface_hub import snapshot_download
    from sentence_transformers import SentenceTransformer

    chemin = snapshot_download(
        config.MODELE_EMBEDDING,
        allow_patterns=FICHIERS_MODELE,
        ignore_patterns=FICHIERS_IGNORES,
    )
    gpu = torch.cuda.is_available()
    modele = SentenceTransformer(
        chemin,
        device="cuda" if gpu else "cpu",
        model_kwargs={"torch_dtype": torch.float16} if gpu else {},
    )
    modele.max_seq_length = LONGUEUR_MAX_MODELE
    return modele


def encoder(modele, textes: list[str]) -> list[list[float]]:
    # Vecteurs normalises (longueur 1) : la similarite cosinus devient un simple produit
    # scalaire, et les scores sont comparables d'une question a l'autre.
    import torch

    vecteurs = modele.encode(
        textes, batch_size=TAILLE_LOT, normalize_embeddings=True, show_progress_bar=False
    )
    # bge-m3 et le modele de generation (Ollama) partagent la carte graphique : on rend la
    # memoire de travail de PyTorch apres chaque encodage, sinon elle grossit au fil des
    # questions et Ollama finit par en manquer (erreur CUDA out of memory constatee).
    if torch.cuda.is_available():
        torch.cuda.empty_cache()
    return vecteurs.tolist()


def ouvrir_collection(recreer: bool = False):
    import chromadb

    client = chromadb.PersistentClient(path=str(config.DONNEES_INDEX))
    if recreer and config.COLLECTION in [c.name for c in client.list_collections()]:
        client.delete_collection(config.COLLECTION)
    return client.get_or_create_collection(
        config.COLLECTION,
        # Distance cosinus : on compare la direction des vecteurs (le sens), pas leur
        # longueur. ChromaDB renvoie une distance = 1 - similarite.
        metadata={"hnsw:space": "cosine"},
    )


def lire_passages() -> list[dict]:
    with (config.DONNEES_TRAITE / "passages.jsonl").open(encoding="utf-8") as f:
        return [json.loads(ligne) for ligne in f]


def indexer_corpus() -> None:
    passages = lire_passages()
    debut = time.perf_counter()
    modele = charger_modele()
    print(f"Modele charge en {time.perf_counter() - debut:.0f} s sur {modele.device}")

    debut = time.perf_counter()
    vecteurs = encoder(modele, [p["texte_indexe"] for p in passages])
    duree = time.perf_counter() - debut
    print(f"{len(passages)} passages encodes en {duree:.1f} s")

    collection = ouvrir_collection(recreer=True)
    # ChromaDB n'accepte que des metadonnees simples (texte, nombre, booleen).
    cles = ("document", "titre", "theme", "page_debut", "page_fin", "section",
            "contient_tableau", "nb_tokens")
    for i in range(0, len(passages), 500):
        lot = passages[i : i + 500]
        collection.add(
            ids=[p["id"] for p in lot],
            embeddings=vecteurs[i : i + 500],
            documents=[p["texte"] for p in lot],
            metadatas=[{cle: p[cle] for cle in cles} for p in lot],
        )
    print(f"Index ChromaDB : {collection.count()} passages dans {config.DONNEES_INDEX}")


if __name__ == "__main__":
    indexer_corpus()
