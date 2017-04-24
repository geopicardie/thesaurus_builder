# thesaurus_builder
Outil de génération de thésaurus pour geonetwork. 

Fonctionne avec les shapefiles ADMINEXPRESS de l'IGN.


Nécessite les modules listés dans requirements.txt :
 * jinja2
 * fiona
 * shapely
 * click
 * pyproj
 * pyyaml

Pour déployer l'outil :
<pre>
python setup.py install
</pre>

Le fichier de configuration permet d'indiquer :
* l'emplacement des fichiers ADMINEXPRESS 
* le nom des champs si ceux si ne correspondaient plus.
* le nom des templates pour chaque type de thesaurus

Une fois l'outil déployé, on peut l'exécuter directement via la commande build_french_thesaurus

Le premier paramètre indique le type de thésaurus à générer : region, departement, epci ou commune
Le second indique le fichier rdf en sortie

Les autres paramètres sont optionnel : 
 * -v : verbous
 * --delete : force la suppression du fichier de sortie existant s'il existe
 * --dept-filter : liste de noms ou numéros de départements pour filtrer le thesaurus de communes
 * --filter-shp-path : chemin vers un shapefile pour filtrer géographiquement les objets qui seront dans le thesaurus
 
 
 Exemples : 

<pre>
build_french_thesaurus commune ../temp/CommunesFR.rdf
build_french_thesaurus --dept-filter "02,60,80" commune ../temp/CommunesFR.rdf
build_french_thesaurus --dept-filter "  02,    oise, SOMME" commune ../temp/CommunesFR.rdf
build_french_thesaurus --dept-filter "02,60,80" --filter-shp-path ../temp/my_shape.shp commune ../temp/CommunesFR.rdf
build_french_thesaurus epci ../temp/EpciFR.rdf -v --delete
</pre>