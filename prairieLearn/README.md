# Automation of PrairieLearn Assessment Data Integration with Google Sheets

This document outlines the design and operational framework of a Python-based automation system for ingesting granular assessment-level data from PrairieLearn and systematically populating it into structured Google Sheets workbooks. The solution is architected for scalable deployment and is capable of handling complex datasets through batched operations, robust API error handling, and extensible formatting workflows.

## Table of Contents

- System Features
- Required Services and Libraries
- Configuration and Initialization
- Environment Variables
- Software Architecture
- Execution Workflow
- Data Processing Methodology
- Logging, Diagnostics, and Fault Tolerance
- Extensibility and Adaptation
- Operational Guidelines
- Prospective Enhancements

## System Features

- Interfaces with the PrairieLearn REST API to retrieve both high-level and granular gradebook data.
- Transforms question-level assessment data into a multidimensional pivot table suitable for analysis and reporting.
- Enforces columnar ordering based on instructional zone sequencing while abstracting that metadata from the final output.
- Annotates output with metadata rows including maximum achievable scores and integer-based column indices.
- Integrates with Google Sheets API to create or update named subsheets with fully formatted data tables.
- Applies batching and exponential backoff strategies to minimize failure due to quota or rate limitations.
- Compatible with Docker and Google Cloud Run deployment pipelines for scheduled or on-demand execution.

## Required Services and Libraries

### External Services
- Google Sheets API access provisioned via a Google Cloud service account.
- PrairieLearn API access via an instructor-level access token.

### Python Library Dependencies
Install the required libraries via pip:

```bash
pip install pandas requests gspread google-api-python-client python-dotenv backoff
```

## Configuration and Initialization

### Google Cloud Service Account
- Provision a service account with access to the Google Sheets API.
- Export its credentials to a JSON file.
- Grant write access to the relevant spreadsheet by sharing it with the service account email.

### PrairieLearn Token
- Obtain a private access token from the instructor dashboard of the corresponding PrairieLearn course instance.

### Directory Layout
```
project-root/
├── config/
│   └── cs10_sp2025.json         # Course-specific configuration schema
├── prairielearn_to_sheets.py   # Main orchestration script
├── .env                        # Sensitive runtime credentials
└── requirements.txt            # Dependency list
```

## Environment Variables

The following environment variables are required in a `.env` file:

```dotenv
PL_API_TOKEN="<your-prairielearn-api-token>"
SERVICE_ACCOUNT_CREDENTIALS='{"type": "service_account", ...}'
```

The service account credentials should be provided as a fully serialized JSON object.

## Software Architecture

### Initialization and Credential Management
- Environment variables are loaded via `dotenv`.
- Configuration JSON is parsed for course identifiers and spreadsheet parameters.
- A Sheets client is instantiated using `gspread` in conjunction with `googleapiclient.discovery`.

### Google Sheets Interaction Layer
- Checks for the existence of target sheets and programmatically creates them if absent.
- Formats data for the Sheets API `pasteData` operation.
- Consolidates API calls into a batch for performance efficiency.

### PrairieLearn Data Extraction
- Retrieves student and assessment records from `/gradebook`.
- Extracts question-level submission records from `/instance_questions`.
- Applies renaming logic to make assessment identifiers more legible.

### Data Reshaping and Augmentation
- Constructs a pivot table using Pandas, with `UIN` as the index and multi-level columns keyed by `(Assessment, Zone title)`.
- Sorts columns using `Zone number` and subsequently eliminates it from final output.
- Prepends two annotation rows:
  - `Max Points`: contains the maximum score available per column.
  - `Column #`: contains a unique integer index for each column starting from zero.

## Execution Workflow

To invoke the script, run:
```bash
python prairielearn_to_sheets.py
```

The pipeline performs the following operations:
1. Loads API keys and spreadsheet configuration.
2. Pulls comprehensive gradebook and per-question performance data.
3. Constructs a well-structured pivot table.
4. Applies columnar sorting and metadata augmentation.
5. Uploads the final dataset to the corresponding Google Sheets tab.

## Data Processing Methodology

### Step 1: Configuration Parsing
- Extracts spreadsheet ID, course ID, and API scopes from `cs10_sp2025.json`.

### Step 2: Data Acquisition
- Collects the roster and assessment definitions via `/gradebook`.
- Iterates over submissions and parses them via `/instance_questions`.

### Step 3: Data Structuring
- Normalizes raw data into tabular format using Pandas.
- Pivots data with respect to each assessment and associated instructional zone.
- Applies an intermediate sort using `Zone number` and omits it from the final output.
- Augments the dataset with a header row of column indices and a row of maximum point values.

### Step 4: Sheet Synchronization
- Translates the DataFrame into a CSV string suitable for `pasteData` ingestion.
- Ensures the target sheet tab exists or creates it.
- Queues API calls and commits them in a batch.

## Logging, Diagnostics, and Fault Tolerance

- Logs are emitted to standard output in a structured format.
- API interactions are monitored, and failures (e.g., 429 or 502) trigger exponential backoff.
- Detailed retry and error messages facilitate rapid diagnostics and remediation.
- Script resilience ensures data propagation continuity across runs.

## Extensibility and Adaptation

### Customizing Course or Sheet Parameters
Modify `config/cs10_sp2025.json` to reflect different course contexts:

```json
{
  "PL_COURSE_ID": 12345,
  "SCOPES": ["https://www.googleapis.com/auth/spreadsheets"],
  "SPREADSHEET_ID": "your-google-sheet-id"
}
```

### Renaming Target Sheets
Adjust the relevant line in the script:

```python
push_pl_csv_to_sheet(df_to_csv(df), "PrairieLearn Gradebook")
```

## Operational Guidelines

- Keep third-party packages in `requirements.txt` current.
- Rotate service account credentials on a scheduled basis.
- Validate schema compatibility if PrairieLearn modifies its API.
- Periodically archive the resulting Google Sheets for compliance.

## Prospective Enhancements

- Introduce CLI arguments for dynamic sheet name selection.
- Partition output into individual tabs per assessment.
- Integrate feedback annotations or status indicators.
- Extend output formats to include Excel and PDF.
- Add richer analytics and summarization utilities.

## Representative Output Schema

| Column #   | 0   | 1   | 2   |
|------------|-----|-----|-----|
| Max Points | 10  | 5   | 15  |
| 12345678   | 9   | 4   | 14  |
| 87654321   | 10  | 5   | 15  |

This schema demonstrates the final tabular output transmitted to Google Sheets, featuring annotated metadata and columnar ordering derived from instructional zone sequencing.

