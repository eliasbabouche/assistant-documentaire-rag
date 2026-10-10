# Assistant documentaire RAG sur les guides de la CNIL

[![Tests](https://github.com/eliasbabouche/assistant-documentaire-rag/actions/workflows/tests.yml/badge.svg)](https://github.com/eliasbabouche/assistant-documentaire-rag/actions/workflows/tests.yml)
![Statut](https://img.shields.io/badge/statut-en%20cours-orange)

> Assistant de questions-réponses sur 23 guides de la CNIL (RGPD) : réponses sourcées, refus
> quand l'information est absente, et évaluation chiffrée d'un modèle local (Mistral via
> Ollama) face à l'API Claude.

## La question

Peut-on interroger 600 pages de documentation réglementaire en langage naturel, et obtenir
des réponses **fiables, sourcées, et qui admettent « je ne sais pas »** quand l'information
n'y est pas ? Et surtout : **comment le prouver avec des chiffres ?**

C'est la question que pose un client avant de confier sa documentation interne à un
assistant. Un modèle de langage seul y répond mal. Interrogé sans document sur la durée de
conservation des images de vidéosurveillance au travail, Mistral 7B cite avec assurance un
« guide pratique » de la CNIL, « page 23 », avec son adresse sur cnil.fr : l'adresse
renvoie une erreur 404, le document n'existe pas. Le RAG (*Retrieval-Augmented
Generation*) consiste à retrouver d'abord les passages pertinents dans les documents, puis à
demander au modèle de répondre uniquement à partir d'eux, en les citant.

## Avancement

| Étape | Statut | Ce qu'elle produit |
|---|---|---|
| 1. Corpus | ✅ | 23 PDF vérifiés par empreinte, convertis en Markdown page par page (texte, titres, tableaux) |
| 2. Jeu d'évaluation | ✅ | 44 questions écrites **avant** le système, dont 14 sans réponse dans le corpus |
| 3. Découpage, embeddings, index vectoriel | 🔄 en cours | passages indexés dans ChromaDB, première mesure de la recherche |
| 4. Génération | ⬜ | réponses citées : Mistral en local, puis l'API Claude |
| 5. Évaluation | ⬜ | exactitude, fidélité aux sources, refus correct, latence, coût par requête |
| 6. Variantes | ⬜ | deux stratégies de découpage, recherche hybride, reclassement (*reranking*) |
| 7. Démo | ⬜ | interface en ligne sur Hugging Face Spaces |

## Ce qui sera mesuré

La recherche et la génération sont évaluées **séparément**. Quand une réponse est fausse, il
faut savoir si le bon passage n'a pas été retrouvé (problème de recherche) ou s'il a été mal
exploité (problème de génération) : les deux ne se corrigent pas de la même façon.

| Maillon | Métrique | Ce qu'elle dit |
|---|---|---|
| Recherche (*retrieval*) | *Hit rate@k*, *recall@k* | la page qui contient la réponse est-elle parmi les k passages retrouvés ? |
| Recherche | MRR (*Mean Reciprocal Rank*) | à quel rang arrive le premier bon passage ? |
| Génération | Exactitude (*answer correctness*) | la réponse dit-elle la même chose que la référence ? |
| Génération | Fidélité (*faithfulness*) | chaque affirmation est-elle appuyée par les passages fournis ? |
| Génération | Refus correct / refus à tort | dit-il « je ne sais pas » quand il le faut, et seulement dans ce cas ? |
| Coût | Latence, coût par requête | le prix de la qualité, du modèle local à l'API |

## Données

| | |
|---|---|
| Source | Guides, recommandations et référentiels de la [CNIL](https://www.cnil.fr) (PDF) |
| Périmètre | « Le RGPD au quotidien dans une entreprise » : socle de conformité, sécurité, RH, numérique et marketing, IA |
| Millésime | liste figée le 2026-10-09, chaque fichier vérifié par son empreinte SHA-256 (`src/config.py`) |
| Volume | 23 documents, 599 pages, 18,2 Mo |
| Période | documents publiés entre 2017 et 2026 |
| Licence | CC BY-ND 4.0 : citation de la source, aucune modification. Les PDF ne sont pas versionnés ; les passages sont cités mot pour mot avec leur source. |

Les données brutes ne sont pas versionnées. Pour les récupérer, puis les convertir en
Markdown page par page :

```bash
python -m src.telechargement
python -m src.extraction
```

### Entonnoir du nettoyage

| Étape | Pages | Tokens (`bge-m3`) | % des tokens de départ |
|---|---:|---:|---:|
| Pages extraites en Markdown | 599 | 405 778 | 100 % |
| Balisage retiré (gras, barré, sauts de ligne de cellule) | 599 | 376 243 | 92,7 % |
| En-têtes et pieds de page retirés | 599 | 374 073 | 92,2 % |
| **Pages vides écartées : corpus retenu** | **593** | **374 073** | **92,2 %** |

Le texte n'est pas réduit : seules la mise en forme et les répétitions disparaissent
(source : `donnees/agrege/entonnoir_extraction.csv`).

## Méthode

1. **Corpus** : téléchargement des 23 PDF, avec vérification de l'empreinte SHA-256 de chaque
   fichier, puis conversion en Markdown page par page (`pymupdf4llm`), qui conserve les
   tableaux ligne par ligne ; retrait de la mise en forme et des en-têtes et pieds de page.
2. **Jeu d'évaluation** : 44 questions rédigées à partir des documents, chacune avec ses
   pages sources et un extrait exact vérifié par les tests (`evaluation/questions.yaml`).
3. **Indexation** : découpage en passages d'au plus 500 tokens, embeddings multilingues
   `BAAI/bge-m3`, index vectoriel ChromaDB en similarité cosinus.
4. **Génération** : les passages retrouvés sont transmis au modèle avec la consigne de
   répondre uniquement à partir d'eux, de citer document et page, et de refuser sinon.
   Même index et mêmes questions pour Mistral (local, via Ollama) et Claude (API).

## Deux choix de méthode qui changent le résultat

**Le jeu d'évaluation est écrit avant le système, et étiqueté par page.**

- Écrites en observant le système, les questions auraient favorisé ce qu'il sait déjà faire,
  et le score n'aurait plus rien mesuré. L'historique git date le jeu avant la première
  ligne de recherche.
- Les réponses sont repérées par page, pas par passage : les passages changent avec la
  stratégie de découpage, les pages jamais. Le même jeu permet donc de comparer les
  stratégies entre elles.
- Un tiers des questions (14 sur 44) n'a pas de réponse dans le corpus, dont 8 sur des
  sujets que la CNIL traite ailleurs : c'est là qu'un système invente le plus volontiers.

**Les PDF sont convertis en Markdown, pas en texte brut.**

- Le corpus contient 152 tableaux, qui portent les réponses les plus précises (durées de
  conservation, bases légales). En texte brut, ils sont lus colonne par colonne et une durée
  se retrouve séparée de la ligne à laquelle elle se rapporte.
- En Markdown, chaque ligne du tableau garde ses colonnes. Le retrait de la mise en forme
  inutile réduit de 35 % le nombre de tokens des pages de tableaux.
- 6 questions du jeu d'évaluation ont leur réponse dans un tableau : l'effet de ce choix
  sera mesuré, pas supposé.

## Limites connues

- **Texte dessiné dans les images** : deux pages de la recommandation sur les applications
  mobiles (p. 9 et 24) sont des schémas pleine page sans couche texte. Leurs définitions
  des acteurs (éditeur, fournisseur de SDK, fournisseur d'OS) ne sont pas indexées ; les
  récupérer demanderait de l'OCR.
- **Volet IA mince** : la CNIL publie l'essentiel de ses recommandations sur l'IA en pages
  web, pas en PDF. Le corpus n'en contient qu'une liste de vérification de 4 pages.
- **Éditions anciennes** : le guide du sous-traitant date de 2017, avant l'entrée en
  application du RGPD. Il reste le guide de référence de la CNIL, mais certains passages
  peuvent être datés.

## Ce qui a été difficile, et ce que j'en retiens

- **Un nettoyage qui abîme le texte.** Retirer le gras collait des mots : `**5 ans**à compter`
  devenait « 5 ansà compter », un mot qu'aucune recherche par mot-clé ne retrouve. Le gras est
  désormais remplacé par une espace, et un test fige ce cas réel.
- **Un filtre trop zélé.** Ma première règle contre les pieds de page (« ligne présente sur la
  moitié des pages, chiffres ignorés ») supprimait aussi des lignes de contenu qui ne
  diffèrent d'une page à l'autre que par un numéro. La règle tient maintenant compte de la
  position (haut ou bas de page). Les tests ont été vérifiés par contre-épreuve : en
  cassant volontairement la règle, ils passent au rouge.

## Exécution

État actuel : constitution du corpus. L'interface de questions-réponses arrivera à
l'étape 7.

```bash
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
python -m src.telechargement
python -m src.extraction
```

## Tests

```bash
pytest
```

Les tests tournent sans réseau. Ceux qui vérifient les citations du jeu d'évaluation
s'exécutent après `python -m src.extraction`, et sont ignorés sinon (dans la CI notamment).

## Structure

```
src/config.py           chemins, paramètres, liste figée des 23 documents
src/telechargement.py   téléchargement vérifié par empreinte SHA-256
src/extraction.py       PDF vers Markdown page par page, entonnoir du nettoyage
evaluation/             jeu d'évaluation (44 questions)
tests/                  tests unitaires, sans réseau
donnees/                brut/ et traite/ non versionnés ; agrege/ versionné (petits tableaux)
```

## Questions fréquentes

<details>
<summary><b>Pourquoi convertir les PDF en Markdown plutôt qu'en texte brut, et sans OCR ?</b></summary>

Les 23 PDF sont nés numériques : leur texte se lit directement, sans erreur, donc l'OCR
n'aurait rien apporté. Le vrai problème était les tableaux : le corpus en contient 152, et
ce sont eux qui portent les réponses les plus précises (les durées de conservation, par
exemple). En texte brut, un tableau est lu colonne par colonne : la durée « 5 ans » se
retrouve à trente lignes de la finalité « registre unique du personnel » à laquelle elle se
rapporte. En Markdown, chaque ligne du tableau garde ses colonnes. J'ai ensuite retiré la
mise en forme sans valeur pour le sens (gras, sauts de ligne de cellule), ce qui réduit de
35 % le nombre de tokens des pages de tableaux. Les images ont été écartées : sur 580, 26
seulement occupent plus de 15 % d'une page, et leur contenu est presque toujours repris dans
le texte, à deux pages près, documentées dans les limites.

</details>

<details>
<summary><b>Pourquoi ne pas avoir écarté les pages trop courtes, comme les couvertures ?</b></summary>

Je l'ai fait dans une première version, avec un seuil de 150 caractères : 29 pages
écartées. En les relisant une par une, 3 portaient une information qui n'existe nulle part
ailleurs, comme la date d'adoption de la recommandation sur l'authentification
multifacteur, inscrite uniquement sur sa couverture. J'ai donc abandonné le seuil : seules
les 6 pages vides sont écartées, et le corpus passe de 599 à 593 pages. Les pages courtes
ne gênent pas, puisqu'au découpage elles se recollent à la page suivante et lui servent de
titre de partie.

</details>

<details>
<summary><b>Comment le jeu d'évaluation a-t-il été construit, et comment savoir qu'il ne favorise pas le système ?</b></summary>

Je l'ai écrit à partir des documents, avant d'écrire la moindre ligne de recherche ou de
génération : l'historique git le montre. Il compte 44 questions. 30 ont une réponse, chacune
avec sa page et un extrait exact que les tests retrouvent mot pour mot dans le texte. Elles
couvrent des cas variés : 6 réponses dans un tableau, 5 questions reformulées sans les mots
du document, 4 qui demandent deux documents, et 3 qui affirment une règle fausse que le
système doit corriger. 14 questions (32 %) n'ont pas de réponse dans le corpus, dont 8 sur
des sujets que la CNIL traite ailleurs, comme la vidéosurveillance au travail : ce sont les
plus susceptibles de provoquer une réponse inventée. J'ai vérifié chaque absence par une
recherche dans les 593 pages, et deux de mes idées de départ avaient en fait une réponse.
Les réponses sont étiquetées par page et non par passage, pour que le même jeu serve à
comparer plusieurs stratégies de découpage.

</details>

## Licence

MIT — voir [LICENSE](LICENSE).

