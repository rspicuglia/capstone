import os
import streamlit as st
import pandas as pd
import numpy as np
import plotly.express as px
import plotly.graph_objects as go
from datetime import datetime

# ==============================================================================
# Page Configuration
# ==============================================================================
st.set_page_config(
    page_title="COVID Across Borders",
    page_icon="🌍",
    layout="wide"
)

# Header & Descriptive Research Question
st.title("COVID Across Borders")
st.markdown(
    "**Central Question:** *How did reported COVID-19 cases and deaths change over time across countries, "
    "and how did first-dose vaccine coverage progress over the same period?*"
)
st.caption("Historical surveillance archive (Jan 2020 – Mar 2023) | Data: Johns Hopkins CSSE & Our World in Data")

with st.expander("ℹ️ How to use this dashboard", expanded=False):
    st.markdown("""
    * **Interactive Legend:** Click any country name in the top legend to temporarily hide or show its curve across both panels; double-click to isolate a single country.
    * **Synchronized Hover:** Move your cursor across the chart to view a single vertical cursor line and synchronized data tooltip displaying outcomes and vaccination progress across all active countries.
    * **Select Countries:** Use the presets or custom multi-select in the sidebar to compare any countries in the JHU archive.
    * **Toggle Outcomes & Scales:** Switch between reported deaths and confirmed cases, daily or cumulative counts, and raw counts vs. crude rates per 100,000 residents.
    * **Customize Milestones:** Use the sidebar milestone selector to track when countries reached specific first-dose coverage thresholds (e.g., 25%, 50%, 75%).
    * **Inspect & Export:** View detailed observations in the data table or export the filtered subset as a CSV file.
    """)

# ==============================================================================
# Constants & Non-Country Filtering
# ==============================================================================
NON_COUNTRIES = [
    "Antarctica",
    "Diamond Princess",
    "MS Zaandam",
    "Summer Olympics 2020",
    "Winter Olympics 2022"
]

JHU_TO_OWID = {
    "US": "United States",
    "Korea, South": "South Korea",
    "Taiwan*": "Taiwan",
    "Burma": "Myanmar",
    "Congo (Kinshasa)": "Democratic Republic of Congo",
    "Congo (Brazzaville)": "Congo",
    "West Bank and Gaza": "Palestine"
}

# Distinct country colors: UK set to Teal (#17becf) so it never collides with Italy (#ff7f0e)
COUNTRY_COLORS = {
    "US": "#1f77b4",             # Blue
    "United Kingdom": "#17becf",    # Teal
    "Italy": "#ff7f0e",          # Orange
    "Chile": "#d62728",          # Red
    "Bolivia": "#2ca02c",        # Green
    "Peru": "#9467bd",           # Purple
    "Uruguay": "#8c564b"         # Brown
}

# Fallback palette excludes colors already reserved for fixed countries
fixed_color_set = set(COUNTRY_COLORS.values())
FALLBACK_PALETTE = [
    c for c in (px.colors.qualitative.Plotly + px.colors.qualitative.Dark24)
    if c not in fixed_color_set
]

PRESETS = {
    "US, Italy, Peru, Chile": ["US", "Italy", "Peru", "Chile"],
    "Bolivia, Chile, Peru": ["Bolivia", "Chile", "Peru"],
    "Chile, Uruguay": ["Chile", "Uruguay"],
    "US, UK": ["US", "United Kingdom"],
    "All six featured": ["Bolivia", "Chile", "Peru", "Uruguay", "United Kingdom", "US"],
    "Custom": []
}

JHU_BASE = "https://raw.githubusercontent.com/CSSEGISandData/COVID-19/master/csse_covid_19_data/"
URL_CONFIRMED = JHU_BASE + "csse_covid_19_time_series/time_series_covid19_confirmed_global.csv"
URL_DEATHS = JHU_BASE + "csse_covid_19_time_series/time_series_covid19_deaths_global.csv"
URL_POP = JHU_BASE + "UID_ISO_FIPS_LookUp_Table.csv"
URL_OWID_VAX = "https://raw.githubusercontent.com/owid/covid-19-data/master/public/data/vaccinations/vaccinations.csv"
LOCAL_VAX_FILE = os.path.join(os.path.dirname(__file__), "data", "vaccinations_snapshot.csv")

