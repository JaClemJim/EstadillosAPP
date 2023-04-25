# Copyright 2010-2018 Google LLC
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
"""Creates a shift scheduling problem and solves it."""

from __future__ import print_function

# módulos lectura de datos entrada
import myInputConfigCRs # datos json configuración cálculos OR
import myInputCRs # datos csv escenario (turnos, posiciones/capacidad, demanda)
import myoutputCRs # escribir resultados en CSV
import math # ceil, floor
import pandas as pd

from ortools.sat.python import cp_model

from google.protobuf import text_format

def negated_bounded_span(works, start, length):
    """Filters an isolated sub-sequence of variables assined to True.
  Extract the span of Boolean variables [start, start + length), negate them,
  and if there is variables to the left/right of this span, surround the span by
  them in non negated form.
  Args:
    works: a list of variables to extract the span from.
    start: the start to the span.
    length: the length of the span.
  Returns:
    a list of variables which conjunction will be false if the sub-list is
    assigned to True, and correctly bounded by variables assigned to False,
    or by the start or end of works.
  """
    sequence = []
    # Left border (start of works, or works[start - 1])
    if start > 0:
        sequence.append(works[start - 1])
    for i in range(length):
        sequence.append(works[start + i].Not())
    # Right border (end of works or works[start + length])
    if start + length < len(works):
        sequence.append(works[start + length])
    return sequence


def add_soft_sequence_constraint(model, works, hard_min, soft_min, min_cost,
                                 soft_max, hard_max, max_cost, prefix):
    """Sequence constraint on true variables with soft and hard bounds.
  This constraint look at every maximal contiguous sequence of variables
  assigned to true. If forbids sequence of length < hard_min or > hard_max.
  Then it creates penalty terms if the length is < soft_min or > soft_max.
  Args:
    model: the sequence constraint is built on this model.
    works: a list of Boolean variables.
    hard_min: any sequence of true variables must have a length of at least
      hard_min.
    soft_min: any sequence should have a length of at least soft_min, or a
      linear penalty on the delta will be added to the objective.
    min_cost: the coefficient of the linear penalty if the length is less than
      soft_min.
    soft_max: any sequence should have a length of at most soft_max, or a linear
      penalty on the delta will be added to the objective.
    hard_max: any sequence of true variables must have a length of at most
      hard_max.
    max_cost: the coefficient of the linear penalty if the length is more than
      soft_max.
    prefix: a base name for penalty literals.
  Returns:
    a tuple (variables_list, coefficient_list) containing the different
    penalties created by the sequence constraint.
  """
    cost_literals = []
    cost_coefficients = []

    # Forbid sequences that are too short.
    for length in range(1, hard_min):
        for start in range(len(works) - length + 1):
            model.AddBoolOr(negated_bounded_span(works, start, length))

    # Penalize sequences that are below the soft limit.
    if min_cost > 0:
        for length in range(hard_min, soft_min):
            for start in range(len(works) - length + 1):
                span = negated_bounded_span(works, start, length)
                name = ': under_span(start=%i, length=%i)' % (start, length)
                lit = model.NewBoolVar(prefix + name)
                span.append(lit)
                model.AddBoolOr(span)
                cost_literals.append(lit)
                # We filter exactly the sequence with a short length.
                # The penalty is proportional to the delta with soft_min.
                cost_coefficients.append(min_cost * (soft_min - length))

    # Penalize sequences that are above the soft limit.
    if max_cost > 0:
        for length in range(soft_max + 1, hard_max + 1):
            for start in range(len(works) - length + 1):
                span = negated_bounded_span(works, start, length)
                name = ': over_span(start=%i, length=%i)' % (start, length)
                lit = model.NewBoolVar(prefix + name)
                span.append(lit)
                model.AddBoolOr(span)
                cost_literals.append(lit)
                # Cost paid is max_cost * excess length.
                cost_coefficients.append(max_cost * (length - soft_max))

    # Just forbid any sequence of true variables with length hard_max + 1
    for start in range(len(works) - hard_max):
        model.AddBoolOr(
            [works[i].Not() for i in range(start, start + hard_max + 1)])
    return cost_literals, cost_coefficients


