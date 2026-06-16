# Guide d'utilisation
## Déploiement d'ensemble via docker-compose
### Prérequis et préparation
#### Systèmes docker
Le moteur *docker engine*, ou alors la suite graphique *docker desktop*, doit être installé sur le système hôte. L'utilisateur doit disposer des droits nécessaires pour les opérations *docker* et *docker compose* de base. (build, pull, run, etc)
Pour l'installation, se référer à la documentaiton officielle de docker :

* installation de *docker engine* : https://docs.docker.com/engine/install/
* installation de *docker desktop* : https://docs.docker.com/get-started/get-docker/

La suite de cette documentation se base sur l'interface en ligne de commandes de *docker engine*.
Un exemple de configuration *docker compose* pour cette application est donné dans le dossier [docker_example/docker-compose.yml](./docker_example/docker-compose.yml)

**Attention :**

* Le moteur *docker engine* doit disposer d'un accès internet à toutes les étapes :
	* récupération des images publiques depuis docker.io et et ghcr.io,
	* compilation d'image depuis le dépôt,
	* accès au service *démarche numérique* depuis le conteneur d'exécution du script `import_declarations`.
* Les images docker.io (alias *dockerhub*) peuvent nécessiter un compte sur ce service, en raison des limitations de téléchargement pour les utilisateurs anonymes.

#### Variables d'environnement sur l'hôte
Il est conseillé d'écrire ces variables dans un fichier ".env" placé avec le fichier "docker-compose.yml". Les précautions de sécurité habituelles du système hôte s'appliquent toujours.

| Variable | Description | Exemple | Note |
| :------- | :---------- | :------ | :--- |
| `HOST_UID` | Identifiant numérique unique de l'utilisateur sur le système hôte, pour définir les droits corrects sur les fichiers créés. | Résultat de la commande `id -u`. | |
| `HOST_GID` | Identifiant numérique unique du groupe l'utilisateur sur le système hôte, pour définir les droits corrects sur les fichiers créés. | Résultat de la commande `id -u`. | |
| `HTTP_PROXY` / `http_proxy` | Adresse du proxy HTTP, si applicable | http://proxy-http.company.com:8080 | |
| `HTTPS_PROXY` / `https_proxy` | Adresse du proxy HTTPS, si applicable | https://proxy-https.company.com:8080 | |
| `OCSGE_PV_REPO_PATH` | Chemin absolu d'accès à la racine du dépôt sur l'hôte | `/home/user/git_repos/ocsge-pv` | |
| `OCSGE_PV_DATA_PATH` | Chemin absolu d'accès au dossier qui contiendra les fichiers de données en entrée, et potentiellement les exports depuis le BDD | `/home/user/data/ocsge-pv` | |
| `OCSGE_PV_SQL_SCRIPTS_PATH` | Chemin absolu d'accès aux scripts SQL d'initialisation de la BDD | `/home/user/git_repos/ocsge-pv/docs/docker_example/sql_scripts` | |
| `TZ` | Nom ISO du fuseau horaire (Timezone) pour l'horodatage. | `Europe/Paris` | Par défaut, "`Europe/Paris`" sera choisi. |
| `DS_GQL_API_AUTH` | Jeton d'authentification sur l'API du service *démarche numérique* | `A9Knc34tP==` | Cette variable est surchargée par la propriété '.input.auth_token' du fichier de configuration. Attention : information sensible à traiter comme un secret. Préférez les outils dédiés à votre disposition pour injecter ce secret dans la stack docker. |

### En cas de volonté de compilation depuis les sources
Si vous voulez compiler l'image applicative principale à partir des sources, au lieu d'utiliser une image publique, éditez le fichier [./docker_example/docker-compose.yml](./docker_example/docker-compose.yml).
Remplacez d'abord la valeur de propriété "image" du service "main", par le tag local `local/ignf/ocsge-pv:nover`. (La valeur d'origine pour l'image publique est `ghcr.io/ignf/ocsge-pv`.)
Ensuite, ajoutez une propriété "build" au service "main" en insérant ce bloc dans la définition du service :

