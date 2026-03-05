import streamlit as st
import yfinance as yf
import pandas as pd
import pandas_datareader as pdr
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import feedparser
import google.generativeai as genai
import urllib.parse 
import re 
import requests
from datetime import datetime, timedelta

# 1. UI SETUP 
st.set_page_config(page_title="Macro & Markets Terminal", layout="wide")

st.markdown("""
    <style>
    .stApp { background-color: #000000; color: #FFFFFF; }
    h1, h2, h3, h4, h5 { color: #ffb900 !important; font-family: 'Courier New', monospace; }
    [data-testid="stMetricLabel"] { font-size: 16px !important; color: #FFFFFF !important; font-weight: 800 !important; text-transform: uppercase; }
    [data-testid="stMetricValue"] { font-size: 32px !important; color: #00ff41 !important; }
    .deal-intel { background-color: #1a1a1a; padding: 20px; border-left: 5px solid #ffb900; font-size: 16px; margin-top: 20px; }
    [data-testid="stExpander"] details { background-color: #0e1117 !important; border: 1px solid #333 !important; border-radius: 5px; }
    [data-testid="stExpander"] summary { background-color: #0e1117 !important; color: #00d4ff !important; }
    [data-testid="stExpander"] summary:hover, [data-testid="stExpander"] summary:focus { background-color: #1a1a1a !important; color: #ffb900 !important; }
    .streamlit-expanderContent { color: #cccccc !important; }
    .stTabs [data-baseweb="tab-list"] { gap: 24px; }
    .stTabs [data-baseweb="tab"] { height: 50px; white-space: pre-wrap; background-color: #0e1117; border-radius: 4px 4px 0px 0px; padding-top: 10px; padding-bottom: 10px; color: #cccccc; font-weight: bold; }
    .stTabs [aria-selected="true"] { background-color: #1a1a1a; color: #ffb900 !important; border-bottom: 2px solid #ffb900; }
    .stButton > button { background-color: #1a1a1a !important; color: #ffb900 !important; border: 1px solid #ffb900 !important; border-radius: 4px; font-family: 'Courier New', monospace; font-weight: bold; width: 100%; }
    .stButton > button:hover { background-color: #ffb900 !important; color: #000000 !important; }
    [data-testid="stToolbar"] { visibility: visible !important; z-index: 9999 !important; }
    header { background-color: transparent !important; }
    </style>
    """, unsafe_allow_html=True)

# Global Table Styling to match terminal aesthetic
TABLE_STYLES = [
    {"selector": "th.col_heading", "props": [("background-color", "#1a1a1a"), ("color", "#ffb900"), ("border", "1px solid #333"), ("text-align", "left")]},
    {"selector": "th.row_heading", "props": [("display", "none")]},
    {"selector": "th.blank.level0", "props": [("display", "none")]},
    {"selector": "td", "props": [("border", "1px solid #333"), ("color", "#ffffff"), ("background-color", "#0e1117")]}
]

# 2. DATA ENGINES
@st.cache_data(ttl=3600)
def fetch_fmp(endpoint, params={}):
    """Primary Database: Financial Modeling Prep (FMP)"""
    try:
        api_key = st.secrets["FMP_API_KEY"]
        base_url = f"https://financialmodelingprep.com/api/v3/{endpoint}"
        params["apikey"] = api_key
        response = requests.get(base_url, params=params)
        return response.json()
    except:
        return None

@st.cache_data(ttl=300)
def fetch_yf(ticker):
    try:
        data = yf.download(ticker, period="2y", interval="1d", progress=False)
        if not data.empty and 'Close' in data:
            if isinstance(data.columns, pd.MultiIndex): return data['Close'][ticker]
            return data['Close']
        return None
    except: return None

@st.cache_data(ttl=3600)
def fetch_fred(series_id):
    try:
        end = datetime.now()
        start = end - timedelta(days=730) 
        data = pdr.get_data_fred(series_id, start, end)
        return data[series_id].dropna()
    except: return None