# ==============================================================================
# Data Loading & Caching
# ==============================================================================
@st.cache_data(ttl=86400, show_spinner="Loading population lookup...")
def load_population_lookup():
    raw_pop = pd.read_csv(URL_POP)
    pop_map = {}
    for country, grp in raw_pop.groupby("Country_Region"):
        if country in NON_COUNTRIES:
            continue
        # Use mainland national row for UK, France, Netherlands, Denmark
        if country in ["United Kingdom", "France", "Netherlands", "Denmark"] and grp["Province_State"].isna().any():
            p = grp[grp["Province_State"].isna()]["Population"].values[0]
        else:
            nat = grp[grp["Province_State"].isna() & grp["Admin2"].isna()]
            if not nat.empty and not pd.isna(nat["Population"].values[0]):
                p = nat["Population"].values[0]
            else:
                p = grp["Population"].dropna().sum()
        if p and p > 0:
            pop_map[country] = float(p)
    return pop_map

@st.cache_data(ttl=86400, show_spinner="Loading JHU surveillance data...")
def load_jhu_time_series(metric_type: str):
    url = URL_DEATHS if metric_type == "Reported Deaths" else URL_CONFIRMED
    raw = pd.read_csv(url)
    meta = ["Province/State", "Country/Region", "Lat", "Long"]
    date_cols = [c for c in raw.columns if c not in meta]
    
    rows = []
    for country, group in raw.groupby("Country/Region"):
        if country in NON_COUNTRIES:
            continue
        # For UK, France, Netherlands, Denmark: use mainland national row
        if country in ["United Kingdom", "France", "Netherlands", "Denmark"] and group["Province/State"].isna().any():
            nat = group[group["Province/State"].isna()][date_cols].iloc[0]
        else:
            nat = group[date_cols].sum()
        
        row_dict = {"Country": country}
        row_dict.update(nat.to_dict())
        rows.append(row_dict)
        
    agg_df = pd.DataFrame(rows)
    tidy = pd.melt(agg_df, id_vars=["Country"], var_name="Date", value_name="Cumulative")
    tidy["Date"] = pd.to_datetime(tidy["Date"], format="%m/%d/%y")
    tidy.sort_values(["Country", "Date"], inplace=True)
    tidy.reset_index(drop=True, inplace=True)
    
    # Calculate daily new counts across full series before filtering
    tidy["Daily"] = tidy.groupby("Country")["Cumulative"].diff().fillna(0)
    tidy["Daily_7Day_Avg"] = tidy.groupby("Country")["Daily"].transform(
        lambda s: s.rolling(7, min_periods=1).mean()
    )
    return tidy

@st.cache_data(ttl=86400, show_spinner="Loading Our World in Data vaccination dataset...")
def fetch_vaccination_data():
    if os.path.exists(LOCAL_VAX_FILE):
        df = pd.read_csv(LOCAL_VAX_FILE, usecols=["location", "date", "people_vaccinated_per_hundred"])
        df["Date"] = pd.to_datetime(df["date"])
        df.rename(columns={"location": "Country", "people_vaccinated_per_hundred": "pct_first_dose"}, inplace=True)
        return df[["Country", "Date", "pct_first_dose"]].dropna(subset=["pct_first_dose"])
    
    df = pd.read_csv(URL_OWID_VAX, usecols=["location", "date", "people_vaccinated_per_hundred"])
    df["Date"] = pd.to_datetime(df["date"])
    df.rename(columns={"location": "Country", "people_vaccinated_per_hundred": "pct_first_dose"}, inplace=True)
    return df[["Country", "Date", "pct_first_dose"]].dropna(subset=["pct_first_dose"])

def get_vaccination_df():
    try:
        return fetch_vaccination_data()
    except Exception:
        return pd.DataFrame(columns=["Country", "Date", "pct_first_dose"])

pop_dict = load_population_lookup()
vax_df = get_vaccination_df()

# ==============================================================================
# Sidebar Controls (Reordered: Countries first)
# ==============================================================================
st.sidebar.header("Controls & Presets")

# Session state initialization for synchronized preset and multiselect
if "country_multiselect" not in st.session_state:
    st.session_state["country_multiselect"] = ["US", "Italy", "Peru", "Chile"]
if "preset_choice" not in st.session_state:
    st.session_state["preset_choice"] = "US, Italy, Peru, Chile"

def on_preset_change():
    chosen = st.session_state["preset_choice"]
    if chosen in PRESETS and chosen != "Custom":
        st.session_state["country_multiselect"] = PRESETS[chosen]

