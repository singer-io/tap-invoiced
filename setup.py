#!/usr/bin/env python
from setuptools import setup

setup(
    name="tap-invoiced",
    version="0.2.0",
    description="Singer.io tap for extracting data from Invoiced",
    author="Invoiced",
    url="https://invoiced.com",
    classifiers=["Programming Language :: Python :: 3 :: Only"],
    py_modules=["tap_invoiced"],
    install_requires=[
        "singer-python>=5.4.1",
        "invoiced==0.12.0"
    ],
    entry_points="""
    [console_scripts]
    tap-invoiced=tap_invoiced:main
    """,
    packages=["tap_invoiced"],
    package_data={
        "schemas": ["tap_invoiced/schemas/*.json"]
    },
    include_package_data=True,
)
