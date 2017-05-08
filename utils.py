# -*- coding: utf-8 -*-

# Standard imports
import os.path
import xml.dom.minidom as minidom

# Non standard imports (see requirements.txt)
from shapely.geometry import shape
from shapely.ops import unary_union
# Fiona should be imported after shapely - see https://github.com/Toblerity/Shapely/issues/288
import fiona


class Bunch:
    """
    See http://code.activestate.com/recipes/52308-the-simple-but-handy-collector-of-a-bunch-of-named/?in=user-97991
    """
    def __init__(self, **kwds):
        self.__dict__.update(kwds)


def u(s):
    """
    decodes utf8
    """
    if isinstance(s, unicode):
        return s.encode("utf-8")
    if isinstance(s, str):
        return s.decode("utf-8")
    # fix this, item may be unicode
    elif isinstance(s, list):
        return [i.decode("utf-8") for i in s]


def get_geometry_from_file(input_file_path):
    """
    Get the union of all the geometries contained in one shapefile.

    :param input_file_path:     the path of the shapefile from which the geometry is computed
    :return:                    the geomtry resulting in the union of the geometries of the shapefile
    """
    with fiona.open(input_file_path) as input_layer:
        geoms = [shape(feat['geometry']) for feat in input_layer]
        geom = unary_union(geoms)
        return geom


def prettify_xml(xml_string, minify=False, indent="  ", newl=os.linesep):
    """
    Function prettifying or minifying an xml string

    :param xml_string:  The XML string to prettify or minify
    :param minify:      True for minification and False for prettification
    :param indent:      String used for indentation
    :param newl:        String used for new lines
    :return:            An XML string
    """

    # Function used to remove XML blank nodes
    def remove_blanks(node):
        for x in node.childNodes:
            if x.nodeType == minidom.Node.TEXT_NODE:
                if x.nodeValue:
                    x.nodeValue = x.nodeValue.strip()
            elif x.nodeType == minidom.Node.ELEMENT_NODE:
                remove_blanks(x)

    xml = minidom.parseString(u(xml_string))
    remove_blanks(xml)
    xml.normalize()

    if minify:
        pretty_xml_as_string = xml.toxml()
    else:
        pretty_xml_as_string = xml.toprettyxml(indent=indent, newl=newl)

    return pretty_xml_as_string
