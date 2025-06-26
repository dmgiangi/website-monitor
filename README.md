# Project Title

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

## Table of Contents

- [Introduction](#introduction)
- [Main Feature](#main-feature)
- [Software Architecture](#software-architecture)
- [Documentation Index](#documentation-index)
- [Dependencies Used](#dependencies-used)
- [Compromises Taken](#compromises-taken)
- [Getting Started](#getting-started)
    - [Prerequisites](#prerequisites)
    - [Installation](#installation)
  - [Configuration](#configuration)
- [How to Run and Test](#how-to-run-and-test)
    - [Running the Application](#running-the-application)
    - [Running Tests](#running-tests)
- [Technical Debt](#technical-debt)
- [Reference](#reference)
- [Contact](#contact)

## Documentation Index

- [Dependencies and Choices](DEPENDENCIES.md)
- [Architectural Compromises](COMPROMISES.md)
- [How to Run and Test](RUN.md)

## Introduction

This project is an implementation of a website monitoring service.\
The program is designed to monitor the availability of many websites by performing periodic checks. For each check, it
collects metrics such as the request timestamp, response time, and HTTP status code, the match of a regex in the
response body and stores these results in a PostgresSQL database. It also includes an optional feature to validate page
contents against a regular expression on a per-URL basis.

## Main Feature

This service is engineered to be a reliable, high-performance monitoring solution. Its key features are designed to
ensure scalability, fault tolerance, and maintainability.

- **Comprehensive Health Checks**: Monitors website uptime, latency, HTTP status codes, and optionally validates page
  content with regular expressions.
- **High-Performance Asynchronous Core**: Built entirely on asyncio with non-blocking libraries (aiohttp, asyncpg) to
  handle thousands of concurrent checks efficiently.
- **Fault-Tolerant DB-Driven Scheduling**: Uses PostgreSQL to manage job state, ensuring no checks are lost during an
  application restart.
- **Efficient Low-Polling Operation**: Leverages PostgreSQL's native LISTEN/NOTIFY system to activate workers in
  real-time, eliminating the need for constant, CPU-intensive database polling.
- **Horizontally Scalable**: Designed to scale by allowing multiple worker instances to operate in parallel against the
  same database safely, using FOR UPDATE SKIP LOCKED.
- **Highly Configurable & Tunable**: Performance, including the number of workers, queue size, and batch size, can be
  finely tuned via command-line arguments or environment variables.
- **Graceful Shutdown**: Supports a controlled shutdown process that ensures all in-flight tasks are completed before
  termination, guaranteeing data integrity.

## Software Architecture

The primary design goal for this solution was maintainability, leading to a decoupled, protocol-driven architecture
that is reliable, efficient, and testable.

**Efficient Concurrency with Adaptive Polling**: To ensure efficiency and horizontal scalability, the system relies on
two core PostgreSQL features:

1. **Concurrent Task Acquisition**: Database-level transactional locks (FOR UPDATE SKIP LOCKED) are used to manage
   concurrency. This allows multiple worker instances, even on different machines, to safely select and lease due tasks
   without race conditions or processing the same target twice.
2. **Adaptive Polling Scheduler**: To avoid wasteful, constant database queries, the worker implements a "smart" polling
   mechanism. When no tasks are immediately available, the scheduler queries for the timestamp of the next due task. It
   then calculates the precise duration to sleep, putting the worker into an idle, low-CPU state until work is expected
   to be ready. This approach is highly efficient and minimizes unnecessary load on the database.

**Decoupled Pipeline**: The application is structured as a pipeline of components, where each major function is governed
by an abstract interface. This includes:

- _WorkScheduler_ for acquiring tasks
- _TargetFetcher_ for executing HTTP calls,
- _ResultProcessor_ components for handling outcomes (e.g., persisting results, updating metrics).\

This design promotes high testability and makes the system flexible and easy to upgrade.

### Technical Choices & Constraints

This solution adheres to all the **constraints** outlined in the project description:

_Language_: The application is written exclusively in Python.\
_Database_: The system uses PostgresSQL and interacts with it using the asyncpg library for direct, raw SQL queries. No
ORM libraries were used, as per the requirements.\
_Concurrency & Scheduling_: All concurrency and scheduling are handled natively using Python's built-in asyncio library
in
combination with the database-driven logic described above. No external scheduling libraries were used.
The code is designed to be production quality, with a strong emphasis on clarity, error handling, and testing. For
details on how to set up the database, install dependencies, and run the application and its tests, please see the
sections below.

```mermaid
graph TD
    subgraph "Persistence Layer"
        PostgresSQL[(PostgresSQL)]
    end

    subgraph "Result Processing Pipeline"
        I_Processor["<< Interface >>\nResultProcessor"]
        DelegatingProcessor[DelegatingProcessor]
        DelegatingProcessor -- implements --> I_Processor
        PrometheusProcessor["PrometheusProcessor\nimplements ResultProcessor"]
        MetricsPersistenceProcessor["MetricsPersistenceProcessor\nimplements ResultProcessor"]
        FailurePersistenceProcessor["FailurePersistenceProcessor\nimplements ResultProcessor"]
        DelegatingProcessor -- delegates --> FailurePersistenceProcessor
        DelegatingProcessor -- delegates --> MetricsPersistenceProcessor
        DelegatingProcessor -- delegates --> PrometheusProcessor
        FailurePersistenceProcessor -- updates --> PostgresSQL
        MetricsPersistenceProcessor -- updates --> PostgresSQL
    end

    subgraph "Scheduling Components"
        I_Scheduler["<< Interface >>\nWorkScheduler"]
        PostgresScheduler[PostgresScheduler]
        PostgresScheduler -- implements --> I_Scheduler
        PostgresSQL -- " Reads/Updates Leases " --> PostgresScheduler
    end

    subgraph "Orchestration"
        Orchestrator(MonitoringWorker)
    end

    subgraph "Fetching Components"
        I_Fetcher["<< Interface >>\nTargetFetcher"]
        AiohttpFetcher[AiohttpFetcher]
        AiohttpFetcher -- implements --> I_Fetcher
    end



%% Data Flow
    I_Scheduler -- " Yields List<Target> " --> Orchestrator
    Orchestrator -- " Calls fetch(target) " --> I_Fetcher
    I_Fetcher -- " Returns FetchResult " --> Orchestrator
    Orchestrator -- " Calls process(result) " --> I_Processor
```

## Dependencies Used

### CORE Dependencies

#### asyncpg

**Description**: A high-performance, asynchronous database driver for PostgresSQL.

**Motivation**: A hard constraint of the project is the prohibition of Database ORM libraries, requiring the use of a "
Python DB API or similar library and raw SQL queries" instead.
Asyncpg meets these requirements perfectly. It is a non-ORM driver that allows for writing raw SQL, and its native
integration with asyncio ensures that database operations are non-blocking and do not halt the concurrent execution of
other tasks.

#### aiohttp

**Description**: An asynchronous HTTP client/server library for asyncio.

**Motivation**: As the entire application's concurrency model is built on asyncio, it is essential to use an HTTP client
that is also
asynchronous. Using a standard, blocking library would negate the benefits of asyncio by halting the entire event loop
for every network request.
Aiohttp is a mature and powerful library that provides the necessary functionality for making HTTP requests
asynchronously. It will be used to collect the response time and the HTTP status code for each check.

#### aiologger

**Description**: An asynchronous logging library that allows log without blocking on I/O.

**Motivation**: As the entire application's concurrency model is built on asyncio, it is essential that all I/O
operations, including logging, are non-blocking to achieve production quality. Using Python's standard logging module in
its default, synchronous configuration would introduce blocking file or console I/O. This can halt the event loop for
every log message, severely degrading the performance and responsiveness required to monitor thousands of sites

## Compromises Taken

### Scheduling Model

#### CHOSEN: database-driven scheduler

The selected model is a database-driven scheduler using a dedicated "lease table" in PostgreSQL. This represents a
deliberate compromise: **we are accepting a higher degree of interaction with the database in exchange for superior
fault
tolerance and data integrity**. By persisting the scheduling state (next_fire_at), the system can gracefully recover
from
restarts and guarantee that tasks are not lost or skipped, a key requirement for production-quality code.

The potential inefficiency of a naive polling loop is mitigated by an intelligent adaptive polling strategy. When no
work is available, the scheduler calculates the exact time until the next task is due and puts itself into an
asynchronous sleep for that precise duration. This approach minimizes unnecessary database load and CPU usage while
maintaining timely execution, directly supporting the design goal of maintainability by leveraging the existing,
reliable database infrastructure.

#### Alternative Approaches Considered

Several alternative scheduling models were evaluated and rejected based on the project's specific constraints and goals.

##### In-Memory Scheduler

**Description**: An approach where all scheduling logic resides within the application's memory, using asyncio timers to
trigger tasks.\
**Trade-off**: While this model offers the highest performance and lowest database load, it was rejected because it
fails
the critical requirement for fault tolerance. An application crash would lead to the complete loss of all scheduling
state, making it unsuitable for a production-quality system that must handle errors reliably.

##### State Columns in Main Table

**Description**: A variation of the database-driven approach where scheduling columns (next_fire_at, etc.) are added
directly to the main monitored_targets table instead of a dedicated lease table.\
**Trade-off**: This was considered as it simplifies the database schema. However, it was rejected because it compromises
the
main design goal of maintainability. Mixing operational state with core business data violates the Single Responsibility
Principle and can lead to long-term performance issues (e.g., table bloat, lock contention) on a critical business
table.

##### External Message Queue (e.g., Redis/Celery)

**Description**: Using a dedicated, external system designed for task queuing and scheduling.\
**Trade-off**: Architecturally, this is a very robust and scalable solution. However, it was rejected as it introduces a
significant external dependency and operational overhead. Given the project's scale "... at least some thousands of
separate sites ..." and the explicit constraint against external schedulers, this was deemed unnecessary complexity. The
chosen database-centric model provides sufficient power without the extra infrastructure.

## Getting Started

This section provides instructions on how to set up the project locally.

### Prerequisites

To run this project, you need to have the following installed:

- Python 3.10 or higher
- PostgreSQL 12 or higher
- Git (for cloning the repository)

### Installation

1. Clone the repository:
   ```bash
   git clone https://github.com/dmgiangi/website-monitor.git
   cd website-monitor
   ```

2. Create and activate a virtual environment:
   ```bash
    python3 -m venv venv
    source venv/bin/activate
   ```

3. Install the project dependencies using pip:
   ```bash
   pip install .
   ```

   For development, install with dev dependencies:
   ```bash
   pip install ".[dev]"
   ```

4. Set up the PostgreSQL database:
    - Create a new PostgreSQL database
    - Initialize the database schema using the SQL scripts in the migrations folder:
      ```bash
      psql -U your_username -d your_database_name -f migrations/0001-create-initial-schema.sql
      psql -U your_username -d your_database_name -f migrations/0002-create-monitoring-schema.sql
      ```

### Configuration

The application supports the following configuration options, which can be set via command-line arguments or environment
variables:

| Parameter                  | Command-line Argument           | Environment Variable                  | Default Value                                                                            | Description                                                                              |
|----------------------------|---------------------------------|---------------------------------------|------------------------------------------------------------------------------------------|------------------------------------------------------------------------------------------|
| Database Connection String | `-dsn`                          | `WEBSITE_MONITOR_DSN`                 | `postgresql://postgres:password@localhost/test?options=-c+search_path%3Dwebsite_monitor` | Specifies the connection string for the PostgreSQL database                              |
| Worker ID                  | `-wid`, `--worker-id`           | `WEBSITE_MONITOR_WORKER_ID`           | `website-monitor-{random-uuid}`                                                          | Specifies the worker ID for the monitoring service                                       |
| Worker Number              | `-wn`, `--worker-number`        | `WEBSITE_MONITOR_WORKER_NUMBER`       | `50`                                                                                     | Specifies the maximum number of concurrent monitoring tasks                              |
| DB Pool Size               | `-ps`, `--db-pool-size`         | `WEBSITE_MONITOR_DB_POOL_SIZE`        | `25`                                                                                     | Specifies the maximum number of connections in the database connection pool              |
| Batch Size                 | `-bs`, `--batch-size`           | `WEBSITE_MONITOR_BATCH_SIZE`          | `15`                                                                                     | Specifies the batch size for processing website monitoring tasks                         |
| Queue Size                 | `-qs`, `--queue-size`           | `WEBSITE_MONITOR_QUEUE_SIZE`          | `150`                                                                                    | Specifies the maximum number of items in the processing queue                            |
| Max Timeout                | `-mt`, `--max-timeout`          | `WEBSITE_MONITOR_MAX_TIMEOUT`         | `3`                                                                                      | Specifies the maximum timeout duration in seconds for HTTP requests                      |
| Raise For Status           | `-rfs`, `--raise-for-status`    | `WEBSITE_MONITOR_RAISE_FOR_STATUS`    | `true`                                                                                   | Specifies whether to raise an exception for non-successful HTTP status codes             |
| Enable Tracing             | `-t`, `--enable-tracing`        | `WEBSITE_MONITOR_ENABLE_TRACING`      | `false`                                                                                  | Enables tracing for client sessions                                                      |
| Logging Type               | `-lt`, `--logging-type`         | `WEBSITE_MONITOR_LOGGING_TYPE`        | `prod`                                                                                   | Specifies the logging configuration type to use. Allowed values: `dev`, `prod`, `custom` |
| Logging Config File        | `-lcf`, `--logging-config-file` | `WEBSITE_MONITOR_LOGGING_CONFIG_FILE` | `""` (empty string)                                                                      | Path to custom logging configuration file. Required when logging-type is `custom`        |

Example usage with command-line arguments:

```bash
python -m src -dsn {your_dsn}
```

Example environment variables in `.env` file:

```
WEBSITE_MONITOR_DSN=postgresql://user:password@localhost/mydb?options=-c+search_path%3Dwebsite_monitor
WEBSITE_MONITOR_WORKER_ID=my-worker-1
WEBSITE_MONITOR_WORKER_NUMBER=100
WEBSITE_MONITOR_DB_POOL_SIZE=100
WEBSITE_MONITOR_BATCH_SIZE=40
WEBSITE_MONITOR_QUEUE_SIZE=300
WEBSITE_MONITOR_RAISE_FOR_STATUS=true
WEBSITE_MONITOR_ENABLE_TRACING=true
WEBSITE_MONITOR_LOGGING_TYPE=dev
WEBSITE_MONITOR_LOGGING_CONFIG_FILE=/path/to/custom/logging/config.json
```

## How to Run and Test

This section provides instructions on how to run the application and execute tests.

### Running the Application

To run the website monitoring application:

1. Ensure you have completed the installation and configuration steps in the [Getting Started](#getting-started)
   section.

2. Run the application using the Python module:
   ```bash
   python -m src.website_monitor
   ```

3. Alternatively, you can use environment variables or command-line arguments to customize the configuration:
   ```bash
   python -m src.website_monitor -dsn "your_connection_string"
   ```

   See the [Configuration](#configuration) section for all available options.

4. The application will start monitoring websites according to the targets defined in your database.

### Running Tests

To run the test suite:

1. Ensure you have installed the development dependencies:
   ```bash
   pip install ".[dev]"
   ```

2. Run the tests using pytest:
   ```bash
   pytest
   ```

   For more verbose output:
   ```bash
   pytest -v
   ```

   To run specific test files:
   ```bash
   pytest tests/test_worker.py
   ```

3. The test suite includes unit tests and integration tests that verify the functionality of all components.

### Utility Modules

The project includes utility modules in the `utils/` directory to help with testing and setup:

#### Mock Server

A simple HTTP mock server for testing website monitoring:

- Simulates a website with varying response times (90% fast, 10% slow)
- Responds to any path with a 200 OK status and random content
- Useful for local testing and development

To run the mock server:

```bash
python utils/mock_server.py
```

The server will start listening on `http://localhost:8080`.

##### Testing with the Mock Server

The mock server provides a controlled environment for testing the website monitoring application. Here's how to use it
for testing:

1. **Start the mock server** in a separate terminal window:
   ```bash
   python utils/mock_server.py
   ```

2. **Generate test data** that points to the mock server:
   ```bash
   python utils/generate_insert_query.py
   ```
   This creates `utils/insert_query.sql` with 2000 URLs pointing to the mock server with different paths.

3. **Insert the test data** into your database:
   ```bash
   psql -U your_username -d your_database_name -f utils/insert_query.sql
   ```

4. **Run the website monitoring application** in another terminal:
   ```bash
   python -m src.website_monitor
   ```

5. **Observe the monitoring results**:
    - The application will monitor the URLs pointing to the mock server
    - You'll see a mix of fast responses (5-500ms) and slow responses (5-30s)
    - This allows you to test how the application handles different response times
    - The regex pattern tests will sometimes pass and sometimes fail (random content)

This setup is particularly useful for:

- Testing the application's handling of slow responses
- Verifying timeout functionality
- Testing concurrent request handling
- Ensuring metrics are correctly recorded for various response scenarios
- Testing the application's behavior with a high volume of targets (2000 by default)

You can modify the constants in `utils/mock_server.py` and `utils/generate_insert_query.py` to adjust the behavior for
specific testing scenarios.

#### SQL Generator

A utility script for generating test data:

- Creates SQL insert queries for the monitored_targets table
- Generates random URLs, check intervals, and regex patterns

To generate test data:

```bash
python utils/generate_insert_query.py
```

Then load the generated SQL into your database:

```bash
psql -U your_username -d your_database_name -f utils/insert_query.sql
```

For more details about these utilities, see the [utils/README.md](utils/README.md) file.

## Technical Debt

### ✅ Implemented: Worker Now Supports Graceful Shutdown

**Description**: The MonitoringWorker now includes a robust mechanism for graceful shutdown. This allows the worker to
be stopped in a controlled manner, ensuring all in-flight operations complete before termination.

**Implementation Details**:

- **Awaitable stop() Method**: A public `async def stop()` method has been implemented that coordinates the shutdown
  process.
- **Complete Task Processing**: The shutdown sequence ensures all queued tasks are processed before termination.
- **Resource Cleanup**: All background tasks are properly cancelled and awaited, preventing resource leaks.
- **Orderly Shutdown Flow**:
    1. Scheduler is stopped to prevent new job production
    2. All pending tasks in the queue are allowed to complete
    3. Background worker tasks and monitoring tasks are cancelled
    4. System waits for all tasks to acknowledge cancellation and exit

This implementation ensures data consistency and system stability during shutdown operations, making the application
suitable for production environments.

### Issue: Synchronous Logging in an Asynchronous Application

**Description**: The current implementation uses Python's standard logging module in its default, synchronous
configuration. Log messages
are processed and written to their destination (e.g., console or file) directly from the asyncio event loop.

**Impact**: In an asyncio application, any synchronous I/O operation has the potential to block the event loop. While
often fast,
file or console I/O for logging can introduce small latencies. At the target load of a few hundred operations per
second, these small blocking calls can accumulate, creating a significant performance bottleneck. This would temporarily
halt all concurrent tasks (e.g., HTTP checks, database queries) and undermine the goal of creating a high-performance,
production quality code.

**Proposed Solution**: To resolve this, the logging system should be moved to a non-blocking model. The recommended
approach is to implement a queue-based logger or use an appropriate dependency.

### Issue: Missing open-telemetry instrumentation

**Description**: The application currently lacks comprehensive, standardized observability. There is no integrated
instrumentation to generate traces, metrics, and correlated logs, leaving a significant visibility gap into application
performance and the lifecycle of user requests. The internal behavior of the service is effectively a "black box" in
production.

**Impact**:

- **Reactive vs. Proactive Problem-Solving**
- **Difficult and Slow Root Cause Analysis**
- **Inability to Identify Performance Bottlenecks**
- **Lack of Business-Critical SLOs**

**Proposed Solution**: Add the OTel SDK to the application.

### Issue: missing CI/CD pipeline

**Description**: The current release process is a fragmented collection of manual or semi-automated steps. Key
stages—running tests, applying database schema changes, and deploying the application—are not integrated into a single,
automated workflow. This forces developers to perform these critical tasks in an ad-hoc manner, creating a process that
is slow, unreliable, and prone to human error.

**Impact**:

- **High Deployment Failure Rate & Downtime**
- **No Quality Assurance Gate**
- **Slow Development Velocity**
- **Inconsistent Environments**

**Proposed Solution**: Implement a unified, automated CI/CD pipeline that enforces quality and makes releases a
reliable, repeatable, and low-risk process. This pipeline will consist of distinct, automated stages.

1. Continuous Integration (CI) Stage:

    - _Trigger_: On every git push to a pull request.
    - _Actions_: The pipeline will automatically build the application, run code linting and static analysis, and
      execute the complete unit and integration test suite.
    - _Gate_: Merging is blocked unless all tests and checks pass, ensuring the main branch is always stable.

2. Staging Environment Deployment Stage:

    - _Trigger_: On every successful merge to the main branch.
    - _Actions_: Automated DB Migration: The pipeline connects to the staging database and automatically applies any
      pending schema migrations.
    - _Automated Application Deployment_: If migrations succeed, the new version of the application is deployed to the
      staging environment.
    - _Automated Smoke Tests_: A suite of end-to-end tests runs against the live staging environment to verify the
      deployment's health.

3. Production Environment Deployment Stage:

    - _Trigger_: On manual approval (e.g., a "Promote to Production" button) or automatically if the staging deployment
      is
      successful.
    - _Actions_: The pipeline will execute the exact same, tested sequence used for staging: first, run database
      migrations
      against the production database, and then deploy the application. Reusing the same automated process eliminates
      surprises and drastically increases reliability.

## REFERENCE

This section lists the key resources and tools that were instrumental in the design, development, and documentation of
this project.

### Books and Literature

- Ramalho, Luciano. **Fluent Python**: Clear, Concise, and Effective Programming. 2nd ed., O'Reilly Media, 2022.

This book was the primary reference for designing the application's concurrency model. Its in-depth exploration of
Python's asyncio library directly influenced the implementation of the producer-consumer pattern, the management of
asynchronous tasks, and the overall approach to building a high-throughput, non-blocking service.

### Development and Documentation Tools

- **Google's Gemini 2.5 Pro Large Language Model**

  The Gemini 2.5 Pro model was used extensively as a development assistant and a technical sounding board throughout the
  project lifecycle. Its contributions were focused in the following areas:

    - **Decision Discussion**: Aiding in the articulation and evaluation of architectural trade-offs, as detailed in
      the "Compromises Taken" section.
    - **Documentation Writing**: Accelerating the creation of structured, professional documentation, including the
      generation of this README.md file, docstrings, and technical debt analysis.
      .
- **JetBrains' Junie AI assistant**
    - **Test Writing**: Scaffolding unit tests and providing idiomatic patterns for mocking asynchronous dependencies
      within the pytest and pytest-asyncio frameworks.

## CONTACT

Name: Gianluigi De Marco\
Email: dem.gianluigi@gmail.com\
GitHub: [link](https://github.com/dmgiangi) \
LinkedIn: [link](https://www.linkedin.com/in/gianluigi-de-marco-890671195/)
