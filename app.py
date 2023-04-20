import streamlit as st
import pandas as pd
from shift_scheduling_sat_revCREF_v20 import solve_shift_scheduling

'#ESTADILLOS INTERACTIVOS'

# @st.cache_data
# def load_data(path):
#     dataset = pd.read_excel(path, source='openpyxl')
#     return dataset

estadillo = solve_shift_scheduling(False,False)

st.dataframe(estadillo)
