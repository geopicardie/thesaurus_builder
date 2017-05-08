# -*- coding: utf-8 -*-

# Standard imports
import datetime
import os
import os.path
import codecs

# Non standard imports (see requirements.txt)
import click
import jinja2
from shapely.geometry import shape
from shapely.ops import unary_union
from shapely.ops import transform
# Fiona should be imported after shapely - see https://github.com/Toblerity/Shapely/issues/288
import fiona
import pyproj
from functools import partial
import yaml

from utils import Bunch
from utils import get_geometry_from_file
from utils import prettify_xml


@click.command()
@click.option('-v', '--verbose', is_flag=True, default=False,
              help='Enables verbose mode')
@click.option('--overwrite/--no-overwrite', default=False,
              help='Allows to overwrite an existing thesaurus file')
@click.option('--compact/--no-compact', default=False,
              help='Write compact rdf file')
@click.option('--dept-filter',
              help='List of departement numbers or names used to filter the municipalities.')
@click.option('--filter-shp-path', type=click.Path(exists=True, dir_okay=False),
              help='Path of a shapefile used to spatially filter the entities.')
@click.option('--cfg-path', type=click.Path(exists=True, dir_okay=False), default="config_ade.yml",
              help='Path of a config file.')
@click.option('--thesaurus', multiple=True, type=click.Choice(['commune', 'region', 'departement', 'epci']),
              help='Selection of the type of thesaurus to produce')
@click.argument('output-dir', nargs=1, type=click.Path(exists=True, dir_okay=True, file_okay=False, writable=True))
def create_thesauri(
        verbose,
        overwrite,
        compact,
        thesaurus,
        output_dir,
        dept_filter=None,
        filter_shp_path=None,
        cfg_path=None):
    """
    This command creates a SKOS thesaurus for the french municipalities based on the ADMIN EXPRESS dataset from IGN
    (french mapping national agency). The created thesaurus can be used in Geonetwork.

    Examples:\n
    python build_thesaurus_from_ade.py output\n
    python build_thesaurus_from_ade.py --verbose --overwrite output\n
    python build_thesaurus_from_ade.py --verbose --overwrite --dept-filter "60,02,somme" output\n
    python build_thesaurus_from_ade.py --verbose --overwrite --dept-filter "60,02,somme" output\n
    python build_thesaurus_from_ade.py --dept-filter "02,60,80" output\n
    python build_thesaurus_from_ade.py --dept-filter "  02,    oise, SOMME" output\n
    python build_thesaurus_from_ade.py --dept-filter "02,60,80" --filter-shp-path my_filter.shp output\n
    python build_thesaurus_from_ade.py --cfg-path config_ade.yml --dept-filter "02,60,80" --overwrite temp\n
    python build_thesaurus_from_ade.py --cfg-path ./temp/config.yml --dept-filter "02,60,80" --overwrite --thesaurus departement temp\n
    """

    thesauri_builder = AdeThesauriBuilder(
        verbose=verbose,
        overwrite=overwrite,
        compact=compact,
        thesaurus=thesaurus,
        output_dir=output_dir,
        dept_filter=dept_filter,
        filter_shp_path=filter_shp_path,
        cfg_path=cfg_path)

    thesauri_builder.create_thesauri()

    click.echo(u"Done. Goodbye")


