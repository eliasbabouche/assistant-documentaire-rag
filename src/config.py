"""Chemins et parametres du projet, centralises en un seul endroit.

Aucun chemin en dur ailleurs dans le code : quand la structure bouge, une seule
ligne change ici.
"""

from dataclasses import dataclass
from pathlib import Path

# Racine du projet, deduite de l'emplacement de ce fichier (jamais un chemin absolu
# machine : le code doit tourner chez quelqu'un d'autre et dans la CI).
RACINE = Path(__file__).resolve().parent.parent

DOSSIER_DONNEES = RACINE / "donnees"
DONNEES_BRUT = DOSSIER_DONNEES / "brut"
DONNEES_TRAITE = DOSSIER_DONNEES / "traite"
# Petits tableaux de synthese (entonnoirs, resultats) : versionnes, lus par le README
# et l'application.
DONNEES_AGREGE = DOSSIER_DONNEES / "agrege"
# Base vectorielle ChromaDB (fichiers sur disque, reconstruits par src.indexation).
DONNEES_INDEX = DOSSIER_DONNEES / "index"
DOSSIER_EVALUATION = RACINE / "evaluation"

# Modele d'embedding. Son tokenizer sert aussi a compter les tokens partout dans
# l'indexation (entonnoir, decoupage) : un seul etalon pour toute la partie « index ».
MODELE_EMBEDDING = "BAAI/bge-m3"
# Une collection par strategie de decoupage : la phase 6 en comparera plusieurs.
COLLECTION = "cnil_structure_500"

# --- Generation ---
# Modele local servi par Ollama (`ollama pull mistral`), sur la machine : gratuit et prive.
MODELE_GENERATION = "mistral"
URL_OLLAMA = "http://localhost:11434"
# Nombre de passages transmis au modele. 5 passages de 500 tokens bge-m3 font environ
# 3 000 tokens Mistral (rapport mesure : 1,21) : d'ou un contexte de 8 192 et non 4 096.
NB_PASSAGES = 5
CONTEXTE_GENERATION = 8192
# Phrase de refus imposee : une formule fixe se detecte sans ambiguite a l'evaluation.
PHRASE_REFUS = "Je ne trouve pas cette information dans les documents."

# --- Format des exports ---
# Ces trois parametres sont la cause la plus frequente d'un import casse en aval.
# Les fixer explicitement, ne jamais se reposer sur les valeurs par defaut de pandas.
ENCODAGE_EXPORT = "utf-8-sig"  # utf-8-sig pour qu'Excel affiche correctement les accents
SEPARATEUR_EXPORT = ";"  # convention francaise
FORMAT_DATE = "%Y-%m-%d"



# --- Corpus : guides et recommandations de la CNIL ---
# Liste figee le 2026-10-09 (regle du millesime) : 23 documents sur le perimetre
# « le RGPD au quotidien dans une entreprise », choisis parmi les 166 PDF recenses sur
# cnil.fr a partir du plan du site. Licence des textes : CC BY-ND 4.0 (citation de la
# source obligatoire, aucune modification) ; les PDF ne sont donc jamais versionnes.
#
# L'empreinte SHA-256 identifie le contenu exact de chaque fichier : si la CNIL publie
# une nouvelle edition a la meme adresse, l'empreinte change et le telechargement
# s'arrete au lieu de melanger les editions en silence.
#
# `date_pdf` est la date de creation inscrite dans le fichier PDF, pas forcement la date
# de publication officielle.

DATE_INVENTAIRE = "2026-10-09"
LICENCE_CORPUS = "CC BY-ND 4.0 (cnil.fr)"


@dataclass(frozen=True)
class Document:
    identifiant: str
    titre: str
    theme: str
    url: str
    date_pdf: str
    sha256: str


_BASE = "https://www.cnil.fr/sites"

