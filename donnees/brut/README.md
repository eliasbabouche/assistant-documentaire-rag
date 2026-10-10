# Données brutes

Ce dossier est volontairement vide sur GitHub : les PDF de la CNIL ne sont jamais
versionnés (poids, licence CC BY-ND 4.0, reproductibilité).

Pour les récupérer, lancer depuis la racine du projet :

```bash
python -m src.telechargement
```

Le script télécharge les 23 documents listés dans `src/config.py` et vérifie l'empreinte
SHA-256 de chacun : un fichier d'une autre édition est refusé.

Source : guides, recommandations et référentiels de la [CNIL](https://www.cnil.fr),
licence CC BY-ND 4.0.