def on_country_change():
    current_sel = set(st.session_state["country_multiselect"])
    matched = "Custom"
    for name, c_list in PRESETS.items():
        if name != "Custom" and set(c_list) == current_sel:
            matched = name
            break
    st.session_state["preset_choice"] = matched

# 1. Country Selection First
st.sidebar.selectbox(
    "Country Presets",
    options=list(PRESETS.keys()),
    key="preset_choice",
    on_change=on_preset_change
)

# Reference country list from surveillance data
metric_ref = load_jhu_time_series("Reported Deaths")
all_countries = sorted([c for c in metric_ref["Country"].unique() if c not in NON_COUNTRIES])

selected_countries = st.sidebar.multiselect(
    "Select / Add Countries",
    options=all_countries,
    key="country_multiselect",
    on_change=on_country_change
)

if not selected_countries:
    st.warning("Please select at least one country from the sidebar.")
    st.stop()

# 2. Outcome Metric & Scale
st.sidebar.markdown("---")
st.sidebar.subheader("Surveillance Metric")

metric_choice = st.sidebar.radio(
    "Outcome Metric",
    ["Reported Deaths", "Confirmed Cases"],
    index=0
)

df_metric = load_jhu_time_series(metric_choice)

rate_mode = st.sidebar.radio(
    "Measurement Scale",
    ["Rates per 100,000 residents", "Raw Counts"],
    index=0,
    help="Crude rates calculated with fixed 2021 population denominators from JHU."
)
use_rate = (rate_mode == "Rates per 100,000 residents")

count_mode = st.sidebar.radio(
    "Count Display",
    ["Daily New Counts", "Cumulative Counts"],
    index=0
)

apply_smoothing = False
if count_mode == "Daily New Counts":
    apply_smoothing = st.sidebar.checkbox("7-Day Rolling Average", value=True)

# Y-Axis cap option to prevent batch additions from compressing transmission curves
clip_y_axis = False
if count_mode == "Daily New Counts" and use_rate and metric_choice == "Reported Deaths" and apply_smoothing:
    clip_y_axis = st.sidebar.checkbox(
        "Clip Y-Axis to 3.0 deaths/100k",
        value=True,
        help="Prevents single-day batch revision spikes (e.g., Chile March 2022) from flattening regular epidemic curves."
    )

# 3. Vaccination Milestone Controls
st.sidebar.markdown("---")
st.sidebar.subheader("Vaccination")
milestones_input = st.sidebar.multiselect(
    "Coverage Milestones (%)",
    options=[10, 20, 25, 30, 40, 50, 60, 70, 75, 80],
    default=[25, 50, 75],
    help="Select population coverage milestones to track in the summary table and as dotted horizontal reference lines in View B."
)
milestones = sorted(milestones_input) if milestones_input else [25, 50, 75]

# 4. Date Range Filter
st.sidebar.markdown("---")
min_date = df_metric["Date"].min().to_pydatetime()
max_date = df_metric["Date"].max().to_pydatetime()

date_range = st.sidebar.date_input(
    "Date Range",
    value=(min_date, max_date),
    min_value=min_date,
    max_value=max_date
)

if isinstance(date_range, tuple) and len(date_range) == 2:
    start_date, end_date = pd.to_datetime(date_range[0]), pd.to_datetime(date_range[1])
else:
    start_date, end_date = pd.to_datetime(min_date), pd.to_datetime(max_date)

# ==============================================================================
# Data Preparation
# ==============================================================================
filtered_df = df_metric[
    (df_metric["Country"].isin(selected_countries)) &
    (df_metric["Date"] >= start_date) &
    (df_metric["Date"] <= end_date)
].copy()

filtered_df["Population"] = filtered_df["Country"].map(pop_dict)
filtered_df["Cumulative_Rate"] = (filtered_df["Cumulative"] / filtered_df["Population"]) * 100000
filtered_df["Daily_Rate"] = (filtered_df["Daily"] / filtered_df["Population"]) * 100000
filtered_df["Daily_7Day_Avg_Rate"] = (filtered_df["Daily_7Day_Avg"] / filtered_df["Population"]) * 100000

# Choose outcome column and axis labels
if count_mode == "Cumulative Counts":
    y_col = "Cumulative_Rate" if use_rate else "Cumulative"
    y_axis_label = f"Cumulative {metric_choice}" + (" / 100k" if use_rate else "")
