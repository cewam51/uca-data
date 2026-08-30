# Vérification du parcours complet

Date de la dernière vérification : 30 août 2026.

## Scénario principal : un seul document

La recherche `voiture` interroge simultanément les quatre catalogues et retourne uniquement des tables utilisables :

- data.gouv.fr : 6 résultats ;
- data.europa.eu : 5 résultats ;
- Recherche Data Gouv : 1 résultat.
- Insee : 1 résultat disponible via le catalogue officiel Melodi.

Le parcours principal utilise la table publique `11_02_voitures_traction-ssd` de data.europa.eu. Dès son ajout :

- le projet s’ouvre sans exiger un second document ;
- les 11 colonnes sont disponibles avec types et exemples ;
- l’utilisateur choisit `Année` et `Voitures` ;
- une courbe est proposée car l’axe est temporel ;
- la somme des voitures est calculée pour chaque année de 2017 à 2025 ;
- la formule, les exclusions éventuelles, la provenance et l’empreinte restent visibles ;
- les colonnes, l’agrégation et le type de graphique restent modifiables après le résultat.
- chaque case de type de graphique présente, avant validation, un aperçu basé sur au plus 20 premières lignes compatibles ;
- le calcul d’aperçu ne remplace pas le graphique déjà enregistré dans le projet.
- les boutons permanents `Accueil` et `Mes projets` restent accessibles depuis la recherche, l’analyse et une fiche publiée ;
- la liste des projets sépare les projets sans publication, encore en cours, de ceux possédant au moins une version publiée, considérés comme terminés ;
- chaque projet de la liste peut être rouvert pour poursuivre l’analyse.

Le champ de recherche accepte également une URL. Une fiche data.gouv.fr, data.europa.eu, Recherche Data Gouv ou Insee est résolue directement ; un lien public CSV/TSV est analysé sans passer par une liste de résultats. Les adresses privées et les pages HTML sont refusées.

Une recherche `population commune` retourne également des jeux Insee. `DS_POPULATIONS_REFERENCE` est résolu via Melodi, son archive officielle fournit automatiquement `DS_POPULATIONS_REFERENCE_2023_data.csv`, soit 106 065 lignes et 6 colonnes, sans demander de fichier à l’utilisateur.

Le fichier Insee `DS_PRENOM`, auparavant exclu par la limite du prototype, est également validé : 6 622 949 observations et un CSV décompressé de 303 594 337 octets sont téléchargés, conservés et analysés en flux en moins de 15 secondes sur l’environnement de vérification.

## Scénario facultatif : deux documents

Le parcours ajoute ensuite une deuxième table publique de data.europa.eu :

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

- tests backend : 36 réussis ;
- compilation de production frontend et backend : réussie ;
- analyse statique frontend : réussie ;
- audit des dépendances frontend : aucune vulnérabilité détectée ;
- aucun endpoint de téléversement direct de CSV n’est exposé.

Ce scénario constitue le critère d’acceptation de bout en bout. Les transformations restent déterministes et aucune valeur manquante n’est remplacée ou inventée.
