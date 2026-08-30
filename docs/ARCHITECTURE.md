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

PostgreSQL conserve les métadonnées des tables importées, leur provenance, les projets qui contiennent une ou deux sources ordonnées, le dernier graphique à une source, les dimensions choisies, le dernier diagnostic de jointure, la configuration/résultat de l’indicateur croisé, les instantanés publiés et leurs commentaires. Les fichiers originaux restent dans le volume dédié.

DuckDB profile les colonnes, agrège deux colonnes choisies dans une source, prépare les valeurs de graphique, calcule la qualité d’un croisement facultatif, compare explicitement les périodes et périmètres communaux et applique les formules directement sur les fichiers conservés. La normalisation de clé est limitée à la casse, aux espaces et à une conversion textuelle explicite ; aucune valeur géographique, temporelle ou numérique manquante n’est créée. Les divisions par zéro et valeurs non numériques sont exclues et comptabilisées.

Une publication copie l’état complet du projet dans un instantané JSONB, numéroté sous verrou transactionnel. Une empreinte SHA-256 calculée sur sa représentation canonique permet de vérifier qu’il n’a pas changé. Aucun endpoint ne modifie ou ne supprime une version ; les contributions sont enregistrées séparément.

L’IA peut assister la recherche, proposer des opérations et générer du code. Les téléchargements, empreintes, filtres, jointures, calculs et agrégations doivent rester déterministes.

Le navigateur ne transmet jamais une URL arbitraire à télécharger. Le backend retrouve la ressource dans le catalogue officiel, bloque les destinations réseau privées, applique une limite de taille, conserve l’original puis lance l’analyse.

Le connecteur Insee interroge l’API publique Melodi (`/catalog/all`), classe localement les métadonnées françaises selon la recherche, puis résout le produit CSV exact par son identifiant. L’archive ZIP officielle est contrôlée en taille et seul le fichier `*_data.csv` est ouvert ; le fichier de métadonnées voisin n’est jamais confondu avec les observations.
