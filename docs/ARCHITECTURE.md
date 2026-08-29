# Architecture

## Stack envisagée

- Frontend : Next.js et TypeScript
- Backend : FastAPI et Python
- Analyse locale : DuckDB
- Métadonnées : PostgreSQL
- Développement local : Docker Compose

## Composants prévus

```text
frontend/  -> recherche, comparaison des résultats et exploration
backend/   -> connecteurs de catalogues, stockage et analyse DuckDB
tests/     -> jeux de données artificiels et tests d’intégration
docs/      -> produit, architecture et règles de données
```

L’IA peut assister la recherche, proposer des opérations et générer du code. Les téléchargements, empreintes, filtres, jointures, calculs et agrégations doivent rester déterministes.

Le navigateur ne transmet jamais une URL arbitraire à télécharger. Le backend retrouve la ressource dans le catalogue officiel, bloque les destinations réseau privées, applique une limite de taille, conserve l’original puis lance l’analyse.
