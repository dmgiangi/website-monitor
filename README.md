# Project Title

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

## Table of Contents

- [Introduction](#introduction)
- [Software Architecture](#software-architecture)
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
- [Contact](#contact)

## Introduction

This project is an implementation of a website monitoring service.\
The program is designed to monitor the availability of many websites by performing periodic checks. For each check, it
collects metrics such as the request timestamp, response time, and HTTP status code, and stores these results in a
PostgresSQL database. It also includes an optional feature to validate page contents against a regular expression on a
per-URL basis.

## Software Architecture

The primary design goal for this solution was maintainability, leading to a decoupled, protocol-driven architecture
that is reliable, efficient, and testable.

**Database-Driven Scheduling**: To meet the requirement of not using an external scheduling library, the system
implements a
robust scheduler directly within PostgresSQL. This is achieved using a lease table pattern, where the database itself
manages the state of when each task is due. This approach provides excellent fault tolerance, as the scheduling state is
durable and survives application restarts.

**Efficient Concurrency**: To ensure efficiency and avoid wasteful, constant polling, the worker is event-driven. It
leverages PostgresSQL's LISTEN/NOTIFY for task wakeup. Database-level transactional locks (FOR UPDATE SKIP LOCKED)
manage concurrency and data integrity, ensuring reliable task processing even at scale.

**Decoupled Pipeline**: The application is structured as a pipeline of components, where each major function is governed
by
an abstract interface. This includes:

- _WorkScheduler_ for acquiring tasks
- _TargetFetcher_ for executing HTTP calls,
- _ResultProcessor_ components for handling outcomes (e.g., persisting results, updating metrics).\

This design promotes high testability and makes the system flexible and easy to upgrade.

### Technical Choices & Constraints

This solution adheres to all the **constraints** outlined in the project description:

_Language_: The application is written exclusively in Python.\
_Database_: The system uses PostgresSQL and interacts with it using the asyncpg library for direct, raw SQL queries. No
ORM
libraries were used, as per the requirements.
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

    subgraph "Result Processing Pipeline"
        I_Processor["<< Interface >>\nResultProcessor"]
        DelegatingProcessor[DelegatingProcessor]
        DelegatingProcessor -- implements --> I_Processor
        Processor1[Processor1]
        Processor2[Processor2]
        DelegatingProcessor -- delegates --> Processor1
        DelegatingProcessor -- delegates --> Processor2

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
Python DB API or
similar library and raw SQL queries" instead.
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

The selected model is a database-driven scheduler using a dedicated "lease table" in PostgresSQL. In this pattern, the
application's worker process queries the database for tasks that are due, locks the corresponding rows to prevent race
conditions, and then executes the work.

This represents a deliberate compromise: we are accepting a higher degree of interaction with the database in exchange
for superior fault tolerance and data integrity. By persisting the scheduling state (next_fire_at), the system can
gracefully recover from restarts and guarantee that tasks are not lost or skipped, a key requirement for production
quality code.

The potential inefficiency of database polling is mitigated by using PostgresSQL's LISTEN/NOTIFY system. This allows the
worker to remain idle until work is likely available, thus meeting the efficiency requirement without constant, empty
queries. This choice directly supports the main design goal of maintainability by leveraging the existing, reliable
database infrastructure.

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

2. Install the project dependencies using pip:
   ```bash
   pip install .
   ```

   For development, install with dev dependencies:
   ```bash
   pip install ".[dev]"
   ```

3. Set up the PostgreSQL database:
    - Create a new PostgreSQL database
    - Initialize the database schema using the SQL scripts in the migrations folder:
      ```bash
      psql -U your_username -d your_database_name -f migrations/0001-create-initial-schema.sql
      ```
    - Optionally, populate the database with test data using the generate_insert_query.py script:
      ```bash
      python utils/generate_insert_query.py
      psql -U your_username -d your_database_name -f utils/insert_query.sql
      ```
      This will generate a SQL file with 10 random monitored targets and insert them into the database.

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
python -m src --batch-size 40 --worker-number 100 --queue-size 300 --raise-for-status true --logging-type dev
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

## CONTACT

Name: Gianluigi De Marco\
Email: dem.gianluigi@gmail.com\
GitHub: [link](https://github.com/dmgiangi) \
LinkedIn: [link](https://www.linkedin.com/in/gianluigi-de-marco-890671195/)
