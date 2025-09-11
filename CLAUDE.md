# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Architecture Overview

This is an **Effort Analysis System** for ULVAC electric design management that processes monthly effort data and provides analysis capabilities. The system has two main components:

### Core Components

1. **Job Organizer** (`job_organizer.py`, `data_merger.py`) - Merges multiple Excel worksheets from monthly effort data into a unified format and splits job descriptions into categorized fields
2. **Analysis Viewer** (`analysis_viewer.py`) - Provides filtering, aggregation, and visualization of effort data with hierarchical filtering capabilities

### Key Architecture Features

- **Modular Design**: Core processing logic separated from UI (`data_processor.py`, `data_merger.py`)
- **Dual Interface**: Both Streamlit web interface and command-line execution supported
- **Japanese Text Processing**: Advanced text normalization and business content categorization for Japanese companies and terms
- **Complex Data Pipeline**: Excel worksheets → data extraction → text splitting → filtering → aggregation → visualization

### Data Flow

1. Input: Multiple Excel worksheets with effort data (年-月 format sheet names)
2. Processing: Merge worksheets, extract year/month from sheet names, split 業務内容 into 10+ categorized fields
3. Analysis: Apply hierarchical filters, aggregate by combinations, visualize results
4. Output: Processed Excel files and interactive visualizations

## Common Commands

### Running the Application

```bash
# Streamlit web interface (primary usage)
streamlit run app.py

# Individual components
streamlit run job_organizer.py
streamlit run analysis_viewer.py

# Command line usage (job organizer)
python job_organizer.py <existing_merged_file> <new_monthly_file> <output_file>
```

### Dependencies

```bash
# Install required packages
pip install -r requirements.txt
```

Required packages: openpyxl, pandas, scikit-learn, matplotlib, plotly, streamlit

### Testing

No specific test framework is configured. Manual testing through the Streamlit interface is the primary testing approach.

## Data Structure

### Input Excel Format
- Sheet names: "年-月" format (e.g., "2024-01", "2024-02")
- Columns include: 従業員名, 作業時間(h), USER_FIELD_01-05, 第1-3分類, UNIT, MODULE, 業務内容

### Output Format
- Unified Excel with standardized columns
- 業務内容 split into 業務内容1-10+ fields using complex Japanese text processing rules
- Company names (アドテック, オムロン, etc.) and business terms (セミナー, 検図, etc.) are specially handled

## Japanese Text Processing Rules

The system implements complex Japanese text processing for business content categorization:
- Parentheses content extraction and separation
- Company name recognition and splitting
- Business term identification
- Full-width to half-width character normalization
- Underscore and space-based tokenization with special handling for mixed Japanese/English text

## File Organization

- `app.py` - Main application entry point (統合工数分析ビューア)
- `web_interface.py` - Streamlit UI components
- `job_organizer.py` - Monthly data merging and processing
- `analysis_viewer.py` - Data analysis and visualization functions
- `data_merger.py` - Core data merging logic
- `data_processor.py` - Text processing and business content splitting
- `spec-*.txt` - Japanese requirement specifications

## Key Constants

- `COMPANY_NAMES`: List of recognized company names for text splitting
- `BUSINESS_TERMS`: List of business activity terms for categorization
- `BASE_COLUMN_ORDER`: Standard column ordering for analysis filters