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

## Spécification des bases de données
### Table des données de déclaration
#### import_declarations
| Colonne | Type | Contraintes |
| :------ | :--- | :---------- |
| id_dossier | bigint | PRIMARY KEY |
| porteur | bool |  |
| siret_port | char(14) |  |
| ref_urba | text |  |
| type_proj | text |  |
| surf_socle | decimal(17, 4) |  |
| etat | text |  |
| puiss_max | int |  |
| date_depot | date |  |
| date_deliv | date |  |
| date_insta | date |  |
| duree_exp | int |  |
| adresse | text |  |
| num_parcelles | text |  |
| surf_occup | decimal(17, 4) |  |
| surf_terr | decimal(17, 4) |  |
| localisat | text |  |
| sol_nature | text |  |
| sol_detail | text |  |
| usage_terr | text |  |
| type_agri | text |  |
| agri_ini | text |  |
| agri_resid | text |  |
| ancrage | text |  |
| cloture | text |  |
| revetement | text |  |
| haut_pann | decimal(6, 3) |  |
| espacement | decimal(8, 3) |  |
| nat_pieux | bool |  |
| transit | bool |  |
| agrivolt | bool |  |
| ex_date | bool |  |
| ex_agriv | bool |  |
| ex_techniq | bool |  |
| geom | geometry(MULTIPOLYGON,2154) |  |
| creation | timestamp (0) with time zone |  |
| dern_modif | timestamp (0) with time zone |  |
| archive | bool |  |
| supprime | bool |  |

#### Autres exécutables
Même chose sans les colonnes `dern_modif`, `archive`, `supprime`.
Si une base de données dédiée est utilisée pour extraire les données du service "démarches simplifiées", alors ces colonnes permettent le filtrage des données à transférer vers la base de données de travail et de diffusion. (Celle utilisée par les exécutables autres que "import_declarations".)

### Table des données de télédétection
| Colonne | Type | Contraintes |
| :------ | :--- | :---------- |
| id_v2 | bigint | PRIMARY KEY |
| id | bigint |  |
| long | decimal(11, 8) |  |
| lat | decimal(11, 8) |  |
| surf_parc | decimal(17, 4) |  |
| nb_pann | int |  |
| nb_const | int |  |
| insee_com | text |  |
| nom_com | text |  |
| millesime | int |  |
| dern_modif | timestamp |  |
| geom | geometry(MULTIPOLYGON,2154) |  |

### Table de liens entre déclarations et détections
| Colonne | Type | Contraintes |
| :------ | :--- | :---------- |
| declaration_id | bigint | REFERENCES declaration |
| detection_id | bigint | REFERENCES detection |