else:
    if apply_smoothing:
        y_col = "Daily_7Day_Avg_Rate" if use_rate else "Daily_7Day_Avg"
        y_axis_label = f"{metric_choice} / 100k (7-d avg)" if use_rate else f"{metric_choice} (7-d avg)"
    else:
        y_col = "Daily_Rate" if use_rate else "Daily"
        y_axis_label = f"Daily {metric_choice}" + (" / 100k" if use_rate else "")

# Country Color Mapping (Stable, collision-free)
country_color_map = {
    c: COUNTRY_COLORS.get(c, FALLBACK_PALETTE[i % len(FALLBACK_PALETTE)])
    for i, c in enumerate(selected_countries)
}

# Determine vaccination availability for selected countries
vax_available = False
if not vax_df.empty:
    for country in selected_countries:
        owid_name = JHU_TO_OWID.get(country, country)
        sub_v = vax_df[
            (vax_df["Country"] == owid_name) &
            (vax_df["Date"] >= start_date) &
            (vax_df["Date"] <= end_date)
        ]
        if not sub_v.empty:
            vax_available = True
            break

# ==============================================================================
# Visualization: Stacked Y-Axes on Single Shared X-Axis with Unified Cursor Spike
# ==============================================================================
fig = go.Figure()

# View A Traces (Outcome trends) - assigned to yaxis1
for country in selected_countries:
    c_df = filtered_df[filtered_df["Country"] == country]
    if not c_df.empty:
        fig.add_trace(
            go.Scatter(
                x=c_df["Date"],
                y=c_df[y_col],
                name=country,
                legendgroup=country,
                yaxis="y1",
                mode="lines",
                line=dict(color=country_color_map[country], width=2.5),
                hovertemplate=f"%{{y:,.2f}}" + (" per 100k" if use_rate else "")
            )
        )

# View B Traces (Vaccination coverage) - assigned to yaxis2
if vax_available:
    for country in selected_countries:
        owid_name = JHU_TO_OWID.get(country, country)
        sub_v = vax_df[
            (vax_df["Country"] == owid_name) &
            (vax_df["Date"] >= start_date) &
            (vax_df["Date"] <= end_date)
        ]
        if not sub_v.empty:
            fig.add_trace(
                go.Scatter(
                    x=sub_v["Date"],
                    y=sub_v["pct_first_dose"],
                    name=f"{country} (% vax)",
                    legendgroup=country,
                    yaxis="y2",
                    mode="lines",
                    line=dict(color=country_color_map[country], width=2.5),
                    showlegend=False,
                    hovertemplate="%{y:.1f}%"
                )
            )

# Panel titles as annotations
panel_annotations = [
    dict(
        x=0.0, y=1.01, xref="paper", yref="paper",
        xanchor="left", yanchor="bottom",
        text="<b>View A: COVID-19 Trends</b>",
        showarrow=False,
        font=dict(size=14, color="#1e293b")
    )
]

if vax_available:
    panel_annotations.append(
        dict(
            x=0.0, y=0.40, xref="paper", yref="paper",
            xanchor="left", yanchor="bottom",
            text="<b>View B: Vaccination Coverage</b>",
            showarrow=False,
            font=dict(size=14, color="#1e293b")
        )
    )

# Plain Data Notes for Known Historical Revisions (Daily-smoothed deaths mode only)
if metric_choice == "Reported Deaths" and count_mode == "Daily New Counts" and apply_smoothing:
    # Chile batch addition on March 21, 2022 (+11,447 probable deaths)
    if "Chile" in selected_countries and (start_date <= pd.to_datetime("2022-03-21") <= end_date):
        chile_color = country_color_map.get("Chile", "#d62728")
        y_pos = 3.0 if clip_y_axis else (8.94 if use_rate else 1708.6)
        label_text = "Chile: +11,447 probable deaths<br>batch addition (clipped to 3.0)" if clip_y_axis else "Chile: +11,447 probable deaths<br>batch addition"
        panel_annotations.append(
            dict(
                x="2022-03-21",
                y=y_pos,
                xref="x",
                yref="y1",
                text=label_text,
                showarrow=True,
                arrowhead=2,
                arrowsize=1,
                arrowwidth=1.5,
                arrowcolor=chile_color,
                ax=-70,
                ay=35,
                font=dict(size=10, color=chile_color)
            )
        )
    # Bolivia batch addition on September 7, 2020 (+1,656 deaths)
    if "Bolivia" in selected_countries and (start_date <= pd.to_datetime("2020-09-07") <= end_date):
        bolivia_color = country_color_map.get("Bolivia", "#2ca02c")
        y_pos = 2.48 if use_rate else 289.6
        panel_annotations.append(
            dict(
                x="2020-09-07",
                y=y_pos,
                xref="x",
                yref="y1",
                text="Bolivia: +1,656 deaths<br>batch addition",
                showarrow=True,
                arrowhead=2,
                arrowsize=1,
                arrowwidth=1.5,
                arrowcolor=bolivia_color,
                ax=45,
                ay=-35,
                font=dict(size=10, color=bolivia_color)
            )
        )
    # Bolivia batch addition on March 29, 2022 (+405 deaths)
    if "Bolivia" in selected_countries and (start_date <= pd.to_datetime("2022-03-29") <= end_date):
        bolivia_color = country_color_map.get("Bolivia", "#2ca02c")
        y_pos = 0.50 if use_rate else 58.7
        panel_annotations.append(
            dict(
                x="2022-03-29",
                y=y_pos,
                xref="x",
                yref="y1",
                text="Bolivia: +405 deaths<br>batch addition",
                showarrow=True,
                arrowhead=2,
                arrowsize=1,
                arrowwidth=1.5,
                arrowcolor=bolivia_color,
                ax=-50,
                ay=-30,
                font=dict(size=10, color=bolivia_color)
            )
        )

