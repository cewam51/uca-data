# Produit

## Objectif produit

Permettre à une personne sans compétence technique de partir d’une question citoyenne, de trouver les données publiques correspondantes sur plusieurs plateformes, de choisir les colonnes qui l’intéressent et de construire un graphique vérifiable. Un document suffit. Un second document peut être ajouté pour être analysé séparément ou relié au premier par une colonne commune. Le site ne demande pas de chercher ou de fournir soi-même un CSV et ne fabrique aucune donnée factuelle.

Le parcours cible est :

1. rechercher des données publiques avec des mots courants ;
2. ajouter une première source directement au projet et comprendre ses colonnes ;
3. choisir deux colonnes du document et un calcul explicite ;
4. choisir parmi les graphiques adaptés et modifier facilement tous les réglages ;
5. éventuellement ajouter un second document et choisir lequel analyser ;
6. éventuellement relier les deux documents par une colonne commune ;
7. voir avant tout calcul croisé le taux de correspondance, les doublons et les différences de période ou de géographie ;
8. publier une fiche collaborative contenant les sources, leurs empreintes, la recette de calcul et l’historique des versions.

Le critère d’acceptation principal exige qu’une recherche publique mène à un graphique modifiable avec un seul document, sans CSV demandé ni transformation silencieuse. Le parcours facultatif à deux documents doit fonctionner sans rendre le croisement obligatoire.

## Premier parcours utilisateur

L’utilisateur décrit les données qu’il recherche sans connaître les catalogues, API ou formats sous-jacents. Le système :

- interroge plusieurs catalogues publics ;
- présente les jeux de données et leurs producteurs ;
- affiche uniquement les résultats contenant une table publique exploitable ou vérifiable ;
- choisit et télécharge automatiquement la meilleure ressource disponible ;
- conserve le fichier original et son empreinte SHA-256 ;
- affiche le nombre de lignes, les colonnes, leurs types et un aperçu ;
- conserve une première source dans un projet et ouvre aussitôt le choix des colonnes ;
- propose les barres, la courbe, le nuage de points ou le tableau selon les types sélectionnés ;
- garde les réglages accessibles après chaque résultat ;
- permet facultativement d’ajouter, d’analyser séparément ou de retirer une deuxième source ;
- suggère, sans l’imposer, les colonnes « commune » et « année » à partir de leur nom et d’exemples ;
- place le croisement dans un mode facultatif et mesure alors les clés appariées, taux par source, doublons, périodes, communes communes et exemples non appariés ;
- refuse d’inventer une année absente et explique quand la comparaison se limite à la commune ;
- agrège une valeur choisie dans chaque source par commune et année, puis applique un rapport ou une différence ;
- affiche la formule, les exclusions, les valeurs intermédiaires et un graphique déterministe ;
- publie une fiche sourcée avec une empreinte propre, un historique immuable et des commentaires collaboratifs.

## Hors périmètre

- authentification ;
- prédictions et projections ;
- génération de données par IA ;
- transformations ou rapprochements non expliqués à l’utilisateur.

Les versions publiées sont immuables. Une correction ou une nouvelle interprétation crée une version supplémentaire ; les commentaires restent attachés à la version qu’ils discutent.
