toggl-fetch |pypi-badge|
========================

``toggl-fetch`` makes it easy to periodically retrieve summary reports for a `Toggl`_ workspace.

Doing that manually is tedious: Each time you need to generate a new report, you need to remember on what date
the previous report ends -- so that you can let the new report start on the correct date. ``toggl-fetch`` takes
care of remembering that piece of information and downloading the report for you.

.. contents::

Operation overview
------------------

The first time you fetch a report for a workspace using ``toggl-fetch``, you need to tell it on what date the report
should start. If you don't specify a start date, then ``toggl-fetch`` lets the report start four weeks ago.

Optionally, you can specify the date the report should end (herafter simply called the "end date"). If you don't
specify an end date, ``toggl-fetch`` uses today's date.

Being given this information, ``toggl-fetch`` downloads the report as a PDF file and stores it on your computer.
It also remembers the "end date" for the report; it does that separately for each workspace, so you can use it for
multiple workspaces.

Now, the next time you use ``toggl-fetch`` to fetch a report for the workspace, you can omit the start date.
``toggl-fetch`` then adds one day to the saved "end date" (which it stored the last time you fetched a report)
and uses the result as the new start date for the report. It then remembers the "end date" for the current report so
that it can use that information the next time you use ``toggl-fetch``.

.. note::

    Both the "start date" and the "end date" are treated as *inclusive* dates; that is, the generated reports will
    *include* data for the specified dates.

Installation
------------

You can install ``toggl-fetch`` using `pip`_::

    pip install toggl-fetch

A short how-to
--------------

Obtaining a Toggl API token
+++++++++++++++++++++++++++

``toggl-fetch`` needs a Toggl API token in order to log in to your Toggl account. You can obtain the API token
for your account at the end of your `profile page`_.

For the following examples, let's assume that you API token is ``9fc1632af9abac871694d49727685b90``.

Generating the first report
+++++++++++++++++++++++++++

Having obtained an API token, you can now generate your first report. To do that, you need to know the name of the
workspace you want to generate a report for; let's assume it to be "John Doe's workspace". Also, the report should
begin on 2016-01-01 and end on today's date (since the latter is the default, you don't need to specify an
end date).

To download the report as a PDF file into your current working directory, execute the
following command::

    toggl-fetch --api-token 9fc1632af9abac871694d49727685b90 --workspace "John Doe's workspace" --start-date 2016-01-01

That's it. Provided that the API token is valid and a workspace with the specified name exists, you should now
find the report as a PDF file named ``summary_<end_year>-<end_month>.pdf`` in the current working directory
(see `Specifying an output file template`_ to learn how to change that filename).

Generating subsequent reports
+++++++++++++++++++++++++++++

Now that you have generated your first report, generating subsequent reports is as easy as running the following
command::

    toggl-fetch --api-token 9fc1632af9abac871694d49727685b90 --workspace "John Doe's workspace"

Note that we omitted the start date -- this makes ``toggl-fetch`` calculate it from the "end date" it stored when you
generated the last report (which in this case, was the first report ever generated).

This again will download the report to a file named ``summary_<end_year>-<end_month>.pdf`` in your current
working directory (see also `Specifying an output file template`_).

Detailed usage
--------------

To view all the command line arguments accepted by ``toggl-fetch``, simply do::

    toggl-fetch --help

Specifying an output file template
----------------------------------

By default, the report is downloaded into the current working directory as a file named
``summary_<end_year>-<end_month>.pdf``, where ``end_year`` and ``end_month`` are taken from
the end date of the report.

This filename template can be changed using the ``--output`` option. It takes a relative or absolute filename
as an argument; the special placeholders ``{start_date}`` and ``{end_date}`` are replaced to produce the name of
the output file.

The default template is ``summary_{end_date:%Y}-{end_date:%m}.pdf``. Here, ``{end_date}`` is used twice, but
each of the two placeholders contains a different string after the colon: This is a date format specification
specifying how to format the end date. In this case, the placeholder ``{end_date:%Y}`` is replaced by the
year of the end date and the placeholder ``{end_date:%m}`` is replaced by the month of the end date.

The Python documentation contains a `list of valid date format codes`_ which can be used in the date format
specification. For example, the two ``{end_date}``
placeholders above could be replaced with a single placeholder ``{end_date:%Y-%m}`` to produce the same result.

Using a configuration file
--------------------------

Specifying the workspace name, your API token and maybe even an output file template each time you use ``toggl-fetch``
is annoying. You can avoid having to specify options on the command line by placing them in a configuration file
instead.

``toggl-fetch`` follows the `XDG Base Directory Specification`_. In most cases, this means you can place a configuration
file in ``~/.config/toggl-fetch/config.ini`` and ``toggl-fetch`` will find it.

Taking the command line parameters used in `A short how-to`_ as an example, a valid configuration file would look like
this:

.. code:: ini

    [options]
    api_token = 9fc1632af9abac871694d49727685b90
    workspace = John Doe's workspace

Specifying these two options in the configuration file is enough to be able to run ``toggl-fetch`` without having to
specify any command line options.

All command line options can be used in the ``[options]`` section. Command line parameters without a value
(like ``--force``) can be set by simply using the option name without a value, like this:

.. code:: ini

    [options]
    force

.. warning::

    This is only an example. Placing the ``force`` option in the configuration file is *discouraged* for obvious
    reasons.

Lines starting with optional whitespace followed by either ``#`` or ``;`` are treated as comments and are ignored.

.. note::

    Inline comments (comments at the end of non-empty lines) are **not** supported.

Version history
---------------

Version 1.0.1
+++++++++++++

- Fix: Add forgotten short option ``-V`` as a counterpart to ``--version``.
- Fix: Document return codes for the ``main()`` function.
- Fix: ``User-Agent`` header: Add our version number and correctly format our URL.

Version 1.0.0
+++++++++++++

- Initial release.


.. _Toggl: https://toggl.com
.. _pip: https://pypi.python.org/pypi/pip
.. _profile page: https://toggl.com/app/profile
.. _list of valid date format codes: https://docs.python.org/3.5/library/datetime.html#strftime-and-strptime-behavior
.. _XDG Base Directory specification: https://specifications.freedesktop.org/basedir-spec/basedir-spec-0.6.html


..
    NB: Without a trailing question mark in the following image URL, the
    generated HTML will contain an <object> element instead of an <img>
    element, which apparently cannot be made into a link (i. e. a
    "clickable" image).

.. |pypi-badge| image:: https://img.shields.io/pypi/v/toggl-fetch.svg?
    :alt:
    :align: middle
    :target: https://pypi.python.org/pypi/toggl-fetch
