from pyomo.environ import *



class SuperstructureModel(AbstractModel):
    """
    Class description
    -----------------

    This class holds the mathematical model equations to describe a superstructure
    model. It defines classical modeling components like sets, parameter, variables
    and constraints.

    The model inlcudes mass balances, energy balances inlcuding detailed
    heat intergration based on heat intervals, cost functions using piece-wise
    linear capital costs and operational costs based on utilities, raw materials,
    operating and maintenance and other aspects. Additionally GWP and fresh
    water demand are calculated.

    """



    def __init__(self, superstructure_input=None, *args, **kwargs):
        super().__init__(*args, **kwargs)

        if superstructure_input is not None:
            self._set_optionals_from_superstructure(superstructure_input)
        else:
            self._set_optionals_from_external(kwargs)

    def _set_optionals_from_superstructure(self, superstructure_input):
        """
        Parameters
        ----------
        superstructure_input : Superstructure Object

        Description
        -----------
        uses a superstructure object to optionals which are:
                - Heat pump implementation (active/TIN/TOUT)
                - Additional logics (Groups/forces connections)
                - Objective name (NPC/NPE/NPFWD)
        """

        self.productDriven = superstructure_input.productDriven

        if superstructure_input.HP_active:
            self.heat_pump_options = {
                "active": superstructure_input.HP_active,
                "t_in": superstructure_input.HP_T_IN["Interval"],
                "t_out": superstructure_input.HP_T_OUT["Interval"],
            }
        else:
            self.heat_pump_options = {
                "active": superstructure_input.HP_active,
                "t_in": 0,
                "t_out": 0}

        self.objective_name = superstructure_input.objective
        self.groups = superstructure_input.groups
        self.connections = superstructure_input.connections

        for i in superstructure_input.UnitsList:
            if i.Type == "ProductPool" and i.ProductType == "MainProduct":
                self.main_pool = i.Number

    def _set_options_from_external(self, **kwargs):
        print("There is no external parsing implemented at the moment.")


    def create_ModelEquations(self):
        """
        Description
        -------
        Calls single methods to build the model in the order:
            - Sets
            - Mass balances
            - Energy balances
            - Economic functions
            - GWP functions
            - FWD functions
            - Logics
            - Objective function

        """
        self.create_Sets()
        self.create_MassBalances()
        self.create_EnergyBalances()
        self.create_EconomicEvaluation()
        self.create_EnvironmentalEvaluation()
        self.create_FreshwaterEvaluation()
        self.create_DecisionMaking()
        self.create_ObjectiveFunction()

    def populateModel(self, Data_file):
        """
        Parameters
        ----------
        Data_file : Dictionary
            Model data in AbstractModel readable file

        Returns
        -------
        PYOMO ConcreteModel
            filled model instance with equations from SuperstructureModel and
            data from Data_file.

        """
        self.ModelInstance = self.create_instance(Data_file)
        return self.ModelInstance

    # Pyomo Model Methods
    # --------------------

    # **** SETS  ****
    # ----------------

    def create_Sets(self):
        """
        Description
        -------
        Creates all needed Sets for the model including, unit operations, components,
        utilities, reactions, heat intervals etc.

        """

        # Process Unit operations
        # -------------
        self.U = Set()
        self.UU = Set(within=self.U)
        self.U_STOICH_REACTOR = Set(within=self.U)
        self.U_YIELD_REACTOR = Set(within=self.U)
        self.U_SPLITTER = Set(within=self.U)
        self.U_TUR = Set(within=self.U)
        self.U_FUR = Set(within=self.U)
        self.U_PP = Set(within=self.U)
        self.U_C = Set(within=self.U)
        self.U_S = Set(within=self.U)
        self.U_SU = Set(within=self.U_S * self.U)
        self.U_DIST = Set(within=self.U)
        self.U_DIST_SUB = Set(within=self.U_DIST * self.U)

        self.U_CONNECTORS = Set(within=self.U * self.U)


        # Components
        # ----------
        self.I = Set()
        self.M = Set(within=self.I)
        self.YC = Set(within=self.U_YIELD_REACTOR * self.I)

        # Reactions, Utilities, Heat intervals
        # ------------------------------------
        self.R = Set()
        self.UT = Set()
        self.H_UT = Set(within=self.UT)
        self.U_UT = Set(within=self.UT)
        self.HI = Set()

        # Piece-Wise Linear CAPEX
        # -----------------------
        self.J = Set()
        self.JI = Set(within=self.J)

        # Distributor Set for decimal numbers

        def iterator(x):
            nlist = []
            for i in range(x):
                nlist.append(i)
            return nlist

        self.DC_SET = Set(within=self.U_DIST * iterator(100))

        self.U_DIST_SUB2 = Set(within=self.U_DIST_SUB * self.U_DIST * iterator(100))

    # **** MASS BALANCES *****
    # -------------------------

    def create_MassBalances(self):
        """
        Description
        -------
        This method creates the PYOMO parameters and variables
        that are necessary for the general Mass Balances (eg. FLOWS, PHI, MYU etc.).
        Afterwards Masse Balance Equations are written as PYOMO Constraints.

        """

        # Parameter
        # ---------

        # Flow parameters (Split factor, concentrations, full load hours)
        self.myu = Param(self.U_CONNECTORS, self.I, initialize=0, mutable=True)
        self.conc = Param(self.U, initialize=0, within=Any)
        self.flh = Param(self.U)
        self.MinProduction = Param(self.U_PP, initialize=0)
        self.MaxProduction = Param(self.U_PP, initialize=100000)


        # Reaction parameters(Stoich. / Yield Coefficients)
        self.gamma = Param(self.U_STOICH_REACTOR, self.I, self.R, initialize=0, mutable=True)
        self.theta = Param(self.U_STOICH_REACTOR, self.R, self.M, initialize=0, mutable=True)
        self.xi = Param(self.U_YIELD_REACTOR, self.I, initialize=0, mutable=True)
        self.ic_on = Param(self.U_YIELD_REACTOR, initialize=0)

        # Additional slack parameters (Flow choice, upper bounds, )
        self.kappa_1_lhs_conc = Param(self.U, self.I, initialize=0)
        self.kappa_1_rhs_conc = Param(self.U, self.I, initialize=0)
        self.kappa_2_lhs_conc = Param(self.U, initialize=3)
        self.kappa_2_rhs_conc = Param(self.U, initialize=3)
        self.Names = Param(self.U, within= Any)
        self.alpha = Param(self.U, initialize=100000)

        # upper and lower bounds for source flows
        self.ul = Param(self.U_S, initialize=100000)
        self.ll = Param(self.U_S, initialize=0)

        # component composition parameters
        self.phi = Param(self.U_S, self.I, initialize=0, mutable=True)

        # cost parameters
        self.materialcosts = Param(self.U_S, initialize=0, mutable=True)

        # Decimal_numbers help to model the distributor equations
        # it sets the degree of "detail" for the distributor
        self.Decimal_numbers = Param(self.DC_SET)

        # Variables
        # --------

        self.FLOW = Var(self.U_CONNECTORS, self.I, within=NonNegativeReals)
        self.FLOW_IN = Var(self.U, self.I, within=NonNegativeReals)
        self.FLOW_OUT = Var(self.U, self.I, within=NonNegativeReals)
        self.FLOW_WASTE = Var(self.U, self.I, within=NonNegativeReals)
        self.FLOW_WASTE_TOTAL = Var(self.I, within=NonNegativeReals)
        self.FLOW_ADD = Var(self.U_SU, within=NonNegativeReals)
        self.FLOW_ADD_TOT = Var(self.U, self.I, within=NonNegativeReals)
        self.FLOW_SUM = Var(self.U, within=NonNegativeReals)
        self.Y = Var(self.U, within=Binary)
        self.FLOW_SOURCE = Var(self.U_S, within=NonNegativeReals)

        self.FLOW_DIST = Var(self.U_DIST_SUB2, self.I, within=NonNegativeReals)
        self.Y_DIST = Var(self.U_DIST_SUB2, within=Binary)

        self.FLOW_FT = Var(self.U_CONNECTORS, within=NonNegativeReals)

        # Constraints
        # -----------

        def MassBalance_1_rule(self, u, i):
            return self.FLOW_IN[u, i] == self.FLOW_ADD_TOT[u, i] + sum(self.flh[uu] / self.flh[u] * self.FLOW[uu, u, i] for uu in self.UU if (uu,u) in self.U_CONNECTORS)

        def MassBalance_2_rule(self, u, i):
            return self.FLOW_ADD_TOT[u, i] == sum(
                self.FLOW_ADD[u_s, u] * self.phi[u_s, i]
                for u_s in self.U_S
                if (u_s, u) in self.U_SU
            )

        def MassBalance_3_rule(self, u_s, u):
            return self.FLOW_ADD[u_s, u] <= self.alpha[u] * self.Y[u]  # Big M constraint

        def MassBalance_4_rule(self, u_s):
            return self.FLOW_SOURCE[u_s] == sum(
                self.FLOW_ADD[u_s, u] * self.flh[u] / self.flh[u_s]
                for u in self.U
                if (u_s, u) in self.U_SU
            )
         # upper and lower bounds for source flows
        def MassBalance_13_rule(self, u_s):
            # bounds defined in tons per year (t/a) hence flow times full loading hours
            return self.FLOW_SOURCE[u_s]  <= self.ul[u_s]

        def MassBalance_14_rule(self, u_s):
            # bounds defined in tons per year (t/a) hence flow times full loading hours
            return self.FLOW_SOURCE[u_s]  >= self.ll[u_s]

        # stoichimoetric and yield reactor equations
        def MassBalance_5_rule(self, u, i):
            if u in self.U_YIELD_REACTOR:
                if self.ic_on[u] == 1:
                    if (u, i) in self.YC:
                        return (
                            self.FLOW_OUT[u, i]
                            == self.FLOW_IN[u, i]
                            + sum(
                                self.FLOW_IN[u, i]
                                for i in self.I
                                if (u, i) not in self.YC
                            )
                            * self.xi[u, i]
                        )
                    else:
                        return (
                            self.FLOW_OUT[u, i]
                            == sum(
                                self.FLOW_IN[u, i]
                                for i in self.I
                                if (u, i) not in self.YC
                            )
                            * self.xi[u, i]
                        )
                else:
                    return (
                        self.FLOW_OUT[u, i]
                        == sum(self.FLOW_IN[u, i] for i in self.I) * self.xi[u, i]
                    )
            elif u in self.U_STOICH_REACTOR:
                return self.FLOW_OUT[u, i] == self.FLOW_IN[u, i] + sum(
                    self.gamma[u, i, r] * self.theta[u, r, m] * self.FLOW_IN[u, m]
                    for r in self.R
                    for m in self.M
                )
            else:
                return self.FLOW_OUT[u, i] == self.FLOW_IN[u, i]

        def MassBalance_9_rule(self, u, i):
            return self.FLOW_WASTE[u, i] == self.FLOW_OUT[u, i] - sum(
                self.FLOW[u, uu, i] for uu in self.UU if (u,uu) in self.U_CONNECTORS
            )

        def MassBalance_10_rule(self, i):
            return self.FLOW_WASTE_TOTAL[i] == sum(
                self.FLOW_WASTE[u, i] for u in self.U
            )

        # concentration constraints
        def MassBalance_11_rule(self, u):
            if self.kappa_2_lhs_conc[u] == 0 and self.kappa_2_rhs_conc[u] == 0:
                return 1e03 * sum(
                    self.FLOW_OUT[u, i] * self.kappa_1_lhs_conc[u, i] for i in self.I
                ) == 1e03 * self.conc[u] * sum(
                    self.FLOW_OUT[u, i] * self.kappa_1_rhs_conc[u, i] for i in self.I
                )
            elif self.kappa_2_lhs_conc[u] == 0 and self.kappa_2_rhs_conc[u] == 1:
                return 1e03 * sum(
                    self.FLOW_OUT[u, i] * self.kappa_1_lhs_conc[u, i] for i in self.I
                ) == 1e03 * self.conc[u] * sum(
                    self.FLOW_IN[u, i] * self.kappa_1_rhs_conc[u, i] for i in self.I
                )
            elif self.kappa_2_lhs_conc[u] == 1 and self.kappa_2_rhs_conc[u] == 0:
                return (1e03 * sum(
                        self.FLOW_IN[u, i] * self.kappa_1_lhs_conc[u, i] for i in self.I)
                        == 1e03 * self.conc[u] * sum(
                        self.FLOW_OUT[u, i] * self.kappa_1_rhs_conc[u, i] for i in self.I
                ))
            elif self.kappa_2_lhs_conc[u] == 1 and self.kappa_2_rhs_conc[u] == 1:
                return 1e03 * sum(self.FLOW_IN[u, i] * self.kappa_1_lhs_conc[u, i] for i in self.I ) == 1e03 * self.conc[u] * sum(self.FLOW_IN[u, i] * self.kappa_1_rhs_conc[u, i] for i in self.I)
            else:
                return Constraint.Skip

        def MassBalance_12_rule(self, u):
            return self.FLOW_SUM[u] == sum(self.FLOW_IN[u, i] for i in self.I)

        # min max production constraints for product pools
        def MassBalance_14a_rule(self, up):
            # bounds defined in tons per year (t/a) hence flow times full loading hours
            return self.FLOW_SUM[up]  >= self.MinProduction[up]

        def MassBalance_14b_rule(self, up):
            # bounds defined in tons per year (t/a) hence flow times full loading hours
            return self.FLOW_SUM[up]  <= self.MaxProduction[up]

        def MassBalance_6_rule(self, u, uu, i):
            if (u, uu) not in self.U_DIST_SUB:
                    if (u, uu) in self.U_CONNECTORS:
                        return self.FLOW[u, uu, i] <= self.myu[u, uu, i] * self.FLOW_OUT[
                            u, i
                            ] + self.alpha[u] * (1 - self.Y[uu])
                    else:
                        return Constraint.Skip

            else:
                return self.FLOW[u, uu, i] <= sum(
                    self.FLOW_DIST[u, uu, uk, k, i]
                    for (uk, k) in self.DC_SET
                    if (u, uu, uk, k) in self.U_DIST_SUB2
                ) + self.alpha[u] * (1 - self.Y[uu])

        def MassBalance_7_rule(self, u, uu, i):
            if (u,uu) in self.U_CONNECTORS:
                return self.FLOW[u, uu, i] <= self.alpha[u] * self.Y[uu]
            else:
                return Constraint.Skip


        def MassBalance_8_rule(self, u, uu, i):
            if (u, uu) not in self.U_DIST_SUB:
                if (u, uu) in self.U_CONNECTORS:
                    return self.FLOW[u, uu, i] >= self.myu[u, uu, i] * self.FLOW_OUT[
                        u, i
                        ] - self.alpha[u] * (1 - self.Y[uu])
                else:
                    return Constraint.Skip
            else:
                return self.FLOW[u, uu, i] >= sum(
                    self.FLOW_DIST[u, uu, uk, k, i]
                    for (uk, k) in self.DC_SET
                    if (u, uu, uk, k) in self.U_DIST_SUB2
                ) - self.alpha[u] * (1 - self.Y[uu])

        # Distributor Equations

        def MassBalance_15a_rule(self, u, uu, uk, k, i):
            return self.FLOW_DIST[u, uu, uk, k, i] <= self.Decimal_numbers[
                u, k
            ] * self.FLOW_OUT[u, i] + self.alpha[u] * (1 - self.Y_DIST[u, uu, uk, k])

        def MassBalance_15b_rule(self, u, uu, uk, k, i):
            return self.FLOW_DIST[u, uu, uk, k, i] >= self.Decimal_numbers[
                u, k
            ] * self.FLOW_OUT[u, i] - self.alpha[u] * (1 - self.Y_DIST[u, uu, uk, k])

        def MassBalance_15c_rule(self, u, uu, uk, k, i):
            return (
                self.FLOW_DIST[u, uu, uk, k, i]
                <= self.alpha[u] * self.Y_DIST[u, uu, uk, k]
            )

        def MassBalance_16_rule(self, u, i):
            return self.FLOW_OUT[u, i] == sum(
                self.FLOW[u, uu, i] for uu in self.U if (u, uu) in self.U_DIST_SUB
            )

        def MassBalance_17_rule(self, u, uu):
            return self.FLOW_FT[u, uu] == sum(self.FLOW[u, uu, i] for i in self.I)

        self.MassBalance_1 = Constraint(self.U, self.I, rule=MassBalance_1_rule)
        self.MassBalance_2 = Constraint(self.U, self.I, rule=MassBalance_2_rule)
        self.MassBalance_3 = Constraint(self.U_SU, rule=MassBalance_3_rule)
        self.MassBalance_4 = Constraint(self.U_S, rule=MassBalance_4_rule)
        self.MassBalance_13 = Constraint(self.U_S, rule=MassBalance_13_rule)
        self.MassBalance_14 = Constraint(self.U_S, rule=MassBalance_14_rule)

        self.MassBalance_5 = Constraint(self.U, self.I, rule=MassBalance_5_rule)
        self.MassBalance_6 = Constraint(self.U, self.UU, self.I, rule=MassBalance_6_rule)
        self.MassBalance_7 = Constraint(self.U, self.UU, self.I, rule=MassBalance_7_rule)
        self.MassBalance_8 = Constraint(self.U, self.UU, self.I, rule=MassBalance_8_rule)
        self.MassBalance_9 = Constraint(self.U, self.I, rule=MassBalance_9_rule)
        self.MassBalance_10 = Constraint(self.I, rule=MassBalance_10_rule)
        self.MassBalance_11 = Constraint(self.U, rule=MassBalance_11_rule)
        self.MassBalance_12 = Constraint(self.U, rule=MassBalance_12_rule)
        self.MassBalance_14a = Constraint(self.U_PP, rule=MassBalance_14a_rule)
        self.MassBalance_14b = Constraint(self.U_PP, rule=MassBalance_14b_rule)
        self.MassBalance_15a = Constraint(
            self.U_DIST_SUB2, self.I, rule=MassBalance_15a_rule
        )
        self.MassBalance_15b = Constraint(
            self.U_DIST_SUB2, self.I, rule=MassBalance_15b_rule
        )
        self.MassBalance_15c = Constraint(
            self.U_DIST_SUB2, self.I, rule=MassBalance_15c_rule
        )
        self.MassBalance_16 = Constraint(self.U_DIST, self.I, rule=MassBalance_16_rule)
        self.MassBalance_17 = Constraint(self.U_CONNECTORS, rule=MassBalance_17_rule)

    # **** ENERGY BALANCES *****
    # -------------------------

    def create_EnergyBalances(self):
        """
        Description
        -------
        This method creates the PYOMO parameters and variables
        that are necessary for the general Energy Balances (eg. TAU, REF_FLOW...).
        Afterwards Energy Balance‚ Equations are written as PYOMO Constraints.

        """

        # Parameter
        # ---------

        # Energy demand (El, Heating/Cooling, Interval H and C)
        self.tau = Param(self.U, self.UT, initialize=0, within=Any)
        self.tau_h = Param(self.H_UT, self.U, initialize=0)
        self.tau_c = Param(self.H_UT, self.U, initialize=0)
        self.beta = Param(self.U, self.H_UT, self.HI, initialize=0)

        # Slack Parameters (Flow Choice, HEN, Upper bounds)
        self.kappa_1_ut = Param(self.U, self.UT, self.I, initialize=0)
        self.kappa_2_ut = Param(self.U, self.UT, initialize=3)
        self.kappa_3_heat = Param(self.U, self.HI, initialize=0)
        self.kappa_3_heat2 = Param(self.U, self.HI, initialize=0)
        self.alpha_hex = Param(initialize=100000)
        self.Y_HEX = Var(self.HI, within=Binary)

        # Additional unit operations (Heat Pump, EL / Heat Generator)
        self.COP_HP = Param(initialize=0)
        self.Efficiency_TUR = Param(self.U_TUR, initialize=0)
        self.Efficiency_FUR = Param(self.U_FUR, initialize=0)
        self.LHV = Param(self.I, initialize=0)
        self.H = Param()

        # Variables
        # ---------

        # Reference Flows for Demand calculation
        self.REF_FLOW_UT = Var(self.U, self.UT)

        # Electricity Demand and Production, Heat Pump

        self.ENERGY_DEMAND = Var(self.U, self.U_UT)
        self.ENERGY_DEMAND_TOT = Var(self.U_UT)
        self.EL_PROD_1 = Var(self.U_TUR, within=NonNegativeReals)
        self.ENERGY_DEMAND_HP_EL = Var(within=NonNegativeReals)

        # Heating and cooling demand (Interval, Unit, Resi, Defi, Cooling, Exchange, Production , HP)
        self.ENERGY_DEMAND_HEAT = Var(self.U, self.HI, within=NonNegativeReals)
        self.ENERGY_DEMAND_COOL = Var(self.U, self.HI, within=NonNegativeReals)
        self.ENERGY_DEMAND_HEAT_UNIT = Var(self.U, within=NonNegativeReals)
        self.ENERGY_DEMAND_COOL_UNIT = Var(self.U, within=NonNegativeReals)
        self.ENERGY_DEMAND_HEAT_RESI = Var(self.HI, within=NonNegativeReals)
        self.ENERGY_DEMAND_HEAT_DEFI = Var(self.HI, within=NonNegativeReals)
        self.ENERGY_DEMAND_COOLING = Var(within=NonNegativeReals)
        self.ENERGY_EXCHANGE = Var(self.HI, within=NonNegativeReals)
        self.EXCHANGE_TOT = Var()
        self.ENERGY_DEMAND_HEAT_PROD_USE = Var(within=NonNegativeReals)
        self.ENERGY_DEMAND_HEAT_PROD_SELL = Var(within=NonNegativeReals)
        self.ENERGY_DEMAND_HEAT_PROD = Var(self.U_FUR, within=NonNegativeReals)
        self.ENERGY_DEMAND_HP = Var(within=NonNegativeReals)
        self.ENERGY_DEMAND_HP_USE = Var(within=NonNegativeReals)

        self.MW = Param(self.I, initialize=1)
        self.CP = Param(self.I, initialize=0)

        # Constraints
        # -----------

        # Utilities other than heating and cooling

        def UtilityBalance_1_rule(self, u, ut):
            if self.kappa_2_ut[u, ut] == 1:
                return self.REF_FLOW_UT[u, ut] == sum(
                    self.FLOW_IN[u, i] * self.kappa_1_ut[u, ut, i] for i in self.I
                )
            elif self.kappa_2_ut[u, ut] == 0:
                return self.REF_FLOW_UT[u, ut] == sum(
                    self.FLOW_OUT[u, i] * self.kappa_1_ut[u, ut, i] for i in self.I
                )
            elif self.kappa_2_ut[u, ut] == 4:
                return self.REF_FLOW_UT[u, ut] == sum(
                    self.FLOW_OUT[u, i] / self.MW[i] * self.kappa_1_ut[u, ut, i]
                    for i in self.I
                )
            elif self.kappa_2_ut[u, ut] == 2:
                return self.REF_FLOW_UT[u, ut] == sum(
                    self.FLOW_IN[u, i] / self.MW[i] * self.kappa_1_ut[u, ut, i]
                    for i in self.I
                )
            elif self.kappa_2_ut[u, ut] == 5:
                return self.REF_FLOW_UT[u, ut] == sum(
                    0.000277   # MWh/MJ conversion factor (1/3600) => uc parameter in thesis Phiilpp Kenkel
                    * self.CP[i]
                    * self.FLOW_IN[u, i]
                    * self.kappa_1_ut[u, ut, i]
                    for i in self.I
                )
            elif self.kappa_2_ut[u, ut] == 6:
                return self.REF_FLOW_UT[u, ut] == sum(
                    0.000277
                    * self.CP[i]
                    * self.FLOW_OUT[u, i]
                    * self.kappa_1_ut[u, ut, i]
                    for i in self.I
                )
            else:
                return self.REF_FLOW_UT[u, ut] == 0

        def UtilityBalance_2_rule(self, u, ut):
            return (
                self.ENERGY_DEMAND[u, ut] == self.REF_FLOW_UT[u, ut] * self.tau[u, ut]
            )

        def UtilityBalance_3_rule(self, ut):
            if ut == "Electricity":
                return self.ENERGY_DEMAND_TOT[ut] == sum(
                    self.ENERGY_DEMAND[u, ut] * self.flh[u] for u in self.U
                ) - sum(self.EL_PROD_1[u] * self.flh[u] for u in self.U_TUR)
            else:
                return self.ENERGY_DEMAND_TOT[ut] == sum(
                    self.ENERGY_DEMAND[u, ut] * self.flh[u] for u in self.U
                )

        # Electrictiy Balance for Production from Turbines

        def ElectricityBalance_1_rule(self, u):
            return self.EL_PROD_1[u] == self.Efficiency_TUR[u] * sum(
                self.LHV[i] * self.FLOW_IN[u, i] for i in self.I
            )

        self.ElectricityBalance_1 = Constraint(
            self.U_TUR, rule=ElectricityBalance_1_rule
        )
        self.UtilityBalance_1 = Constraint(self.U, self.UT, rule=UtilityBalance_1_rule)
        self.UtilityBalance_2 = Constraint(
            self.U, self.U_UT, rule=UtilityBalance_2_rule
        )
        self.UtilityBalance_3 = Constraint(self.U_UT, rule=UtilityBalance_3_rule)

        # Heat and Cooling Balance (Demand)

        def HeatBalance_1_rule(self, u, hi):
            return self.ENERGY_DEMAND_HEAT[u, hi] == sum(
                self.beta[u, ut, hi] * self.tau_c[ut, u] * self.REF_FLOW_UT[u, ut]
                for ut in self.H_UT
            )

        def HeatBalance_2_rule(self, u, hi):
            return self.ENERGY_DEMAND_COOL[u, hi] == sum(
                self.beta[u, ut, hi] * self.tau_h[ut, u] * self.REF_FLOW_UT[u, ut]
                for ut in self.H_UT
            )

        # Heating anc Cooling Balance (Either with or without Heat pump)
        # Rigorous HEN Optimization approach

        if self.heat_pump_options["active"] is True:
            hp_tin = self.heat_pump_options["t_in"]
            hp_tout = self.heat_pump_options["t_out"]

            def HeatBalance_3_rule(self, u, hi):
                k = len(self.HI)
                if hi == 1:
                    return (
                        sum(
                            self.ENERGY_DEMAND_HEAT[u, hi] * self.flh[u] / self.H
                            for u in self.U
                        )
                        + self.ENERGY_DEMAND_HEAT_PROD_USE
                        - self.ENERGY_DEMAND_HEAT_RESI[hi]
                        - self.ENERGY_EXCHANGE[hi]
                        == 0
                    )
                elif hi == hp_tin:
                    return (
                        sum(
                            self.ENERGY_DEMAND_HEAT[u, hi] * self.flh[u] / self.H
                            for u in self.U
                        )
                        + self.ENERGY_DEMAND_HEAT_RESI[hi - 1]
                        - self.ENERGY_DEMAND_HEAT_RESI[hi]
                        - self.ENERGY_DEMAND_HP
                        - self.ENERGY_EXCHANGE[hi]
                        == 0
                    )
                elif hi == k:
                    return (
                        sum(
                            self.ENERGY_DEMAND_HEAT[u, hi] * self.flh[u] / self.H
                            for u in self.U
                        )
                        + self.ENERGY_DEMAND_HEAT_RESI[hi - 1]
                        - self.ENERGY_DEMAND_COOLING
                        - self.ENERGY_EXCHANGE[hi]
                        == 0
                    )
                else:
                    return (
                        sum(
                            self.ENERGY_DEMAND_HEAT[u, hi] * self.flh[u] / self.H
                            for u in self.U
                        )
                        + self.ENERGY_DEMAND_HEAT_RESI[hi - 1]
                        - self.ENERGY_EXCHANGE[hi]
                        - self.ENERGY_DEMAND_HEAT_RESI[hi]
                        == 0
                    )

            def HeatBalance_4_rule(self, u, hi):
                if hi == 1:
                    return (
                        sum(
                            self.ENERGY_DEMAND_COOL[u, hi] * self.flh[u] / self.H
                            for u in self.U
                        )
                        - self.ENERGY_EXCHANGE[hi]
                        - self.ENERGY_DEMAND_HEAT_DEFI[hi]
                        == 0
                    )
                elif hi == hp_tout:
                    return (
                        sum(
                            self.ENERGY_DEMAND_COOL[u, hi] * self.flh[u] / self.H
                            for u in self.U
                        )
                        - self.ENERGY_DEMAND_HEAT_DEFI[hi]
                        - self.ENERGY_EXCHANGE[hi]
                        - self.ENERGY_DEMAND_HP_USE
                        == 0
                    )
                else:
                    return (
                        sum(
                            self.ENERGY_DEMAND_COOL[u, hi] * self.flh[u] / self.H
                            for u in self.U
                        )
                        - self.ENERGY_EXCHANGE[hi]
                        - self.ENERGY_DEMAND_HEAT_DEFI[hi]
                        == 0
                    )

            def HeatBalance_8_rule(self):
                return self.ENERGY_DEMAND_HP_USE == self.ENERGY_DEMAND_HP / (
                    1 - (1 / self.COP_HP)
                )

            def HeatBalance_9_rule(self):
                return self.ENERGY_DEMAND_HP_EL == self.ENERGY_DEMAND_HP / (
                    self.COP_HP - 1
                )

            self.HeatBalance_8 = Constraint(rule=HeatBalance_8_rule)
            self.HeatBalance_9 = Constraint(rule=HeatBalance_9_rule)

        else:

            def HeatBalance_3_rule(self, u, hi):
                k = len(self.HI)
                if hi == 1:
                    return (
                        sum(
                            self.ENERGY_DEMAND_HEAT[u, hi] * self.flh[u] / self.H
                            for u in self.U
                        )
                        + self.ENERGY_DEMAND_HEAT_PROD_USE
                        - self.ENERGY_DEMAND_HEAT_RESI[hi]
                        - self.ENERGY_EXCHANGE[hi]
                        == 0
                    )
                elif hi == k:
                    return (
                        sum(
                            self.ENERGY_DEMAND_HEAT[u, hi] * self.flh[u] / self.H
                            for u in self.U
                        )
                        + self.ENERGY_DEMAND_HEAT_RESI[hi - 1]
                        - self.ENERGY_DEMAND_COOLING
                        - self.ENERGY_EXCHANGE[hi]
                        == 0
                    )
                else:
                    return (
                        sum(
                            self.ENERGY_DEMAND_HEAT[u, hi] * self.flh[u] / self.H
                            for u in self.U
                        )
                        + self.ENERGY_DEMAND_HEAT_RESI[hi - 1]
                        - self.ENERGY_EXCHANGE[hi]
                        - self.ENERGY_DEMAND_HEAT_RESI[hi]
                        == 0
                    )

            def HeatBalance_4_rule(self, u, hi):
                return (
                    sum(
                        self.ENERGY_DEMAND_COOL[u, hi] * self.flh[u] / self.H
                        for u in self.U
                    )
                    - self.ENERGY_EXCHANGE[hi]
                    - self.ENERGY_DEMAND_HEAT_DEFI[hi]
                    == 0
                )

            def HeatBalance_8_rule(self):
                return self.ENERGY_DEMAND_HP_USE == 0

            def HeatBalance_9_rule(self):
                return self.ENERGY_DEMAND_HP_EL == 0

            self.HeatBalance_8 = Constraint(rule=HeatBalance_8_rule)
            self.HeatBalance_9 = Constraint(rule=HeatBalance_9_rule)

        #  Exchange Constraints, Production and Sell etc.
        def HeatBalance_5_rule(self, hi):
            return self.ENERGY_EXCHANGE[hi] <= sum(
                self.ENERGY_DEMAND_COOL[u, hi] * self.flh[u] / self.H for u in self.U
            )

        def HeatBalance_6_rule(self, hi):
            if hi == 1:
                return (
                    self.ENERGY_EXCHANGE[hi]
                    <= sum(
                        self.ENERGY_DEMAND_HEAT[u, hi] * self.flh[u] / self.H
                        for u in self.U
                    )
                    + self.ENERGY_DEMAND_HEAT_PROD_USE
                )
            else:
                return (
                    self.ENERGY_EXCHANGE[hi]
                    <= sum(
                        self.ENERGY_DEMAND_HEAT[u, hi] * self.flh[u] / self.H
                        for u in self.U
                    )
                    + self.ENERGY_DEMAND_HEAT_RESI[hi - 1]
                )

        def HeatBalance_7_rule(self):
            return self.EXCHANGE_TOT == sum(self.ENERGY_EXCHANGE[hi] for hi in self.HI)

        def HeatBalance_12_rule(self, hi):
            return self.ENERGY_EXCHANGE[hi] <= self.Y_HEX[hi] * self.alpha_hex

        def HeatBalance_13_rule(self, u):
            return self.ENERGY_DEMAND_HEAT_PROD[u] == self.Efficiency_FUR[u] * sum(
                self.LHV[i] * self.FLOW_IN[u, i] for i in self.I
            )

        def HeatBalance_14_rule(self, u):
            return self.ENERGY_DEMAND_HEAT_UNIT[u] == sum(
                self.ENERGY_DEMAND_COOL[u, hi] for hi in self.HI
            )

        def HeatBalance_15_rule(self, u):
            return self.ENERGY_DEMAND_COOL_UNIT[u] == sum(
                self.ENERGY_DEMAND_HEAT[u, hi] for hi in self.HI
            )

        def HeatBalance_16_rule(self):
            return (
                self.ENERGY_DEMAND_HEAT_PROD_USE
                == sum(
                    self.ENERGY_DEMAND_HEAT_PROD[u] * self.flh[u] / self.H
                    for u in self.U_FUR
                )
                - self.ENERGY_DEMAND_HEAT_PROD_SELL
            )

        self.HeatBalance_1 = Constraint(self.U, self.HI, rule=HeatBalance_1_rule)
        self.HeatBalance_2 = Constraint(self.U, self.HI, rule=HeatBalance_2_rule)
        self.HeatBalance_3 = Constraint(self.U, self.HI, rule=HeatBalance_3_rule)
        self.HeatBalance_4 = Constraint(self.U, self.HI, rule=HeatBalance_4_rule)
        self.HeatBalance_5 = Constraint(self.HI, rule=HeatBalance_5_rule)
        self.HeatBalance_6 = Constraint(self.HI, rule=HeatBalance_6_rule)
        self.HeatBalance_7 = Constraint(rule=HeatBalance_7_rule)

        self.HeatBalance_12 = Constraint(self.HI, rule=HeatBalance_12_rule)
        self.HeatBalance_13 = Constraint(self.U_FUR, rule=HeatBalance_13_rule)
        self.HeatBalance_14 = Constraint(self.U, rule=HeatBalance_14_rule)
        self.HeatBalance_15 = Constraint(self.U, rule=HeatBalance_15_rule)
        self.HeatBalance_16 = Constraint(rule=HeatBalance_16_rule)

    # **** COST BALANCES *****
    # -------------------------

    def create_EconomicEvaluation(self):
        """
        Description
        -------
        This method creates the PYOMO parameters and variables
        that are necessary for the general Cost Calculation (eg. detla_ut, COST_UT etc.).
        Afterward Cost calculation equations are written as PYOMO Constraints.
        """

        # Parameter
        # ---------

        # Specific costs (Utility, raw materials, Product prices)

        self.delta_ut = Param(self.U_UT, initialize=0)
        self.delta_q = Param(self.HI, initialize=30)
        self.delta_cool = Param(initialize=15)
        self.ProductPrice = Param(self.U_PP, initialize=0, mutable=True)

        # Cost factors (CAPEX, Heat Pump)
        self.DC = Param(self.U, initialize=0)
        self.IDC = Param(self.U, initialize=0)
        self.ACC_Factor = Param(self.U, initialize=0)

        self.HP_ACC_Factor = Param(initialize=1)
        self.HP_Costs = Param(initialize=1)

        # Piecewise Linear CAPEX
        self.lin_CAPEX_x = Param(self.U_C, self.J, initialize=0)
        self.lin_CAPEX_y = Param(self.U_C, self.J, initialize=0)
        self.kappa_1_capex = Param(self.U_C, self.I, initialize=0)
        self.kappa_2_capex = Param(self.U_C, initialize=5)

        # OPEX factors

        self.K_OM = Param(self.U_C, initialize=0.04)

        # Variables
        # ---------

        # Utilitiy Costs ( El, Heat, El-TOT, HEN)
        self.ENERGY_COST = Var(self.U_UT)
        self.COST_HEAT = Var(self.HI)
        self.COST_UT = Var()
        self.ELCOST = Var()
        self.HEATCOST = Var(self.HI)
        self.C_TOT = Var()
        self.HENCOST = Var(self.HI, within=NonNegativeReals)
        self.UtCosts = Var()

        # Piece-Wise Linear CAPEX
        self.lin_CAPEX_s = Var(self.U_C, self.JI, bounds=(0, 1))
        self.lin_CAPEX_z = Var(self.U_C, self.JI, within=Binary)
        self.lin_CAPEX_lambda = Var(self.U_C, self.J, bounds=(0, 1))
        self.REF_FLOW_CAPEX = Var(self.U_C, within=NonNegativeReals)

        # CAPEX (Units, Returning costs, Heat Pump, Total)
        self.EC = Var(self.U_C, within=NonNegativeReals)
        self.FCI = Var(self.U_C, within=NonNegativeReals)
        self.ACC = Var(self.U_C, within=NonNegativeReals)
        self.to_acc = Param(self.U_C, initialize=0)
        self.TO_CAPEX = Var(self.U_C, within=NonNegativeReals)
        self.TO_CAPEX_TOT = Var(within=NonNegativeReals)
        self.ACC_HP = Var(within=NonNegativeReals)
        self.TAC = Var()
        self.CAPEX = Var()

        # OPEX (Raw Materials, O&M, , UtilitiesTotal, Profits)
        self.RM_COST = Var(self.U_C, within=NonNegativeReals)
        self.RM_COST_TOT = Var(within=NonNegativeReals)
        self.M_COST = Var(self.U_C)
        self.M_COST_TOT = Var(within=NonNegativeReals)
        self.O_H = Var()
        self.O_COST = Var()
        self.OM_COST = Var(within=NonNegativeReals)
        self.OPEX = Var()
        self.PROFITS = Var(self.U_PP)
        self.PROFITS_TOT = Var()

        # Constraints
        # -----------

        # CAPEX Calculation (Reference Flow, Piece-Wise linear Lambda Constraints)

        def CapexEquation_1_rule(self, u):
            if self.kappa_2_capex[u] == 1:
                return self.REF_FLOW_CAPEX[u] == sum(
                    self.FLOW_IN[u, i] * self.kappa_1_capex[u, i] for i in self.I
                )
            elif self.kappa_2_capex[u] == 0:
                return self.REF_FLOW_CAPEX[u] == sum(
                    self.FLOW_OUT[u, i] * self.kappa_1_capex[u, i] for i in self.I
                )
            elif self.kappa_2_capex[u] == 2:
                return self.REF_FLOW_CAPEX[u] == self.ENERGY_DEMAND[u, "Electricity"]

            elif self.kappa_2_capex[u] == 3:
                return self.REF_FLOW_CAPEX[u] == self.ENERGY_DEMAND_HEAT_PROD[u]

            elif self.kappa_2_capex[u] == 4:
                return self.REF_FLOW_CAPEX[u] == self.EL_PROD_1[u]
            else:
                return self.REF_FLOW_CAPEX[u] == 0

        def CapexEquation_2_rule(self, u):
            return (
                sum(
                    self.lin_CAPEX_x[u, j] * self.lin_CAPEX_lambda[u, j] for j in self.J
                )
                == self.REF_FLOW_CAPEX[u]
            )

        def CapexEquation_3_rule(self, u):
            return self.EC[u] == sum(
                self.lin_CAPEX_y[u, j] * self.lin_CAPEX_lambda[u, j] for j in self.J
            )

        def CapexEquation_4_rule(self, u):
            return sum(self.lin_CAPEX_z[u, j] for j in self.JI) == 1

        def CapexEquation_5_rule(self, u, j):
            return self.lin_CAPEX_s[u, j] <= self.lin_CAPEX_z[u, j]

        def CapexEquation_6_rule(self, u, j):
            if j == 1:
                return (
                    self.lin_CAPEX_lambda[u, j]
                    == self.lin_CAPEX_z[u, j] - self.lin_CAPEX_s[u, j]
                )
            elif j == len(self.J):
                return self.lin_CAPEX_lambda[u, j] == self.lin_CAPEX_s[u, j - 1]
            else:
                return (
                    self.lin_CAPEX_lambda[u, j]
                    == self.lin_CAPEX_z[u, j]
                    - self.lin_CAPEX_s[u, j]
                    + self.lin_CAPEX_s[u, j - 1]
                )

        # Fixed Capital investment, Annual capital costs, Heat Pump, Returning costs, Total
        def CapexEquation_7_rule(self, u):
            return self.FCI[u] == self.EC[u] * (1 + self.DC[u] + self.IDC[u])

        def CapexEquation_8_rule(self, u):
            return self.ACC[u] == self.FCI[u] * self.ACC_Factor[u]

        self.ACC_H = Var(within=NonNegativeReals)

        def CapexEquation_9_rule(self):
            return (
                self.ACC_H
                == self.HP_ACC_Factor * self.HP_Costs * self.ENERGY_DEMAND_HP_USE
            )

        def Cap(self):
            return self.ACC_HP == self.ACC_H / 1000

        self.Xap = Constraint(rule=Cap)

        # reoccuring costs of equipment
        # --------------------------------
        def CapexEquation_11_rule(self, u):
            return self.TO_CAPEX[u] == self.to_acc[u] * self.EC[u]

        def CapexEquation_12_rule(self):
            return self.TO_CAPEX_TOT == sum(self.TO_CAPEX[u] for u in self.U_C)
        # --------------------------------

        # the three equations below are for the HEN CAPITAL COSTS (CAPEX)
        # not realted to the operating costs of HEN
        # --------------------------------------------------------------------
        def HEN_CostBalance_4_rule(self, hi):
            return self.HENCOST[hi] <= 13.459 * self.ENERGY_EXCHANGE[
                hi
            ] + 3.3893 + self.alpha_hex * (1 - self.Y_HEX[hi])
        def HEN_CostBalance_4b_rule(self, hi):
            return self.HENCOST[hi] >= 13.459 * self.ENERGY_EXCHANGE[
                hi
            ] + 3.3893 - self.alpha_hex * (1 - self.Y_HEX[hi])
        def HEN_CostBalance_4c_rule(self, hi):
            return self.HENCOST[hi] <= self.Y_HEX[hi] * self.alpha_hex
        # --------------------------------------------------------------------

        def CapexEquation_10_rule(self):
            return (
                self.CAPEX
                == sum(self.ACC[u] for u in self.U_C)      # annual capital costs
                + self.ACC_HP/1000                         # heat pump capital costs
                + self.TO_CAPEX_TOT                        # reoccurring costs of equipment
                + sum(self.HENCOST[hi] for hi in self.HI)  # HEN capital costs
            )

        self.CapexEquation_1 = Constraint(self.U_C, rule=CapexEquation_1_rule)
        self.CapexEquation_2 = Constraint(self.U_C, rule=CapexEquation_2_rule)
        self.CapexEquation_3 = Constraint(self.U_C, rule=CapexEquation_3_rule)
        self.CapexEquation_4 = Constraint(self.U_C, rule=CapexEquation_4_rule)
        self.CapexEquation_5 = Constraint(self.U_C, self.JI, rule=CapexEquation_5_rule)
        self.CapexEquation_6 = Constraint(self.U_C, self.J, rule=CapexEquation_6_rule)
        self.CapexEquation_7 = Constraint(self.U_C, rule=CapexEquation_7_rule)
        self.CapexEquation_8 = Constraint(self.U_C, rule=CapexEquation_8_rule)
        self.CapexEquation_9 = Constraint(rule=CapexEquation_9_rule)

        self.HEN_CostBalance_4 = Constraint(self.HI, rule=HEN_CostBalance_4_rule)
        self.HEN_CostBalance_4b = Constraint(self.HI, rule=HEN_CostBalance_4b_rule)
        self.HEN_CostBalance_4c = Constraint(self.HI, rule=HEN_CostBalance_4c_rule)

        self.CapexEquation_10 = Constraint(rule=CapexEquation_10_rule)
        self.CapexEquation_11 = Constraint(self.U_C, rule=CapexEquation_11_rule)
        self.CapexEquation_12 = Constraint(rule=CapexEquation_12_rule)

        # OPEX Calculation (HEN Costs: Heating / Cooling, CAPEX)

        def HEN_CostBalance_1_rule(self, hi):
            return (
                self.HEATCOST[hi]
                == self.ENERGY_DEMAND_HEAT_DEFI[hi] * self.delta_q[hi] * self.H
            )

        def HEN_CostBalance_2_rule(self):
            return self.UtCosts == (
                sum(self.HEATCOST[hi] for hi in self.HI)
                - self.ENERGY_DEMAND_HEAT_PROD_SELL * self.H * self.delta_q[1] * 0.7
                + self.ENERGY_DEMAND_COOLING * self.H * self.delta_cool
            )

        def HEN_CostBalance_3_rule(self):
            return (
                self.ELCOST
                == self.ENERGY_DEMAND_HP_EL
                * self.delta_ut["Electricity"]
                * self.H
                / 1000
            )

        # selling buying of energy see UtCosts (HEN_CostBalance_2_rule)
        def HEN_CostBalance_6_rule(self):
            return self.C_TOT == self.UtCosts/1000


        self.HEN_CostBalance_1 = Constraint(self.HI, rule=HEN_CostBalance_1_rule)
        self.HEN_CostBalance_2 = Constraint(rule=HEN_CostBalance_2_rule)
        self.HEN_CostBalance_3 = Constraint(rule=HEN_CostBalance_3_rule)
        self.HEN_CostBalance_6 = Constraint(rule=HEN_CostBalance_6_rule)

        # Utility Costs (Electricity/Chilling)

        def Ut_CostBalance_1_rule(self, ut):
            return (
                self.ENERGY_COST[ut]
                == self.ENERGY_DEMAND_TOT[ut] * self.delta_ut[ut] / 1000 # euro to million euro conversion
            )

        self.Ut_CostBalance_1 = Constraint(self.U_UT, rule=Ut_CostBalance_1_rule)

        # Raw Materials and Operating and Maintenance

        def RM_CostBalance_1_rule(self):
            return self.RM_COST_TOT == sum(
                self.materialcosts[u_s] * self.FLOW_SOURCE[u_s] * self.flh[u_s] / 1000 # euro to million euro conversion
                for u_s in self.U_S
            )

        def OM_CostBalance_1_rule(self, u):
            return self.M_COST[u] == self.K_OM[u] * self.FCI[u] # in million euro (M€)

        def OM_CostBalance_2_rule(self):
            return self.M_COST_TOT == sum(self.M_COST[u] for u in self.U_C)

        # Total OPEX
        def Opex_1_rule(self): # im M€ (million euro)
            return (
                self.OPEX
                == self.M_COST_TOT                                 # operating and maintenance costs
                + self.RM_COST_TOT/1000                                 # raw material costs
                + sum(self.ENERGY_COST[ut] for ut in self.U_UT)/1000    # utility costs energy
                + self.C_TOT   /1000                                    # selling or buying of energy (from HEN)
                + self.ELCOST /1000                                      # electricity costs for heat pump
            )

        self.RM_CostBalance_1 = Constraint(rule=RM_CostBalance_1_rule)
        self.OM_CostBalance_1 = Constraint(self.U_C, rule=OM_CostBalance_1_rule)
        self.OM_CostBalance_2 = Constraint(rule=OM_CostBalance_2_rule)
        self.OpexEquation = Constraint(rule=Opex_1_rule)

        # Profits

        def Profit_1_rule(self, u): # in M€ (million euro)
            return (
                self.PROFITS[u]
                == sum(self.FLOW_IN[u, i] for i in self.I) * self.ProductPrice[u] / 1000
            )

        def Profit_2_rule(self):
            return (
                self.PROFITS_TOT
                == sum(self.PROFITS[u] for u in self.U_PP) * self.H / 1000
            )

        self.ProfitEquation_1 = Constraint(self.U_PP, rule=Profit_1_rule)
        self.ProfitEquation_2 = Constraint(rule=Profit_2_rule)

        # Total Annualized Costs

        def TAC_1_rule(self):
            return self.TAC == (self.CAPEX + self.OPEX - self.PROFITS_TOT) * 1000

        self.TAC_Equation = Constraint(rule=TAC_1_rule)

    # **** ENVIRONMENTAL BALANCES *****
    # -------------------------

    def create_EnvironmentalEvaluation(self):
        """
        Description
        -------
        This method creates the PYOMO parameters and variables
        that are necessary for the general CO2 Emissions (eg. emission factors etc.).
        Afterwards Emission equations are written as PYOMO Constraints.

        """

        # Parameter
        # --------

        # Emission factors (Utilities, Components, Products, Building of units)
        self.em_fac_ut = Param(self.UT, initialize=0)
        self.em_fac_comp = Param(self.I, initialize=0)
        self.em_fac_prod = Param(self.U_PP, initialize=0)
        self.em_fac_unit = Param(self.U_C, initialize=0)
        self.em_fac_source = Param(self.U_S, initialize=0)

        # Lifetime of Units
        self.LT = Param(self.U, initialize=1)

        # Variables
        # ---------

        self.GWP_UNITS = Var(self.U_C)
        self.GWP_CREDITS = Var(self.U_PP)
        self.GWP_CAPTURE = Var()
        self.GWP_U = Var(self.U)
        self.GWP_UT = Var(self.UT)
        self.GWP_TOT = Var()

        # Constraints
        # -----------

        def GWP_1_rule(self, u):
            return self.GWP_U[u] == self.flh[u] * sum(
                self.FLOW_WASTE[u, i] * self.em_fac_comp[i] for i in self.I
            )

        def GWP_2_rule(self, ut):
            if ut == "Electricity":
                return (
                    self.GWP_UT[ut]
                    == (self.ENERGY_DEMAND_TOT[ut] + self.ENERGY_DEMAND_HP_EL * self.H)
                    * self.em_fac_ut[ut]
                )
            else:
                return (
                    self.GWP_UT[ut] == self.ENERGY_DEMAND_TOT[ut] * self.em_fac_ut[ut]
                )

        def GWP_3_rule(self):
            return self.GWP_UT["Heat"] == self.em_fac_ut["Heat"] * self.H * (
                sum(self.ENERGY_DEMAND_HEAT_DEFI[hi] for hi in self.HI)
                - self.ENERGY_DEMAND_HEAT_PROD_SELL * 0.7
            )

        def GWP_5_rule(self):
            return self.GWP_UT["Heat2"] == 0

        def GWP_6_rule(self, u):
            return self.GWP_UNITS[u] == self.em_fac_unit[u] / self.LT[u] * self.Y[u]

        def GWP_7_rule(self, u):
            return (
                self.GWP_CREDITS[u]
                == self.em_fac_prod[u]
                * sum(self.FLOW_IN[u, i] for i in self.I)
                * self.flh[u]
            )

        def GWP_8_rule(self):
            return self.GWP_CAPTURE == sum(
                self.FLOW_SOURCE[u_s] * self.flh[u_s] * self.em_fac_source[u_s]
                for u_s in self.U_S
            )

        def GWP_4_rule(self):
            return self.GWP_TOT == sum(self.GWP_U[u] for u in self.U_C) + sum(
                self.GWP_UT[ut] for ut in self.UT
            ) - self.GWP_CAPTURE - sum(self.GWP_CREDITS[u] for u in self.U_PP) + sum(
                self.GWP_UNITS[u] for u in self.U_C
            )

        self.EnvironmentalEquation1 = Constraint(self.U_C, rule=GWP_1_rule)
        self.EnvironmentalEquation2 = Constraint(self.U_UT, rule=GWP_2_rule)
        self.EnvironmentalEquation3 = Constraint(rule=GWP_3_rule)
        self.EnvironmentalEquation4 = Constraint(rule=GWP_4_rule)
        self.EnvironmentalEquation5 = Constraint(rule=GWP_5_rule)
        self.EnvironmentalEquation6 = Constraint(self.U_C, rule=GWP_6_rule)
        self.EnvironmentalEquation7 = Constraint(self.U_PP, rule=GWP_7_rule)
        self.EnvironmentalEquation8 = Constraint(rule=GWP_8_rule)

    # **** FRESH WATER DEMAND EQUATIONS
    # --------------------------------------

    def create_FreshwaterEvaluation(self):
        """

        Description
        -------
        This method creates the PYOMO parameters and variables
        that are necessary for the general Fresh water demand (eg. demand factors etc.).
        Afterwards FWD equations are written as PYOMO Constraints.

        """

        self.FWD_UT1 = Var()
        self.FWD_UT2 = Var()
        self.FWD_S = Var()
        self.FWD_C = Var()
        self.FWD_TOT = Var()

        self.fw_fac_source = Param(self.U_S, initialize=0)
        self.fw_fac_ut = Param(self.UT, initialize=0)
        self.fw_fac_prod = Param(self.U_PP, initialize=0)

        def FWD_1_rule(self):
            return self.FWD_S == sum(
                self.FLOW_SOURCE[u_s] * self.fw_fac_source[u_s] * self.flh[u_s]
                for u_s in self.U_S
            )

        def FWD_2_rule(self):
            return self.FWD_C == sum(
                sum(self.FLOW_IN[u_p, i] for i in self.I)
                * self.flh[u_p]
                * self.fw_fac_prod[u_p]
                for u_p in self.U_PP
            )

        def FWD_3_rule(self):
            return self.FWD_UT1 == sum(
                self.ENERGY_DEMAND_TOT[ut] * self.fw_fac_ut[ut] for ut in self.U_UT
            )

        def FWD_4_rule(self):
            return (
                self.FWD_UT2
                == (
                    sum(self.ENERGY_DEMAND_HEAT_DEFI[hi] for hi in self.HI)
                    - self.ENERGY_DEMAND_HEAT_PROD_SELL * 0.7
                )
                * self.H
                * self.fw_fac_ut["Heat"]
            )

        def FWD_5_rule(self):
            return self.FWD_TOT == self.FWD_UT2 + self.FWD_UT1 - self.FWD_S - self.FWD_C

        self.FreshWaterEquation1 = Constraint(rule=FWD_1_rule)
        self.FreshWaterEquation2 = Constraint(rule=FWD_2_rule)
        self.FreshWaterEquation3 = Constraint(rule=FWD_3_rule)
        self.FreshWaterEquation4 = Constraint(rule=FWD_4_rule)
        self.FreshWaterEquation5 = Constraint(rule=FWD_5_rule)

    # **** DECISION MAKING EQUATIONS *****
    # -------------------------

    def create_DecisionMaking(self):
        """


        Description
        -------
        This function creates additional (optional) logic contraints of
        the flowsheet topology.

        """

        # Parameter
        # --------

        numbers = [1, 2, 3]

        # Variables
        # ---------

        # Constraints
        # -----------

        def ProcessGroup_logic_1_rule(self, u, uu):

            ind = False

            for i, j in self.groups.items():

                if u in j and uu in j:
                    return self.Y[u] == self.Y[uu]
                    ind = True

            if ind == False:
                return Constraint.Skip

        def ProcessGroup_logic_2_rule(self, u, k):

            ind = False

            for i, j in self.connections.items():
                if u == i:
                    if j[k]:
                        return sum(self.Y[uu] for uu in j[k]) >= self.Y[u]
                        ind = True

            if ind == False:
                return Constraint.Skip

        self.ProcessGroup_logic_1 = Constraint(self.U, self.UU, rule=ProcessGroup_logic_1_rule)

        self.ProcessGroup_logic_2 = Constraint(self.U, numbers, rule=ProcessGroup_logic_2_rule)


    # **** OBJECTIVE FUNCTIONS *****
    # -------------------------

    def create_ObjectiveFunction(self):
        """


        Description
        -------
        Defines the main product flow and the objetive function.

        """

        # Parameter
        # ---------

        self.ProductLoad = Param()


        # Variables
        # ---------

        self.MainProductFlow = Var()

        self.NPC = Var()
        self.NPFWD = Var()
        self.NPE = Var()
        self.EBIT = Var()
        self.SumOfProductFlows = Var()

        # Constraints
        # -----------

        # Definition of Main Product and Product Load for NPC / NPE Calculation

        def SumOfProducts_rule(self):
            return self.SumOfProductFlows == sum(self.FLOW_IN[U_pp, i]
                                             for U_pp in self.U_PP
                                             for i in self.I
                                             ) * self.H

        self.SumOfProducts_Equation = Constraint(rule=SumOfProducts_rule)



        def MainProduct_1_rule(self):
            # If product driven, skip this constraint
            if self.productDriven == "no":
                return Constraint.Skip
            else:
                return (
                    self.MainProductFlow
                    == sum(self.FLOW_IN[self.main_pool, i] for i in self.I) * self.H
                )
        def MainProduct_2_rule(self):
            if self.productDriven == "no":
                return Constraint.Skip
            else:
                return self.MainProductFlow == self.ProductLoad

        self.MainProduct_Equation_1 = Constraint(rule=MainProduct_1_rule)
        self.MainProduct_Equation_2 = Constraint(rule=MainProduct_2_rule)

        # Definition of specific fucntion

        def Specific_NPC_rule(self): # in € per year (euro/ton/year)
            # ProductLoad is 1 is substrate driven, otherwise it is the target production
            return self.NPC == (self.TAC * 1000)/self.ProductLoad # in € per tonne of product per year (so your target production)


        def Specific_GWP_rule(self):
            return self.NPE == self.GWP_TOT / self.ProductLoad
            #return self.NPE == self.GWP_TOT

        def Specific_FWD_rule(self):
            return self.NPFWD == self.FWD_TOT / self.ProductLoad
            #return self.NPFWD == self.FWD_TOT

        def Specific_EBIT_rule(self):
            return self.EBIT == (self.PROFITS_TOT - self.CAPEX - self.OPEX)  # in M€ (million euro)

        self.Specific_NPC_rule = Constraint(rule=Specific_NPC_rule)
        self.Specific_GWP_rule = Constraint(rule=Specific_GWP_rule)
        self.Specific_FWD_rule = Constraint(rule=Specific_FWD_rule)
        self.Specific_EBIT_rule = Constraint(rule=Specific_EBIT_rule)

        # Definition of the used Objective Function

        if self.objective_name == "NPC":

            def Objective_rule(self):
                return self.NPC

        elif self.objective_name == "NPE":

            def Objective_rule(self):
                return self.NPE

        elif self.objective_name == "FWD":

            def Objective_rule(self):
                return self.NPFWD

        elif self.objective_name == "EBIT":
                def Objective_rule(self):
                    return self.EBIT

        else:
            def Objective_rule(self):
                return self.NPC

        if self.objective_name == "EBIT":
            self.Objective = Objective(rule=Objective_rule, sense=maximize)

        else: # want to minimise the other objective functions
            self.Objective = Objective(rule=Objective_rule, sense=minimize)

        self.objective_sense = Var(initialize=0, within=Binary)

        def objective_sense_rule1(self):
            if self.objective_name == "EBIT":
                return self.objective_sense == 1  # 1 for maximizing
            else:
                return self.objective_sense == 0  # 0 for minimizing

        self.objective_sense_rule = Constraint(rule=objective_sense_rule1)
