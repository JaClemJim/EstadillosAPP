import streamlit as st
import pandas as pd
from shift_scheduling_sat_revCREF_v20 import solve_shift_scheduling
import base64
import requests, os


######
#Entradilla
######
st.write(""" # ESTADILLOS INTERACTIVOS """)

st.markdown("""
 Seleccione los parámetros: 
""")

######
# Carga de los resultados en cache
######
@st.cache_data
def load_data(datos):
    dataset = solve_shift_scheduling(datos)
    return dataset

aerop = st.text_input("código OACI")
atcos = st.number_input('Número de ATCOS disponibles para el turno', min_value=1, step=1)
turno = st.selectbox('0 -> Mañana, 1 -> tarde, 2 -> noche', [0,1,2])
bloque = st.number_input('Bloque de tiempo para dividir la hora', min_value=5, max_value= 60, step=5)
demanda = st.number_input('Bloque de tiempo para captar la demanda', min_value=5, max_value = 60, step=5)


list_input = [aerop, atcos, turno, bloque, demanda]

boton1 = st.button("Click para calcular")

st.write("boton:", boton1)

if boton1:
    estadillo = load_data(list_input)
    
    st.write(estadillo)