@st.cache_data(ttl=900) 
def get_news(topic):
    queries = {
        "United States": '"United States" AND (economy OR markets OR "M&A")',
        "Eurozone": '("Eurozone" OR "ECB" OR "European markets") AND (economy OR "M&A")',
        "United Kingdom": '("UK" OR "Bank of England" OR "FTSE") AND (economy OR markets OR "M&A")',
        "China": '("China" OR "PBOC") AND (economy OR markets OR "M&A")',
        "Japan": '("Japan" OR "Bank of Japan" OR "BOJ") AND (economy OR markets OR "M&A")',
        "Global Banking / Financials": '("banking" OR "financial services" OR "global banks") AND (markets OR "M&A")',
        "Energy & Energy Transition": '("energy markets" OR "oil prices" OR "energy transition" OR "renewables")',
        "Global Rates & Central Banks": '("central banks" OR "interest rates" OR "monetary policy" OR "Fed" OR "ECB")',
        "Global FX": '("foreign exchange" OR "FX markets" OR "currency" OR "USD" OR "EUR")',
        "India": '("India" OR "RBI" OR "Indian markets") AND (economy OR "M&A")',
        "Global Commodities": '("crude oil" OR "copper" OR "gold" OR "natural gas" OR "commodities") AND (markets OR economy)'
    }
    search_query = queries.get(topic, "global macro markets")
    encoded_query = urllib.parse.quote(search_query)
    url = f"https://news.google.com/rss/search?q={encoded_query}&hl=en-US&gl=US&ceid=US:en"
    feed = feedparser.parse(url)
    return feed.entries[:6]

def slice_data(df, start_date):
    if df is None or df.empty: return df
    return df.loc[start_date:]

# 3. HEADER
st.title("MACRO & MARKETS TERMINAL")
st.write(f"SYSTEM STATUS: ONLINE | MULTI-DATABASE PIPELINE (YF+FMP) | {datetime.now().strftime('%Y-%m-%d')}")
st.markdown("---")

# 4. TABS
tab1, tab2, tab3, tab4 = st.tabs([
    "Macro Data & Indices", 
    "AI Global Intelligence", 
    "Target Overview & Catalysts", 
    "Valuation & M&A Engine"
])

# ==========================================
# TAB 1: MACRO DATA
# ==========================================
with tab1:
    market_regions = {
        "Global Baseline": {'S&P 500': '^GSPC', 'FTSE 100': '^FTSE', 'NIFTY 50': '^NSEI', 'Nikkei 225': '^N225', 'GBP/USD': 'GBPUSD=X', 'GOLD': 'GC=F'},
        "United States": {'S&P 500': '^GSPC', 'Dow Jones': '^DJI', 'NASDAQ 100': '^NDX', 'Russell 2000': '^RUT', 'DXY (Dollar)': 'DX-Y.NYB', 'VIX': '^VIX'},
        "United Kingdom": {'FTSE 100': '^FTSE', 'FTSE 250': '^FTMC', 'GBP/USD': 'GBPUSD=X', 'EUR/GBP': 'EURGBP=X', 'UK 10Y Gilt': 'TMBMKGB-10Y=X', 'UK VIX': '^VFTSE'},
        "India": {'NIFTY 50': '^NSEI', 'BSE SENSEX': '^BSESN', 'NIFTY BANK': '^NSEBANK', 'NIFTY IT': '^CNXIT', 'USD/INR': 'INR=X', 'India VIX': '^INDIAVIX'},
        "Asia-Pacific": {'Nikkei (JP)': '^N225', 'Hang Seng (HK)': '^HSI', 'Shanghai (CN)': '000001.SS', 'ASX 200 (AU)': '^AXJO', 'USD/JPY': 'JPY=X', 'Japan VIX': '^JNIV'},
        "Global Commodities": {'WTI Crude': 'CL=F', 'Brent Crude': 'BZ=F', 'Copper': 'HG=F', 'Gold': 'GC=F', 'Natural Gas': 'NG=F', 'Silver': 'SI=F'}
    }
    
    ctrl1, ctrl2, ctrl3 = st.columns([2, 1, 1])
    with ctrl1: selected_region = st.selectbox("Select Market Workspace:", list(market_regions.keys()))
    with ctrl2: selected_tf = st.selectbox("Select Timeframe:", ["1M", "3M", "6M", "YTD", "1Y", "2Y"], index=3)
    with ctrl3: 
        st.markdown("<br>", unsafe_allow_html=True) 
        raw_mode = st.toggle("Show Raw Prices")

    now = datetime.now()
    start_date = (now - timedelta(days=730)).strftime('%Y-%m-%d') # Default baseline

    current_tickers = market_regions[selected_region]
    cols = st.columns(len(current_tickers))
    for i, (name, sym) in enumerate(current_tickers.items()):
        df_sliced = slice_data(fetch_yf(sym), start_date)
        if df_sliced is not None and len(df_sliced) > 1:
            try:
                val, prev = float(df_sliced.iloc[-1]), float(df_sliced.iloc[0])
                change = ((val - prev) / prev) * 100
                cols[i].metric(label=name, value=f"{val:,.2f}", delta=f"{change:.2f}%")
            except: cols[i].metric(label=name, value="ERR")
        else: cols[i].metric(label=name, value="N/A")