# Layout configuration
fig.update_layout(
    height=640 if vax_available else 440,
    template="plotly_white",
    hovermode="x unified",
    hoversubplots="axis",
    legend=dict(
        orientation="h",
        yanchor="bottom",
        y=1.07,
        x=0,
        font=dict(size=14),
        traceorder="normal"
    ),
    margin=dict(l=50, r=40, t=95, b=50),
    annotations=panel_annotations,
    xaxis=dict(
        showspikes=True,
        spikemode="across",
        spikesnap="cursor",
        spikethickness=1,
        spikedash="dot",
        spikecolor="#888888",
        title=dict(text="Date")
    ),
    yaxis=dict(
        domain=[0.48, 1.0] if vax_available else [0.0, 1.0],
        title=dict(text=y_axis_label),
        range=[0, 3.2] if clip_y_axis else None
    )
)

if vax_available:
    fig.update_layout(
        yaxis2=dict(
            domain=[0.0, 0.38],
            title=dict(text="% with ≥1 Dose"),
            range=[0, 100]
        )
    )
    # Milestone reference lines in View B
    for m in milestones:
        fig.add_hline(
            y=m,
            yref="y2",
            line_dash="dot",
            line_color="#bbbbbb",
            line_width=1,
            annotation_text=f"{m}%",
            annotation_position="bottom right",
            annotation_font=dict(size=9, color="#666666")
        )

st.plotly_chart(fig, use_container_width=True)

if not vax_available:
    st.info("Note: Vaccination coverage data from Our World in Data is currently unavailable or unmapped for the selected countries.")

# ==============================================================================
# Descriptive Milestone Table (Configurable First-Dose Dates)
# ==============================================================================
st.subheader("First Reported Coverage Milestones")
st.caption(f"Calendar dates when each selected country first reached {', '.join([str(m) + '%' for m in milestones])} population coverage with at least one dose.")

milestone_rows = []
if not vax_df.empty:
    for c in selected_countries:
        owid_name = JHU_TO_OWID.get(c, c)
        sub_vax = vax_df[vax_df["Country"] == owid_name].sort_values("Date")
        row = {"Country": c}
        for m in milestones:
            if not sub_vax.empty:
                reached = sub_vax[sub_vax["pct_first_dose"] >= m]
                row[f"{m}% Coverage"] = reached["Date"].iloc[0].strftime("%b %d, %Y") if not reached.empty else "Not reached"
            else:
                row[f"{m}% Coverage"] = "Data unavailable"
        milestone_rows.append(row)
    
    st.dataframe(pd.DataFrame(milestone_rows), hide_index=True, use_container_width=True)
else:
    st.info("Milestone table unavailable due to vaccination data fetch status.")

