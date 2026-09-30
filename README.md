# Data Contract Studio

Data Contract Studio is a Streamlit application that profiles CSV datasets,
generates structured data contracts in YAML/JSON, and validates datasets
against those contracts.

## Features

- CSV upload with encoding and delimiter detection
- Automatic column profiling
- Data contract generation in YAML
- Manual contract editing
- Validation report with pass/fail rules
- Export contract and report in YAML, JSON, Markdown, HTML

## Run locally

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
streamlit run app.py