#DATOS DE ENTRADA 
import pandas as pd
import numpy as np
import json


"""
Variables globales
PARÁMETROS DE LA SIMULACIÓN
fileTrafico: ICAO,DIAMES,MES,HORA_LOCAL (con formato HH:MM),TOTALES


PENDIENTE: 
    - turnos nocturnos
    - hora final turnos (cierre AD) en configCSV
    - listas ordenadas de datos TWR ()
"""

class MyEscenario:
    def __init__(self,icao,
                 fileTWR="datosDependencias1.csv",
                 fileTrafico="datos.csv",
                 separadorcolumnas=";"):
        
        print(fileTWR)
        dftwr= pd.read_csv(fileTWR,sep=separadorcolumnas)
        dftraf= pd.read_csv(fileTrafico,sep=separadorcolumnas)   
        
        #añadimos horalocal en formato horadec
        values = dftraf['HORA_LOCAL'].str.split(':', expand=True).astype(int)
        factors = np.array([1, 60])

        dftraf['HORA_LOCAL_DEC'] = (values / factors).sum(1)
        
        self.ICAO=icao
        self.dfTWR=dftwr
        self.dfTrafico = dftraf 
        
        data = self.getdataTWR()
        self.turnos=data[0]
        self.duracionturnos=data[1]
        self.cap=data[2] # [12, 22, 33] 
        self.dfpos = data[3] # dataframe ['TOTALES_FLOTANTE','POS']
        # lista [1,1,1,..,2,...]  id=movtos. self.pos[12]=numpos con cap>=12
        self.pos=self.dfpos['POS'].values.tolist() 

        
    def getdataTWR(self,separadordatos=","):
        '''
        Devuelve turnos,cap
        turnos=lista con las hora inicio de cada turno 
        cap= lista con las capacidades sostenibles (cap[i]=capacidad(POS=i+1))
        '''
        #dataframe filtrado por designador como np
        npc=self.dfTWR.loc[self.dfTWR['ICAO']==self.ICAO,
                           ['capsostenible']].to_numpy()
        nph=self.dfTWR.loc[self.dfTWR['ICAO']==self.ICAO,
                           ['turnoshini']].to_numpy()
        
        #turnos en float para poder hacer filtros
        turnos=pd.Series(nph[0,0].split(separadordatos)).astype(float)
        
        #Difference with previous row
        duracionturnos=turnos.diff()
        duracionturnos=duracionturnos.dropna() #elimina primer y último row (NaN)

        
        cap=npc[0,0].split(separadordatos)
        cap = [int(x) for x in cap] # valores enteros
        #tabla inverse pos/cap (de pos=1 ... maxpos)
        maxcap=cap[-1]
        auxcap=[i for i in range(maxcap+1)] #cap=0,1,....,maxcap
        auxpos=[]
        for i in range(maxcap+1):
            id=indices(cap, lambda x: i<=x)
            auxpos.append(id[0]+1)

        #TOTALES_FLOTANTE = CAPACIDAD, nombre para que sirva como key  
        #zip empareja valores de ambas listas (auxcap[i],auxpos[i])          
        dfpos=pd.DataFrame(list(zip(auxcap,auxpos)), 
                           columns=['TOTALES_FLOTANTE','POS']) 
        
        return  turnos,duracionturnos,cap,dfpos      
        
    def getdfTrafico(self,diames,idturno,ventanaflotante=20,separadordatos=",", TRAF = []):        
        '''
        devuelve demanda en el turno (0,1,...) del diames 
        turno corresponde a un intervalo horas ('turnos ini')
        '''
        idturno=min(idturno,len(self.turnos)-1)            
        hini=self.turnos[idturno]
        
        if (idturno+1>=len(self.turnos)):
            hfin=24 
        else:
            hfin=self.turnos[idturno+1]
        
        # filtro por AD, día y hora (entera). 
        # Hay que incluir la anterior y posterior
        myfiltro=((self.dfTrafico['ICAO']==self.ICAO) &
                  (self.dfTrafico['DIAMES']==diames) &
                  (self.dfTrafico['HORA_LOCAL_DEC']>=hini-1) &
                  (self.dfTrafico['HORA_LOCAL_DEC']<hfin+1) )
        
        dfflotante0=self.dfTrafico.loc[myfiltro,
                                  ['HORA_LOCAL','HORA_LOCAL_DEC','TOTALES']].reset_index(drop=True)
                
        print(dfflotante0, "LINEA 108")

        if TRAF != []:
            new_demand = pd.DataFrame(TRAF).astype('float')
            # print(new_demand,  "despues de hacerlo dataframe")
            # print(new_dfflotante['TOTALES_FLOTANTE'], type(new_dfflotante['TOTALES_FLOTANTE']))
            dfflotante0['TOTALES']  = new_demand.iloc[:,0] 

            print(dfflotante0, "DENTRO DEL IF, DESPUES DEL CAMBIO")

        
        frames=[dfflotante0]       
        #ventana flotante
        numventanasporhora=int(60/ventanaflotante)
        for i in range(1,numventanasporhora):
            dfaux=dfflotante0.copy()
            dfaux['HORA_LOCAL_DEC']=dfaux['HORA_LOCAL_DEC']+i*ventanaflotante/60
            frames.append(dfaux)
        
        dfflotante=pd.concat(frames)
        #ordena el dataframe
        dfflotante=dfflotante.sort_values('HORA_LOCAL_DEC')
        #calcula TOT en cada ventana (ej. 15')
        dfflotante['TOTALES_VENTANA']=dfflotante['TOTALES']/numventanasporhora       
        #acumulado en cada hora flotante
        #empieza a calcular a partir de la última ventana de la 1ª hora (ej 3ª fila)
        dfflotante['TOTALES_FLOTANTE']=dfflotante[
                'TOTALES_VENTANA'].rolling(numventanasporhora).sum().round()
        #se avanza el total flotante (ultimas filas quedan NaN)
        dfflotante['TOTALES_FLOTANTE']=dfflotante[
                'TOTALES_FLOTANTE'].shift(1-numventanasporhora)
        #se rellenan las últimas filas (NaN) como la última calculada
        dfflotante['TOTALES_FLOTANTE']=dfflotante[
                'TOTALES_FLOTANTE'].fillna(method='ffill')
                
        #Filtro por hora decimal del turno
        myfiltro=((dfflotante['HORA_LOCAL_DEC']>=hini) &
                  (dfflotante['HORA_LOCAL_DEC']<hfin) )
        

        # merge performs an INNER JOIN by default

        print(dfflotante, 'ANTES DEL FILTRO')

        new_dfflotante = dfflotante.loc[myfiltro,
                                  ['HORA_LOCAL','HORA_LOCAL_DEC','TOTALES', 'TOTALES_FLOTANTE']].reset_index(drop=True)

        new_dfflotante_2=pd.merge(new_dfflotante, self.dfpos, 
                            on='TOTALES_FLOTANTE', 
                            how='left')
        print(new_dfflotante_2, "despues del merge")       
        
#        print('hini',hini,'hfin',hfin)
#        print('dfflotante', dfflotante)
        listademanda=list(new_dfflotante_2['TOTALES_FLOTANTE'].to_numpy())
        listaposiciones=list(new_dfflotante_2['POS'].to_numpy())
        return listademanda,listaposiciones

#print("")
#print(dfT[['DIAMES','HORA_LOCAL','TOTALES']].head(5))
#print(dfT[dfT['TOTALES']<10])
#print("")
#tot=dfA.loc[dfA['ICAO']=='LEBL',['capsostenible']].to_numpy()
#print(tot[0,0].split(","))


#FILTRO lista
#print(indices([1,0,3,5,1], lambda x: x<3))
#devuelve una lista con TODOS los índices de los valores que cumplen
def indices(list, filtr=lambda x: bool(x)):
    return [i for i,x in enumerate(list) if filtr(x)]
