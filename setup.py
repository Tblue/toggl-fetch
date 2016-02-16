import codecs
import os

from setuptools import setup


setup(
    name="toggl-fetch",
    use_scm_version=True,
    description="Fetch summary reports from Toggl.com, with automatic date range calculation.",
    # Read the long description from our README.rst file, as UTF-8.
    long_description=codecs.open(
            os.path.join(
                os.path.dirname(os.path.realpath(__file__)),
                "README.rst"
            ),
            "rb",
            "utf-8"
        ).read(),
    author="Tilman Blumenbach",
    author_email="tilman+pypi@ax86.net",
    entry_points={
        "console_scripts": [
            "toggl-fetch = toggl_fetch.fetch:main"
        ]
    },
    url="https://github.com/Tblue/toggl-fetch",
    py_modules=["toggl_fetch"],
    install_requires=[
        "requests ~= 2.2",
        "python-dateutil ~= 2.0",
        "pyxdg ~= 0.20"
    ],
    setup_requires=["setuptools_scm ~= 1.10"],
    classifiers=[
        "Development Status :: 5 - Production/Stable",
        "Environment :: Console",
        "Intended Audience :: End Users/Desktop",
        "License :: OSI Approved :: GNU General Public License v3 or later (GPLv3+)",
        "Natural Language :: English",
        "Operating System :: OS Independent",
        "Programming Language :: Python :: 3.5",
        "Programming Language :: Python :: 3 :: Only",
        "Topic :: Office/Business",
        "Topic :: Utilities"
    ],
    keywords="toggl report export",
)
