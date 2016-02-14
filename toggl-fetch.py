#!/usr/bin/env python

import sys
from argparse import ArgumentParser, ArgumentTypeError

import datetime
import dateutil.parser
import dateutil.tz
import pprint

import logging

import re
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

    return date.astimezone(datetime.timezone.utc).date()


def get_argparser():
    argparser = ArgumentParser(description="retrieve Toggl reports")

    argparser.add_argument(
        "-s",
        "--start-date",
        type=parse_date,
        default=datetime.datetime.now(datetime.timezone.utc).date() - datetime.timedelta(weeks=4),
        help="First day to include in report, inclusive. Defaults to 4 weeks ago (or the last time this program was "
             "used plus one day, if possible)."
    )
    argparser.add_argument(
        "-e",
        "--end-date",
        type=parse_date,
        default=datetime.datetime.now(datetime.timezone.utc).date(),
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

    return argparser


logging.basicConfig()
args = get_argparser().parse_args()

api = toggl.Toggl(args.api_token)
reports = toggl.TogglReports(args.api_token)

if not re.fullmatch(r"[0-9]+", args.workspace):
    resolved_workspace = api.get_workspace_by_name(args.workspace)
    if resolved_workspace is None:
        logging.error("Cannot find a workspace with that name: %s", args.workspace)
        sys.exit(2)

    args.workspace = resolved_workspace

with open("summary.pdf", "wb") as fh:
    fh.write(
            reports.get_summary(
                workspace_id=args.workspace,
                since=args.start_date.isoformat(),
                until=args.end_date.isoformat(),
                as_pdf=True
            )
    )
