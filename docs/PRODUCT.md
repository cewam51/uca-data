# Produit

## Objectif produit

Permettre à une personne sans compétence technique de partir d’une question citoyenne, de trouver les données publiques correspondantes sur plusieurs plateformes, de croiser deux sources et de publier un indicateur vérifiable. Le site ne demande pas de chercher ou de fournir soi-même un CSV et ne fabrique aucune donnée factuelle.

Le parcours cible est :

1. rechercher des données publiques avec des mots courants ;
2. ajouter une première source directement au projet et comprendre ses colonnes ;
3. ajouter une seconde source ;
4. choisir les dimensions de rapprochement, par exemple la commune et l’année ;
5. voir avant validation le taux de correspondance, les doublons et les différences de période ou de géographie ;
6. définir un calcul explicite et déterministe, par exemple `voitures / population × 1 000` ;
7. créer une visualisation reconstruisible à partir des sources ;
8. publier une fiche collaborative contenant les sources, leurs empreintes, la recette de calcul et l’historique des versions.

Le critère d’acceptation global n’est atteint que lorsque ce parcours fonctionne de bout en bout avec deux jeux de données publics réels, sans transformation silencieuse.

## Premier parcours utilisateur

L’utilisateur décrit les données qu’il recherche sans connaître les catalogues, API ou formats sous-jacents. Le système :

- interroge plusieurs catalogues publics ;
- présente les jeux de données et leurs producteurs ;
- affiche uniquement les résultats contenant une table publique exploitable ou vérifiable ;
- choisit et télécharge automatiquement la meilleure ressource disponible ;
- conserve le fichier original et son empreinte SHA-256 ;
- affiche le nombre de lignes, les colonnes, leurs types et un aperçu ;
- conserve une première source dans un projet puis permet d’y ajouter une deuxième source ;
- suggère, sans l’imposer, les colonnes « commune » et « année » à partir de leur nom et d’exemples ;
- mesure le croisement confirmé : clés appariées, taux par source, doublons et exemples non appariés ;
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
