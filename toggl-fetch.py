#!/usr/bin/env python

import os.path
import datetime
import json
import logging
import pprint
import re
import sys
from argparse import ArgumentParser, ArgumentTypeError

import configparser
from xdg import BaseDirectory

import dateutil.parser
import dateutil.tz
import requests

import toggl


def parse_date(string):
    try:
        date = dateutil.parser.parse(string)
    except (ValueError, OverflowError) as e:
        raise ArgumentTypeError("Invalid date specified: " + str(e)) from e

    # If no time zone was given, assume the current user's timezone.
    if date.tzinfo is None:
        date = date.replace(tzinfo=dateutil.tz.gettz())

    return date


def get_argparser():
    argparser = ArgumentParser(description="retrieve Toggl reports")

    argparser.add_argument(
            "-s",
            "--start-date",
            type=parse_date,
            help="First day to include in report, inclusive. Defaults to 4 weeks ago (or the last time this program "
                 "was used plus one day, if possible)."
    )
    argparser.add_argument(
            "-e",
            "--end-date",
            type=parse_date,
            default=datetime.datetime.now(dateutil.tz.gettz()),
            help="Last day to include in report, inclusive. Defaults to today."
    )
    argparser.add_argument(
            "-t",
            "--api-token",
            help="Your Toggl API token."
    )
    argparser.add_argument(
            "-w",
            "--workspace",
            help="Workspace to retrieve data for. Either a workspace ID or a workspace name."
    )
    argparser.add_argument(
            "-o",
            "--output",
            default="summary_{end_date:%Y}-{end_date:%m}.pdf",
            help="Output file. Can include {start_date} and {end_date} placeholders. Default: `%(default)s'"
    )

    return argparser


# XXX: Locking?
def get_last_end_date(workspace_id):
    # See http://stackoverflow.com/q/1450957
    workspace_id = str(workspace_id)

    for dir in BaseDirectory.load_data_paths("toggl-fetch"):
        path = os.path.join(dir, "end_dates.json")

        if not os.path.isfile(path):
            continue

        with open(path, "r") as fh:
            data = json.load(fh)

        if workspace_id in data:
            return dateutil.parser.parse(data[workspace_id])

        # Else try the next data file.

    # No data files yet.
    return None


# XXX: Locking?
def set_last_end_date(workspace_id, date):
    # See http://stackoverflow.com/q/1450957
    workspace_id = str(workspace_id)

    path = os.path.join(
        BaseDirectory.save_data_path("toggl-fetch"),
        "end_dates.json"
    )

    if os.path.exists(path):
        # Load existing data so that we preserve it.
        with open(path, "r") as fh:
            data = json.load(fh)
    else:
        data = {}

    data[workspace_id] = date.isoformat()

    with open(path, "w") as fh:
        json.dump(data, fh)


def set_argparser_defaults_from_config(argparser):
    conf_dir = BaseDirectory.load_first_config("toggl-fetch")
    if conf_dir is None:
        return

    path = os.path.join(conf_dir, "config.ini")
    if not os.path.isfile(path):
        return

    config = configparser.ConfigParser(interpolation=None)
    config.read_dict({"options": {}})
    config.read(path)

    argparser.set_defaults(**dict(config.items("options")))


def check_argparser_arguments(args):
    if args.api_token is None:
        logging.error("Please specify an API token, either in the configuration file or on the command line.")
        sys.exit(1)

    if args.workspace is None:
        logging.error("Please specify a workspace, either in the configuration file or on the command line.")
        sys.exit(1)


logging.basicConfig(level=logging.INFO)
argparser = get_argparser()

try:
    set_argparser_defaults_from_config(argparser)
except (configparser.Error, OSError) as e:
    logging.error("Could not load configuration file: %s", e)
    sys.exit(9)

args = argparser.parse_args()
check_argparser_arguments(args)

api = toggl.Toggl(args.api_token)
reports = toggl.TogglReports(args.api_token)

if not re.fullmatch(r"[0-9]+", args.workspace):
    try:
        resolved_workspace = api.get_workspace_by_name(args.workspace)
    except (toggl.APIError, json.JSONDecodeError, requests.RequestException) as e:
        logging.error("Cannot retrieve workspaces: %s", e)
        sys.exit(2)

    if resolved_workspace is None:
        logging.error("Cannot find a workspace with that name: %s", args.workspace)
        sys.exit(3)

    logging.info("Resolved workspace name `%s' to ID %d.", args.workspace, resolved_workspace)
    args.workspace = resolved_workspace

if args.start_date is None:
    try:
        args.start_date = get_last_end_date(args.workspace)
    except (OSError, json.JSONDecodeError, ValueError, OverflowError) as e:
        logging.error("XDG data file for end dates is corrupt: %s", e)
        sys.exit(6)

    if args.start_date is None:
        # No last end date stored, use default of "4 weeks ago":
        args.start_date = datetime.datetime.now(dateutil.tz.gettz()) - datetime.timedelta(weeks=4)
    else:
        args.start_date = args.start_date + datetime.timedelta(1)

logging.info("Start date: %s", args.start_date)
logging.info("End date: %s", args.end_date)

output_path = args.output.format(
        start_date=args.start_date,
        end_date=args.end_date
)

if os.path.exists(output_path):
    logging.error("Output file `%s' exists, not overwriting it.", output_path)
    sys.exit(8)

try:
    with open(output_path, "wb") as fh:
        fh.write(
                reports.get_summary(
                        workspace_id=args.workspace,
                        since=args.start_date.astimezone(datetime.timezone.utc).date().isoformat(),
                        until=args.end_date.astimezone(datetime.timezone.utc).date().isoformat(),
                        order_field="title",
                        as_pdf=True
                )
        )
except (toggl.APIError, json.JSONDecodeError, requests.RequestException) as e:
    logging.error("Cannot retrieve summary report: %s", e)
    sys.exit(4)
except IOError as e:
    logging.error("Cannot write to output file `%s': %s", output_path, e)
    sys.exit(5)

try:
    set_last_end_date(args.workspace, args.end_date)
except (OSError, json.JSONDecodeError) as e:
    logging.error("Cannot store end date: %s", e)
    sys.exit(7)
