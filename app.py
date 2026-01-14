#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Calculador ROIC - Versión Final Optimizada
"""

import yfinance as yf
import pandas as pd
import numpy as np
import plotly.express as px
import streamlit as st

# 1. Configuración de la página
st.set_page_config(page_title="Calculador ROIC", layout="wide")

# 2. Lógica de Cálculo Robusta
@st.cache_data
def calculate_roic_for_ticker(ticker_symbol, num_years=5):
    roic_values_by_year = {} 
    try:
        ticker = yf.Ticker(ticker_symbol)
        income_stmt = ticker.income_stmt
        balance_sheet = ticker.balance_sheet

        if income_stmt.empty or balance_sheet.empty:
            return {}

        # Alineación por fechas comunes para evitar desajustes entre estados financieros
        common_dates = income_stmt.columns.intersection(balance_sheet.columns)
        common_dates = sorted(common_dates, reverse=True)[:num_years]

        for date in common_dates:
            try:
                is_data = income_stmt[date]
                bs_data = balance_sheet[date]
                year = int(date.year)

                # --- Extracción de datos ---
                ebit = is_data.get('EBIT', is_data.get('Operating Income', 0))
                
                # Tasa impositiva con respaldo
                tax_rate = is_data.get('Tax Rate For Calcs')
                if tax_rate is None or pd.isna(tax_rate):
                    pretax_inc = is_data.get('Pretax Income', 0)
                    tax_prov = is_data.get('Tax Provision', 0)
                    tax_rate = (tax_prov / pretax_inc) if (pretax_inc and pretax_inc > 0) else 0.21

                # Capital Invertido (Equity + Debt - Cash)
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

# 3. Interfaz de Usuario
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
        
        # Crear DataFrame y estandarizar columnas (años como enteros)
        roic_df = pd.DataFrame.from_dict(all_results, orient='index')
        roic_df.columns = [int(col) for col in roic_df.columns if str(col).isdigit()]
        
        # Ordenar columnas de más reciente a más antigua
        available_years = sorted(roic_df.columns, reverse=True)
        roic_df = roic_df[available_years]

    if not roic_df.dropna(how='all').empty:
        # --- SECCIÓN GRÁFICO ---
        st.subheader("📈 Tendencia Histórica")
        plot_data = roic_df.reset_index().melt(id_vars='index', var_name='Año', value_name='ROIC')
        plot_data.columns = ['Ticker', 'Año', 'ROIC']
        plot_data = plot_data.sort_values(['Ticker', 'Año'])
        
        fig = px.line(plot_data, x='Año', y='ROIC', color='Ticker', markers=True, template="plotly_white")
        fig.update_layout(yaxis_tickformat='.1%', xaxis_type='category')
        st.plotly_chart(fig, use_container_width=True)

        # --- SECCIÓN TABLA (Corrección de formato visual) ---
        st.subheader("📋 Datos Detallados")
        
        # Función para formatear cada celda como texto y evitar desalineación
        def format_to_text(val):
            if pd.isna(val) or val is None:
                return "-"  # Usamos un guion para que se vea limpio
            return f"{val:.2%}"

        # Creamos una copia para visualización formateada como texto
        display_df = roic_df.applymap(format_to_text)

        # Configuración de columnas para forzar alineación y ancho uniforme
        st.dataframe(
            display_df,
            use_container_width=True,
            column_config={
                year: st.column_config.TextColumn(str(year), width="medium")
                for year in available_years
            }
        )
        
        # Botón de descarga (usa el DataFrame numérico original)
        csv = roic_df.to_csv().encode('utf-8')
        st.download_button("📥 Descargar CSV", csv, "datos_roic.csv", "text/csv")
    else:
        st.warning("No se encontraron datos suficientes para los tickers ingresados.")