```yml
    build:
      args:
        - HOST_UID=$HOST_UID
        - HOST_GID=$HOST_GID
        - http_proxy=$http_proxy
        - HTTP_PROXY=$HTTP_PROXY
        - https_proxy=$https_proxy
        - HTTPS_PROXY=$HTTPS_PROXY
      context: $OCSGE_PV_REPO_PATH/
      dockerfile: $OCSGE_PV_REPO_PATH/Dockerfile
      network: host
      tags:
        - "local/ignf/ocsge-pv:latest"
        - "local/ignf/ocsge-pv:nover"
```

## Déploiement classique sans conteneur
### Préparation de la base de données
#### Prérequis
La technologie attendue pour la base de données est une base PostgreSQL v14+ avec l'extension PostGIS v3+. (Non testé sur les versions antérieures.)
Le projet s'appuie sur une base de données PostgreSQL avec l'extension PostGIS. Il faut donc d'abord créer la base de données sur un serveur PostgreSQL v14+ / PostGIS v3+, et autoriser l'accès et l'écriture dans cette base pour le role à utiliser pour les traitements.

#### Structure de la base de données
Le projet git contient des fichiers d'initialisation de la base de données pour créer la structure des tables, dans le dossier `docker_example/sql_scripts/` :
* Table adaptée à l'import des données issues de *démarche numérique* : [init-db-import_declarations.sql](./docker_example/sql_scripts/init-db-import_declarations.sql)
* Tables adaptées au traitement d'appariement, et vue de jointure pour la visualisation des données agrégées : [init-db-paired_data.with_id_generation.sql](./docker_example/sql_scripts/init-db-paired_data.with_id_generation.sql)
  * En cas de conflit d'insertion en table à cause de la clé primaire de la table "detection", utilisez l'alternative [init-db-paired_data.no_id_generation.sql](./docker_example/sql_scripts/init-db-paired_data.no_id_generation.sql). Il faut alors penser à calculer la clé primaire "id_millesime" et à l'insérer avec le reste des colonnes. (La formule se trouve dans le script `init-db-paired_data.with_id_generation.sql`)

Ces fichiers prévoient l'utilisation de schémas (ou bases de données) séparés pour l'import et pour l'appariement. Ceci dit, la table d'import peut être utilisée aussi pour le traitement d'appariement. (L'inverse n'est pas vrai.) La seule différence entre les deux versions de la table "declaration" est la présence de quatre champs supplémentaires dans la table d'import. Ce sont des champs inutiles pour le traitement et la diffusion des données sur les parcs photovoltaïques, mais liés spécifiquement au cycle de vie des dossiers administratifs utilisés comme source. Dans un modèle à deux schémas, ces colonnes permettent par exemple de filtrer les données qui seront insérées dans le schéma prévu pour l'appariement en fonction du statut du dossier.

Autrement dit : les exemples sont basés sur une séparation en deux schémas, un schéma d'archivage des déclarations et un schéma de travail dédié aux données agrégées. L'utilisation d'un schéma unique est possible, tout comme l'hébergement des deux schémas dans des bases de données distinctes. Par contre, toutes les tables utilisées par un même traitement doivent
se trouver au sein d'un même schéma, donc aussi dans une même base de données. (Non testé avec des *foreign data wrappers*.)
* Pour un modèle à deux schémas :
  * les deux scripts SQL cités peuvent être exécutés tels quels dans la base de données, dans n'importe quel ordre.
* Pour un modèle à schéma unique :
  1. modifiez les informations de schéma pour que les deux scripts référencent le même schéma,
  2. exécutez le script `init-db-import_declarations.sql` dans la base de données,
  3. exécutez le script `init-db-paired_data.with_id_generation.sql` dans la base de données.

La base de données est prête.

