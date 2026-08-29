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

PostgreSQL conserve les métadonnées des tables importées, leur provenance, les projets qui associent deux sources ordonnées, les dimensions choisies, le dernier diagnostic de jointure et la configuration/résultat de l’indicateur. Les fichiers originaux restent dans le volume dédié.

DuckDB profile les colonnes, calcule la qualité du croisement, agrège les mesures choisies et applique la formule directement sur les fichiers conservés. La normalisation de clé est limitée à la casse, aux espaces et à une conversion textuelle explicite ; aucune valeur géographique, temporelle ou numérique manquante n’est créée. Les divisions par zéro et valeurs non numériques sont exclues et comptabilisées.

L’IA peut assister la recherche, proposer des opérations et générer du code. Les téléchargements, empreintes, filtres, jointures, calculs et agrégations doivent rester déterministes.

Le navigateur ne transmet jamais une URL arbitraire à télécharger. Le backend retrouve la ressource dans le catalogue officiel, bloque les destinations réseau privées, applique une limite de taille, conserve l’original puis lance l’analyse.
