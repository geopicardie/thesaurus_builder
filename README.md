# thesaurus_builder
Outils de génération de thésaurus pour GeoNetwork.

* build_thesaurus_from_ade.py : création de thésaurus à par des shapefiles ADMINEXPRESS de l'IGN
* build_thesaurus_from_simple_shp.py : création de thésaurus à d'un shapefile quelconque.

Nécessite les modules listés dans requirements.txt :
 * jinja2
 * fiona
 * shapely
 * click
 * pyproj
 * pyyaml
Ces modules peuvent être installés via la commande suivante :
<pre>
pip install -r requirements
</pre>

## build_thesaurus_from_ade.py

L'argument de la commande est le répertoire dans lequel les thésaurus au format RDF seront créés.

Les options :
* --cfg-path : fichier de configuration décrivant les thesaurus à créer. Par défaut il s'agit du fichier config_ade.yml
 à la racine du projet
* --thesaurus : type de thesaurus à créer (commune, epci, departement ou region. Cette option est répétable. Si cette
 option n'est pas renseignée, tous les thésaurus décrits dans le fichier de configuration seront créés.
* --verbose ou -v : mode verbeux
* --overwrite/--np-overwrite : interdit ou autorise le remplacement des fichiers existants en sortie
* --dept-filter : liste de noms ou numéros de départements pour limiter la zone géographique sur laquelle est créé
le thésaurus
* --filter-shp-path : chemin vers un shapefile pour limiter la zone géographique sur laquelle est créé le thésaurus

Exemples :

<pre>
python build_thesaurus_from_ade.py output
python build_thesaurus_from_ade.py --verbose --overwrite output
python build_thesaurus_from_ade.py --verbose --overwrite --dept-filter "60,02,somme" output
python build_thesaurus_from_ade.py --verbose --overwrite --dept-filter "60,02,somme" output
python build_thesaurus_from_ade.py --dept-filter "02,60,80" output
python build_thesaurus_from_ade.py --dept-filter "  02,    oise, SOMME" output
python build_thesaurus_from_ade.py --dept-filter "02,60,80" --filter-shp-path my_filter.shp output
python build_thesaurus_from_ade.py --cfg-path config_ade.yml --dept-filter "02,60,80" --overwrite temp
python build_thesaurus_from_ade.py --cfg-path ./temp/config.yml --dept-filter "02,60,80" --overwrite --thesaurus departement temp
</pre>


## build_thesaurus_from_simple_shp.py

L'argument de la commande est le répertoire dans lequel les thésaurus au format RDF seront créés.

Les options :
* --cfg-path : fichier de configuration décrivant les thesaurus à créer. Par défaut il s'agit du fichier
 config_simple_shp.yml à la racine du projet
* --verbose ou -v : mode verbeux
* --overwrite/--np-overwrite : interdit ou autorise le remplacement des fichiers existants en sortie

Exemples :

<pre>
python build_thesaurus_from_simple_shp.py output
python build_thesaurus_from_simple_shp.py --verbose --overwrite output
python build_thesaurus_from_simple_shp.py --cfg-path ./temp/config.yml --overwrite temp/out
</pre>