class AdeThesauriBuilder(object):

    def __init__(self,
                 verbose,
                 overwrite,
                 compact,
                 thesaurus,
                 output_dir,
                 cfg_path,
                 dept_filter=None,
                 filter_shp_path=None):

        self.verbose = verbose
        self.overwrite = overwrite
        self.compact = compact
        self.thesaurus = thesaurus
        self.output_dir = output_dir
        self.filter_shp_path = filter_shp_path

        with open(cfg_path, 'r') as yaml_file:
            self.cfg = yaml.load(yaml_file)

        # Configure the templates dir variables
        templates_dir_path = os.path.join(os.path.dirname(__file__), self.cfg['template_dir_name'])
        template_loader = jinja2.FileSystemLoader(searchpath=templates_dir_path)
        self.template_env = jinja2.Environment(
            loader=template_loader,
            trim_blocks=True,
            lstrip_blocks=True)

        # Get the geometry of the spatial filter
        if verbose:
            click.echo(u"Shapefile filter: {}".format(filter_shp_path))
        self.spatial_filter_geom = None
        try:
            if filter_shp_path is not None:
                self.spatial_filter_geom = get_geometry_from_file(filter_shp_path)
        except Exception as e:
            click.echo(u"The shapefile specified for spatial filtering could not be  opened. "
                       u"No spatial filter will be applied.")

        # Create the list of departements
        self.dept_list = None
        if dept_filter is not None:
            self.dept_list = [dept.strip().lower() for dept in dept_filter.split(",")]
        if verbose:
            click.echo(u"Departements filter: {}".format('|'.join(self.dept_list)))

        if not self.thesaurus:
            self.thesaurus = ("commune", "departement", "region", "epci")

        click.echo(u"Thesauri to be produced: {}".format(", ".join(self.thesaurus)))

    def create_thesauri(self):
        for thesaurus_type in self.thesaurus:
            self.create_thesaurus(thesaurus_type)

    def create_thesaurus(self, thesaurus_type):

        click.echo(u"Thesaurus creation: {}".format(thesaurus_type))

        thesaurus_cfg = self.cfg.get(thesaurus_type, None)
        if not thesaurus_cfg:
            click.echo(u"  Unknown thesaurus type: {}.".format(thesaurus_type))
            return

        # Output file name and path
        rdf_file_name = thesaurus_cfg.get('out')
        if rdf_file_name:
            rdf_file_path = os.path.join(self.output_dir, rdf_file_name)
        else:
            click.echo(u"  Output rdf file name not found. Stop here")
            return

        if self.verbose:
            click.echo(u"  Output file path: {}".format(rdf_file_path))

        # Test if the rdf file already exists when --no-overwrite
        if not self.overwrite and os.path.isfile(rdf_file_path):
            click.echo(u"  Output file {} already exists. Won't be overwritten.".format(rdf_file_path))
            click.echo(u"  Add option --overwrite to overwrite it.")
            return

        # Read the template file using the environment object
        if self.verbose:
            click.echo(u"  Loading template {}".format(thesaurus_cfg['template']))

        try:
            template = self.template_env.get_template(thesaurus_cfg['template'])
        except Exception as e:
            click.echo(u"  Template {} not found. Stop here.".format(thesaurus_cfg['template']))
            return

        # Create the list of territories
        terr_list = []
        depts = []
        depts_geom = None
        check_ade = True
        ade_shp_path = os.path.join(self.cfg['ade_dir_name'], thesaurus_cfg['shp'])

        if self.verbose:
            click.echo(u"  Read shapefile {}".format(ade_shp_path))

        if thesaurus_type in ("region", "epci"):

            # Reading departement shapefile to get departements list for each region
            dept_shp_file_name = self.cfg['departement']['shp']
            dept_shp_file_path = os.path.join(self.cfg['ade_dir_name'], dept_shp_file_name)

            if os.path.isfile(dept_shp_file_path):
                if self.verbose:
                    click.echo(u"  Read shapefile {}".format(dept_shp_file_path))
            else:
                click.echo(u"  Shapefile {} not found. Mandatory to list departements in regions. Stop here.".format(
                    dept_shp_file_path))
                return

            with fiona.open(dept_shp_file_path, 'r') as dept_shp:
                for d in dept_shp:
                    dept = {
                        "dept_name": d['properties'][self.cfg['departement']['fields']['nom']].strip(),
                        "dept_code": d['properties'][self.cfg['departement']['fields']['code']].strip(),
                        "reg_code": d['properties'][self.cfg['departement']['fields']['codereg']].strip(),
                        "geometry": d['geometry'],
                    }
                    depts.append(dept)

                if self.dept_list:
                    depts_geoms = [shape(dept['geometry']) for dept in depts
                                   if dept["dept_name"].lower() in self.dept_list or
                                   dept["dept_code"] in self.dept_list]
                    depts_geom = unary_union(depts_geoms)

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
                            click.echo(u"  Fatal error: field {} not found in shapefile.".format(fields[f]))
                            return
                    check_ade = False

                name = f_props[fields['nom']].strip().replace("&", "&amp;")
                code = f_props[fields['code']].strip()

                dept_name = ''
                dept_code = ''
                reg_code = ''
                reg_dept_codes = None

                # If municipalities, get dept infos for filter
                if thesaurus_type == 'commune':
                    dept_name = f_props[fields['nomdept']].strip()
                    dept_code = f_props[fields['codedept']].strip()
                # If departement, get region code
                elif thesaurus_type == 'departement':
                    reg_code = f_props[fields['codereg']].strip()
                # If region, get departement list
                elif thesaurus_type == 'region':
                    reg_dept_codes = [dept['dept_code'] for dept in depts
                                      if dept['reg_code'] == f_props[fields['code']].strip()]

                terr = Bunch(name=name,
                             lon_min=lon_min, lat_min=lat_min, lon_max=lon_max, lat_max=lat_max,
                             code=code, reg=reg_code, dept_reg=reg_dept_codes)

                # Add the object to the list of territories if non spatial filter, else we only add it to the list
                # if its geometry intersects the spatial filter
                filter_geom = self.spatial_filter_geom is None or f_geom.relate(self.spatial_filter_geom)[0] != 'F'

                if thesaurus_type == 'commune':
                    filter_dept = self.dept_list is None or len(self.dept_list) == 0 or \
                                  dept_name.lower() in self.dept_list or dept_code in self.dept_list
                elif thesaurus_type == 'epci':
                    filter_dept = self.dept_list is None or len(self.dept_list) == 0 or \
                                  depts_geom is None or f_geom.relate(depts_geom)[0] == '2'
                elif thesaurus_type == 'departement':
                    filter_dept = self.dept_list is None or len(self.dept_list) == 0 or \
                                  name.lower() in self.dept_list or code in self.dept_list
                elif thesaurus_type == 'region':
                    filter_dept = self.dept_list is None or len(self.dept_list) == 0 or \
                                  len(set(self.dept_list).intersection(reg_dept_codes)) > 0
                else:
                    filter_dept = self.dept_list is None or len(self.dept_list) == 0 or \
                                  depts_geom is None or f_geom.relate(depts_geom)[0] == '2'

                if filter_geom and filter_dept:
                    terr_list.append(terr)

            terr_list.sort(key=lambda t: t.code)

        # data passed to the template
        data = {
            "title": thesaurus_cfg["title"],
            "date": datetime.date.today().isoformat(),
            "terr_list": terr_list,
            "thesaurus": thesaurus_type
        }

        # Finally, process the template to produce our final text.
        rdf_content = template.render(data)
        rdf_content = prettify_xml(rdf_content, minify=self.compact)

        if self.verbose:
            click.echo(u"  Write output file {}".format(rdf_file_path))

        with codecs.open(rdf_file_path, "w", "utf-8") as f:
            f.write(rdf_content)

if __name__ == '__main__':
    create_thesauri()
