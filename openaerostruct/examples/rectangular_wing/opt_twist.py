"""
Perform inviscid drag minimization of rectangular wing with respect to spanwise
twist, subject to a lift constraint. The expected result from lifting line
theory should produce an elliptical lift distrbution. Check output directory for
Tecplot solution files.
"""

import numpy as np

import openmdao.api as om

from openaerostruct.meshing.mesh_generator import generate_mesh
from openaerostruct.geometry.geometry_group import Geometry
from openaerostruct.aerodynamics.aero_groups import AeroPoint


# Instantiate the problem and the model group
prob = om.Problem()

# Define flight variables as independent variables of the model
indep_var_comp = om.IndepVarComp()
indep_var_comp.add_output("v", val=248.136, units="m/s")  # Freestream Velocity
indep_var_comp.add_output("alpha", val=5.0, units="deg")  # Angle of Attack
indep_var_comp.add_output("beta", val=0.0, units="deg")  # Sideslip angle
indep_var_comp.add_output("omega", val=np.zeros(3), units="deg/s")  # Rotation rate
indep_var_comp.add_output("Mach_number", val=0.0)  # Freestream Mach number
indep_var_comp.add_output("re", val=1.0e6, units="1/m")  # Freestream Reynolds number
indep_var_comp.add_output("rho", val=0.38, units="kg/m**3")  # Freestream air density
indep_var_comp.add_output("cg", val=np.zeros((3)), units="m")  # Aircraft center of gravity
# Add vars to model, promoting is a quick way of automatically connecting inputs
# and outputs of different OpenMDAO components
prob.model.add_subsystem("flight_vars", indep_var_comp, promotes=["*"])

# Create a dictionary to store options about the surface
mesh_dict = {
    "num_y": 35,
    "num_x": 11,
    "wing_type": "rect",
    "symmetry": True,
    "span": 10.0,
    "root_chord": 1,
    "span_cos_spacing": 1.0,
    "chord_cos_spacing": 1.0,
}

# Generate half-wing mesh of rectangular wing
mesh = generate_mesh(mesh_dict)

# Define input surface dictionary for our wing
surface = {
    # Wing definition
    "name": "wing",  # name of the surface
    "type": "aero",
    "symmetry": True,  # if true, model one half of wing
    # reflected across the plane y = 0
    "S_ref_type": "projected",  # how we compute the wing area,
    # can be 'wetted' or 'projected'
    "twist_cp": np.zeros(3),  # Define twist using 3 B-spline cp's
    "ref_axis_pos": 0.25,  # Define the reference axis position. 0 is the leading edge, 1 is the trailing edge.
    # distributed along span
    "mesh": mesh,
    # Aerodynamic performance of the lifting surface at
    # an angle of attack of 0 (alpha=0).
    # These CL0 and CD0 values are added to the CL and CD
    # obtained from aerodynamic analysis of the surface to get
    # the total CL and CD.
    # These CL0 and CD0 values do not vary wrt alpha.
    "CL0": 0.0,  # CL of the surface at alpha=0
    "CD0": 0.0,  # CD of the surface at alpha=0
    # Airfoil properties for viscous drag calculation
    "k_lam": 0.05,  # percentage of chord with laminar
    # flow, used for viscous drag
    "t_over_c": 0.12,  # thickness over chord ratio (NACA0015)
    "c_max_t": 0.303,  # chordwise location of maximum (NACA0015)
    # thickness
    "with_viscous": False,  # if true, compute viscous drag,
    "with_wave": False,
}  # end of surface dictionary

name = surface["name"]

# Add geometry to the problem as the name of the surface.
# These groups are responsible for manipulating the geometry of the mesh,
# in this case spanwise twist.
geom_group = Geometry(surface=surface)
prob.model.add_subsystem(name, geom_group)

# Create the aero point group for this flight condition and add it to the model
aero_group = AeroPoint(surfaces=[surface], rotational=True)
point_name = "aero_point_0"
prob.model.add_subsystem(
    point_name, aero_group, promotes_inputs=["v", "alpha", "beta", "omega", "Mach_number", "re", "rho", "cg"]
)

# Connect the mesh from the geometry component to the analysis point
prob.model.connect(name + ".mesh", point_name + "." + name + ".def_mesh")

# Perform the connections with the modified names within the
# 'aero_states' group.
prob.model.connect(name + ".mesh", point_name + ".aero_states." + name + "_def_mesh")

# Set optimizer as model driver
prob.driver = om.ScipyOptimizeDriver()
prob.driver.options["debug_print"] = ["nl_cons", "objs", "desvars"]

# Setup problem and add design variables, constraint, and objective
prob.model.add_design_var("wing.twist_cp", lower=-10.0, upper=15.0)
prob.model.add_constraint(point_name + ".wing_perf.CL", equals=0.5)
prob.model.add_objective(point_name + ".wing_perf.CD", scaler=1e4)

# Set up the problem
prob.setup()

# Run optimization
prob.run_driver()
