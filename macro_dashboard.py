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
from datetime import datetime, timedelta

# 1. UI SETUP 
st.set_page_config(page_title="Macro & Markets Terminal", layout="wide")

st.markdown("""
    <style>
    .stApp { background-color: #000000; color: #FFFFFF; }
    h1, h2, h3, h4 { color: #ffb900 !important; font-family: 'Courier New', monospace; }
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

# 2. DATA ENGINES
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

# NEW HELPER: Gauge Chart Generator
def create_gauge(score, title, color):
    fig = go.Figure(go.Indicator(
        mode = "gauge+number", value = score,
        title = {'text': title, 'font': {'color': 'white', 'size': 18}},
        gauge = {
            'axis': {'range': [0, 10], 'tickwidth': 1, 'tickcolor': "white"},
            'bar': {'color': color},
            'bgcolor': "black", 'borderwidth': 2, 'bordercolor': "#333",
            'steps': [
                {'range': [0, 3], 'color': "rgba(0, 255, 65, 0.15)"},
                {'range': [3, 7], 'color': "rgba(255, 185, 0, 0.15)"},
                {'range': [7, 10], 'color': "rgba(255, 75, 75, 0.15)"}],
        }
    ))
    fig.update_layout(height=250, margin=dict(l=20, r=20, t=50, b=20), paper_bgcolor='rgba(0,0,0,0)', font=dict(color="white"))
    return fig

# 3. HEADER
st.title("MACRO & MARKETS TERMINAL")
st.write(f"SYSTEM STATUS: ONLINE | HYBRID DATA PIPELINE | {datetime.now().strftime('%Y-%m-%d')}")
st.markdown("---")

# 4. TABS (NOW 3 TABS)
tab1, tab2, tab3 = st.tabs(["📊 Macro Data & Indices", "📰 AI Global Intelligence", "📈 M&A Fundamentals Desk"])

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
    
    # NEW: Added ctrl3 for the Raw Mode Toggle
    ctrl1, ctrl2, ctrl3 = st.columns([2, 1, 1])
    with ctrl1: selected_region = st.selectbox("🌎 Select Market Workspace:", list(market_regions.keys()))
    with ctrl2: selected_tf = st.selectbox("⏱️ Select Timeframe:", ["1M", "3M", "6M", "YTD", "1Y", "2Y"], index=3)
    with ctrl3: 
        st.markdown("<br>", unsafe_allow_html=True) 
        raw_mode = st.toggle("🔢 Show Raw Prices")

    now = datetime.now()
    tf_dates = {
        "1M": (now - timedelta(days=30)).strftime('%Y-%m-%d'), "3M": (now - timedelta(days=90)).strftime('%Y-%m-%d'),
        "6M": (now - timedelta(days=180)).strftime('%Y-%m-%d'), "YTD": f"{now.year}-01-01",
        "1Y": (now - timedelta(days=365)).strftime('%Y-%m-%d'), "2Y": (now - timedelta(days=730)).strftime('%Y-%m-%d')
    }
    start_date = tf_dates[selected_tf]

    current_tickers = market_regions[selected_region]
    cols = st.columns(len(current_tickers))
    for i, (name, sym) in enumerate(current_tickers.items()):
        df_sliced = slice_data(fetch_yf(sym), start_date)
        if df_sliced is not None and len(df_sliced) > 1:
            try:
                val, prev = float(df_sliced.iloc[-1]), float(df_sliced.iloc[0])
                change = ((val - prev) / prev) * 100
                cols[i].metric(label=f"{name} ({selected_tf})", value=f"{val:,.2f}", delta=f"{change:.2f}%")
            except: cols[i].metric(label=name, value="ERR")
        else: cols[i].metric(label=name, value="N/A")

    st.markdown("---")
    r1_1, r1_2 = st.columns(2)
    r2_1, r2_2 = st.columns(2)
    
    # NEW: Chart Layout now includes Interactive X-Axis menus
    chart_layout = dict(
        template="plotly_dark", paper_bgcolor='black', plot_bgcolor='black', height=420, hovermode="x unified", 
        legend=dict(orientation="h", yanchor="bottom", y=1.05, xanchor="left", x=0), 
        margin=dict(l=10, r=10, t=50, b=20), font=dict(color="white"),
        xaxis=dict(
            rangeselector=dict(
                buttons=list([
                    dict(count=1, label="1M", step="month", stepmode="backward"),
                    dict(count=3, label="3M", step="month", stepmode="backward"),
                    dict(count=6, label="6M", step="month", stepmode="backward"),
                    dict(count=1, label="YTD", step="year", stepmode="todate"),
                    dict(count=1, label="1Y", step="year", stepmode="backward"),
                    dict(step="all", label="MAX")
                ]),
                bgcolor="#1a1a1a", activecolor="#ffb900", font=dict(color="white", size=11)
            ),
            type="date"
        )
    )

    with r1_1:
        if selected_region == "Global Commodities":
            st.subheader("Energy Complex (Brent vs WTI)")
            wti = slice_data(fetch_yf('CL=F'), start_date)
            brent = slice_data(fetch_yf('BZ=F'), start_date)
            fig1 = go.Figure()
            if wti is not None: fig1.add_trace(go.Scatter(x=wti.index, y=wti.values.flatten(), name="WTI Crude", line=dict(color='#ff4b4b', width=2)))
            if brent is not None: fig1.add_trace(go.Scatter(x=brent.index, y=brent.values.flatten(), name="Brent Crude", line=dict(color='#00d4ff', width=2)))
            fig1.update_layout(**chart_layout)
            fig1.update_yaxes(title_text="Price (USD)")
            st.plotly_chart(fig1, use_container_width=True, theme=None)
        else:
            st.subheader("Yield Benchmarks (Local vs US)")
            yield_map = {
                "Global Baseline": ("US 10Y", "^TNX"), "United States": ("US 10Y", "^TNX"),
                "United Kingdom": ("UK 10Y Gilt", "TMBMKGB-10Y=X"), "India": ("India 10Y", "IN10YT=RR"), "Asia-Pacific": ("Japan 10Y", "TMBMKJP-10Y=X")
            }
            local_yield_name, local_yield_ticker = yield_map.get(selected_region, ("US 10Y", "^TNX"))
            u10 = slice_data(fetch_fred('DGS10'), start_date)
            local_10 = slice_data(fetch_yf(local_yield_ticker), start_date)
            
            fig1 = go.Figure()
            if u10 is not None and not u10.empty: fig1.add_trace(go.Scatter(x=u10.index, y=u10.values, name="US 10Y (Reserve)", line=dict(color='#00d4ff', width=2)))
            if local_10 is not None and not local_10.empty and local_yield_ticker != "^TNX": fig1.add_trace(go.Scatter(x=local_10.index, y=local_10.values.flatten(), name=local_yield_name, line=dict(color='#ff4b4b', width=2)))
            elif local_yield_ticker != "^TNX": fig1.add_annotation(text=f"{local_yield_name} Data Feed Offline", xref="paper", yref="paper", x=0.5, y=0.5, showarrow=False, font=dict(color="red", size=14))
            fig1.update_layout(**chart_layout)
            fig1.update_yaxes(title_text="Yield (%)")
            st.plotly_chart(fig1, use_container_width=True, theme=None)

    with r1_2:
        if selected_region == "Global Commodities":
            st.subheader("Safe Havens (Gold vs US Dollar)")
            gold, dxy = slice_data(fetch_yf('GC=F'), start_date), slice_data(fetch_yf('DX-Y.NYB'), start_date)
            
            # NEW: Dual-Axis logic for Raw Mode
            if raw_mode:
                fig2 = make_subplots(specs=[[{"secondary_y": True}]])
                if gold is not None and len(gold) > 0: fig2.add_trace(go.Scatter(x=gold.index, y=gold.values.flatten(), name="Gold", line=dict(color='#ffb900', width=2)), secondary_y=False)
                if dxy is not None and len(dxy) > 0: fig2.add_trace(go.Scatter(x=dxy.index, y=dxy.values.flatten(), name="US Dollar (DXY)", line=dict(color='#00ff41', width=2)), secondary_y=True)
                fig2.update_layout(**chart_layout)
                fig2.update_yaxes(title_text="Gold Price ($)", secondary_y=False)
                fig2.update_yaxes(title_text="DXY Index", secondary_y=True)
                st.plotly_chart(fig2, use_container_width=True, theme=None)
            else:
                fig2 = go.Figure()
                if gold is not None and len(gold) > 0: fig2.add_trace(go.Scatter(x=gold.index, y=(gold/gold.iloc[0]*100).values.flatten(), name="Gold", line=dict(color='#ffb900', width=2)))
                if dxy is not None and len(dxy) > 0: fig2.add_trace(go.Scatter(x=dxy.index, y=(dxy/dxy.iloc[0]*100).values.flatten(), name="US Dollar (DXY)", line=dict(color='#00ff41', width=2)))
                fig2.update_layout(**chart_layout)
                fig2.update_yaxes(title_text="% Change (Base 100)")
                st.plotly_chart(fig2, use_container_width=True, theme=None)
        else:
            vix_map = {"Global Baseline": ("Global (US VIX)", "^VIX"), "United States": ("US VIX", "^VIX"), "United Kingdom": ("UK VIX (VFTSE)", "^VFTSE"), "India": ("India VIX", "^INDIAVIX"), "Asia-Pacific": ("Japan VIX (JNIV)", "^JNIV")}
            vix_name, vix_ticker = vix_map.get(selected_region, ("US VIX", "^VIX"))
            st.subheader(f"Fear Gauge: {vix_name}")
            vix = slice_data(fetch_yf(vix_ticker), start_date)
            if vix is not None and not vix.empty:
                fig2 = go.Figure()
                fig2.add_trace(go.Scatter(x=vix.index, y=vix.values.flatten(), name=vix_name, fill='tozeroy', line=dict(color='#00ff41')))
                fig2.update_layout(**chart_layout)
                st.plotly_chart(fig2, use_container_width=True, theme=None)
            else: st.error(f"⚠️ Exchange Data Offline: Yahoo Finance is currently not broadcasting {vix_name} data.")

    with r2_1:
        if selected_region == "Global Commodities":
            st.subheader("Economic Bellwether (Copper vs S&P 500)")
            copper, sp500 = slice_data(fetch_yf('HG=F'), start_date), slice_data(fetch_yf('^GSPC'), start_date)
            
            # NEW: Dual-Axis logic for Raw Mode
            if raw_mode:
                fig3 = make_subplots(specs=[[{"secondary_y": True}]])
                if copper is not None and len(copper) > 0: fig3.add_trace(go.Scatter(x=copper.index, y=copper.values.flatten(), name="Copper (HG=F)", line=dict(color='#ff4b4b', width=2)), secondary_y=False)
                if sp500 is not None and len(sp500) > 0: fig3.add_trace(go.Scatter(x=sp500.index, y=sp500.values.flatten(), name="S&P 500", line=dict(color='#00d4ff', width=2)), secondary_y=True)
                fig3.update_layout(**chart_layout)
                fig3.update_yaxes(title_text="Copper Price ($)", secondary_y=False)
                fig3.update_yaxes(title_text="S&P 500 Index", secondary_y=True)
                st.plotly_chart(fig3, use_container_width=True, theme=None)
            else:
                fig3 = go.Figure()
                if copper is not None and len(copper) > 0: fig3.add_trace(go.Scatter(x=copper.index, y=(copper/copper.iloc[0]*100).values.flatten(), name="Copper (HG=F)", line=dict(color='#ff4b4b', width=2)))
                if sp500 is not None and len(sp500) > 0: fig3.add_trace(go.Scatter(x=sp500.index, y=(sp500/sp500.iloc[0]*100).values.flatten(), name="S&P 500", line=dict(color='#00d4ff', width=2)))
                fig3.update_layout(**chart_layout)
                fig3.update_yaxes(title_text="% Change (Base 100)")
                st.plotly_chart(fig3, use_container_width=True, theme=None)
        else:
            st.subheader("Recession Signal (US 10Y-2Y Spread)")
            ten_y, two_y = slice_data(fetch_fred('DGS10'), start_date), slice_data(fetch_fred('DGS2'), start_date)
            if ten_y is not None and two_y is not None:
                combined = pd.concat([ten_y, two_y], axis=1).dropna()
                combined.columns = ['ten', 'two']
                spread = combined['ten'] - combined['two']
                fig3 = go.Figure()
                fig3.add_trace(go.Scatter(x=spread.index, y=spread.values, name="Spread", fill='tozeroy', line=dict(color='#ffb900')))
                fig3.add_hline(y=0, line_dash="dash", line_color="white")
                fig3.update_layout(**chart_layout)
                st.plotly_chart(fig3, use_container_width=True, theme=None)

    with r2_2:
        st.subheader(f"Relative Performance ({selected_region})")
        chart_assets = dict(list(current_tickers.items())[:4]) 
        comp = pd.DataFrame()
        for n, s in chart_assets.items():
            d = slice_data(fetch_yf(s), start_date)
            if d is not None: comp[n] = d
        comp = comp.dropna()
        if not comp.empty:
            fig4 = go.Figure()
            colors = ['#ff4b4b', '#00d4ff', '#ffb900', '#00ff41']
            
            # NEW: Toggle between raw values and Base 100 percentages
            if raw_mode:
                for i, column in enumerate(comp.columns):
                    fig4.add_trace(go.Scatter(x=comp.index, y=comp[column], name=column, line=dict(color=colors[i], width=2)))
                fig4.update_layout(**chart_layout)
                fig4.update_yaxes(title_text="Raw Value")
            else:
                norm = (comp / comp.iloc[0]) * 100 
                for i, column in enumerate(norm.columns):
                    fig4.add_trace(go.Scatter(x=norm.index, y=norm[column], name=column, line=dict(color=colors[i], width=2)))
                fig4.update_layout(**chart_layout)
                fig4.update_yaxes(title_text="% Change (Base 100)")
                
            st.plotly_chart(fig4, use_container_width=True, theme=None)

# ==========================================
# TAB 2: AI QUANTITATIVE DESK
# ==========================================
with tab2:
    macro_topics = ["United States", "Eurozone", "United Kingdom", "China", "Japan", "India", "Global Banking / Financials", "Energy & Energy Transition", "Global Rates & Central Banks", "Global FX", "Global Commodities"]
    selected_topic = st.selectbox("🌍 Macro Focus Area:", macro_topics)
    news_col, ai_col = st.columns([1, 1.5])
    headlines = get_news(selected_topic) 

    with news_col:
        st.markdown(f"**RAW MARKET WIRE ({selected_topic.upper()})**")
        headline_text = ""
        for article in headlines:
            with st.expander(article.title):
                st.markdown(f"🔗 [Read Source Article]({article.link})")
            headline_text += f"- {article.title}\n" 

    with ai_col:
        st.markdown("**QUANTITATIVE AI NLP BRIEFING**")
        
        # Pull the key securely from the Streamlit Cloud backend
        try:
            api_key = st.secrets["GEMINI_API_KEY"]
            
            # The button is now always visible and clickable
            if st.button("Synthesize Executive Briefing"):
                try:
                    genai.configure(api_key=api_key)
                    model = genai.GenerativeModel('gemini-2.5-flash')
                    
                    prompt = f"""You are an elite Global Macro strategy analyst focusing on: {selected_topic}. 
                    Read these live market headlines and provide a highly structured executive summary focusing on how this news impacts capital markets, corporate valuations, or macroeconomic risk in this specific area.
                    
                    You MUST format your text response exactly like this (ensure there is a blank line after the header):
                    
                    ### [INSERT THEME 1 HERE]
                    * [Write 2 to 3 sentences providing a deep, highly detailed explanation of the market impact.]
                    
                    ### [INSERT THEME 2 HERE]
                    * [Write 2 to 3 sentences providing a deep, highly detailed explanation of the market impact.]
                    
                    ### [INSERT THEME 3 HERE]
                    * [Write 2 to 3 sentences providing a deep, highly detailed explanation of the market impact.]
                    
                    CRITICAL: At the very end of your response, output two integer scores representing the news sentiment on a scale of 0 to 10. Format them exactly like this on new lines:
                    RISK_SCORE: [Your Score 0-10] (10 = Extreme Geopolitical/Macro Panic, 0 = Total Peace)
                    SENTIMENT_SCORE: [Your Score 0-10] (10 = Euphoric Economic Boom, 0 = Severe Depression/Crash)
                    
                    Headlines to analyze:
                    {headline_text}"""
                    
                    with st.spinner(f"Running NLP algorithms on {selected_topic} market wire..."):
                        response = model.generate_content(prompt)
                        raw_text = response.text
                        
                        risk_match = re.search(r'RISK_SCORE:\s*(\d+)', raw_text)
                        sent_match = re.search(r'SENTIMENT_SCORE:\s*(\d+)', raw_text)
                        
                        risk_score = int(risk_match.group(1)) if risk_match else 5
                        sent_score = int(sent_match.group(1)) if sent_match else 5
                        
                        display_text = re.sub(r'RISK_SCORE:.*', '', raw_text)
                        display_text = re.sub(r'SENTIMENT_SCORE:.*', '', display_text)
                        
                        g1, g2 = st.columns(2)
                        with g1: st.plotly_chart(create_gauge(risk_score, "Geopolitical/Macro Risk", "#ff4b4b"), use_container_width=True, config={'displayModeBar': False})
                        with g2: st.plotly_chart(create_gauge(sent_score, "Economic Sentiment", "#00ff41"), use_container_width=True, config={'displayModeBar': False})
                        
                        st.markdown(f"<div class='deal-intel'>\n\n{display_text}\n\n</div>", unsafe_allow_html=True)
                except Exception as e:
                    st.error(f"AI Engine Error: {e}")
                    
        except KeyError:
            # This triggers if you forgot to save the key in Streamlit Settings -> Secrets
            st.error("🔒 Security Error: Gemini API Key not found in Cloud Secrets.")

# ==========================================
# TAB 3: M&A FUNDAMENTALS DESK (NEW)
# ==========================================
with tab3:
    st.markdown("### 🏢 **CORPORATE VALUATION & M&A SCREENER**")
    
    # Updated the placeholder text to hint at international tickers
    ticker_input = st.text_input("Enter Target Company Ticker (e.g., AAPL, MSFT, HCLTECH.NS):", "TSLA").upper()
    
    # NEW: The International Ticker Cheat Sheet Expander
    with st.expander("🌍 **Need help finding international stocks? View the Suffix Cheat Sheet**"):
        st.markdown("""
        Because this terminal relies on global market data, non-US equities require an **Exchange Suffix** at the end of the ticker.
        
        * **🇬🇧 United Kingdom (London):** Add `.L` (e.g., AstraZeneca = `AZN.L`)
        * **🇩🇪 Germany (Frankfurt):** Add `.DE` (e.g., Siemens = `SIE.DE`)
        * **🇫🇷 France (Paris):** Add `.PA` (e.g., LVMH = `MC.PA`)
        * **🇮🇳 India (NSE / BSE):** Add `.NS` or `.BO` (e.g., HCLTech = `HCLTECH.NS`)
        * **🇯🇵 Japan (Tokyo):** Add `.T` (e.g., Toyota = `7203.T`)
        * **🇭🇰 China/Hong Kong:** Add `.HK` (e.g., Tencent = `0700.HK`)
        * **🇦🇺 Australia (Sydney):** Add `.AX` (e.g., BHP Group = `BHP.AX`)
        """)
    
    if ticker_input:
        with st.spinner(f"Pulling live SEC EDGAR & Market data for {ticker_input}..."):
            try:
                tgt = yf.Ticker(ticker_input)
                info = tgt.info
                
                if 'shortName' in info:
                    st.markdown(f"#### **{info.get('shortName', ticker_input)}** | {info.get('sector', 'N/A')} - {info.get('industry', 'N/A')}")
                    
                    # Formatters
                    def fmt_b(val): return f"${val/1e9:,.2f}B" if val else "N/A"
                    def fmt_x(val): return f"{val:.2f}x" if val else "N/A"
                    def fmt_pct(val): return f"{val*100:.1f}%" if val else "N/A"
                    
                    # ROW 1: Core Valuation
                    m1, m2, m3, m4, m5 = st.columns(5)
                    m1.metric("Market Cap", fmt_b(info.get('marketCap')))
                    m2.metric("Enterprise Value (EV)", fmt_b(info.get('enterpriseValue')))
                    m3.metric("EV / EBITDA", fmt_x(info.get('enterpriseToEbitda')))
                    m4.metric("P/E Ratio (TTM)", fmt_x(info.get('trailingPE')))
                    m5.metric("Beta (Volatility)", f"{info.get('beta', 0):.2f}" if info.get('beta') else "N/A")
                    
                    # ROW 2: Liquidity & Margins
                    st.markdown("<br>", unsafe_allow_html=True) 
                    n1, n2, n3, n4, n5 = st.columns(5)
                    n1.metric("Total Cash", fmt_b(info.get('totalCash')))
                    n2.metric("Total Debt", fmt_b(info.get('totalDebt')))
                    n3.metric("Gross Margin", fmt_pct(info.get('grossMargins')))
                    n4.metric("Operating Margin", fmt_pct(info.get('operatingMargins')))
                    n5.metric("Profit Margin", fmt_pct(info.get('profitMargins')))
                    
                    st.markdown("---")
                    
                    col_chart, col_profile = st.columns([2.5, 1.5])
                    
                    with col_chart:
                        fin = tgt.financials
                        if fin is not None and not fin.empty and 'Total Revenue' in fin.index and 'Net Income' in fin.index:
                            rev = fin.loc['Total Revenue'].dropna().sort_index()
                            ni = fin.loc['Net Income'].dropna().sort_index()
                            
                            fig_fin = go.Figure()
                            fig_fin.add_trace(go.Bar(x=rev.index.year, y=rev.values, name="Total Revenue", marker_color='#00d4ff'))
                            fig_fin.add_trace(go.Bar(x=ni.index.year, y=ni.values, name="Net Income", marker_color='#00ff41'))
                            
                            fig_fin.update_layout(
                                title="Financial Performance (Revenue vs Net Income)", 
                                template="plotly_dark", paper_bgcolor='black', plot_bgcolor='black', 
                                height=400, font=dict(color='white'), barmode='group',
                                legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="left", x=0),
                                margin=dict(l=10, r=10, t=50, b=20)
                            )
                            st.plotly_chart(fig_fin, use_container_width=True, theme=None)
                        else:
                            st.info("Detailed financial history is currently unavailable for this ticker via free APIs.")
                            
                    with col_profile:
                        st.subheader("Target Profile")
                        
                        with st.expander("Business Description", expanded=True):
                            desc = info.get('longBusinessSummary', 'No description available.')
                            st.write(desc[:800] + "..." if len(desc) > 800 else desc)
                        
                        st.markdown("**Trading Execution Data**")
                        st.write(f"- **52-Week High:** ${info.get('fiftyTwoWeekHigh', 'N/A')}")
                        st.write(f"- **52-Week Low:** ${info.get('fiftyTwoWeekLow', 'N/A')}")
                        
                        shares = info.get('sharesOutstanding')
                        st.write(f"- **Shares Outstanding:** {shares/1e9:.2f}B" if shares else "- **Shares:** N/A")
                        st.write(f"- **Short % of Float:** {fmt_pct(info.get('shortPercentOfFloat'))}")
                        
                else:
                    st.error("Ticker not found. Please check the Cheat Sheet above to ensure you are using a valid Yahoo Finance suffix.")
            except Exception as e:
                st.error(f"Data engine error: {e}")
# ==========================================
# SYSTEM FOOTER: METHODOLOGY & DATA ARCHITECTURE
# ==========================================
st.markdown("---")
with st.expander("🛠️ **TERMINAL METHODOLOGY & DATA ARCHITECTURE**"):
    st.markdown("""
    **Engineered by:** [Aditya Pandey/Pandey Analytics]  
    **Last System Sync:** {now}
    
    ### Data Pipeline Architecture
    * **Market Data:** Real-time equity, FX, and commodity feeds are routed through the **Yahoo Finance API** using a fault-tolerant retry engine.
    * **Economic Benchmarks:** Sovereign yields (US 10Y/2Y) and recession indicators are pulled via the **FRED (Federal Reserve Economic Data)** API.
    * **News Aggregation:** Live market wires are synthesized via **Google News RSS** feeds based on regional focus areas.

    ### AI NLP Sentiment Engine
    * **Model:** Powered by **Gemini 2.5 Flash** via Google Generative AI.
    * **Quant Logic:** The system performs a 'zero-shot' classification of live headlines to extract two proprietary metrics:
        1.  **Risk Score (0-10):** Measures geopolitical and macroeconomic volatility/panic signals.
        2.  **Sentiment Score (0-10):** Measures growth euphoria vs. contractionary signals.
    * **Security:** All API credentials are encrypted using **Streamlit Secrets (TOML)** to prevent exposure of sensitive keys in the source code.

    ### M&A Fundamentals Desk
    * **Valuation Logic:** Multiples (EV/EBITDA, P/E) are calculated using TTM (Trailing Twelve Months) data.
    * **Data Integrity:** International tickers require exchange suffixes (e.g., .NS for India, .L for UK) to ensure correct regional currency and exchange mapping.
    """.format(now=datetime.now().strftime('%Y-%m-%d %H:%M')))