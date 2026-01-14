import yfinance as yf
import pandas as pd
import numpy as np
import plotly.express as px
import streamlit as st

# Configuración de la página
st.set_page_config(page_title="Calculador ROIC", layout="wide")

# --- Lógica de Cálculo Robusta ---
@st.cache_data
def calculate_roic_for_ticker(ticker_symbol, num_years=5):
    roic_values_by_year = {} 
    try:
        ticker = yf.Ticker(ticker_symbol)
        income_stmt = ticker.income_stmt
        balance_sheet = ticker.balance_sheet

        if income_stmt.empty or balance_sheet.empty:
            return {}

        # Alineamos por fechas comunes para evitar desajustes
        common_dates = income_stmt.columns.intersection(balance_sheet.columns)
        common_dates = sorted(common_dates, reverse=True)[:num_years]

        for date in common_dates:
            try:
                is_data = income_stmt[date]
                bs_data = balance_sheet[date]
                year = int(date.year) # Aseguramos que el año sea un entero para las columnas

                # EBIT y Tax Rate
                ebit = is_data.get('EBIT', is_data.get('Operating Income', 0))
                tax_rate = is_data.get('Tax Rate For Calcs')
                
                if tax_rate is None or pd.isna(tax_rate):
                    pretax_inc = is_data.get('Pretax Income', 0)
                    tax_prov = is_data.get('Tax Provision', 0)
                    tax_rate = (tax_prov / pretax_inc) if (pretax_inc and pretax_inc > 0) else 0.21

                # Capital Invertido
                equity = bs_data.get('Stockholders Equity', bs_data.get('Total Equity Gross Minority Interest', 0))
                total_debt = bs_data.get('Total Debt', 
                             bs_data.get('Current Debt And Capital Lease Obligation', 0) + 
                             bs_data.get('Long Term Debt And Capital Lease Obligation', 0))
                cash = bs_data.get('Cash And Cash Equivalents', bs_data.get('Cash Cash Equivalents And Short Term Investments', 0))

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
    st.info("Fórmula utilizada:")
    st.latex(r"ROIC = \frac{EBIT \times (1 - Tax Rate)}{Equity + Debt - Cash}")

if tickers_input:
    ticker_list = [t.strip().upper() for t in tickers_input.split(',') if t.strip()]
    
    with st.spinner('Analizando datos financieros...'):
        all_results = {symbol: calculate_roic_for_ticker(symbol) for symbol in ticker_list}
        
        # --- SOLUCIÓN AL DESCOLOCAMIENTO ---
        # 1. Creamos el DataFrame inicial
        roic_df = pd.DataFrame.from_dict(all_results, orient='index')
        
        # 2. Convertimos nombres de columnas a enteros (por si acaso) y ordenamos años
        roic_df.columns = [int(col) for col in roic_df.columns if str(col).isdigit()]
        roic_df = roic_df.sort_index(axis=1, ascending=False) 

    if not roic_df.dropna(how='all').empty:
        # Gráfico
        st.subheader("📈 Tendencia Histórica")
        # Preparamos datos para Plotly asegurando que los años se traten como categorías
        plot_data = roic_df.reset_index().melt(id_vars='index', var_name='Año', value_name='ROIC')
        plot_data.columns = ['Ticker', 'Año', 'ROIC']
        plot_data = plot_data.sort_values(['Ticker', 'Año'])
        
        fig = px.line(plot_data, x='Año', y='ROIC', color='Ticker', markers=True, template="plotly_white")
        fig.update_layout(yaxis_tickformat='.1%', xaxis_type='category')
        st.plotly_chart(fig, use_container_width=True)

        # Tabla de datos (Formato fijo)
        st.subheader("📋 Datos Detallados")
        # Mostramos la tabla. Pandas se encarga de poner NaN donde no hay coincidencia
        st.dataframe(
            roic_df.style.format("{:.2%}", na_rep="N/A")
            .highlight_max(axis=0, color='#1f77b422'),
            use_container_width=True
        )
        
        # Descarga
        csv = roic_df.to_csv().encode('utf-8')
        st.download_button("📥 Descargar CSV", csv, "datos_roic.csv", "text/csv")
    else:
        st.warning("No se encontraron datos para los tickers ingresados.")
