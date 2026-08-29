# Architecture

## Stack envisagée

- Frontend : Next.js et TypeScript
- Backend : FastAPI et Python
- Analyse locale : DuckDB
- Métadonnées : PostgreSQL
- Développement local : Docker Compose

## Composants prévus

```text
frontend/  -> interface d’import et d’aperçu
backend/   -> API, stockage et analyse DuckDB
tests/     -> jeux de données artificiels et tests d’intégration
docs/      -> produit, architecture et règles de données
```

L’IA peut assister la recherche, proposer des opérations et générer du code. Les téléchargements, empreintes, filtres, jointures, calculs et agrégations doivent rester déterministes.