def add_soft_sum_constraint(model, works, hard_min, soft_min, min_cost,
                            soft_max, hard_max, max_cost, prefix,
                            myParametroControl=7):
    """Sum constraint with soft and hard bounds.
  This constraint counts the variables assigned to true from works.
  If forbids sum < hard_min or > hard_max.
  Then it creates penalty terms if the sum is < soft_min or > soft_max.
  Args:
    model: the sequence constraint is built on this model.
    works: a list of Boolean variables.
    hard_min: any sequence of true variables must have a sum of at least
      hard_min.
    soft_min: any sequence should have a sum of at least soft_min, or a linear
      penalty on the delta will be added to the objective.
    min_cost: the coefficient of the linear penalty if the sum is less than
      soft_min.
    soft_max: any sequence should have a sum of at most soft_max, or a linear
      penalty on the delta will be added to the objective.
    hard_max: any sequence of true variables must have a sum of at most
      hard_max.
    max_cost: the coefficient of the linear penalty if the sum is more than
      soft_max.
    prefix: a base name for penalty variables.
  Returns:
    a tuple (variables_list, coefficient_list) containing the different
    penalties created by the sequence constraint.
  """
    
    cost_variables = []
    cost_coefficients = []
    sum_var = model.NewIntVar(hard_min, hard_max, '')
    # This adds the hard constraints on the sum.
    model.Add(sum_var == sum(works))

    # Penalize sums below the soft_min target.
    if soft_min > hard_min and min_cost > 0:
        delta = model.NewIntVar(-len(works), len(works), '')
        model.Add(delta == soft_min - sum_var)
        # TODO(user): Compare efficiency with only excess >= soft_min-sum_var.
        excess = model.NewIntVar(0, myParametroControl, prefix + ': under_sum')
        model.AddMaxEquality(excess, [delta, 0])
        cost_variables.append(excess)
        cost_coefficients.append(min_cost)

    # Penalize sums above the soft_max target.
    if soft_max < hard_max and max_cost > 0:
        delta = model.NewIntVar(-myParametroControl, myParametroControl, '')
        model.Add(delta == sum_var - soft_max)
        excess = model.NewIntVar(0, myParametroControl, prefix + ': over_sum')
        model.AddMaxEquality(excess, [delta, 0])
        cost_variables.append(excess)
        cost_coefficients.append(max_cost)

    return cost_variables, cost_coefficients


#def solve_shift_scheduling(params, output_proto):
def solve_shift_scheduling(lista):    
    """Solves the shift scheduling problem."""
    
     #escenario
    #PENDIENTE:
    # -seleccionar escenario 
        #PENDIENTE: poner nombre a turnos
    mC=myInputConfigCRs.MyConfig() #lee inputconfigCRs.json
    
