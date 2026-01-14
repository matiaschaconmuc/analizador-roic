import yfinance as yf
import pandas as pd
import numpy as np
import plotly.express as px
import streamlit as st

st.set_page_config(page_title="Calculador ROIC", layout="wide")

@st.cache_data
def calculate_roic_for_ticker(ticker_symbol, num_years=5):
    roic_values_by_year = {} 
    try:
        ticker = yf.Ticker(ticker_symbol)
        # Obtenemos los estados financieros
        income_stmt = ticker.income_stmt
        balance_sheet = ticker.balance_sheet

        if income_stmt.empty or balance_sheet.empty:
            return {}

        # ALINEACIÓN: Buscamos las fechas que existan en AMBOS documentos
        common_dates = income_stmt.columns.intersection(balance_sheet.columns)
        common_dates = sorted(common_dates, reverse=True)[:num_years]

        for date in common_dates:
            try:
                is_data = income_stmt[date]
                bs_data = balance_sheet[date]
                year = date.year

                # --- EXTRACCIÓN ROBUSTA DE DATOS ---
                # EBIT
                ebit = is_data.get('EBIT', is_data.get('Operating Income', 0))
                
                # Tasa impositiva (Tax Rate)
                tax_rate = is_data.get('Tax Rate For Calcs')
                if tax_rate is None or pd.isna(tax_rate):
                    pretax_inc = is_data.get('Pretax Income', 0)
                    tax_prov = is_data.get('Tax Provision', 0)
                    tax_rate = (tax_prov / pretax_inc) if (pretax_inc and pretax_inc > 0) else 0.21

                # Capital Invertido: Equity + Deuda Total - Caja
                equity = bs_data.get('Stockholders Equity', bs_data.get('Total Equity Gross Minority Interest', 0))
                
                # Intentamos obtener deuda total de varias formas
                total_debt = bs_data.get('Total Debt', 
                             bs_data.get('Current Debt And Capital Lease Obligation', 0) + 
                             bs_data.get('Long Term Debt And Capital Lease Obligation', 0))
                
                cash = bs_data.get('Cash And Cash Equivalents', bs_data.get('Cash Cash Equivalents And Short Term Investments', 0))

                # Cálculo de ROIC
                nopat = ebit * (1 - tax_rate)
                invested_capital = equity + total_debt - cash

                if invested_capital > 0:
                    roic_values_by_year[year] = nopat / invested_capital
                else:
                    roic_values_by_year[year] = np.nan

            except Exception:
                continue
    except Exception:
        pass

    return roic_values_by_year

# --- Interfaz de Usuario ---
st.title("Calculador ROIC") 

with st.sidebar:
    st.subheader("Introduce los tikkers que quieres analizar separados por comas")
    tickers_input = st.text_input(label="Ejemplo: V, MSFT, AAPL", value="V, MSFT, GOOGL, AAPL")
    st.divider()
    st.info("La fórmula utilizada es:")
    st.latex(r"ROIC = \frac{EBIT \times (1 - Tax Rate)}{Equity + Debt - Cash}")

if tickers_input:
    ticker_list = [t.strip().upper() for t in tickers_input.split(',') if t.strip()]
    
    with st.spinner('Extrayendo y alineando datos...'):
        all_results = {symbol: calculate_roic_for_ticker(symbol) for symbol in ticker_list}
        # Crear DataFrame y limpiar filas vacías
        roic_df = pd.DataFrame.from_dict(all_results, orient='index')
        roic_df = roic_df.sort_index(axis=1) # Ordenar años cronológicamente

    if not roic_df.dropna(how='all').empty:
        # 1. Gráfico
        st.subheader("📈 Tendencia Histórica")
        plot_data = roic_df.reset_index().melt(id_vars='index', var_name='Año', value_name='ROIC')
        plot_data.columns = ['Ticker', 'Año', 'ROIC']
        
        fig = px.line(plot_data, x='Año', y='ROIC', color='Ticker', markers=True, template="plotly_white")
        fig.update_layout(yaxis_tickformat='.1%', xaxis_type='category')
        st.plotly_chart(fig, use_container_width=True)

        # 2. Tabla
        st.subheader("📋 Datos Detallados")
        display_df = roic_df[sorted(roic_df.columns, reverse=True)]
        st.dataframe(display_df.style.format("{:.2%}", na_rep="N/A").highlight_max(axis=0, color='#1f77b422'))
        
        csv = display_df.to_csv().encode('utf-8')
        st.download_button("📥 Descargar CSV", csv, "datos_roic.csv", "text/csv")
    else:
        st.warning("No se encontraron datos suficientes para generar el análisis.")
