#!/usr/bin/env python

# --------------------------------------------------------------------------------------------
# Copyright (c) Microsoft Corporation. All rights reserved.
# Licensed under the MIT License. See License.txt in the project root for license information.
# --------------------------------------------------------------------------------------------

# This script is intended to be executed from within a tox script. It takes care of of unzipping
# an package sdist and prepping for a sphinx execution.

from m2r import parse_from_file

import glob
import logging
import shutil
import argparse
from pkg_resources import Requirement
import ast
import os
import textwrap
import io
from tox_helper_tasks import (
    get_package_details,
    unzip_sdist_to_directory,
    move_and_rename
)

logging.getLogger().setLevel(logging.INFO)

RST_EXTENSION_FOR_INDEX = """

Indices and tables
------------------

* :ref:`genindex`
* :ref:`modindex`
* :ref:`search`

.. toctree::
  :maxdepth: 5
  :glob:
  :caption: Developer Documentation

  {}
"""

root_dir = os.path.abspath(os.path.join(os.path.abspath(__file__), "..", "..", ".."))
sphinx_conf = os.path.join(root_dir, "doc", "sphinx", "individual_build_conf.py")


def should_build_docs(package_name):
    return not ("nspkg" in package_name or package_name in ["azure", "azure-mgmt", "azure-keyvault", "azure-documentdb", "azure-mgmt-documentdb", "azure-servicemanagement-legacy"])

def create_index_file(readme_location, package_rst):
    readme_ext = os.path.splitext(readme_location)[1]

    if readme_ext == ".md":
        output = parse_from_file(readme_location)
    elif readme_ext == ".rst":
        with open(readme_location, "r") as file:
            output = file.read()
    else:
        logging.error(
            "{} is not a valid readme type. Expecting RST or MD.".format(
                readme_location
            )
        )

    output += RST_EXTENSION_FOR_INDEX.format(package_rst)

    return output


def copy_conf(doc_folder):
    if not os.path.exists(doc_folder):
        os.mkdir(doc_folder)

    shutil.copy(sphinx_conf, os.path.join(doc_folder, 'conf.py'))


def create_index(doc_folder, source_location, namespace):
    index_content = ""

    package_rst = "{}.rst".format(namespace)
    content_destination = os.path.join(doc_folder, "index.rst")

    if not os.path.exists(doc_folder):
        os.mkdir(doc_folder)

    # grep all content
    markdown_readmes = glob.glob(os.path.join(source_location, "README.md"))
    rst_readmes = glob.glob(os.path.join(source_location, "README.rst"))

    # if markdown, take that, otherwise rst
    if markdown_readmes:
        index_content = create_index_file(markdown_readmes[0], package_rst)
    elif rst_readmes:
        index_content = create_index_file(rst_readmes[0], package_rst)
    else:
        logging.warning("No readmes detected for this namespace {}".format(namespace))
        index_content = RST_EXTENSION_FOR_INDEX.format(package_rst)

    # write index
    with open(content_destination, "w+") as f:
        f.write(index_content)


def write_version(site_folder, version):

    if not os.path.isdir(site_folder):
        os.mkdir(site_folder)

    with open(os.path.join(site_folder, "version.txt"), "w") as f:
        f.write(version)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Prep a doc folder for consumption by sphinx."
    )

    parser.add_argument(
        "-d",
        "--dist_dir",
        dest="dist_dir",
        help="The dist location on disk. Usually /tox/dist.",
        required=True,
    )

    parser.add_argument(
        "-t",
        "--target",
        dest="target_package",
        help="The target package directory on disk. The target module passed to pylint will be <target_package>/azure.",
        required=True,
    )

    args = parser.parse_args()

    package_path = os.path.abspath(args.target_package)
    package_name, namespace, package_version, _, _ = get_package_details(
        os.path.join(package_path, "setup.py")
    )

    if should_build_docs(package_name):
        source_location = move_and_rename(unzip_sdist_to_directory(args.dist_dir))
        doc_folder = os.path.join(source_location, "docgen")

        create_index(doc_folder, source_location, namespace)

        site_folder = os.path.join(args.dist_dir, "site")
        write_version(site_folder, package_version)
    else:
        logging.info("Skipping sphinx prep for {}".format(package_name))