# ==========================================
# TAB 2: AI GLOBAL INTELLIGENCE
# ==========================================
with tab2:
    macro_topics = ["United States", "Eurozone", "United Kingdom", "China", "Japan", "India", "Global Banking / Financials", "Energy & Energy Transition", "Global Rates & Central Banks", "Global FX", "Global Commodities"]
    selected_topic = st.selectbox("Macro Focus Area:", macro_topics)
    news_col, ai_col = st.columns([1, 1.5])
    headlines = get_news(selected_topic) 

    with news_col:
        st.markdown(f"**RAW MARKET WIRE**")
        headline_text = ""
        for article in headlines:
            with st.expander(article.title):
                st.markdown(f"[Read Source Article]({article.link})")
            headline_text += f"- {article.title}\n" 

    with ai_col:
        st.markdown("**AI NLP BRIEFING**")
        if st.button("Synthesize Executive Briefing"):
            try:
                genai.configure(api_key=st.secrets["GEMINI_API_KEY"])
                model = genai.GenerativeModel('gemini-2.5-flash')
                prompt = f"Elite Global Macro Analyst briefing on {selected_topic}. Summarize headlines focusing on capital markets impact: {headline_text}"
                response = model.generate_content(prompt)
                st.markdown(f"<div class='deal-intel'>\n\n{response.text}\n\n</div>", unsafe_allow_html=True)
            except: st.error("AI engine temporarily offline.")

# ==========================================
# TAB 3: TARGET OVERVIEW & CATALYSTS (REFORMATTED)
# ==========================================
with tab3:
    st.markdown("### TARGET OVERVIEW AND QUALITATIVE CATALYSTS")
    st.markdown("##### Enter Target Company Ticker:")
    ticker_input_cat = st.text_input("Target Catalyst", "DIS", key="ticker_tab3", label_visibility="collapsed").upper()
    
    if ticker_input_cat:
        with st.spinner(f"Querying global registries for {ticker_input_cat}..."):
            try:
                # Resolve company name via FMP for better accuracy
                fmp_profile = fetch_fmp(f"profile/{ticker_input_cat}")
                company_name = fmp_profile[0].get('companyName', ticker_input_cat) if fmp_profile else ticker_input_cat
                
                st.markdown(f"#### {company_name} | Ownership and Activist Intelligence")
                st.markdown("---")
                
                col_ai, col_own = st.columns([1.5, 1])
                
                with col_ai:
                    st.markdown("#### AI Deal Chatter and Catalyst Scanner")
                    query_str = f'"{company_name}" AND (merger OR acquisition OR buyout OR activist OR takeover)'
                    feed = feedparser.parse(f"https://news.google.com/rss/search?q={urllib.parse.quote(query_str)}&hl=en-US&gl=US&ceid=US:en")
                    articles = feed.entries[:6]
                    
                    if st.button("Generate Event-Driven Briefing"):
                        genai.configure(api_key=st.secrets["GEMINI_API_KEY"])
                        model = genai.GenerativeModel('gemini-2.5-flash')
                        brief_prompt = f"Summarize 3 strategic M&A/Activist catalysts for {company_name}: " + "\n".join([a.title for a in articles])
                        res = model.generate_content(brief_prompt)
                        st.markdown(f"<div class='deal-intel'>{res.text}</div>", unsafe_allow_html=True)
                    
                    st.markdown("<br><b>Raw Event-Driven Feed:</b>", unsafe_allow_html=True)
                    for a in articles:
                        with st.expander(a.title):
                            st.markdown(f"[View Source]({a.link})")
                            
                with col_own:
                    st.markdown("#### Ownership and Filings")
                    tab_inst, tab_insider = st.tabs(["Top Institutional Holders", "Recent Insider Trades"])
                    
                    with tab_inst:
                        # FAIL-SAFE: Try FMP first for structured global ownership
                        inst_data = fetch_fmp(f"institutional-holder/{ticker_input_cat}")
                        if inst_data:
                            df_inst = pd.DataFrame(inst_data).head(10)[['holder', 'shares', 'dateReported']]
                            st.table(df_inst.style.format({'shares': '{:,.0f}'}).hide(axis="index").set_table_styles(TABLE_STYLES))
                        else:
                            st.info("Institutional data unavailable for this ticker in current registries.")
                            
                    with tab_insider:
                        ins_data = fetch_fmp(f"insider-trading/{ticker_input_cat}")
                        if ins_data:
                            df_ins = pd.DataFrame(ins_data).head(10)[['reportingName', 'typeOfOwner', 'transactionType', 'securitiesTransacted', 'transactionDate']]
                            st.table(df_ins.style.format({'securitiesTransacted': '{:,.0f}'}).hide(axis="index").set_table_styles(TABLE_STYLES))
                        else:
                            st.info("No recent insider transactions found in local filings.")
            except: st.error("Registry connection error.")

