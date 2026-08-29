# Vérification du parcours complet

Date de la dernière vérification : 29 août 2026.

## Scénario public réel

La recherche `voiture` interroge simultanément les trois catalogues et retourne uniquement des tables utilisables :

- data.gouv.fr : 6 résultats ;
- data.europa.eu : 5 résultats ;
- Recherche Data Gouv : 1 résultat.

Le parcours complet utilise ensuite deux tables publiques de data.europa.eu :

1. `11_02_voitures_traction-ssd` — voitures par type de traction ;
2. `11_02_voitures_boite_vitesses-ssd` — voitures par type de boîte de vitesses.

Les deux ressources sont téléchargées par le backend, sans fichier demandé à l’utilisateur, puis conservées avec leur URL de provenance et leur empreinte SHA-256.

## Résultats attendus et observés

- les deux tables comportent 11 colonnes qualifiées avec exemples ;
- les clés confirmées sont `Commune` et `Année` dans chaque source ;
- 119 communes sont présentes dans les deux sources ;
- la première source couvre 2017–2025, la seconde 2022–2025 ;
- l’alerte de période différente est affichée ;
- 476 couples commune–année correspondent ;
- les taux de correspondance sont 44,4 % et 100 % ;
- les clés répétées sont signalées avant le choix de l’agrégation ;
- l’indicateur agrège `Voitures` par somme dans chaque source ;
- la formule publiée est `(Somme source 1 ÷ Somme source 2) × 100` ;
- 476 résultats sont calculés et visualisés ;
- une version publiée conserve la recette, les résultats, les alertes, les URLs et les deux empreintes de sources ;
- l’empreinte de la version est vérifiée à la lecture ;
- une contribution peut être ajoutée sans modifier la version ;
- publier une correction crée un nouveau numéro et laisse les versions précédentes inchangées.

## Vérifications automatisées

- tests backend : 24 réussis ;
- compilation de production frontend et backend : réussie ;
- analyse statique frontend : réussie ;
- audit des dépendances frontend : aucune vulnérabilité détectée ;
- aucun endpoint de téléversement direct de CSV n’est exposé.

Ce scénario constitue le critère d’acceptation de bout en bout. Les transformations restent déterministes et aucune valeur manquante n’est remplacée ou inventée.
