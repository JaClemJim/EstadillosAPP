import streamlit as st
import pandas as pd

'#ESTADILLOS INTERACTIVOS'

@st.cache_data
def load_data(path):
    dataset = pd.read_excel(path, source='openpyxl')
    return dataset

estadillo = load_data('prueba_6.xlsx')

st.dataframe(estadillo)