#    myAD='LEMD_DCL'
#    myturno=0
#    mydiames=15 #SEGÚN FORMATO FICHERO TRAFICO
    myAD=lista[0]
    myturno=lista[2]
    mydiames=mC.num_day
    mynummes=mC.num_month
    myfileTWR=mC.fileTWR
    myfileTrafico=mC.fileTrafico
    mE=myInputCRs.MyEscenario(icao=myAD,fileTWR=myfileTWR,
                 fileTrafico=myfileTrafico) #lee datosDependencias
    
    # input Config
    if mC.num_hours==0:
        #si 0 lee el turno
        mC.num_hours=mE.duracionturnos.iloc[myturno]
    
    num_employees=lista[1]
    
    print(myAD)
    print("shift:",myturno)
    if len(mC.hourly_cover_demands)==0:
        print("day:", mydiames, "/" , mynummes)
    
    num_hours=mC.num_hours # 8 hours = duración turno
    print("num_hours",num_hours)
        
    demand_interval_length=lista[4]
    intervals_per_hour=int(60/demand_interval_length)
    num_demandintervals=int(num_hours*intervals_per_hour)
    
    block_length=lista[3] # 5  minutes
    blocks_per_hour = int(60/block_length) # equivale a days/week=7
    blocks_per_interval=int(demand_interval_length/block_length)
    num_blocks = int(num_hours * blocks_per_hour)    # bloques (ej. 15 minutos)
    
    #25% 
    min_daily_sum_offblocks=math.ceil(mC.min_daily_sum_off*num_blocks)
    print("min_daily_sum_offblocks",min_daily_sum_offblocks)
    shifts = mC.shifts # ['O', 'F', 'b'] # off, FRQ, Brief
    
    if len(mC.label_hours)==blocks_per_hour:
        label_hours=mC.label_hours
    else:
        label_hours = [
                str(i*block_length) for i in range(blocks_per_hour)
            ] # '00 15 30 45 '
        
    myheader=" ".join(label_hours) + "  "
    
    
    # Demanda posiciones del inputconfigCRs.json (mC.hourly_cover_demands)
    # o a partir de la demanda de tráfico
    listaposiciones=[]
    listademanda=[]
    if len(mC.hourly_cover_demands)>0:
        # expande listaposiciones de demand_interval_length a num_blocks
        # demanda por 60' a bloques de 5'
        print('hourly_cover_demands not empty')
        for x in mC.hourly_cover_demands:
            for y in range(math.ceil(mC.demand_interval_length/mC.block_length)):
                listaposiciones.append(int(x[0]))
    else:
        # demand_interval_length=15' p.ej
        print('usa getdfTwr()')
        (listademanda,
        listaposiciones) = (mE.getdfTrafico(
                diames=mydiames,
                idturno=myturno,
                ventanaflotante=mC.demand_interval_length))
        
        if len(listademanda)==0:
            print("No hay datos de demanda")
            return
        if len(listaposiciones)==0:
            print("No hay datos de posiciones")
            return
        print(mC.shifts,listademanda,listaposiciones)
        
    # según demanda posiciones ó tráfico (pasar a int)
    mC.hourly_cover_demands=[[int(x)] for x in listaposiciones] #[[0],[1],...]
    mC.hourly_traffic_demands=[[int(x)] for x in listademanda] #[[0],[12],...]  
        
    
    # lista [1,1,1,..,2,...]  id=movtos. self.pos[12]=numpos con cap>=12
    capacidad_segun_posiciones=mE.cap
    posiciones_segun_movimientos=mE.pos
    maxcap=len(posiciones_segun_movimientos) #número posiciones por cada valor 
    # de movimientos [1,1,...,10] de x=0 ... 100 (maxcap)   
    
    # Fixed assignment: [employee, shift, block].
    # This fixes the first 2 days of the schedule.
    #[
    #    [0, 0, 0],
    #    [1, 0, 0],
    #    [2, 1, 0],
    #]
    fixed_assignments=mC.fixed_assignments

    # Request: [employee, shift, day, weight]
    # A negative weight indicates that the employee desire this assignment.
    #[
        # Employee 2 wants the first Saturday off.
        # [2, 0, 5, -2]
    #]
    requests = mC.requests
    

    # Shift constraints on continuous sequence :
    #     (shift, hard_min, soft_min, min_penalty,
    #             soft_max, hard_max, max_penalty)
    #        [
#            # One or two consecutive days of rest (s=0), this is a hard constraint.
#            (0, 1, 1, 0, 2, 2, 0),
#           # betweem 2 and 3 consecutive days of night shifts (s=3), 1 and 4 are
#           # possible but penalized.
#            (3, 1, 2, 20, 3, 4, 5),
#        ]
    # hard/soft min/max in minutes => translate to blocks
    shift_constraints=[]
    for x in mC.shift_constraints:
        shift_constraints.append([x[0],
                                  math.ceil(x[1]/block_length),
                                  math.ceil(x[2]/block_length),x[3],
                                  math.ceil(x[4]/block_length),
                                  math.ceil(x[5]/block_length),x[6]
                                  ])
         
    

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
    daily_sum_constraints = mC.daily_sum_constraints
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
    penalized_transitions=mC.penalized_transitions
#        

    # daily demands for work shifts (morning, afternon, night) for each day
    # of the week starting on Monday.
    #     [        
