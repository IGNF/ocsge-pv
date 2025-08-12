# ocsge-pv
## Présentation
Projet d'aggrégation de données concernant les parcs photovoltaïques en France, pour l'OCS GE.

Ce projet traite des données obtenues depuis deux sources :
* Données de télédétection à partir de photographies aériennes
* Dossiers de déclaration sur le formulaire [declaration_pv_decret2023-1408](https://www.demarches-simplifiees.fr/commencer/declaration_pv_decret2023-1408) du service "demarches-simplifiees.fr".

## Utilisation
Le programme est séparé en plusieurs exécutables :
* `import_declarations` : Importe les données sur les déclarations d'installations photovoltaïques vers une base de données PostgreSQL+PostGIS.
* `pair_from_sources` : Détermine la correspondance entre les données de déclaration et celles de télédétection, et référence ces liens dans une table dédiée.

Les BDD ne sont pas forcément partagées entre les exécutables. Pour chaque exécutable la structure des tables utilisées dans les BDD en entrée comme en sortie doit correspondre aux attentes du programme. Les seuls paramètres flexibles sur les données sont les paramètres de connexion aux BDD, ainsi que les noms de schémas et de tables. Dans le cas de `pair_from_sources`, les données doivent toutes se trouver dans un même schéma au sein d'une même BDD.

La syntaxe de l'interface en ligne de commandes est commune aux différents exécutables : `<exécutable> [-v|--verbose] <chemin vers la configuration>`
L'option `-v` (ou `--verbose`) sert à activer les logs de débug.
La configuration se présente sous la forme d'un fichier json. Les schémas de validation annotés se trouvent dans le dossier `src/ocsge_pv/resources/` de ce dépôt, avec l'extension `.schema.json`.

## Installation
(Commandes exécutées depuis la racine du projet.)
Différentes méthodes sont possibles

### Depuis le dépôt d'images docker
**En construction**

### Installation depuis apt et python sur un OS basé sur Debian
(Non testée sur les versions de python strictement inférieures à 3.11)

```bash
sudo apt install python3 python3-gdal libgdal-dev python3-venv python3-pip
python3 -m venv ./.venv
source ./.venv/bin/activate
python3 -m pip install "gdal==$(gdal-config --version)" .
ln -s src/ocsge_pv/resources $HOME/ocsge-pv-resources
```

### Compilation depuis le dockerfile
```bash
docker build -t local/ocsge-pv [--build-arg TZ=<timezone_name>]
docker run -v <conf_host_filepath>:<conf_container_filepath> local/ocsge-pv <executable> [--verbose] <conf_container_filepath>
```
(Par défaut : `TZ="Europe/Paris"`)

## Exemple de spécification des bases de données
Les fichiers sql liés décrivent un exemple de cas d'utilisation avec :
* un schéma dédié à l'import des dossiers de déclaration depuis l'APi du service "Démarches Simplifiées"
* un schéma pour le reste des opérations (appariement des données, puis diffusion et visualisation des données appariées, etc)

### Données de déclarations brutes
Voir [src/resources/init_declaration_source_db_schema.sql](./src/resources/init_declaration_source_db_schema.sql)
Les exécutables suivants utilisent ces données :
* `import_declarations`

Toutes les colonnes citée dans le fichier SQL d'exemple sont obligatoires pour le fonctionnement des exécutables ci-dessus.

Les colonnes suivantes sont utilisée pour filtrer l'export de données depuis cette table :
* `accepte`
* `dern_modif`
* `archive`
* `supprime`

### Données de travail et de diffusion
Voir [src/resources/init_declaration_source_db_schema.sql](./src/resources/init_aggregation_db_schema.sql)
Les exécutables suivants utilisent ces données :
* `pair_from_sources`
* `delete_data`

Les colonnes obligatoires pour le fonctionnement des exécutables ci-dessus sont :
* table des déclarations :
    * Clé primaire (identifiant unique) : `id_dossier`
    * `creation`
    * `date_insta`
    * `geom`
* table des détections
    * Clé primaire (identifiant unique) : `id_millesime`
        * Les valeurs dans la colonne `id` ne sont pas uniques dans la table : un même objet détecté conserve son identifiant "id" s'il est détecté sur plusieurs millésimes "millesime". C'est donc bien le couple (`id`, `millesime`) qui est unique.
    * `millesime`
    * `geom`
* table de lien :
    * toutes
* vue agrégée : non concernée

Les autres colonnes dans le fichier SQL d'exemple sont utilisées par la vue "donnees_agregees". Cette vue réalise une jointure partielle entre les tables du schéma et sert de base pour d'éventuels flux de diffusion des données agrégées/appariées. (OSGeo TMS, OGC WFS, etc)
