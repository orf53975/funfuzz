# coding=utf-8
#
# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.

"""setuptools install script"""

from setuptools import find_packages
from setuptools import setup

EXTRAS = {
    "test": [
        "codecov==2.0.15",
        "coverage==4.5.2",
        "flake8==3.6.0",
        "flake8-commas==2.0.0",
        "flake8-isort==2.6.0",
        "flake8-quotes==1.0.0",
        "isort==4.3.4",
        "pylint==2.2.2",
        "pytest==4.1.1",
        "pytest-cov==2.6.1",
        "pytest-flake8==1.0.3",
        "pytest-pylint==0.14.0",
    ]}


if __name__ == "__main__":
    setup(name="funfuzz",
          version="0.6.0a1",
          entry_points={
              "console_scripts": ["funfuzz = funfuzz.bot:main"],
          },
          package_data={"funfuzz": [
              "autobisectjs/*",
              "ccoverage/*",
              "js/*",
              "js/jsfunfuzz/*",
              "js/shared/*",
              "util/*",
          ]},
          package_dir={"": "src"},
          packages=find_packages(where="src"),
          install_requires=[
              "boto>=2.49.0",
              "fasteners>=0.14.1,<0.15",
              # https://www.mercurial-scm.org/wiki/SupportedPythonVersions#Python_3.x_support
              # "mercurial>=4.7.2",  # Mercurial does not support Python 3 yet
              "requests>=2.20.1",
          ],
          extras_require=EXTRAS,
          python_requires=">=3.6",
          zip_safe=False)
