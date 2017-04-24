# -*- coding: utf-8 -*-

# Standard imports
import datetime
import os.path
import codecs

# Non standard imports (see requirements.txt)
import click
import jinja2
import fiona
from shapely.geometry import shape
from shapely.ops import unary_union, transform
import pyproj 
from functools import partial
import yaml


# DONE: ajouter en paramètres globaux les noms des champs de ADMIN EXPRESS utilisés par le script
# DONE: gérer les erreurs sur la présence du template
# DONE: gérer les erreurs sur la présence d'ADMIN EXPRESS
# DONE: gérer les erreurs sur la présence des champs d'ADMIN EXPRESS
# DONE: vérifier le srs d'ADMIN EXPRESS
# DONE: vérifier le srs du filtre spatial
# DONE: ajouter une option pour écraser la sortie ou non
# DONE: ajouter une option pour mode debug ou mode verbose


class Bunch:
    """
    See http://code.activestate.com/recipes/52308-the-simple-but-handy-collector-of-a-bunch-of-named/?in=user-97991
    """
    def __init__(self, **kwds):
        self.__dict__.update(kwds)


def get_geometry_from_file(input_file_path):
    try:
        with fiona.open(input_file_path) as input_layer:
            geoms = [shape(feat['geometry']) for feat in input_layer]
            geom = unary_union(geoms)
            return geom
    except Exception as e:
        click.echo(u"Le fichier spécifié pour filtrer les données spatialement "
                   u"n'a pas pu être exploité. Aucun filtre spatial ne sera appliqué.")

@click.command()
@click.option('-v', '--verbose', count=True)
@click.option('--delete/--no-delete', default=False)
@click.option('--dept-filter',
              help='List of departement numbers or names used to filter the municipalities.')
@click.option('--filter-shp-path', type=click.Path(exists=True, dir_okay=False),
              help='Shapefile path of the commune layer of ADMIN EXPRESS.')
