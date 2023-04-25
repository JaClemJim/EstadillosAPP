#DATOS DE ENTRADA ESCENARIO A1
import json

#https://docs.scipy.org/doc/scipy-0.16.1/reference/stats.html#module-scipy.stats

#PENDIENTE: cargar datos (INI?)
#PENDIENTE: percentilDLUP
"""
Variables globales
PARÁMETROS DE LA SIMULACIÓN
"""

class MyConfig:
    def __init__(self,file='inputconfigCRs.json',):
        print(file)
        with open(file) as f:
            inputdata = json.load(f)

    # Data
        self.num_employees=inputdata["num_employees"] # 3
        self.num_hours=inputdata["num_hours"] # si 0 lee el turno
        self.name_AD=inputdata["name_AD"] # "LEMD_DCL"
        self.id_shift=inputdata ["id_shift"] # 0
        self.num_day=inputdata["num_day"] # 15 
        self.num_month=inputdata["num_month"] #7
        self.fileTrafico=inputdata["fileTrafico"] # "datosTrafico_LEMD_DCL_2021.csv"
        self.fileTWR=inputdata["fileTWR"] # "datosDependencias1.csv"
        self.block_length=inputdata["block_length"] # 5  minutes
        
        self.shifts = inputdata["shifts"] # ['O', 'F', 'b'] # off, FRQ, Brief
        
        self.label_hours = inputdata["label_hours"] # '00 15 30 45 '
        
        self.myheader=" ".join(self.label_hours) + "  "
        # Fixed assignment: (employee, shift, block).
        # This fixes the first 2 days of the schedule.
        #[
        #    (0, 0, 0),
        #    (1, 0, 0),
        #    (2, 1, 0),
        #]
        self.fixed_assignments=inputdata["fixed_assignments"] 
    
        # Request: (employee, shift, day, weight)
        # A negative weight indicates that the employee desire this assignment.
        #[
            # Employee 2 wants the first Saturday off.
            # (2, 0, 5, -2)
        #]
        self.requests = inputdata["requests"]
        
    
        # Shift constraints on continuous sequence :
        #     (shift, hard_min, soft_min, min_penalty,
        #             soft_max, hard_max, max_penalty)
        #        [
#            # One or two consecutive days of rest, this is a hard constraint.
#            (0, 6, 6, 0, 18, 24, 20),
#           # betweem 2 and 3 consecutive days of night shifts, 1 and 4 are
#           # possible but penalized.
#            (1, 3, 3, 20, 15, 17, 20),
#        ]
        self.shift_constraints = inputdata["shift_constraints"]

    
        # daily sum constraints on shifts days:
        #     (shift, hard_min, soft_min, min_penalty,
        #             soft_max, hard_max, max_penalty)
        #        # Constraints on rests per week.
#        
#    #        (0, 1, 2, 7, 2, 3, 4),
#            # At least 1 night shift per week (penalized). At most 4 (hard).
#    #        (3, 0, 1, 3, 4, 4, 0),
#            # At least 1 freq shift per hour (penalized). At most 17=85' (hard)
#            (1, 0, 3, 3, 17, 17, 0),
#        ]
        self.daily_sum_constraints = inputdata["daily_sum_constraints"]
#    
    
        # Penalized transitions:
        #     (previous_shift, next_shift, penalty (0 means forbidden))
        #[
#            # Afternoon to night has a penalty of 4.
#    #        (2, 3, 4),
#            # off -> Freq is forbidden.
#           (0, 1, 0),
#           #briefing -> off is forbidden.
#           (2, 0, 0)
#        ]
        self.penalized_transitions=inputdata["penalized_transitions"]
#       
        # minimun daily off (ej. 0.25=25%)
        self.min_daily_sum_off=inputdata["min_daily_sum_off"]
        
        
        # demand interval length (minutes): 60 min, 20 min, 5 min
        # MENOR QUE 60 MINUTOS
        self.demand_interval_length=inputdata["demand_interval_length"]
        
        
        # daily demands for work shifts (morning, afternon, night) for each day
        # of the week starting on Monday.
        #     [        
        #        [1,0],  # Monday
        #        [1,0],  # Wednesday
        #        [1,0],  # Thursday
        #        [1,0],  # Friday
        #    ]
        # si se rellena, no utiliza el csv de tráfico.
        # OJO: si se rellena,
        # duración turno debe ser INT. No vale para turnos 7.5h p.ej.
        #tantos datos como duración turno * interval_length/60
        self.hourly_cover_demands = inputdata["hourly_cover_demands"]
    
        self.hourly_traffic_demands= [] # se lee del csv de tráfico
    
        # Penalty for exceeding the cover constraint per shift type.
        #[5,1]
        self.excess_cover_penalties=inputdata["excess_cover_penalties"]

        # Penalty for exceeding the evenly daily shifts constraint per shift type.
        #[10,10]
        self.evenly_penalties=inputdata["evenly_penalties"]
        # Tolerance (in +/-number of evenly distributed shifts)
        self.even_shift_tolerance=inputdata["even_shift_tolerance"]

        #parámetro ganancia para evaluar opciones
        self.parametroControl=inputdata["parametroControl"] #7

        #time limit in seconds
        self.max_time_in_seconds=inputdata["max_time_in_seconds"]
        
        #True (=1): fuerza que se cubra la demanda, 
        # aunque se incumpla daily_sum_constraints
        self.match_full_demand=bool(inputdata["match_full_demand"])