# -*- coding: utf-8 -*-

from setuptools import setup

setup(
    name='thesaurus_builder',
    version='0.1',
    py_modules=['thesaurus_builder'], 
    packages=['static'],
    include_package_data=True,
    install_requires=[
        'jinja2',
        'fiona',
        'shapely',
        'click',
        'pyproj',
        'pyyaml'
    ],
    entry_points='''
        [console_scripts]
        build_french_thesaurus=thesaurus_builder:build_french_thesaurus
    ''',
)
