# Explorateur de données publiques

Prototype open source permettant de rechercher des données publiques, d’explorer leurs ressources, de croiser des sources et de créer des indicateurs transparents et reproductibles.

## Vision

Permettre à une personne sans compétences techniques de :

- rechercher simultanément dans plusieurs catalogues publics ;
- ouvrir une ressource sans manipuler directement de CSV ;
- comprendre leur structure et leur provenance ;
- croiser plusieurs sources avec des contrôles explicites ;
- construire des indicateurs déterministes ;
- créer des visualisations dont les sources et calculs restent vérifiables.

## Principes

- aucune donnée factuelle inventée par une IA ;
- aucune transformation ou jointure silencieuse ;
- conservation des fichiers sources, métadonnées et empreintes SHA-256 ;
- calculs reproductibles et versions précédentes accessibles ;
- séparation entre assistance par IA et moteur de calcul déterministe.

## Fonctionnalités disponibles

Le site recherche actuellement dans data.gouv.fr, data.europa.eu et Recherche Data Gouv. Il permet de comparer les métadonnées et les formats, puis d’explorer automatiquement les ressources CSV de data.gouv.fr. Le fichier sélectionné est téléchargé côté serveur, conservé sans modification, analysé avec DuckDB et identifié par son empreinte SHA-256.

Étapes suivantes : identification sémantique des colonnes, croisement de plusieurs sources, calcul d’indicateurs, visualisations Vega-Lite et fiches collaboratives versionnées.

Stack : Next.js/TypeScript, FastAPI/Python, DuckDB et PostgreSQL.

## Lancement avec Docker

Prérequis : Docker avec le plugin Compose.

```bash
docker compose up --build
```

Ouvrir ensuite :

- interface : <http://localhost:3000>
- documentation de l’API : <http://localhost:8000/docs>
- état de l’API : <http://localhost:8000/health>

Les CSV originaux et les données PostgreSQL sont conservés dans des volumes Docker.

## Développement local

Backend :

```bash
cd backend
python -m venv .venv
.venv/bin/pip install -e '.[test]'
DATABASE_URL=postgresql://uca:uca@localhost:5432/uca .venv/bin/uvicorn app.main:app --reload
```

Frontend :

```bash
cd frontend
npm install
npm run dev
```

Tests backend :

```bash
cd backend
.venv/bin/pytest
```

Voir [`docs/PRODUCT.md`](docs/PRODUCT.md), [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md) et [`docs/DATA_RULES.md`](docs/DATA_RULES.md).

## Licence

Ce projet est distribué sous licence AGPL-3.0. Voir [`LICENSE`](LICENSE).
