# Mexican Energy Market Analytics - Data Ingestion

S3-based data lake for ingesting daily PML (Precios Marginales Locales) energy spot prices from CENACE API for the Mexican energy market.

## Overview

This project implements Phase 1 of the Mexican Energy Market Analytics platform:
- Fetches last 7 days of PML data for ~100 nodes from CENACE
- Stores data in S3 as Parquet files with date/node partitioning
- Runs daily via AWS Lambda + EventBridge

## Project Structure

```
mexican_energy_analytics/
├── src/
│   ├── ingestion/
│   │   ├── cenace_client.py      # CENACE API calls with retry logic
│   │   ├── data_validator.py     # Data quality validation
│   │   ├── s3_manager.py         # S3 operations (upload/download)
│   │   └── main.py               # Lambda entry point
│   └── utils/
│       └── config.py             # Node list, API URLs, constants
├── tests/
│   └── test_ingestion.py
├── infrastructure/
│   ├── setup.sh                  # AWS CLI deployment script
│   ├── lifecycle-rules.json      # S3 lifecycle configuration
│   └── lambda-role-policy.json    # IAM trust policy for Lambda
├── requirements.txt
└── README.md
```

## Prerequisites

- Python 3.9+
- AWS CLI configured with appropriate credentials
- AWS account with permissions for S3, Lambda, IAM, and EventBridge

## Setup

### 1. Install Python Dependencies

```bash
pip install -r requirements.txt
```

### 2. Deploy AWS Infrastructure

```bash
cd infrastructure
chmod +x setup.sh
./setup.sh
```

This script will:
- Create S3 bucket `mexican-energy-pml-raw`
- Configure lifecycle rules (90-day retention for raw data)
- Create IAM role for Lambda
- Deploy Lambda function
- Set up EventBridge rule for daily 06:00 UTC trigger

### 3. Verify Deployment

```bash
# Check Lambda function exists
aws lambda get-function --function-name cenace-pml-ingestion

# Check EventBridge rule
aws events describe-rule --name cenace-daily-ingestion

# Test Lambda manually
aws lambda invoke --function-name cenace-pml-ingestion --payload '{}' response.json
```

## Local Testing

```bash
# Test the ingestion locally
python -m src.ingestion.main
```

## S3 Data Structure

```
s3://mexican-energy-pml-raw/
└── raw/
    └── pml/
        └── {year}/
            └── {month}/
                └── {day}/
                    └── {nodo}/
                        └── data.parquet
```

Example:
```
s3://mexican-energy-pml-raw/raw/pml/2026/03/28/03CHI-115/data.parquet
```

## Configuration

### Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `S3_BUCKET` | `mexican-energy-pml-raw` | S3 bucket name |
| `LOOKBACK_DAYS` | `7` | Days of historical data to fetch |
| `NODOS` | (all nodes) | Comma-separated node list (optional) |

### Node List

Nodes are defined in `src/utils/config.py` (from `Nodos.md`). Current count: **100 nodes**

## CENACE API

- **Endpoint:** `https://ws01.cenace.gob.mx:8082/SWPML/SIM`
- **Parameters:** Sistema (SIN), Proceso (MDA), Node, Date Range
- **Format:** JSON

## Development

### Run Tests

```bash
pytest tests/ -v
```

### Package Lambda

```bash
cd src
zip -r ../dist.zip ingestion utils *.py
```

## Troubleshooting

### Lambda Execution Errors

Check CloudWatch logs:
```bash
aws logs tail /aws/lambda/cenace-pml-ingestion --follow
```

### API Rate Limiting

If CENACE API rate limits are hit, adjust the delay in `src/ingestion/main.py`:
```python
time.sleep(0.1)  # Increase this value
```

### S3 Upload Failures

Verify IAM role has correct permissions:
```bash
aws iam list-attached-role-policies --role-name cenace-lambda-role
```

## Future Phases

- Phase 3.2: AWS Glue ETL processing
- Phase 4: Redshift data warehouse
- Phase 5: dbt transformations
- Phase 6: ML/RL hedging models

## License

MIT
