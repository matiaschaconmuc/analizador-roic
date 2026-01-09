#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Fri Jan  9 16:49:55 2026

@author: MatiasiCloud
"""

import yfinance as yf
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import streamlit as st

# Configuración de la página de Streamlit
st.set_page_config(page_title="Analizador de ROIC", layout="wide")

# --- Lógica de Cálculo (Tu función original) ---
@st.cache_data # Esto evita descargar los mismos datos varias veces al cambiar el gráfico
def calculate_roic_for_ticker(ticker_symbol, num_years=3):
    roic_values_by_year = {} 
    try:
        ticker = yf.Ticker(ticker_symbol)
        income_stmt = ticker.income_stmt
        balance_sheet = ticker.balance_sheet

        if income_stmt.empty or balance_sheet.empty:
            for i in range(num_years):
                roic_values_by_year[f"Año -{i}"] = np.nan
            return roic_values_by_year

        for i in range(num_years):
            try:
                if i >= income_stmt.shape[1] or i >= balance_sheet.shape[1]:
                    roic_values_by_year[f"Año -{i}"] = np.nan
                    continue 

                current_year_income = income_stmt.iloc[:, i]
                current_year_bs = balance_sheet.iloc[:, i]
                fiscal_year = income_stmt.columns[i].year

                # Extracción y limpieza
                ebit = current_year_income.get('EBIT', 0)
                tax_rate = current_year_income.get('Tax Rate For Calcs', 0)
                equity = current_year_bs.get('Stockholders Equity', 0)
                st_debt = current_year_bs.get('Current Debt And Capital Lease Obligation', 0)
                lt_debt = current_year_bs.get('Long Term Debt And Capital Lease Obligation', 0)
                m_securities = current_year_bs.get('Other Short Term Investments', 0)

                nopat = ebit * (1 - tax_rate)
                invested_capital = equity + st_debt + lt_debt - m_securities

                if invested_capital <= 0 or pd.isna(nopat):
                    roic_values_by_year[fiscal_year] = np.nan
                else:
                    roic_values_by_year[fiscal_year] = nopat / invested_capital

            except:
                roic_values_by_year[f"Error {i}"] = np.nan
                continue
    except:
        for i in range(num_years):
            roic_values_by_year[f"Año -{i}"] = np.nan

    return roic_values_by_year

# --- Interfaz de Usuario con Streamlit ---
st.title("📊 Dashboard de Retorno sobre Capital Invertido (ROIC)")
st.markdown("""
Esta herramienta calcula el **ROIC** utilizando datos en tiempo real de Yahoo Finance. 
El ROIC mide la eficiencia de una empresa para generar beneficios con el capital que han aportado tanto accionistas como acreedores.
""")

# Barra lateral para configuración
with st.sidebar:
    st.header("Configuración")
    tickers_input = st.text_input("Introduce Tickers (separados por comas):", "V, MSFT, GOOGL, AAPL")
    years_to_calculate = st.slider("Años de histórico:", min_value=2, max_value=10, value=5)
    st.divider()
    st.info("Fórmula: NOPAT / Capital Invertido")

if tickers_input:
    ticker_list = [t.strip().upper() for t in tickers_input.split(',') if t.strip()]
    
    with st.spinner('Extrayendo datos financieros...'):
        all_results = {}
        for symbol in ticker_list:
            all_results[symbol] = calculate_roic_for_ticker(symbol, num_years=years_to_calculate)
        
        roic_df = pd.DataFrame.from_dict(all_results, orient='index')

    if not roic_df.empty:
        # 1. Preparación de datos para gráfico (numéricos y ordenados)
        year_columns = sorted([col for col in roic_df.columns if isinstance(col, (int, np.integer))])
        roic_numeric = roic_df[year_columns].copy()

        # --- SECCIÓN DE GRÁFICO ---
        st.subheader("📈 Tendencia Histórica")
        fig, ax = plt.subplots(figsize=(12, 5))
        for ticker in roic_numeric.index:
            ax.plot(year_columns, roic_numeric.loc[ticker], marker='o', label=ticker, linewidth=2)
        
        ax.set_ylabel("ROIC")
        ax.set_title("Evolución Anual")
        ax.grid(True, linestyle='--', alpha=0.6)
        ax.legend()
        
        # Formatear eje Y como porcentaje
        vals = ax.get_yticks()
        ax.set_yticklabels(['{:,.0%}'.format(x) for x in vals])
        
        st.pyplot(fig)

        # --- SECCIÓN DE TABLA ---
        st.subheader("📋 Datos Detallados")
        
        # Formatear tabla para visualización (Most recent first)
        display_df = roic_df[sorted(year_columns, reverse=True)].copy()
        
        # Aplicar estilo de porcentaje
        def format_pct(val):
            return f"{val:.2%}" if pd.notna(val) else "N/A"
        
        st.dataframe(display_df.style.format(format_pct).highlight_max(axis=0, color='#2e7d32'))

        # Botón de descarga CSV
        csv = display_df.to_csv().encode('utf-8')
        st.download_button(
            label="Descargar datos en CSV",
            data=csv,
            file_name='roic_data.csv',
            mime='text/csv',
        )
    else:
        st.error("No se pudieron obtener datos para los tickers introducidos.")