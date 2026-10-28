# COVID Across Borders: Outcomes and Vaccination Progress
**Data Science for Public Health in Python — Final Capstone Project**  
*Johns Hopkins Bloomberg School of Public Health*  
*Student: Beks Spicuglia*  
*Instructors: Prof. Brian S. Caffo & Dr. Ahmed Hassoon*

---

## 📖 Research Question & Overview
> **Central Question:** *How did reported COVID-19 cases and deaths change over time across countries, and how did first-dose vaccine coverage progress over the same period?*

This application is as an interactive, descriptive historical surveillance explorer (covering January 2020 through March 2023, when JHU concluded global data collection). The dashboard defaults to **US, Italy, Peru, and Chile** and provides synchronized, neutral comparison presets:
1. **US, Italy, Peru, Chile (Default):** Cross-regional comparative baseline.
2. **Bolivia, Chile, Peru:** Regional neighboring countries in South America.
3. **Chile, Uruguay:** Early vaccination leaders in the Southern Hemisphere.
4. **US, UK:** High-income reference benchmarks.
5. **All Six Featured:** Comprehensive comparative view.
6. **Custom:** Automatically activates whenever countries are manually added or removed.

Users can also select and compare any country from the global Johns Hopkins dataset.

---

## 🌟 Application Architecture & Key Features

### 1. Unified Shared-X-Axis Dashboard
- Built on a **single continuous x-axis with two stacked y-axes** (`domain` allocation): **View A** (Reported Deaths or Confirmed Cases per 100,000 residents) on top and **View B** (Vaccination Coverage: % with at least one dose from Our World in Data) below.
- **Continuous Hover Cursor:** A single vertical cursor spike runs continuously through both panels simultaneously (`hovermode="x unified"`, `hoversubplots="axis"`), displaying aligned health outcomes and vaccination metrics in one unified tooltip. Missing vaccination dates are cleanly omitted rather than displayed as zero.
- **Interactive Top Legend:** Placed horizontally at the top (`y=1.07`, font size 14). Clicking any country toggles its line across **both** panels simultaneously (`legendgroup`).

### 2. User Controls & Sidebar Layout
- **Countries First:** Country selection sits at the top of the sidebar.
- **Outcome Metrics:** Toggle between **Reported Deaths** and **Confirmed Cases**.
- **Display Modes:** Toggle between **Daily New Counts** and **Cumulative Counts**.
- **Measurement Scales:** Toggle between **Crude Rates per 100,000 residents** (using JHU fixed 2021 population denominators) and **Raw Counts**.
- **Smoothing:** Toggleable **7-day rolling moving average** to filter out administrative weekend reporting dips.
- **Y-Axis Clipping Option:** When viewing daily smoothed mortality rates, an optional checkbox allows clipping the y-axis to 3.0 deaths per 100k, preventing single-day batch addition outliers from compressing regular transmission waves while labeling clipped data clearly.
- **Vaccination Milestones:** Located under a dedicated "Vaccination" sidebar subheader, users can select coverage milestones (defaulting to **25%**, **50%**, and **75%**). These appear as subtle horizontal dotted reference lines in View B and across columns in the milestone summary table.

### 3. Plain Annotations for Historical Batch Revisions
- **Chile (March 21, 2022):** Annotates the single-day addition of 11,447 historical probable deaths by DEIS (~60 deaths/100k on that day, translating to an 8.9/100k 7-day average peak; only when Chile is selected).
- **Bolivia (Sept 7, 2020 & March 29, 2022):** Annotates the batch additions of 1,656 and 405 deaths (only when Bolivia is selected).
- Annotations appear only in daily-smoothed mode when the revision dates fall within the selected date range.

### 4. Descriptive Coverage Milestones Table
- Reports the exact calendar dates when each selected country first reached user-selected first-dose population coverage milestones (defaulting to **25%**, **50%**, and **75%**).

### 5. Formatted Data Explorer & CSV Export
- Clean inspection table featuring formatted ISO dates (`YYYY-MM-DD`), plain English column labels, rates rounded to 2 decimals, formatted population denominators with commas, and the **percentage with at least one dose** column.
- Clicking **Download Filtered Data as CSV** exports the merged dataset for external analysis.

---

## 🛠️ Data Cleaning Rigor & Methodological Correctness
1. **Differencing Before Filtering:** Daily counts ($\text{New}_t = \text{Cumulative}_t - \text{Cumulative}_{t-1}$) and 7-day rolling averages are calculated across the full uninterrupted time series **before** user date filtering to prevent window-edge distortion.
2. **Reporting Revisions Retained:** Retrospective corrections released by national health ministries (including negative daily adjustments and batch additions) are retained as historical corrections rather than silently zeroed out.
3. **Geographic Boundaries & Non-Country Filtering:** Non-country records (cruise ships and Olympic events) are excluded. For countries with separately listed overseas dependencies (notably the UK, France, Netherlands, and Denmark), the mainland national row is used so that mortality and case counts match national population denominators and vaccination coverage series.
4. **Denominators:** Crude rates per 100,000 residents use fixed 2021 population estimates from JHU CSSE's official lookup table (`UID_ISO_FIPS_LookUp_Table.csv`).
5. **Robust Ingestion:** A bundled snapshot of the OWID vaccination data (`data/vaccinations_snapshot.csv`) keeps that series fixed and reproducible; JHU surveillance data loads from the archived JHU repository with graceful error handling.

---

## 🚀 How to Run Locally

### 1. Prerequisites
Python 3.9+ with dependencies:
```bash
pip install -r requirements.txt
```

### 2. Launch Application
```bash
streamlit run capstone.py
```
The app will open automatically in your browser at `http://localhost:8502`.

---

## 📦 Project Directory Structure
```text
Python Conclusion-Capstone/
├── capstone.py              # Main Streamlit web application
├── capstone.ipynb           # Executed Jupyter notebook walking through data pipeline
├── capstone.docx            # 1-page structured project write-up
├── presentation_script.md   # 5-minute video presentation speaking script & cues
├── README.md                # Project documentation and methodology
├── requirements.txt         # Python dependencies (plotly>=5.21)
└── data/
    └── vaccinations_snapshot.csv  # Bundled OWID vaccination data snapshot
```