#@click.argument('com-shp-path', nargs=1, type=click.Path(exists=True, dir_okay=False))
@click.argument('thesaurus', nargs=1, type=click.Choice(['commune', 'region', 'departement', 'epci']))
@click.argument('out-rdf-path', nargs=1, type=click.Path(exists=False, dir_okay=False))
def build_french_municipalities_thesaurus(thesaurus, out_rdf_path, dept_filter=None, filter_shp_path=None, verbose=None, delete=False):
    """
    This command creates a skos thesaurus for the french municipalities based on the ADMIN EXPRESS dataset from IGN
    (french mapping national agency). The created thesaurus can be used in Geonetwork.

    Examples:\n
    build_french_municipalities_thesaurus ../ADE/COMMUNE.shp ../temp/CommunesFR.rdf\n
    build_french_municipalities_thesaurus --dept-filter "02,60,80" ../ADE/COMMUNE.shp ../temp/CommunesFR.rdf\n
    build_french_municipalities_thesaurus --dept-filter "  02,    oise, SOMME" ../ADE/COMMUNE.shp ../temp/CommunesFR.rdf\n
    build_french_municipalities_thesaurus --dept-filter "02,60,80" --filter-shp-path ../temp/my_shape.shp ../ADE/COMMUNE.shp ../temp/CommunesFR.rdf\n
    """

    with open("static/config.yml", 'r') as ymlfile:
        cfg = yaml.load(ymlfile)

    #{'template_dir_name': 'templates', 'commune': {'shp': 'COMMUNE', 'nom': 'NOM_COM', 'code': 'INSEE_COM', 'template': 'CommunesFR.xml', 'nomdept': 'NOM_DEP', 'codedept': 'INSEE_DEP'}}


    # Configure the templates dir variables
    templates_dir_path = os.path.join(os.path.dirname(__file__), cfg['template_dir_name'])
    template_loader = jinja2.FileSystemLoader(searchpath=templates_dir_path)
    template_env = jinja2.Environment(
        loader=template_loader,
        trim_blocks=True,
        lstrip_blocks=True)

    # Test if rdf already exists when --no-delete
    if not delete and os.path.isfile(out_rdf_path):
        click.echo(u"Output file %s already exists. Try --delete to force replace." % out_rdf_path)
        exit(0)

    thesaurus_cfg = cfg[thesaurus]

    # Read the template file using the environment object
    if verbose : 
        click.echo(u"Loading template %s" % thesaurus_cfg['template'])

    try:
        template = template_env.get_template(thesaurus_cfg['template'])
    except Exception as e:
        click.echo(u"Template %s not found. Stop here." % thesaurus_cfg['template'])
        exit(0)

    # Get the geometry of the spatial filter
    spatial_filter_geom = None
    if filter_shp_path is not None:
        spatial_filter_geom = get_geometry_from_file(filter_shp_path)
        if verbose:
            click.echo(u"Filter with shapefile : %s" % filter_shp_path)
    elif verbose: 
        click.echo(u"No shapefile filter set")

    # Create the list of departements
    dept_list = None
    if dept_filter is not None:
        dept_list = [dept.strip().lower() for dept in dept_filter.split(",")]
        if verbose:
            click.echo(u"Filter with departement list : %s" % '|'.join(dept_list))
    elif verbose: 
        click.echo(u"No departement list set")

    # Create the list of municipalities
    terr_list = []
    check_ade = True
    ade_shp_path = os.path.join(cfg['ade_dir_name'],thesaurus_cfg['shp'])

    if verbose : 
        click.echo(u"Read shapefile %s" % ade_shp_path)

    with fiona.open(ade_shp_path, 'r') as shp:
        # func to reproject geom
        project = partial(
            pyproj.transform,
            pyproj.Proj(shp.crs),
            pyproj.Proj(init='EPSG:4326'))

        for feat in shp:
            f_props = feat['properties']
            f_geom = shape(feat['geometry'])
            f_geom_wgs84 = transform(project, f_geom)
            lon_min, lat_min, lon_max, lat_max = f_geom_wgs84.bounds

            # On first item only, check ADE fields
            fields = thesaurus_cfg['fields']
            if check_ade:
                for f in fields:
                    if not fields[f] in f_props:
                        click.echo(u"Fatal error : field %s not found in shapefile." % (fields[f]))
                        exit(0)
                check_ade = False

            name = f_props[fields['nom']].strip()
            code = f_props[fields['code']].strip()


            dept_name = ''
            dept_code = ''
            reg_code = ''
            dept_reg = []

            # If municipalities, get dept infos for filter
            if thesaurus == 'commune':
                dept_name = f_props[fields['nomdept']].strip()
                dept_code = f_props[fields['codedept']].strip()
            # If departement, get code region
            elif thesaurus == 'departement':
                reg_code = f_props[fields['codereg']].strip()
            # If region, get departement list
            elif thesaurus == 'region':
                # Reading departement shapefile to get departements list for each region
                dept_shp = cfg['departement']['shp'];
                dept_shp_path = os.path.join(cfg['ade_dir_name'], dept_shp)
                if os.path.isfile(dept_shp_path):
                    if verbose:
                        click.echo(u"Read shapefile %s" % dept_shp_path)

                    with fiona.open(dept_shp_path, 'r') as shpdept:
                        for d in shpdept:
                            d_props = d['properties']
                            reg_code = d_props[cfg['departement']['fields']['codereg']].strip()
                            dep_code = d_props[cfg['departement']['fields']['code']].strip()
                            if reg_code == f_props[fields['code']].strip():
                                dept_reg.append(dep_code)

                    if verbose:
                        click.echo("Region %s : %s" % (f_props[fields['code']].strip(), ','.join(dept_reg)))


                else:
                    click.echo(u"Shapefile %s not found. Mandatory to list departements in regions. Stop here." % dept_shp_path)
                    exit(0)

            terr = Bunch(name=name,
                    lon_min=lon_min, lat_min=lat_min, lon_max=lon_max, lat_max=lat_max,
                    code=code, reg=reg_code, dept_reg=dept_reg)

            # On ajoute l'objet à la liste si aucun filtre n'est défini ou si les filtres sont compatibles
            filter_geom = spatial_filter_geom is None or f_geom.intersects(spatial_filter_geom)
            filter_dept = dept_filter is None or len(dept_list) == 0 or \
                              dept_name.lower() in dept_list or dept_code.lower() in dept_list
            if filter_geom and filter_dept:
                terr_list.append(terr)

        terr_list.sort(key=lambda terr: terr.code)

    # data passed to the template
    data = {
        "source_year": 2017,
        "date": datetime.date.today().isoformat(),
        "terr_list": terr_list,
        "thesaurus": thesaurus
    }

    # Finally, process the template to produce our final text.
    template_result = template.render(data)

    if verbose : 
        click.echo(u"Write output file %s" % out_rdf_path)

    with codecs.open(out_rdf_path, "w", "utf-8") as f:
        f.write(template_result)


    if verbose : 
        click.echo(u"Done. Goodbye")
