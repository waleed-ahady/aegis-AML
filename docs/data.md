# Data contract and dataset setup

## Dataset source

AegisAML is compatible with the public IBM synthetic anti-money-laundering transaction data. The publisher describes it as synthetic financial activity generated from a multi-agent virtual world and provides a laundering label for model development. The data is downloaded separately and is not committed here.

Suggested development order:

1. Run the built-in demo generator to verify the platform.
2. Download a small IBM transaction file.
3. Train on a bounded sample while iterating.
4. Move to a larger variant after profiling memory and runtime.

## External IBM-style columns

| External column | Canonical column | Type | Meaning |
|---|---|---|---|
| `Timestamp` | `timestamp` | UTC datetime | Transaction event time |
| `From Bank` | `from_bank` | string | Originating bank identifier |
| `Account` | `from_account` | string | Originating account identifier |
| `To Bank` | `to_bank` | string | Receiving bank identifier |
| `Account.1` | `to_account` | string | Receiving account identifier |
| `Amount Received` | `amount_received` | float | Amount received in receiving currency |
| `Receiving Currency` | `receiving_currency` | string | Receiving currency code |
| `Amount Paid` | `amount_paid` | float | Amount paid in payment currency |
| `Payment Currency` | `payment_currency` | string | Payment currency code |
| `Payment Format` | `payment_format` | string | Transfer mechanism/category |
| `Is Laundering` | `is_laundering` | integer | Synthetic ground-truth label |

## Quality checks

Ingestion records:

- input row count;
- exact duplicates;
- invalid timestamps;
- negative paid or received amounts;
- missing sender or receiver accounts;
- observed positive-label rate.

Rows with invalid required values are removed after the report is calculated. Processed rows are deduplicated and sorted by event time.

## Leakage policy

The laundering label is used only as the training target and in the offline graph investigation report. It is never used to calculate model input features. Historical features are calculated before updating state with the current row.

## Storage policy

Raw and processed data directories are ignored by Git. Do not commit the IBM CSV files. For team use, store datasets in an access-controlled object store and track immutable object versions or checksums in experiment metadata.

## Download

```bash
pip install -e ".[data]"
export KAGGLE_USERNAME=...
export KAGGLE_KEY=...
python scripts/download_ibm_data.py --output data/raw/ibm
```

The downloader delegates to the official Kaggle CLI and prints candidate transaction files after extraction.

## Ingestion

```bash
python scripts/ingest_data.py \
  --input data/raw/ibm/HI-Small_Trans.csv \
  --output data/processed/ibm_hi_small.csv \
  --quality-report reports/ibm_hi_small_quality.json
```

Parquet is supported when the `data` extra is installed and the output suffix is `.parquet`.

## Demo-data warning

`generate_demo_transactions` embeds simple laundering-like cycles, fan-out structuring, and a small amount of label noise. It exists to exercise infrastructure and tests. Its model metrics are expected to be optimistic and must not be presented as benchmark performance.
