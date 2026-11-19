"""Appel a l'API Claude, partage par la generation (src.generation) et le juge (src.juge).

Un seul endroit connait le SDK : le reste du code recoit un texte, des comptes de tokens
et un cout. La cle n'apparait nulle part dans le code : elle est lue dans le fichier .env
(jamais versionne) sous le nom ANTHROPIC_API_KEY.
"""

from dataclasses import dataclass
from functools import lru_cache

import anthropic
from dotenv import load_dotenv

from src import config


@dataclass
class AppelClaude:
    texte: str
    tokens_entree: int
    tokens_sortie: int  # reflexion comprise : elle est facturee comme de la sortie
    cout_usd: float


@lru_cache(maxsize=1)
def client() -> anthropic.Anthropic:
    load_dotenv(config.RACINE / ".env")
    # Le SDK relance de lui-meme les erreurs passageres (429, 5xx, reseau). Une erreur de
    # cle ou de quota n'est pas relancee : elle remonte et arrete le lancement.
    return anthropic.Anthropic(max_retries=4)


def cout_usd(modele: str, tokens_entree: int, tokens_sortie: int) -> float:
    tarif_entree, tarif_sortie = config.TARIFS_USD_PAR_MILLION[modele]
    return (tokens_entree * tarif_entree + tokens_sortie * tarif_sortie) / 1_000_000


def appeler_claude(
    modele: str, consignes: str, prompt: str, effort: str, schema: dict | None = None
) -> AppelClaude:
    """Un appel, une reponse. Avec `schema`, la reponse est un JSON conforme a ce schema."""
    options: dict = {"effort": effort}
    if schema is not None:
        options["format"] = {"type": "json_schema", "schema": schema}
    message = client().messages.create(
        model=modele,
        max_tokens=config.TOKENS_MAX_CLAUDE,
        system=consignes,
        messages=[{"role": "user", "content": prompt}],
        output_config=options,
    )
    # Une reponse coupee (max_tokens) ou declinee (refusal) ne doit pas etre notee comme
    # une mauvaise reponse : on arrete, pour la voir.
    if message.stop_reason != "end_turn":
        raise RuntimeError(f"Réponse de {modele} interrompue : {message.stop_reason}")
    # Le modele qui a repondu doit etre celui qu'on evalue.
    if not message.model.startswith(modele):
        raise RuntimeError(f"Modèle demandé : {modele}, modèle qui a répondu : {message.model}")
    texte = "".join(bloc.text for bloc in message.content if bloc.type == "text").strip()
    entree, sortie = message.usage.input_tokens, message.usage.output_tokens
    return AppelClaude(texte, entree, sortie, cout_usd(modele, entree, sortie))
