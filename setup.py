import codecs
import os

from setuptools import setup


MY_DIR = os.path.dirname(os.path.realpath(__file__))


setup(
    name="toggl-fetch",
    use_scm_version={
        "write_to": os.path.join(MY_DIR, "toggl_fetch", "app_version.py")
    },
    description="Fetch summary reports from Toggl.com, with automatic date range calculation.",
    # Read the long description from our README.rst file, as UTF-8.
    long_description=codecs.open(
            os.path.join(MY_DIR, "README.rst"),
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
    packages=["toggl_fetch"],
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
