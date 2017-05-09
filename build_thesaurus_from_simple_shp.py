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
from shapely.ops import transform
# Fiona should be imported after shapely - see https://github.com/Toblerity/Shapely/issues/288
import fiona
import pyproj
from functools import partial
import yaml

from utils import Bunch
from utils import prettify_xml


@click.command()
@click.option('-v', '--verbose', is_flag=True, default=False,
              help='Enables verbose mode')
@click.option('--overwrite/--no-overwrite', default=False,
              help='Allows to overwrite an existing thesaurus file')
@click.option('--compact/--no-compact', default=False,
              help='Write compact rdf file')
@click.option('--cfg-path', type=click.Path(exists=True, dir_okay=False), default="config_simple_shp.yml",
              help='Path of a config file.')
@click.argument('output-dir', nargs=1, type=click.Path(exists=True, dir_okay=True, file_okay=False, writable=True))
def create_thesauri(
        verbose,
        overwrite,
        compact,
        output_dir,
        cfg_path):
    """
    This command creates a SKOS thesaurus for the french municipalities based on the ADMIN EXPRESS dataset from IGN
    (french mapping national agency). The created thesaurus can be used in Geonetwork.

    Examples:\n
    python build_thesaurus_from_simple_shp.py output\n
    python build_thesaurus_from_simple_shp.py --verbose --overwrite output\n
    python build_thesaurus_from_simple_shp.py --cfg-path ./temp/config_simple_shp.yml --overwrite temp/out\n
    """

    thesauri_builder = ShpThesauriBuilder(
        verbose=verbose,
        overwrite=overwrite,
        compact=compact,
        output_dir=output_dir,
        cfg_path=cfg_path)

    thesauri_builder.create_thesauri()

    click.echo(u"Done. Goodbye")


class ShpThesauriBuilder(object):

    def __init__(self,
                 verbose,
                 overwrite,
                 compact,
                 output_dir,
                 cfg_path):

        self.verbose = verbose
        self.overwrite = overwrite
        self.compact = compact
        self.output_dir = output_dir

        with open(cfg_path, 'r') as yaml_file:
            self.cfg = yaml.load(yaml_file)

        # Configure the templates dir variables
        templates_dir_path = os.path.join(os.path.dirname(__file__), self.cfg['template_dir_name'])
        template_loader = jinja2.FileSystemLoader(searchpath=templates_dir_path)
        self.template_env = jinja2.Environment(
            loader=template_loader,
            trim_blocks=True,
            lstrip_blocks=True)

        # Thesauri list
        self.thesauri_list = self.cfg["thesauri"].keys()
        click.echo(u"Thesauri to be produced: {}".format(", ".join(self.thesauri_list)))

    def create_thesauri(self):

        for thesaurus_name in self.thesauri_list:
            self.create_thesaurus(thesaurus_name)

    def create_thesaurus(self, thesaurus_name):

        click.echo(u"Thesaurus creation: {}".format(thesaurus_name))

        thesaurus_cfg = self.cfg["thesauri"].get(thesaurus_name, None)
        if not thesaurus_cfg:
            click.echo(u"  Unknown thesaurus name: {}.".format(thesaurus_name))
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

        # URI template
        uri_scheme = thesaurus_cfg.get('uri_scheme')
        uri_template = "{}#{}".format(uri_scheme, "{}")

        # Create the list of territories
        terr_list = []
        # depts = []
        # depts_geom = None
        check_fields = True
        shp_path = thesaurus_cfg['shp']

        if self.verbose:
            click.echo(u"  Read shapefile {}".format(shp_path))

        with fiona.open(shp_path, 'r') as shp:
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
                if check_fields:
                    for f in fields:
                        if not fields[f] in f_props:
                            click.echo(u"  Fatal error: field {} not found in shapefile.".format(fields[f]))
                            return
                    check_fields = False

                name = f_props[fields['name']].strip().replace("&", "&amp;")
                code = f_props[fields['code']].strip()
                uri = None
                if uri_template:
                    uri = uri_template.format(code)

                terr = Bunch(name=name,
                             lon_min=lon_min, lat_min=lat_min, lon_max=lon_max, lat_max=lat_max,
                             code=code,
                             uri=uri)

                # if filter_geom and filter_dept:
                terr_list.append(terr)

            terr_list.sort(key=lambda t: t.code)

        # data passed to the template
        data = {
            "title": thesaurus_cfg["title"],
            "uri_scheme": uri_scheme,
            "date": datetime.date.today().isoformat(),
            "terr_list": terr_list,
            "thesaurus": thesaurus_name
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