# ==============================================================================
# Data Explorer & Export
# ==============================================================================
st.markdown("---")
with st.expander("📋 Data Explorer & Export"):
    st.write("Inspect the processed dataset for the selected countries and date range.")
    
    # Merge vaccination coverage with filtered surveillance dataset
    m_df = filtered_df.copy()
    m_df["OWID_Name"] = m_df["Country"].map(lambda c: JHU_TO_OWID.get(c, c))
    
    if not vax_df.empty:
        v_sub = vax_df[["Country", "Date", "pct_first_dose"]].rename(columns={"Country": "OWID_Name"})
        m_df = pd.merge(m_df, v_sub, on=["OWID_Name", "Date"], how="left")
    else:
        m_df["pct_first_dose"] = np.nan
        
    # Format dates as YYYY-MM-DD
    m_df["Date"] = m_df["Date"].dt.strftime("%Y-%m-%d")
    
    # Round numerical metrics to 2 decimals
    for col in ["Daily_7Day_Avg", "Daily_Rate", "Daily_7Day_Avg_Rate", "Cumulative_Rate", "pct_first_dose"]:
        if col in m_df.columns:
            m_df[col] = m_df[col].round(2)
            
    # Format population with commas
    m_df["Population_Formatted"] = m_df["Population"].apply(lambda p: f"{int(p):,}" if pd.notnull(p) else "")
    
    explorer_cols = [
        "Country", "Date", "Daily", "Daily_7Day_Avg", "Cumulative",
        "Daily_Rate", "Daily_7Day_Avg_Rate", "Cumulative_Rate",
        "pct_first_dose", "Population_Formatted"
    ]
    rename_labels = {
        "Daily_7Day_Avg": "7-Day Avg",
        "Daily_Rate": "Daily per 100k",
        "Daily_7Day_Avg_Rate": "7-Day Avg per 100k",
        "Cumulative_Rate": "Cumulative per 100k",
        "pct_first_dose": "% with ≥1 Dose",
        "Population_Formatted": "Population"
    }
    display_df = m_df[explorer_cols].rename(columns=rename_labels)
    
    st.dataframe(display_df, hide_index=True, use_container_width=True, height=260)
    
    csv = display_df.to_csv(index=False).encode("utf-8")
    st.download_button(
        label="📥 Download Filtered Data as CSV",
        data=csv,
        file_name="covid_across_borders_data.csv",
        mime="text/csv"
    )

# ==============================================================================
# Methods, Data Sources & Limitations
# ==============================================================================
with st.expander("📖 Methods, Data Sources & Limitations", expanded=False):
    st.markdown("""
    ### Data Notes & Methodological Summary
    
    #### 1. Data Sources & Historical Scope
    * **COVID-19 Outcomes:** Sourced from the **Johns Hopkins University Center for Systems Science and Engineering (JHU CSSE)** time-series archive. JHU ceased active global data collection on **March 10, 2023**; this application is designed as a historical surveillance explorer covering January 2020 through March 2023.
    * **Vaccination Coverage:** Sourced from **Our World in Data (OWID)**. The metric displayed is `people_vaccinated_per_hundred` (percentage of total population receiving at least one dose).
    * **Population Denominators:** Extracted from the official JHU `UID_ISO_FIPS_LookUp_Table.csv` (fixed 2021 population estimates).
    
    #### 2. Data Cleaning & Boundary Handling
    * **Differencing Before Filtering:** Daily counts are computed as $\\text{New}_t = \\text{Cumulative}_t - \\text{Cumulative}_{t-1}$. Differencing and 7-day rolling averages are calculated across the entire uninterrupted time series **before** user date filtering to avoid edge-window distortion.
    * **Reporting Revisions Retained:** Retrospective data corrections released by national health ministries (including negative daily adjustments and batch additions) are retained as historical corrections rather than silently zeroed out. Known batch revisions (e.g., Bolivia on September 7, 2020 and March 29, 2022; Chile on March 21, 2022) are annotated directly on the display when those nations are active.
    * **Country Boundaries & Dependencies:** For countries with separately listed overseas dependencies (notably the United Kingdom, France, Netherlands, and Denmark), the mainland national row is used so outcome counts match the national population denominator and vaccination coverage series. Non-country records (cruise ships and Olympic events) are excluded.
    * **Crude Rates:** Rates are calculated as $(\\text{Count} / \\text{Population}) \\times 100{,}000$ using fixed 2021 population denominators. These represent **crude rates** and are not age-standardized.
    
    #### 3. Analytical Limitations
    * Reported case rates reflect testing volume and case detection guidelines rather than total infection rates.
    * Reported COVID-19 deaths reflect official cause-of-death certification rather than excess mortality.
    * Vaccination coverage measures doses received by individuals; it does not distinguish vaccine supply availability, delivery infrastructure, eligibility policies, or vaccine refusal.
    """)