CORPUS = [
    # Socle de conformite
    Document(
        "dpo",
        "Guide pratique RGPD - Délégués à la protection des données",
        "socle",
        f"{_BASE}/default/files/atoms/files/guide_pratique_rgpd_-_delegues_a_la_protection_des_donnees.pdf",
        "2021-10-29",
        "a109eb80dbedf415b092d297fa375a6941433b733b0f6bd63f9b16cf87f969da",
    ),
    Document(
        "sous_traitant",
        "RGPD : Guide du sous-traitant (édition 2017)",
        "socle",
        f"{_BASE}/default/files/atoms/files/rgpd-guide_sous-traitant-cnil.pdf",
        "2017-09-27",
        "4e1e603384051ad3f23ed5d6a2b2d800af0b0103f661c83371895179c76a71f7",
    ),
    Document(
        "durees_conservation",
        "Guide pratique - Les durées de conservation",
        "socle",
        f"{_BASE}/cnil/files/atoms/files/guide_durees_de_conservation.pdf",
        "2020-07-28",
        "3839b9290f92d9f433eae66bf84b78a4a57a79fdac28de3a9380b22330318af9",
    ),
    Document(
        "tpe_pme",
        "Guide de sensibilisation au RGPD pour les TPE-PME (CNIL et Bpifrance)",
        "socle",
        f"{_BASE}/cnil/files/atoms/files/bpi-cnil-rgpd_guide-tpe-pme.pdf",
        "2019-03-15",
        "84b1a2f32332958c1d1590a19520c41972a174fafec7ce933f5e5f6fa8b09d3d",
    ),
    Document(
        "aipd_methode",
        "Analyse d'impact relative à la protection des données (PIA) : la méthode",
        "socle",
        f"{_BASE}/cnil/files/atoms/files/cnil-pia-1-fr-methode.pdf",
        "2018-02-22",
        "d97c41937f3965c7b04c085f05c4e973c883394d765ac3b61b73e69de636e389",
    ),
    Document(
        "transferts_aitd",
        "Guide pratique - Analyse d'impact des transferts de données (AITD)",
        "socle",
        f"{_BASE}/cnil/files/2025-02/guide_aitd_pdf.pdf",
        "2025-02-05",
        "0e71f0fba2373c2582feb6bad89a8ab32c0490a8675cea030e188b2dd72c69fe",
    ),
    # Securite
    Document(
        "securite",
        "Guide pratique RGPD - Sécurité des données personnelles (édition 2024)",
        "securite",
        f"{_BASE}/default/files/2026-05/cnil_guide_securite_personnelle.pdf",
        "2026-05-06",
        "5602bd27bc00e5c593a05679895ba40c9c4d7ebd5b60df5543f65e11467636a8",
    ),
    Document(
        "journalisation",
        "Recommandation relative aux mesures de journalisation",
        "securite",
        f"{_BASE}/default/files/atoms/files/recommandation_-_journalisation.pdf",
        "2021-11-18",
        "d50dba765026fcb6f6d31cd70ca034b5f6e63a19965f0194390a856cf9388de3",
    ),
    Document(
        "mots_de_passe",
        "Recommandation relative aux mots de passe et autres secrets partagés (2022)",
        "securite",
        f"{_BASE}/default/files/atoms/files/"
        "deliberation-2022-100-du-21-juillet-2022_recommandation-aux-mots-de-passe.pdf",
        "2022-10-12",
        "4d4baea893ea2d00f0d118dbd6034fd09c73f6ddc60e151f5a75d4b6db0d5a25",
    ),
    Document(
        "authentification_multifacteur",
        "Recommandation relative à l'authentification multifacteur",
        "securite",
        f"{_BASE}/cnil/files/2025-05/recommandation_relative_a_l_authentification_multifacteur.pdf",
        "2025-05-27",
        "e260da77fbeaf21656b9f95404de6b541b872049ca5c43d7713c0fc5c2736627",
    ),
    Document(
        "filtrage_web",
        "Recommandation sur le déploiement d'un serveur mandataire web filtrant",
        "securite",
        f"{_BASE}/default/files/2026-03/recommandation_serveur_mandataire_web_filtrant.pdf",
        "2026-03-13",
        "c5c4cfe03d858cadb0fff9493584e51441abd1247591e6d9d4fa49dee44a3410",
    ),
    # RH et travail
    Document(
        "gestion_rh",
        "Référentiel - Gestion des ressources humaines",
        "rh",
        f"{_BASE}/default/files/2023-09/referentiel_gestion_des_ressources_humaines.pdf",
        "2023-09-04",
        "db39c38bfe50e031e968a3f57462d5739ef50cefca19d46115211615a2c94c3a",
    ),
    Document(
        "durees_conservation_rh",
        "Référentiel - Les durées de conservation en gestion des ressources humaines",
        "rh",
        f"{_BASE}/default/files/2026-04/"
        "referentiel_durees_de_conservation_gestion_des_ressources_humaines.pdf",
        "2026-05-21",
        "406d1359d7b63bc8d26c3ee23ef16deb245fa8b9a37656f2517f9b275844ef3a",
    ),
    Document(
        "alertes_professionnelles",
        "Référentiel - Alertes professionnelles",
        "rh",
        f"{_BASE}/default/files/2024-01/referentiel_alertes_professionnelles.pdf",
        "2023-08-25",
        "34cbf45233313d8b6b1f7c510a7dd9a024e1bf8dd1a23c61ebc2871dcd5bffd4",
    ),
    Document(
        "diversite_travail",
        "Recommandation relative à la mesure de la diversité au travail",
        "rh",
        f"{_BASE}/default/files/2025-06/recommandation_mesure_de_la_diversite_au_travail.pdf",
        "2025-06-10",
        "cb7c7b427d8f1a39dab71c99b63e77a7086b7a29ef0f77031b3e4ec44ea7573a",
    ),
    # Numerique et marketing
    Document(
        "cookies_recommandation",
        "Recommandation « cookies et autres traceurs » (version consolidée 2026)",
        "numerique",
        f"{_BASE}/default/files/2026-01/recommandation_cookies_consolidee.pdf",
        "2026-01-15",
        "5938f55ef8eed35651cd8f25133593f56cd6c5f8627bea0fa6d44b0ec469822d",
    ),
    Document(
        "cookies_lignes_directrices",
        "Lignes directrices « cookies et autres traceurs » (2020)",
        "numerique",
        f"{_BASE}/default/files/atoms/files/"
        "lignes_directrices_de_la_cnil_sur_les_cookies_et_autres_traceurs.pdf",
        "2020-09-30",
        "88de95e6032b898b5a46b5c981bf9998a57ab1deacd82123d6a32447509572dd",
    ),
    Document(
        "pixels_email",
        "Recommandation relative aux pixels de suivi dans les courriels",
        "numerique",
        f"{_BASE}/default/files/2026-04/recommandation-pixels_de_suivi.pdf",
        "2026-04-13",
        "2ce3c66ac21792f6db299480f3b9649340b886da52b6ff4f1d7cd1c19653e8e9",
    ),
    Document(
        "applications_mobiles",
        "Recommandation relative aux applications mobiles (version modifiée 2025)",
        "numerique",
        f"{_BASE}/cnil/files/2025-04/recommandation-applications-mobiles-modifiee.pdf",
        "2025-04-07",
        "0686cc0ec5429ebc6a91d5d260f6191786f3231a373d0814a106e1a31abe7788",
    ),
    Document(
        "api",
        "Recommandation technique relative aux interfaces de programmation (API)",
        "numerique",
        f"{_BASE}/cnil/files/2023-07/recommandation_api.pdf",
        "2023-07-07",
        "0aa71702c1bfb51ba877e1e25f5dd47593066daaf5e8e39c8d4c7dc80ec4e7d4",
    ),
    Document(
        "gestion_commerciale",
        "Référentiel - Gestion des activités commerciales",
        "numerique",
        f"{_BASE}/default/files/atoms/files/"
        "referentiel_traitements-donnees-caractere-personnel_gestion-activites-commerciales.pdf",
        "2022-03-18",
        "3b70f8a66ca97eacd56b903acc28691748aeafb50b9efee9402eff02d965e6e7",
    ),
    Document(
        "localisation",
        "Recommandation relative à l'utilisation des données de localisation",
        "numerique",
        f"{_BASE}/default/files/2026-06/recommandation_utilisation_de_donnees_de_localisation.pdf",
        "2026-06-29",
        "71bb9aa87ea25907c5838c6be3a728f8bfd2a68fb09c84cf9d1b8ac39e122b26",
    ),
    # IA
    Document(
        "ia_verification",
        "Développement des systèmes d'IA : que faut-il vérifier ? (liste de vérification)",
        "ia",
        f"{_BASE}/default/files/2025-07/ia_liste_de_verification.pdf",
        "2025-07-22",
        "dd3b8cf85d60c1a2093184e14a62df0c1e9197aadec15e18e29bfb4c755de4c2",
    ),
]


def creer_dossiers() -> None:
    """Cree l'arborescence de donnees si elle n'existe pas encore."""
    for dossier in (DONNEES_BRUT, DONNEES_TRAITE, DONNEES_AGREGE):
        dossier.mkdir(parents=True, exist_ok=True)