Notez bien les informations suivantes d'accès aux données, qui seront utilisées dans les fichiers de configurations :
* hôte et port d'accès au serveur SQL
* nom et mot de passe du rôle SQL à utiliser
* nom de la base de données
* nom du schema
* nom des tables
  * déclarations
  * détections (uniquement pour l'appariement)
  * table de liens (uniquement pour l'appariement)

Dans la cas d'un modèle à deux schémas SQL, pensez à noter les informations pour chacun des deux usages. (Import et appariement.)

### Installation des exécutables
#### Prérequis
Python v3.10+ avec pip et GDAL v3.6+ sont requis sur le système.
Une égalité de version est obligatoire entre les bibliothèques libgdal et le paquet python GDAL.

#### Installation
L'exemple donné est basé sur un terminal `bash` sur un système `ubuntu v22.04+`, en utilisant un environnement virtuel python. Les commandes sont lancées dans le répertoire racine du dépôt de code.
L'utilisation d'un environnement virtuel python est fortement recommandé, même sur un système dédié à ce projet. L'installation hors environnement virtuel peut en effet provoquer des conflits entre le gestionnaire de paquets du système et pip.

```bash
sudo apt install python3 python3-pip python3-venv gdal-bin python3-gdal libgdal-dev
python3 -m venv .venv
source .venv/bin/activate
pip install "gdal==$(gdal-config --version)" .
OCSGE_PV_RESOURCE_DIR="$(realpath ./src/ocsge_pv/resources)"
export OCSGE_PV_RESOURCE_DIR

### DEV - En cas de développement sur le projet, pré-requis des actions obligatoires pour contribuer. ###
pip install .[dev] .[test]
OCSGE_PV_FIXTURE_DIR="$(realpath ./tests/fixtures)"
export OCSGE_PV_FIXTURE_DIR
pre-commit install --install-hooks
pytest # Permet de détecter si des prérequis ne sont pas remplis, pour les versions qui valident les tests lors de l'intégration continue.
### DEV fin ###

### (Non implémenté, mais prévu) DOC - Pour compiler la documentation, par exemple sous forme de site HTML. ###
pip install .[doc]
### DOC fin ###
```

## Exécution des outils du projet
### Informations générales
#### Suite à une installation classique
Les commandes décrites nécessitent d'avoir suivi la procédure d'installation et activé l'environnement virtuel python. Les chemins de fichiers donnés en exemple correspondent au cas où la commande est lancée depuis le répertoire racine du dépôt de code.

#### Suite à une installation docker-compose
Les commandes décrites nécessitent :
* Le déploiement préalable via docker-compose
* Que le service "main" de la stack soit actif
* De se placer dans le même répertoire que le fichier docker-compose utilisé pour lancer la stack

Les commandes citées à la suite sont celle exécutées sur la machine où le projet est installé. Dans ce cas, il s'agit du conteneur dédié au service "main". Pour les exécuter depuis l'hôte, il faut précéder la commande de l'instruction docker d'exécution dans un conteneur :

```sh
docker compose exec main <commande>
```

#### Dans tous les cas
Les commandes de base peuvent être remplacées par une commande python classique. Les deux commandes suivantes seront donc normalement équivalentes :

```sh
<nom_executable> <arguments>
```

```sh
python src/ocsge_pv/<nom_executable>.py <arguments>
```

Le fichier de configuration dont le chemin est fourni en argument doit être lisible sur la machine d'exécution par l'utilisateur qui lance la commande. Dans le cas d'une utilisation de docker, le fichier doit donc être lisible à l'adresse donnée depuis le conteneur du service "main". La méthode pour rendre le fichier disponible importe peu : volume monté, création au sein du conteneur, `docker compose cp`, etc.


### Aide CLI
Une aide CLI spécifique à chaque exécutable, et générée à partir du code, peut-être obtenue avec l'option `-h` comme seul argument de l'exécutable.
La commande suivante permet de visualiser toutes ces aides CLI à la suite (en concaténant l'aide de tous les exécutables) :

```sh
ocsge_pv_help
```


### Import des données déclaratives
#### Prérequis spécifique
Il est nécessaire de disposer d'un jeton d'accès à l'API du service "Démarche numérique". Le compte associé au jeton doit disposer des droits d'administration sur la démarche suivante :

* Titre : "Déclaration des installations de production d’énergie photovoltaïque pour l'exemption dans le calcul de la consommation d'espaces naturels et agricoles"
* URL publique : https://demarche.numerique.gouv.fr/commencer/declaration_pv_decret2023-1408
* id : `86067`

(L'accès administrateur est exigé par le service pour utiliser son API.)

#### Configuration
Le modèle json-schema qui documente la configuration pour ce processus est [src/ocsge_pv/resources/import_declarations_config.schema.json](../external/resources/import_declarations_config.schema.json)

Un exemple fictif valide est disponible dans ce fichier, cohérent avec les fichiers d'initialisation de BDD fournis : [docker_example/configurations/import_decl.json](./docker_example/configurations/import_decl.json)

#### Exécution
La commande suivante exécute le traitement d'import des données déclaratives :

```sh
import_declarations [-v] <path_to_configuration_file>
```

Où `path_to_configuration_file` est le chemin d'accès au fichier de configuration pour ce traitement.
Les données seront écrites dans la table décrite par le propriété "output" de la configuration.
En cas de mise à jour, c'est à dire si la table de destination est déjà remplie, des objets peuvent en être supprimés par le traitement. Ce comportement vise à éviter les doublons, c'est à dire les exploitations photovoltaïques déclarées plusieurs fois par erreur.

### Transition entre les étapes
Si les deux étapes décrites sont exécutées sur des schémas SQL différents, ou des bases de données différentes, pensez à copier les lignes de la table des déclarations qui vous intéressent depuis le schéma d'import vers le schéma d'appariement. Pour rappel, les fichiers d'exemples fournis correspondent à ce cas.

Cette copie est inutile si vous réalisez l'import directement vers la table de déclarations utilisée par le traitement d'appariement.

### Appariement des données déclaratives avec les données d'observation
#### Configuration
Le modèle json-schema qui documente la configuration pour ce processus est [src/ocsge_pv/resources/pair_config.schema.json](../external/resources/pair_config.schema.json)

Un exemple fictif valide est disponible dans ce fichier, cohérent avec les fichiers d'initialisation de BDD fournis : [docker_example/configurations/pair.json](./docker_example/configurations/pair.json).

#### Exécution
La commande suivante exécute le traitement d'appariement des données déclaratives avec les données d'observation :

```sh
pair_from_sources [-v] <path_to_configuration_file>
```

Où `path_to_configuration_file` est le chemin d'accès au fichier de configuration pour ce traitement.
Ce traitement édite la table ciblée, qui est donc à la fois en entrée et en sortie. Il peut supprimer des doublons ou des données conflictuelles ou invalides.


### Suppression d'objets dans les données
#### Configuration
Le modèle json-schema qui documente la configuration pour ce processus est [src/ocsge_pv/resources/delete_data_config.schema.json](../external/resources/delete_data_config.schema.json)

Deux exemples fictifs valides sont disponibles dans les fixtures de tests automatisés :
* [tests/fixtures/delete_data_config.ok_full.json](../external/fixtures/delete_data_config.ok_full.json)
* [tests/fixtures/delete_data_config.ok_minimal.json](../external/fixtures/delete_data_config.ok_minimal.json)

#### Exécution
La commande suivante exécute le traitement de suppression d'objets dans les données en base :

```sh
delete_data [-v] <path_to_configuration_file>
```

Où `path_to_configuration_file` est le chemin d'accès au fichier de configuration pour ce traitement.
Ce traitement édite la table ciblée, qui est donc à la fois en entrée et en sortie. Il sert à corriger les données en base quand des objets invalides ont été identifiés hors de l'exécution d'un autre traitement.