# ==========================================
# TAB 4: VALUATION & M&A ENGINE
# ==========================================
with tab4:
    st.markdown("### CORPORATE VALUATION AND M&A SCREENER")
    st.markdown("##### Enter Target Company Ticker:")
    ticker_input = st.text_input("Target", "DIS", key="ticker_tab4", label_visibility="collapsed").upper()
    
    if ticker_input:
        tgt = yf.Ticker(ticker_input)
        info = tgt.info
        if 'shortName' in info:
            st.markdown(f"#### {info.get('shortName', ticker_input)} | {info.get('sector', 'N/A')}")
            
            # Football Field Logic
            st.markdown("---")
            st.markdown("#### VALUATION SYNTHESIS (FOOTBALL FIELD)")
            
            tgt_currency = info.get('currency', 'USD').upper()
            curr_sym = {'USD': '$', 'INR': '₹', 'GBP': '£', 'EUR': '€'}.get(tgt_currency, '$ ')
            
            fig_ff = go.Figure()
            # Bar logic (Simplified for space)
            fig_ff.add_trace(go.Bar(y=["52-Week Range"], x=[info.get('fiftyTwoWeekHigh',0)-info.get('fiftyTwoWeekLow',0)], 
                                    base=[info.get('fiftyTwoWeekLow',0)], orientation='h', marker_color='#333'))
            
            fig_ff.update_layout(template="plotly_dark", paper_bgcolor='black', plot_bgcolor='black', font=dict(color='white'),
                                xaxis=dict(title=f"Implied Share Price ({tgt_currency})", gridcolor='#333'), height=300)
            st.plotly_chart(fig_ff, use_container_width=True)
            
            # LBO Calculator
            st.markdown("---")
            st.markdown("#### QUICK-AND-DIRTY LBO CALCULATOR")
            ebitda = info.get('ebitda', 0)
            if ebitda > 0:
                l_col, r_col = st.columns(2)
                with l_col:
                    lev = st.slider("Leverage (Debt / EBITDA)", 2.0, 7.0, 4.5)
                    st.write(f"Implied Debt Capacity: {curr_sym}{ebitda*lev/1e9:.2f}B")
                with r_col:
                    st.write("Target Acquisition Mix")
                    fig_lbo = go.Figure(data=[go.Pie(labels=['Debt', 'Equity'], values=[lev, 5], hole=.4, marker_colors=['#ff4b4b', '#00d4ff'])])
                    fig_lbo.update_layout(paper_bgcolor='black', plot_bgcolor='black', height=250, showlegend=False)
                    st.plotly_chart(fig_lbo, use_container_width=True)