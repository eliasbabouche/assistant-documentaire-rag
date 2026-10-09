# assistant-documentaire-rag

[![Tests](https://github.com/eliasbabouche/assistant-documentaire-rag/actions/workflows/tests.yml/badge.svg)](https://github.com/eliasbabouche/assistant-documentaire-rag/actions/workflows/tests.yml)
[![Démo](https://img.shields.io/badge/démo-en%20ligne-brightgreen)](LIEN-DE-LA-DEMO)
[![Open In Colab](https://colab.research.google.com/assets/colab-badge.svg)](https://colab.research.google.com/github/eliasbabouche/NOM-DU-DEPOT/blob/main/notebooks/01_restitution.ipynb)

> Assistant de questions-réponses sur les guides de la CNIL : réponses sourcées, refus quand l'information est absente, et évaluation chiffrée (Ollama vs API Claude)

<!--
  Ordre imposé : le résultat AVANT la méthode. Un lecteur donne 20 secondes à ce fichier.
  Remplacer chaque section, puis supprimer ces commentaires.
-->

## Résultat

<!--
  Un résultat NUANCÉ et chiffré, pas un slogan. « 9 villes sur 10, mais résultat contrasté
  sur les maisons, avec deux exceptions » est crédible ; « les prix explosent » ne l'est pas.
  Les chiffres cités ici doivent être EXACTEMENT ceux du notebook et du dashboard.
-->

![Aperçu](docs/apercu.png)

**Démo en ligne** : <lien Streamlit Cloud ou Hugging Face Spaces>

**Notebook de restitution** : [`notebooks/01_restitution.ipynb`](notebooks/01_restitution.ipynb)
— lisible directement sur GitHub, graphiques compris.

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

1. <étape>
2. <étape>
3. <étape>

## Deux choix de méthode qui changent le résultat

<!--
  Les réponses d'entretien, écrites en AFFIRMATIONS à puces, pas en questions.
  Prendre les deux décisions qui, si on les avait prises autrement, auraient donné
  un résultat différent. C'est ce qu'un recruteur technique va creuser.
-->

**<Le premier choix>**

- <ce qui a été décidé, et pourquoi>
- <ce que donnerait l'autre option, chiffré si possible>

**<Le second choix>**

- <idem>

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

```bash
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
streamlit run app.py
```

## Tests

```bash
pytest
```

## Structure

```
app.py        point d'entrée de l'application (à la RACINE : sinon l'import de src échoue)
src/          code métier, une responsabilité par module
tests/        tests unitaires
notebooks/    restitution : importe depuis src/, ne contient pas de logique métier
donnees/      brut/ et traite/ non versionnés ; reference/ et agrege/ versionnés (petits)
```

Le code vit dans `src/` et reste testable ; le notebook importe depuis `src/` et raconte
l'histoire. Ses sorties sont volontairement conservées dans le fichier pour que les
graphiques s'affichent sur GitHub sans rien exécuter.

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

