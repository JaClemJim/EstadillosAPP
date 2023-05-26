# EstadillosAPP


- app.py: controla el frontend de la aplicación web. Llama al as funciones que calculan el estadillo y procesa los resultados y los posibles mensajes para mostralos en pantalla. Se genera un fichero excel para su descarga.
- shift_scheduling_sat_revCREF_v20.py: función para el calculo de estadillos. Llama al resto de funciones en otros archivos. Coge parte de los datos de entrada de inputconfigCRs.json y el resto de app.py. Los datos de tráfico vienen de la función getdftraffic que se encuentra en el archivo myInputCRs.py

**Conflictos de compatibilidad entre versiones de librerías**: 

Las librerías stramlit y ortools necesitan cada una versión diferente de protobuf. Se solucionan dejando a pip que encuentre compatibilidades de manera automática. Esto provoca que si se ejecuta en un puerto local o en la nube de streamlit, ciertas funciones usadas generen fallos. 