# UCA Data

Prototype open source d’outil citoyen pour explorer des données publiques, croiser des sources et créer des indicateurs transparents et reproductibles.

## Vision

Permettre à une personne sans compétences techniques de :

- rechercher ou importer des données publiques ;
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

## MVP disponible

Le MVP permet de téléverser un CSV, de conserver l’original et d’afficher son nombre de lignes, ses colonnes, les types détectés et ses 20 premières lignes. L’empreinte SHA-256 et les métadonnées sont enregistrées dans PostgreSQL.

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
