import yfinance as yf
import pandas as pd
import numpy as np
import plotly.express as px
import streamlit as st

# Configuración de la página
st.set_page_config(page_title="Pro Analizador de ROIC", layout="wide")

# --- Lógica de Cálculo Mejorada ---
@st.cache_data
def calculate_roic_for_ticker(ticker_symbol, num_years=5):
    roic_values_by_year = {} 
    try:
        ticker = yf.Ticker(ticker_symbol)
        income_stmt = ticker.income_stmt
        balance_sheet = ticker.balance_sheet

        if income_stmt.empty or balance_sheet.empty:
            return {f"Año -{i}": np.nan for i in range(num_years)}

        for i in range(min(num_years, income_stmt.shape[1])):
            try:
                # Datos de cuenta de resultados
                current_year_income = income_stmt.iloc[:, i]
                current_year_bs = balance_sheet.iloc[:, i]
                fiscal_year = income_stmt.columns[i].year

                # --- Mejora en cálculo de Impuestos ---
                ebit = current_year_income.get('EBIT', 0)
                tax_rate = current_year_income.get('Tax Rate For Calcs')
                
                if tax_rate is None or pd.isna(tax_rate):
                    # Intento de cálculo manual: Tax Provision / Pretax Income
                    pretax_inc = current_year_income.get('Pretax Income', 0)
                    tax_prov = current_year_income.get('Tax Provision', 0)
                    tax_rate = (tax_prov / pretax_inc) if pretax_inc > 0 else 0.21
                
                # --- Balance Sheet ---
                equity = current_year_bs.get('Stockholders Equity', 0)
                st_debt = current_year_bs.get('Current Debt And Capital Lease Obligation', 0)
                lt_debt = current_year_bs.get('Long Term Debt And Capital Lease Obligation', 0)
                cash = current_year_bs.get('Cash And Cash Equivalents', 0)

                nopat = ebit * (1 - tax_rate)
                # Capital Invertido: Equity + Deuda - Exceso de Caja (simplificado)
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
st.title("🚀 Dashboard Avanzado de ROIC")
st.markdown("Análisis profundo del **Return on Invested Capital** con datos de Yahoo Finance.")

# Barra lateral
with st.sidebar:
    st.header("Configuración")
    tickers_input = st.text_input("Tickers (ej: AAPL, MSFT, GOOGL):", "V, MSFT, GOOGL, AAPL")
    years_to_calculate = st.slider("Años de histórico:", 3, 10, 5)
    st.info("💡 **ROIC** indica qué tan rentable es una empresa respecto al capital invertido.")

if tickers_input:
    ticker_list = [t.strip().upper() for t in tickers_input.split(',') if t.strip()]
    
    with st.spinner('Consultando Wall Street...'):
        all_results = {symbol: calculate_roic_for_ticker(symbol, years_to_calculate) for symbol in ticker_list}
        roic_df = pd.DataFrame.from_dict(all_results, orient='index')

    if not roic_df.dropna(how='all').empty:
        # Limpieza de columnas (solo años numéricos)
        year_cols = sorted([c for c in roic_df.columns if isinstance(c, int)])
        roic_numeric = roic_df[year_cols].copy()

        # 1. Métricas destacadas (Último año disponible)
        st.subheader("📌 Resumen del Último Año Fiscal")
        cols = st.columns(len(ticker_list))
        for i, ticker in enumerate(ticker_list):
            if ticker in roic_numeric.index:
                val = roic_numeric.loc[ticker].dropna().iloc[0] if not roic_numeric.loc[ticker].dropna().empty else 0
                cols[i].metric(label=ticker, value=f"{val:.2%}")

        st.divider()

        # 2. Gráfico Interactivo con Plotly
        st.subheader("📈 Tendencia del ROIC")
        # Transformar datos para Plotly (formato largo)
        plot_data = roic_numeric.reset_index().melt(id_vars='index', var_name='Año', value_name='ROIC')
        plot_data.columns = ['Ticker', 'Año', 'ROIC']
        
        fig = px.line(plot_data, x='Año', y='ROIC', color='Ticker', 
                      markers=True, template="plotly_white",
                      labels={'ROIC': 'Retorno (%)'})
        fig.update_layout(yaxis_tickformat='.1%')
        st.plotly_chart(fig, use_container_width=True)

        # 3. Tabla de datos
        st.subheader("📋 Detalle Histórico")
        display_df = roic_numeric[sorted(year_cols, reverse=True)]
        
        # Estilo visual para la tabla
        st.dataframe(
            display_df.style.format("{:.2%}", na_rep="N/A")
            .background_gradient(cmap="Greens", axis=None)
        )

        # Descarga
        csv = display_df.to_csv().encode('utf-8')
        st.download_button("📥 Descargar Excel (CSV)", csv, "analisis_roic.csv", "text/csv")

    else:
        st.error("No se encontraron datos suficientes. Revisa los Tickers.")