#        [1,0],  # Monday
#        [1,0],  # Wednesday
#        [1,0],  # Thursday
#        [1,0],  # Friday
#    ]
    # OJO: por intervalo h=1 ...num_demandintervals
    hourly_cover_demands = mC.hourly_cover_demands
    hourly_traffic_demands = mC.hourly_traffic_demands 
    if len(mC.hourly_cover_demands)==0:
        print("TRAFFIC_DEMAND",hourly_traffic_demands)
    # BOOKMARK. 
    # PENDIENTE CONTROLAR pos_demand=max(hourly_cover_demands)>num_employees
    
    
    # Penalty for exceeding the cover constraint per shift type.
    #[5,1]
    excess_cover_penalties=mC.excess_cover_penalties
       
    # Penalty for exceeding the evenly daily shifts constraint per shift type.
    #[10,10]
    evenly_penalties=mC.evenly_penalties
    # Tolerance (in +/-number of evenly distributed shifts)
    even_shift_tolerance=mC.even_shift_tolerance
    
    num_shifts = len(shifts)
    
    #parámetro ganancia para evaluar opciones
    myParametroControl=mC.parametroControl #7
    #time limit in seconds
    max_time_in_seconds = mC.max_time_in_seconds
    #True (=1): fuerza que se cubra la demanda, 
        # aunque se incumpla daily_sum_constraints
    match_full_demand=mC.match_full_demand
    if match_full_demand==True:
        print("match_full_demand")
        
    model = cp_model.CpModel()
    
    work = {}
    for e in range(num_employees):
        for s in range(num_shifts):
            for b in range(num_blocks):
                work[e, s, b] = model.NewBoolVar('work%i_%i_%i' % (e, s, b))
    
    # Linear terms of the objective in a minimization context.
    obj_int_vars = []
    obj_int_coeffs = []
    obj_bool_vars = []
    obj_bool_coeffs = []

    # Exactly one shift per day.
    for e in range(num_employees):
        for b in range(num_blocks):
            model.Add(sum(work[e, s, b] for s in range(num_shifts)) == 1)

    # Fixed assignments.
    for e, s, b in fixed_assignments:
        model.Add(work[e, s, b] == 1)

    # Employee requests
    for e, s, b, h in requests:
        obj_bool_vars.append(work[e, s, b])
        obj_bool_coeffs.append(h)

    # Shift constraints
    for ct in shift_constraints:
        shift, hard_min, soft_min, min_cost, soft_max, hard_max, max_cost = ct
        for e in range(num_employees):
            works = [work[e, shift, b] for b in range(num_blocks)]
            variables, coeffs = add_soft_sequence_constraint(
                model, works, hard_min, soft_min, min_cost, soft_max, hard_max,
                max_cost, 'shift_constraint(employee %i, shift %i)' % (e,
                                                                       shift))
            obj_bool_vars.extend(variables)
            obj_bool_coeffs.extend(coeffs)

    # daily sum constraints
    #including Assign shifts evenly: se añade como dailysumconstraint
    
    #average shifts per employee 
    #si no pide cobertura de demanda => descanso mínimo
    #PRUEBA
    maxblocks_available=num_blocks*num_employees
    print('num_shifts',num_shifts)
    print('hourly_cover_demands',hourly_cover_demands)   
    
    for s in range(1, num_shifts):
        even_shifts=[(sum(hourly_cover_demands[h][s-1] 
            for h in range(num_demandintervals))
            *demand_interval_length/block_length) // num_employees ] #floor div
    
    # offshifts per employee
    # comprueba min_daily_sum_offblocks (25%)
    aux=(maxblocks_available-sum(even_shifts) *
                       num_employees) // num_employees 
    if aux<min_daily_sum_offblocks:
        print("minimum daily offblocks > available offblocks")
        print("minimum daily offblocks per employee",min_daily_sum_offblocks)
        print("available offblocks per employee",aux)
        print("Check number of employees")
        return
    
    even_shifts.insert(0,aux) 
    print('even_shifts',even_shifts)
    print('num_blocks',num_blocks)
    print('num_demandintervals',num_demandintervals)
    print('maxblocks_available',maxblocks_available)
    
    # PRUEBA quita una condición redundante
    if even_shift_tolerance>0:
        if min_daily_sum_offblocks>0:
            mins=1 # daily_sum_constraints  para off a partir del 25% 
        else:
            mins=0 # daily_sum_constraints con even_shift incluye off

        for s in range(mins,len(even_shifts)):
            if even_shifts[s]>0: 
                hmin=int(even_shifts[s]-even_shift_tolerance)
                smin=hmin+even_shift_tolerance
                hmax=int(even_shifts[s]+2*even_shift_tolerance)
                smax=hmax-even_shift_tolerance
                daily_sum_constraints.append([s,hmin,smin,evenly_penalties[s],
                                              hmax,smax,evenly_penalties[s]])      
    
    # min_daily_sum_offblocks
    # si es viable esta condición se cumplirá por el reparto equilibrado
    if min_daily_sum_offblocks>0:
        s=0 #descanso
        hmin=min_daily_sum_offblocks
        smin=hmin
        hmax=int(even_shifts[0]+2*even_shift_tolerance)
        smax=hmax-even_shift_tolerance
        daily_sum_constraints.insert(0,[s,hmin,smin,evenly_penalties[s],
                                              hmax,smax,evenly_penalties[s]])
            
    print('maxWorkingblocks_available',
          maxblocks_available-daily_sum_constraints[0][1]*num_employees)
    print('daily_sum_constraints',daily_sum_constraints)  
    
    #FIN PRUEBA
    
    for ct in daily_sum_constraints:
        shift, hard_min, soft_min, min_cost, soft_max, hard_max, max_cost = ct
        for e in range(num_employees):
                works = [work[e, shift, b] 
                            for b in range(num_blocks)]
                variables, coeffs = add_soft_sum_constraint(
                    model, works, hard_min, soft_min, min_cost, soft_max,
                    hard_max, max_cost,
                    'daily_sum_constraint(employee %i, shift %i)' %
                    (e, shift),myParametroControl)
                obj_int_vars.extend(variables)
                obj_int_coeffs.extend(coeffs)

    # Penalized transitions
    for previous_shift, next_shift, cost in penalized_transitions:
        for e in range(num_employees):
            for b in range(num_blocks - 1):
                transition = [
                    work[e, previous_shift, b].Not(),
                    work[e, next_shift, b + 1].Not()
                ]
                if cost == 0:
                    model.AddBoolOr(transition)
                else:
                    trans_var = model.NewBoolVar(
                        'transition (employee=%i, block=%i)' % (e, b))
                    transition.append(trans_var)
                    model.AddBoolOr(transition)
                    obj_bool_vars.append(trans_var)
                    obj_bool_coeffs.append(cost)

    # Cover constraints
    # PRUEBA
    # PRUEBA
    # capacidad disponible
    mycap_pos=[model.NewConstant(0)] 
    for x in capacidad_segun_posiciones:        # [12,20,34]
        mycap_pos.append(model.NewConstant(x))  # [0,12,20,34] 0pos=0Cap
    print("mycap_pos",mycap_pos)
    #
    #PRUEBA
    valorCero=model.NewConstant(0) #auxiliar cte=0
    
    for s in range(1, num_shifts): # Ignore Off shift.
        demoras=[]
        for h in range(num_demandintervals):
            for b in range(blocks_per_interval):
                
                timeblock=h * blocks_per_interval + b
                works = [work[e, s, timeblock] 
                            for e in range(num_employees)]
                #prueba 
                pos_demand = hourly_cover_demands[h][s - 1] #demanda por hora
                if len(hourly_traffic_demands)>0:
                    traffic_demand = hourly_traffic_demands[h][s - 1]
                
                #limitado entre 0 y pos_demand
                worked = model.NewIntVar(0,pos_demand, '')
                model.Add(worked == sum(works))
                over_penalty = excess_cover_penalties[s - 1]
                
                if over_penalty > 0:
                    #PRUEBA: demanda posiciones
                    name = 'excess_pos_demand(shift=%i, block=%i)' % (
                            s, timeblock)
                    
                    if match_full_demand:
                        # ajusta exactamente a la demanda (sin importar descanso)
                        param_mindemand=0
                    else:
                        # permite menos posiciones que demanda
                        param_mindemand=-pos_demand
                
                    # BOOKMARK. PENDIENTE CONTROLAR pos_demand>num_employees
                    excess = model.NewIntVar(
                            param_mindemand, 
                            num_employees - pos_demand,
                            name)
                    
                    model.Add(excess == worked - pos_demand)
                    obj_int_vars.append(excess)
                    obj_int_coeffs.append(over_penalty)
                    
#                    PRUEBA: demanda tráfico
                    if len(hourly_traffic_demands)>0:
                        capacity=model.NewIntVar(0,maxcap,'')
#                        #worked=num posiciones
#                        #capacity=mycap_pos[worked]
                        model.AddElement(worked, mycap_pos, capacity) 
                        name = 'excess_traf_demand(shift=%i, block=%i)' % (
                            s, timeblock)
    # Objective
    model.Minimize(
        sum(obj_bool_vars[i] * obj_bool_coeffs[i]
            for i in range(len(obj_bool_vars)))
        + sum(obj_int_vars[i] * obj_int_coeffs[i]
              for i in range(len(obj_int_vars))))

    # Solve the model.
    solver = cp_model.CpSolver()
    # Sets a time limit of XX seconds.
    solver.parameters.max_time_in_seconds = max_time_in_seconds
    # Specify the number of parallel workers to use during search.
    solver.parameters.num_search_workers = num_employees #8
    

    solution_printer = cp_model.ObjectiveSolutionPrinter()
    status = solver.SolveWithSolutionCallback(model, solution_printer)

#     Create a solver and solve.
# =============================================================================
#     solver = cp_model.CpSolver()
#     solution_printer = VarArraySolutionPrinter([work])
#     status = solver.SearchForAllSolutions(model, solution_printer)
# 
# 
#     print('Status = %s' % solver.StatusName(status))
#     print('Number of solutions found: %i' % solution_printer.solution_count())
# =============================================================================
                
    # Print solution.
    #PENDIENTE: PASAR A SOLUTION CALLBACK
    if status == cp_model.OPTIMAL or status == cp_model.FEASIBLE:
        # myOutput=myoutputCRs.MyOutput(myAD + ".csv")
        # print()
        # header = ' '
        # for h in range(num_hours):
        #     header += myheader
        # print(header)
        myOutput=myoutputCRs.MyOutput(myAD + "_all.csv") #csv de salida
        
        #-----------------
        #se cambia el formato de salida del csv para simplificar su procesado con excel
        #-----------------
        
        # añade a la cadena (separada inicialmente por ':')
        #scadena=solver.StatusName(status) + ":" 
        #if match_full_demand:
            #formato para importar csv en excel
         #   scadena=scadena + "," + " match_full_demand" + ":,"
        #scadena = scadena + myAD + ':turno:' + str(myturno) + ':día:' + str(mydiames)
        #myOutput.añadirResultados(scadena) 


        ouput = []
        while len(listaposiciones)<= num_blocks: 
            listaposiciones.append(' ')
            listademanda.append(' ')
        
        #straux=",".join([str(int(x)) for x in listaposiciones])
        straux=",".join([str(int(x)) if x != ' ' else x for x in listaposiciones])
        
        #print('POS_DEMAND: ', strposdemanda)
        myOutput.añadirResultados('POS_DEMAND:,' + straux + ',') # añade a la cadena
        ouput.append(straux)

        #straux=",".join([str(int(x)) for x in listademanda])
        straux=",".join([str(int(x)) if x != ' ' else x for x in listademanda])
        #print('POS_DEMAND: ', strposdemanda)
        myOutput.añadirResultados('TRAFFIC_DEMAND:,' + straux+ ',') # añade cadena
        ouput.append(straux)

        for e in range(num_employees):
            schedule = ''
            for b in range(num_blocks):
                for s in range(num_shifts):
                    if solver.BooleanValue(work[e, s, b]):
                        schedule += shifts[s] + ','
            fila='worker%i:,%s' % (e, schedule)
            print(fila)
            myOutput.añadirResultados(fila) # añade a la cadena
            ouput.append(fila)
        
        
        # mensaje del asistente para evuluar soluciones
        tipAssessor=""
        incumplebloque_descansominimo=False
        print()
        print('Penalties:')
        for i, var in enumerate(obj_bool_vars):
            if solver.BooleanValue(var):
                penalty = obj_bool_coeffs[i]
                if penalty > 0:
                    # controla incumplimiento descanso 35'
                    if ("shift_constraint" in var.Name() and
                        "shift 0" in var.Name()):
                            incumplebloque_descansominimo=True
                    print('  %s violated, penalty=%i' % (var.Name(), penalty))
                else:
                    print('  %s fulfilled, gain=%i' % (var.Name(), -penalty))
        
        if incumplebloque_descansominimo:
            tipAssessor="continuous off shift_constraint violated."
            if match_full_demand:
                #primero probar quitando condición match_demand
                tipAssessor=tipAssessor + "\n Consider [match_full_demand]=0"
                tipAssessor=tipAssessor + "\n Or check [num_employees]"
            else:
                #después probar suavizar condición even_shift
                tipAssessor=tipAssessor + "\n Consider increase [even_shift_tolerance]"
            
        for i, var in enumerate(obj_int_vars):
            if solver.Value(var) > 0:
                print('  %s violated by %i, linear penalty=%i' %
                      (var.Name(), solver.Value(var), obj_int_coeffs[i]))
        
        print()
        print(tipAssessor)
        ouput.append(tipAssessor)
        myOutput.añadirResultados(tipAssessor)
        myOutput.volcarResultados(overwrite=True) # sobreescribe archivo
        
        Output = pd.DataFrame(ouput)

    

    print()
    print(solver.ResponseStats())
    return Output

