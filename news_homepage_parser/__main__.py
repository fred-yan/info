import argparse
import sys
from .parser import parse
from .pretty_printer import to_json, to_table


def main():
    parser = argparse.ArgumentParser(description="News Homepage Parser")
    parser.add_argument("url", help="News website URL to parse")
    parser.add_argument("--format", choices=["json", "table"], default="json", dest="fmt")
    args = parser.parse_args()

    result = parse(args.url)
    if args.fmt == "table":
        print(to_table(result))
    else:
        print(to_json(result))


if __name__ == "__main__":
    main()
