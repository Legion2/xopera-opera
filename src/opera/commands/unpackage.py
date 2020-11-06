import argparse
import uuid

from pathlib import Path

from opera.error import DataError, ParseError
from opera.parser.tosca.csar import CloudServiceArchive


def add_parser(subparsers):
    parser = subparsers.add_parser(
        "unpackage",
        help="Unackage TOSCA CSAR to a specified location"
    )
    parser.add_argument(
        "--destination", "-d",
        help="Path to the location where the CSAR file will be extracted to",
    )
    parser.add_argument(
        "--format", "-f", choices=("zip", "tar"),
        default="zip", help="CSAR compressed file format",
    )
    parser.add_argument("csar", help="Path to the TOSCA Cloud service archive")
    parser.set_defaults(func=_parser_callback)


def _parser_callback(args):
    if not Path(args.csar).is_file():
        raise argparse.ArgumentTypeError("CSAR file {} is not a valid path!"
                                         .format(args.csar))

    # if the output is set use it, if not create a random file name with UUID
    if args.destination:
        extracted_folder = args.destination
    else:
        # use uuid4 to create a unique extracted CSAR folder name
        extracted_folder = "opera-unpackage-" + str(uuid.uuid4().hex)

    try:
        unpackage(args.csar, extracted_folder, args.format)
        print("The CSAR was unpackaged to '{}'.".format(extracted_folder))
    except ParseError as e:
        print("{}: {}".format(e.loc, e))
        return 1
    except DataError as e:
        print(str(e))
        return 1

    return 0


def unpackage(csar_input: str, output_dir: str, csar_format: str):
    """
    :raises ParseError:
    :raises DataError:
    """
    csar = CloudServiceArchive(csar_input)
    csar.unpackage_csar(output_dir, csar_format)
