#!/usr/bin/env python

import configparser
import datetime
import json
import logging
import os.path
import re
import sys
from argparse import ArgumentParser, ArgumentTypeError

import dateutil.parser
import dateutil.tz
import requests
from xdg import BaseDirectory

import toggl


APP_SHORTNAME = "toggl-fetch"
CONFIG_FILENAME = "config.ini"
END_DATES_FILENAME = "end_dates.json"


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
            help="First day to include in report, inclusive. Defaults to 4 weeks ago (or the last used --end-date "
                 "for the given workspace plus one day, if that information is available)."
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
    argparser.add_argument(
            "-f",
            "--force",
            action="store_true",
            help="Overwrite the output file if it exists."
    )
    argparser.add_argument(
            "-x",
            "--no-update",
            action="store_true",
            help="Do not update stored end dates."
    )

    return argparser


# XXX: Locking?
def get_last_end_date(workspace_id):
    # See http://stackoverflow.com/q/1450957
    workspace_id = str(workspace_id)

    for dir in BaseDirectory.load_data_paths(APP_SHORTNAME):
        path = os.path.join(dir, END_DATES_FILENAME)

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
        BaseDirectory.save_data_path(APP_SHORTNAME),
        END_DATES_FILENAME
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
    conf_dir = BaseDirectory.load_first_config(APP_SHORTNAME)
    if conf_dir is None:
        return

    path = os.path.join(conf_dir, CONFIG_FILENAME)
    if not os.path.isfile(path):
        return

    config = configparser.ConfigParser(
            allow_no_value=True,
            interpolation=None
    )
    config.read_dict({"options": {}})
    config.read(path)

    defaults = {}
    for key, value in config.items("options"):
        if value is None:
            value = True

        defaults[key] = value

    argparser.set_defaults(**defaults)


def check_argparser_arguments(args):
    if args.api_token is None:
        logging.error("Please specify an API token, either in the configuration file or on the command line.")
        sys.exit(1)

    if args.workspace is None:
        logging.error("Please specify a workspace, either in the configuration file or on the command line.")
        sys.exit(1)


# Set up logging:
logging.basicConfig(level=logging.INFO)

# Now prepare to parse the config file and the command line arguments.
argparser = get_argparser()

try:
    # Read the config file -- this sets defaults for the command line argument parser.
    set_argparser_defaults_from_config(argparser)
except (configparser.Error, OSError) as e:
    logging.error("Could not load configuration file: %s", e)
    sys.exit(9)

# Now parse the command line arguments. These will override defaults set in the config file.
args = argparser.parse_args()

# Certain command line arguments are only required if they are not already specified in the config file.
# Check for those.
check_argparser_arguments(args)

# Set up Toggl.com API wrappers
api = toggl.Toggl(args.api_token)
reports = toggl.TogglReports(args.api_token)

# We need to retrieve the user info from Toggl to determine the correct timezone for the date parameters.
try:
    user_info = api.get_user_info()
except (toggl.APIError, json.JSONDecodeError, requests.RequestException) as e:
    logging.error("Cannot retrieve user information: %s", e)
    sys.exit(3)

# If the user specified a workspace name and not an ID, then try to find a workspace with that name and use its ID.
if not re.fullmatch(r"[0-9]+", args.workspace):
    resolved_workspace = api.get_workspace_by_name_from_user_info(user_info, args.workspace)

    if resolved_workspace is None:
        logging.error("Cannot find a workspace with that name: %s", args.workspace)
        sys.exit(3)

    logging.info("Resolved workspace name `%s' to ID %d.", args.workspace, resolved_workspace["id"])
    args.workspace = resolved_workspace["id"]

# Determine the timezone of the Toggl user
user_timezone = dateutil.tz.gettz(user_info["data"]["timezone"])
if user_timezone is None:
    logging.error("Unknown timezone: %s", user_info["data"]["timezone"])
    sys.exit(3)

logging.info("User timezone: %s", user_timezone)

# If no start date was specified, then either use the last used end date for this workspace or -- if we don't have that
# information -- just use "4 weeks ago" as the start date.
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
        # We know the last used end date; add one day to that date and use the result as the start date.
        args.start_date = args.start_date + datetime.timedelta(1)

logging.info("Start date: %s", args.start_date)
logging.info("End date: %s", args.end_date)

# Where should the downloaded PDF file go?
output_path = args.output.format(
        start_date=args.start_date,
        end_date=args.end_date
)

# Refuse to overwrite the output file if it exists (unless --force is given).
if not args.force and os.path.exists(output_path):
    logging.error("Output file `%s' exists, not overwriting it.", output_path)
    sys.exit(8)

# Download and save the generated PDF file.
try:
    with open(output_path, "wb") as fh:
        fh.write(
                reports.get_summary(
                        workspace_id=args.workspace,
                        since=args.start_date.astimezone(user_timezone).date().isoformat(),
                        until=args.end_date.astimezone(user_timezone).date().isoformat(),
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

logging.info("Output written to file: %s", output_path)

# Finally, save the end date for the specified workspace (unless disabled using the --no-update command line option).
if not args.no_update:
    try:
        set_last_end_date(args.workspace, args.end_date)
    except (OSError, json.JSONDecodeError) as e:
        logging.error("Cannot store end date: %s", e)
        sys.exit(7)
