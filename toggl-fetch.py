#!/usr/bin/env python

import datetime
import json
import logging
import re
import sys
from argparse import ArgumentParser, ArgumentTypeError

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
            default=datetime.datetime.now(dateutil.tz.gettz()) - datetime.timedelta(weeks=4),
            help="First day to include in report, inclusive. Defaults to 4 weeks ago (or the last time this program "
                 "was "
                 "used plus one day, if possible)."
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
            required=True,
            help="Your Toggl API token."
    )
    argparser.add_argument(
            "-w",
            "--workspace",
            required=True,
            help="Workspace to retrieve data for. Either a workspace ID or a workspace name."
    )
    argparser.add_argument(
            "-o",
            "--output",
            default="summary_{end_date:%Y}-{end_date:%m}.pdf",
            help="Output file. Can include {start_date} and {end_date} placeholders. Default: `%(default)s'"
    )

    return argparser


logging.basicConfig(level=logging.INFO)
args = get_argparser().parse_args()

logging.info("Start date: %s", args.start_date)
logging.info("End date: %s", args.end_date)

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

output_path = args.output.format(
        start_date=args.start_date,
        end_date=args.end_date
)

try:
    with open(output_path, "wb") as fh:
        fh.write(
                reports.get_summary(
                        workspace_id=args.workspace,
                        since=args.start_date.astimezone(datetime.timezone.utc).date().isoformat(),
                        until=args.end_date.astimezone(datetime.timezone.utc).date().isoformat(),
                        as_pdf=True
                )
        )
except (toggl.APIError, json.JSONDecodeError, requests.RequestException) as e:
    logging.error("Cannot retrieve summary report: %s", e)
    sys.exit(4)
except IOError as e:
    logging.error("Cannot write to output file `%s': %s", output_path, e)
    sys.exit(5)
