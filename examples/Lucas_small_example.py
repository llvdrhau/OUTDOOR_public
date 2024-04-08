"""
This is a test case for the outdoor package applied to AGRILOOP. It is used to test the functionality of the package.
Made by Philippe adapted by Lucas

Possible optimization modes: "Single run optimization", "Multi-criteria optimization", "Sensitivity analysis",
or "Cross-parameter sensitivity"
"""

import sys
import os
import tracemalloc
from delete_function import delete_all_files_in_directory


# start the memory profiler
tracemalloc.start()
# add the path to the src folder to the system path
a = os.path.dirname(__file__)
a = os.path.dirname(a)
b = a + '/src'
sys.path.append(b)

import outdoor



# define the paths to the Excel file and the results directories
Excel_Path = "Excel_files/Test_case_study_Biorefinery.xlsm"
Results_Path = r"C:\Users\Lucas\PycharmProjects\OUTDOOR_USC\examples\results\Agriloop_test"
Results_Path_single = r"C:\Users\Lucas\PycharmProjects\OUTDOOR_USC\examples\results\Agriloop_test\single"
Results_Path_stochatic = r"C:\Users\Lucas\PycharmProjects\OUTDOOR_USC\examples\results\Agriloop_test\stochastic"
Results_Path_sensitivity = r"C:\Users\Lucas\PycharmProjects\OUTDOOR_USC\examples\results\Agriloop_test\sensitivity"


# create the superstructure data from the Excel file and
superstructure_Data = outdoor.get_DataFromExcel(Excel_Path)
#superstructure_Data = get_DataFromExcel(Excel_Path)

# create the superstructure flowsheet
outdoor.create_superstructure_flowsheet(superstructure_Data, Results_Path)
#create_superstructure_flowsheet(superstructure_Data, Results_Path)

# solve the optimization problem
abstract_model = outdoor.SuperstructureProblem(parser_type='Superstructure')


solverOptions = {"IntFeasTol": 1e-8,  # tolerance for integer feasibility
                 "NumericFocus": 0}   # 0: balanced, 1: feasibility, 2: optimality, 3: feasibility and optimality

model_output = abstract_model.solve_optimization_problem(input_data=superstructure_Data,
                                                         solver='gurobi',
                                                         interface='local',
                                                         calculation_VSS=False,
                                                         calculation_EVPI=False,
                                                         options=solverOptions,)

current, peak = tracemalloc.get_traced_memory()
print(f"Current memory usage is {current / 10 ** 6}MB; Peak was {peak / 10 ** 6}MB")

if model_output._optimization_mode == "single":  # single run optimization
    # delete old file in the results directory, so it does not pile up
    delete_all_files_in_directory(Results_Path_single)
    # save the results as a txt file, you have to specify the path
    model_output.get_results(savePath=Results_Path_single)
    # save and analyze the new results
    analyzer = outdoor.BasicModelAnalyzer(model_output)
    # create the flow sheets of the superstructure and the optimized flow sheet
    analyzer.create_flowsheet(Results_Path_single)


elif model_output._optimization_mode == "sensitivity":  # single run optimization

    model_output.get_results(savePath=Results_Path_sensitivity, pprint=False)
    # make an analysis of the results by creating the analysis object and calling the method
    analyzer = outdoor.AdvancedMultiModelAnalyzer(model_output)
    fig = analyzer.create_sensitivity_graph(savePath=Results_Path_sensitivity,
                                            saveName="sensitivity_part2",
                                            figureMode="single")


