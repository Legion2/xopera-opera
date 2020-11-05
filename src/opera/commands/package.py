import argparse
import uuid

from pathlib import Path

from opera.error import DataError, ParseError
from opera.parser.tosca.csar import CloudServiceArchive


def add_parser(subparsers):
    parser = subparsers.add_parser(
        "package",
        help="Package service template and all accompanying files into a CSAR"
    )
    parser.add_argument(
        "--service-template", "-t",
        help="Name or path to the TOSCA service template "
             "file from the root of the input folder",
    )
    parser.add_argument(
        "--output", "-o",
        help="Output CSAR file path",
    )
    parser.add_argument(
        "--format", "-f", choices=("zip", "tar"),
        default="zip", help="CSAR compressed file format",
    )
    parser.add_argument("service_template_folder",
                        help="Path to the root of the service template or "
                             "folder you want to create the TOSCA CSAR from")
    parser.set_defaults(func=_parser_callback)


def _parser_callback(args):
    if not Path(args.service_template_folder).is_dir():
        raise argparse.ArgumentTypeError("Directory {} is not a valid path!"
                                         .format(args.service_template_folder))

    # if the output is set use it, if not create a random file name with UUID
    if args.output:
        # remove the file extension if needed
        csar_output = str(Path(args.output).with_suffix(''))
    else:
        # use uuid4 to create a unique file name
        csar_output = "opera-package-" + str(uuid.uuid4().hex)

    try:
        output_package = package(args.service_template_folder, csar_output,
                                 args.service_template, args.format)
        print("CSAR was created and packed to '{}'.".format(output_package))
    except ParseError as e:
        print("{}: {}".format(e.loc, e))
        return 1
    except DataError as e:
        print(str(e))
        return 1

    return 0


def package(input_dir: str, csar_output: str, service_template: str,
            csar_format: str) -> str:
    """
    :raises ParseError:
    :raises DataError:
    """
    csar = CloudServiceArchive(input_dir)
    return csar.package_csar(csar_output, service_template, csar_format)
