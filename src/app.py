"""Prepare each bank complaint into a working record.

prepare_complaints
  load_complaint_records
    GET /v1/cases
    build_complaint_records
      read the intake
      match the policy version
      missing_information from the three CARD-PROCEDURE-01 lines
      routing request_information when any of those lines is missing
"""

import json
import sys
from pathlib import Path

from src.load_records import load_complaint_records
from src.models import WorkingRecord


def prepare_complaints(base_url: str, data_dir: str | Path) -> list[WorkingRecord]:
    """Load the bank case list and return one working record per complaint.

    Each record includes missing_information. routing is request_information
    when any procedure line was not supplied.
    """
    return load_complaint_records(base_url, data_dir)


def main() -> None:
    """Print the working records for the local mock as a JSON array."""
    base_url = sys.argv[1] if len(sys.argv) > 1 else "http://127.0.0.1:8765"
    data_dir = sys.argv[2] if len(sys.argv) > 2 else "data/dev"
    json.dump(prepare_complaints(base_url, data_dir), sys.stdout, indent=2)
    sys.stdout.write("\n")


if __name__ == "__main__":
    main()
