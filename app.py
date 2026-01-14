import yfinance as yf
import pandas as pd
import numpy as np
import plotly.express as px
import streamlit as st

# Configuración de la página
st.set_page_config(page_title="Calculador ROIC", layout="wide")

# --- Lógica de Cálculo ---
@st.cache_data
def calculate_roic_for_ticker(ticker_symbol, num_years=5): # Fijado a 5 años por defecto
    roic_values_by_year = {} 
    try:
        ticker = yf.Ticker(ticker_symbol)
        income_stmt = ticker.income_stmt
        balance_sheet = ticker.balance_sheet

        if income_stmt.empty or balance_sheet.empty:
            return {f"Año -{i}": np.nan for i in range(num_years)}

        # Limitamos el bucle al número de años disponibles o al máximo fijado
        years_available = min(num_years, income_stmt.shape[1])
        
        for i in range(years_available):
            try:
                current_year_income = income_stmt.iloc[:, i]
                current_year_bs = balance_sheet.iloc[:, i]
                fiscal_year = income_stmt.columns[i].year

                # Datos de cuenta de resultados
                ebit = current_year_income.get('EBIT', 0)
                tax_rate = current_year_income.get('Tax Rate For Calcs')
                
                # Backup de Tax Rate si no existe en Yahoo
                if tax_rate is None or pd.isna(tax_rate):
                    pretax_inc = current_year_income.get('Pretax Income', 0)
                    tax_prov = current_year_income.get('Tax Provision', 0)
                    tax_rate = (tax_prov / pretax_inc) if pretax_inc > 0 else 0.21
                
                # Balance Sheet
                equity = current_year_bs.get('Stockholders Equity', 0)
                st_debt = current_year_bs.get('Current Debt And Capital Lease Obligation', 0)
                lt_debt = current_year_bs.get('Long Term Debt And Capital Lease Obligation', 0)
                cash = current_year_bs.get('Cash And Cash Equivalents', 0)

                nopat = ebit * (1 - tax_rate)
                invested_capital = equity + st_debt + lt_debt - cash

                if invested_capital > 0:
                    roic_values_by_year[fiscal_year] = nopat / invested_capital
                else:
                    roic_values_by_year[fiscal_year] = np.nan

            except Exception:
                continue
    except Exception:
        pass

    return roic_values_by_year

# --- Interfaz de Usuario ---
st.title("Calculador ROIC") 

# Barra lateral modificada según tus instrucciones
with st.sidebar:
    st.subheader("Introduce los tikkers que quieres analizar separados por comas")
    # Dejamos el label vacío porque el encabezado ya da la instrucción
    tickers_input = st.text_input(label="Ejemplo: V, MSFT, AAPL", value="V, MSFT, GOOGL, AAPL")
    st.divider()
    st.info("💡 El ROIC se calcula como NOPAT / Capital Invertido.")

if tickers_input:
    ticker_list = [t.strip().upper() for t in tickers_input.split(',') if t.strip()]
    
    with st.spinner('Extrayendo datos financieros...'):
        # Llamamos a la función con el valor fijo de 5 años
        all_results = {symbol: calculate_roic_for_ticker(symbol, num_years=5) for symbol in ticker_list}
        roic_df = pd.DataFrame.from_dict(all_results, orient='index')

    if not roic_df.dropna(how='all').empty:
        # Filtrar columnas numéricas (años)
        year_cols = sorted([c for c in roic_df.columns if isinstance(c, int)])
        roic_numeric = roic_df[year_cols].copy()

        # 1. Gráfico interactivo
        st.subheader("📈 Tendencia Histórica")
        plot_data = roic_numeric.reset_index().melt(id_vars='index', var_name='Año', value_name='ROIC')
        plot_data.columns = ['Ticker', 'Año', 'ROIC']
        
        fig = px.line(plot_data, x='Año', y='ROIC', color='Ticker', 
                      markers=True, template="plotly_white")
        fig.update_layout(yaxis_tickformat='.1%')
        st.plotly_chart(fig, use_container_width=True)

        # 2. Tabla de datos
        st.subheader("📋 Datos Detallados")
        display_df = roic_numeric[sorted(year_cols, reverse=True)]
        
        st.dataframe(
            display_df.style.format("{:.2%}", na_rep="N/A")
            .highlight_max(axis=0, color='#1f77b422') # Resalta el máximo de cada año
        )

        # 3. Botón de descarga
        csv = display_df.to_csv().encode('utf-8')
        st.download_button("📥 Descargar CSV", csv, "datos_roic.csv", "text/csv")

    else:
        st.error("No se han podido encontrar datos para esos tickers. Asegúrate de que los nombres sean correctos.")
