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

Lorsqu’une URL est collée dans la recherche, le backend résout les fiches des catalogues officiels pris en charge. Il accepte aussi un lien public direct uniquement si la réponse est bien une table CSV, TSV ou XLSX. Les destinations réseau privées et les pages HTML sont bloquées. La source est téléchargée progressivement sur le volume persistant et conservée dans son état original. Pour un classeur Excel, le backend lit les feuilles en mode flux, retient automatiquement celle qui contient la structure tabulaire la plus riche et produit un CSV interne réservé aux calculs ; le nom de la feuille et l’empreinte du classeur original restent dans la provenance. Aucune limite de taille applicative n’est activée par défaut ; la capacité réelle est celle du stockage disponible. Un exploitant peut néanmoins définir `MAX_UPLOAD_BYTES` s’il doit imposer son propre quota.

Le connecteur Insee interroge l’API publique Melodi (`/catalog/all`), classe localement les métadonnées françaises selon la recherche, puis résout le produit CSV exact par son identifiant. Seul le fichier `*_data.csv` de l’archive officielle est décompressé en flux vers le stockage ; le fichier de métadonnées voisin n’est jamais confondu avec les observations.
