#!/usr/bin/env python3
"""
Script to generate SQL INSERT queries for the monitored_targets table.

This script generates a SQL query that can be used to insert multiple values into the
monitored_targets table in the website_monitor schema. The generated query
follows these specifications:
- id is not provided (it's SERIAL)
- url is http://localhost:8080/{uuid4()}
- method is GET
- default_headers is null
- check_interval is between 5 and 300 seconds
- regex_pattern is a 3-character string with [a-z] characters only

The generated query is written to a file named 'insert_query.sql'.
"""

import random
import string
from pathlib import Path
from uuid import uuid4

# Number of rows to insert
ROWS_TO_INSERT = 2000


def generate_random_regex() -> str:
    """Generate a random 3-character string with [a-z] characters only.

    Returns:
        str: A random 3-character string containing only lowercase letters.
    """
    return "".join(random.choices(string.ascii_lowercase, k=3))


def generate_check_interval() -> str:
    """Generate a random interval between 5 and 300 seconds.

    Returns:
        str: A PostgreSQL interval string in the format "'X seconds'::interval"
             where X is a random integer between 5 and 300.
    """
    seconds = random.randint(5, 300)
    return f"'{seconds} seconds'::interval"


def generate_insert_query() -> str:
    """Generate a multi-insert query for the monitored_targets table.

    This function creates a SQL query that inserts multiple rows into the
    monitored_targets table. Each row contains random values according to
    the specifications in the module docstring.

    Returns:
        str: A SQL query string containing a multi-row INSERT statement for
             the monitored_targets table with randomly generated values.
    """
    values_list = []

    for _ in range(ROWS_TO_INSERT):
        url = f"'http://localhost:8080/{uuid4()}'"
        method = "'GET'"
        check_interval = generate_check_interval()
        default_headers = "NULL"
        regex_pattern = f"'{generate_random_regex()}'" if random.random() < 0.1 else "NULL"

        values = f"({url}, {method}, {check_interval}, {default_headers}, {regex_pattern})"
        values_list.append(values)

    # Join all values with commas
    all_values = ",\n    ".join(values_list)

    query = f"""-- Set the search path to website_monitor
SET search_path TO website_monitor;

-- Insert multiple monitored targets
INSERT INTO monitored_targets (url, method, check_interval, default_headers, regex_pattern)
VALUES
    {all_values};
"""
    return query


def main() -> None:
    """Main function to generate and save the SQL query.

    This function generates a SQL insert query using generate_insert_query()
    and saves it to a file named 'insert_query.sql' in the current directory.
    It also prints a confirmation message to the console.

    Returns:
        None
    """
    query = generate_insert_query()

    # Create the output file
    output_file = Path("insert_query.sql")
    with open(output_file, "w") as f:
        f.write(query)

    print(f"SQL query with {ROWS_TO_INSERT} rows has been generated and saved to {output_file}")


if __name__ == "__main__":
    main()
