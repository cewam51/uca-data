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

Le site recherche actuellement dans data.gouv.fr, data.europa.eu et Recherche Data Gouv. Il affiche uniquement les résultats qui contiennent une table publique exploitable ou vérifiable, choisit automatiquement la meilleure ressource CSV ou TSV et l’ajoute au projet sans demander de fichier à l’utilisateur. Les résultats non tabulaires ou restreints ne sont pas affichés. Chaque fichier retenu est téléchargé côté serveur, conservé sans modification, analysé avec DuckDB et identifié par son empreinte SHA-256.

Une première source crée un projet persistant. L’utilisateur peut ensuite lancer une nouvelle recherche et ajouter une seconde source ; les deux jeux de données restent ordonnés dans le projet avec leur titre, producteur, provenance, structure et empreinte.

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

Les tables originales et les données PostgreSQL sont conservées dans des volumes Docker.

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
