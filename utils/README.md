# Utilities

This directory contains utility scripts for testing and setting up the website monitoring application.

## Mock Server

A simple HTTP mock server for testing website monitoring applications.

### Features

- Listens on `http://localhost:8080`
- Responds to any path with a 200 OK status
- Generates a random sequence of 100 lowercase letters for each response
- Simulates varying response times:
    - 90% of requests: 5-500ms response time
    - 10% of requests: 5-30s response time
- Handles hundreds of concurrent requests efficiently

## Requirements

- Python 3.10 or higher
- aiohttp package

## Usage

### Running the Mock Server

To start the mock server, run:

```bash
python utils/mock_server.py
```

The server will start listening on `http://localhost:8080` and will respond to any path.

### Testing the Mock Server

#### Manual Testing

A test script is provided to verify that the mock server is working correctly. The test script sends multiple concurrent
requests to the server and analyzes the response times.

To run the test script:

```bash
python utils/mock_server/test_mock_server.py
```

The test script will:

1. Send 100 requests to the mock server with 20 concurrent requests at a time
2. Measure the response time for each request
3. Analyze the distribution of response times
4. Verify that all responses have the expected content length (100 characters)

## Implementation Details

The mock server is implemented using aiohttp, which provides an asynchronous HTTP server that can handle many concurrent
connections efficiently. The server uses asyncio to simulate varying response times without blocking the server.

Key components:

- `handle_request`: Handles incoming HTTP requests, generates random responses, and simulates processing time
- `init_app`: Initializes the aiohttp application and sets up routes
- `run_server`: Starts the HTTP server

The test script uses aiohttp's client to send concurrent requests to the server and measure response times.

## SQL Generator

A utility script for generating test data for the website monitoring application.

### Features

- Generates a SQL multi-insert query for the monitored_targets table
- Creates 10 rows with random data
- Each row includes:
    - A unique URL pointing to the mock server with a random UUID
    - GET method
    - Random check interval between 5-300 seconds
    - NULL default headers
    - Random 3-character regex pattern with lowercase letters
- Outputs the SQL query to a file named 'insert_query.sql'

### Requirements

- Python 3.10 or higher

### Usage

To generate the SQL insert query, run:

```bash
python utils/generate_insert_query.py
```

The script will create a file named 'insert_query.sql' in the utils directory. You can then use this file to populate
your database:

```bash
psql -U your_username -d your_database_name -f utils/insert_query.sql
```

### Implementation Details

The script uses Python's random module to generate random values for each field according to the specifications. It
creates a multi-insert SQL statement that inserts all rows in a single transaction, which is more efficient than
individual inserts.
