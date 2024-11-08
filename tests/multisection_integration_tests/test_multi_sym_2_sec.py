from openmdao.utils.assert_utils import assert_near_equal
import unittest


class Test(unittest.TestCase):
    def test(self):
        import numpy as np

        import openmdao.api as om

        from openaerostruct.geometry.geometry_group import MultiSecGeometry
        from openaerostruct.aerodynamics.aero_groups import AeroPoint
        from openaerostruct.geometry.geometry_group import build_sections
        from openaerostruct.geometry.geometry_unification import unify_mesh
        from openaerostruct.geometry.multi_unified_bspline_utils import build_multi_spline, connect_multi_spline

        try:
            import pyoptsparse

            SNOPT = pyoptsparse.Optimizers.SNOPT
            if SNOPT:
                SNOPT_FLAG = True
            else:
                SNOPT_FLAG = False
        except ImportError:
            SNOPT_FLAG = False

        SNOPT_FLAG = False
        # Set-up B-splines for each section. Done here since this information will be needed multiple times.
        sec_chord_cp = [np.array([1.0, 1.0]), np.array([1.0, 1.0])]

        # Create a dictionary with info and options about the multi-section aerodynamic
        # lifting surface
        surface = {
            # Wing definition
            # Basic surface parameters
            "name": "surface",
            "isMultiSection": True,
            "num_sections": 2,  # The number of sections in the multi-section surface
            "sec_name": ["sec0", "sec1"],  # names of the individual sections
            "symmetry": True,  # if true, model one half of wing. reflected across the midspan of the root section
            "S_ref_type": "wetted",  # how we compute the wing area, can be 'wetted' or 'projected'
            "rootSection": 1,
            # Geometry Parameters
            "taper": [1.0, 1.0],  # Wing taper for each section
            "span": [1.0, 1.0],  # Wing span for each section
            "sweep": [0.0, 0.0],  # Wing sweep for each section
            "chord_cp": sec_chord_cp,
            "twist_cp": [np.zeros(2), np.zeros(2)],
            # "chord_cp": [np.ones(1),2*np.ones(1),3*np.ones(1)], #Chord B-spline control points for each section
            "root_chord": 1.0,  # Wing root chord for each section
            # Mesh Parameters
            "meshes": "gen-meshes",  # Supply a mesh for each section or "gen-meshes" for automatic mesh generation
            "nx": 2,  # Number of chordwise points. Same for all sections
            "ny": [21, 21],  # Number of spanwise points for each section
            # Aerodynamic Parameters
            "CL0": 0.0,  # CL of the surface at alpha=0
            "CD0": 0.015,  # CD of the surface at alpha=0
            # Airfoil properties for viscous drag calculation
            "k_lam": 0.05,  # percentage of chord with laminar
            # flow, used for viscous drag
            # "t_over_c_cp": [np.array([0.15]),np.array([0.15])],  # thickness over chord ratio (NACA0015)
            "c_max_t": 0.303,  # chordwise location of maximum (NACA0015)
            # thickness
            "with_viscous": False,  # if true, compute viscous drag
            "with_wave": False,  # if true, compute wave drag
            "groundplane": False,
        }

        # Create the OpenMDAO problem for the constrained version
        prob1 = om.Problem()

        # Create the OpenMDAO problem for the constructed version
        prob2 = om.Problem()

        # Create an independent variable component that will supply the flow
        # conditions to the problem.
        indep_var_comp = om.IndepVarComp()
        indep_var_comp.add_output("v", val=1.0, units="m/s")
        indep_var_comp.add_output("alpha", val=10.0, units="deg")
        indep_var_comp.add_output("Mach_number", val=0.3)
        indep_var_comp.add_output("re", val=1.0e5, units="1/m")
        indep_var_comp.add_output("rho", val=0.38, units="kg/m**3")
        indep_var_comp.add_output("cg", val=np.zeros((3)), units="m")

        # Add this IndepVarComp to the problem model
        prob1.model.add_subsystem("prob_vars", indep_var_comp, promotes=["*"])
        prob2.model.add_subsystem("prob_vars", indep_var_comp, promotes=["*"])

        # Generate the sections and unified mesh here in addition to adding the components.
        # This has to also be done here since AeroPoint has to know the unified mesh size.
        section_surfaces = build_sections(surface)
        uniMesh = unify_mesh(section_surfaces)
        surface["mesh"] = uniMesh

        # Build a component with B-spline control points that joins the sections by construction
        chord_comp = build_multi_spline("chord_cp", len(section_surfaces), sec_chord_cp)
        prob2.model.add_subsystem("chord_bspline", chord_comp)

        # Connect the B-spline component to the section B-splines
        connect_multi_spline(prob2, section_surfaces, sec_chord_cp, "chord_cp", "chord_bspline")

        # Create and add a group that handles the geometry for the
        # aerodynamic lifting surface
        multi_geom_group_constraint = MultiSecGeometry(
            surface=surface, joining_comp=True, dim_constr=[np.array([1, 0, 0]), np.array([1, 0, 0])]
        )
        multi_geom_group = MultiSecGeometry(surface=surface)
        prob1.model.add_subsystem(surface["name"], multi_geom_group_constraint)
        prob2.model.add_subsystem(surface["name"], multi_geom_group)

        # Create the aero point group, which contains the actual aerodynamic
        # analyses
        aero_group = AeroPoint(surfaces=[surface])
        point_name = "aero_point_0"
        prob1.model.add_subsystem(
            point_name, aero_group, promotes_inputs=["v", "alpha", "Mach_number", "re", "rho", "cg"]
        )
        prob2.model.add_subsystem(
            point_name, aero_group, promotes_inputs=["v", "alpha", "Mach_number", "re", "rho", "cg"]
        )

        # Get name of surface and construct unified mesh name
        name = surface["name"]
        unification_name = "{}_unification".format(surface["name"])

        # Connect the mesh from the mesh unification component to the analysis point
        prob1.model.connect(
            name + "." + unification_name + "." + name + "_uni_mesh", point_name + "." + "surface" + ".def_mesh"
        )
        prob2.model.connect(
            name + "." + unification_name + "." + name + "_uni_mesh", point_name + "." + "surface" + ".def_mesh"
        )

        # Perform the connections with the modified names within the
        # 'aero_states' group.
        prob1.model.connect(
            name + "." + unification_name + "." + name + "_uni_mesh",
            point_name + ".aero_states." + "surface" + "_def_mesh",
        )
        prob2.model.connect(
            name + "." + unification_name + "." + name + "_uni_mesh",
            point_name + ".aero_states." + "surface" + "_def_mesh",
        )

        # Add DVs
        prob1.model.add_design_var("surface.sec0.chord_cp", lower=0.1, upper=10.0, units=None)
        prob1.model.add_design_var("surface.sec1.chord_cp", lower=0.1, upper=10.0, units=None)
        prob1.model.add_design_var("alpha", lower=0.0, upper=10.0, units="deg")

        prob2.model.add_design_var("surface.sec0.chord_cp", lower=0.1, upper=10.0, units=None)
        prob2.model.add_design_var("surface.sec1.chord_cp", lower=0.1, upper=10.0, units=None)
        prob2.model.add_design_var("alpha", lower=0.0, upper=10.0, units="deg")

        # Add joined mesh constraint
        if SNOPT_FLAG:
            prob1.model.add_constraint("surface.surface_joining.section_separation", equals=0.0, scaler=1)
        else:
            prob1.model.add_constraint("surface.surface_joining.section_separation", upper=0, lower=0)

        # Add CL constraint
        prob1.model.add_constraint(point_name + ".CL", equals=0.3)
        prob2.model.add_constraint(point_name + ".CL", equals=0.3)

        # Add Area constraint
        prob1.model.add_constraint(point_name + ".total_perf.S_ref_total", equals=2.0)
        prob2.model.add_constraint(point_name + ".total_perf.S_ref_total", equals=2.0)

        # Add objective
        prob1.model.add_objective(point_name + ".CD", scaler=1e4)
        prob2.model.add_objective(point_name + ".CD", scaler=1e4)

        if SNOPT_FLAG:
            prob1.driver = om.pyOptSparseDriver()
            prob1.driver.options["optimizer"] = "SNOPT"
            prob1.driver.opt_settings["Major feasibility tolerance"] = 1e-7
            prob1.driver.opt_settings["Major iterations limit"] = 1000
            # prob1.driver.options["debug_print"] = ["nl_cons", "objs", "desvars"]

            prob2.driver = om.pyOptSparseDriver()
            prob2.driver.options["optimizer"] = "SNOPT"
            prob2.driver.opt_settings["Major feasibility tolerance"] = 1e-7
            prob2.driver.opt_settings["Major iterations limit"] = 1000
            # prob2.driver.options["debug_print"] = ["nl_cons", "objs", "desvars"]

        else:
            prob1.driver = om.ScipyOptimizeDriver()
            prob1.driver.options["optimizer"] = "SLSQP"
            prob1.driver.options["tol"] = 1e-7
            prob1.driver.options["disp"] = True
            prob1.driver.options["maxiter"] = 1000
            # prob1.driver.options["debug_print"] = ["nl_cons", "objs", "desvars"]

            prob2.driver = om.ScipyOptimizeDriver()
            prob2.driver.options["optimizer"] = "SLSQP"
            prob2.driver.options["tol"] = 1e-7
            prob2.driver.options["disp"] = True
            prob2.driver.options["maxiter"] = 1000
            # prob2.driver.options["debug_print"] = ["nl_cons", "objs", "desvars"]

        # Set up and run the optimization problem
        prob1.setup()
        prob1.run_driver()

        prob2.setup()
        prob2.run_driver()

        assert_near_equal(prob1["aero_point_0.surface_perf.CD"][0], 0.02920058, 1e-3)
        assert_near_equal(prob1["aero_point_0.surface_perf.CL"][0], 0.2999996, 1e-3)
        assert_near_equal(prob1["aero_point_0.CM"][1], -0.07335945, 1e-3)

        assert_near_equal(prob2["aero_point_0.surface_perf.CD"][0], 0.02920058, 1e-3)
        assert_near_equal(prob2["aero_point_0.surface_perf.CL"][0], 0.2999996, 1e-3)
        assert_near_equal(prob2["aero_point_0.CM"][1], -0.07335945, 1e-3)


if __name__ == "__main__":
    unittest.main()
