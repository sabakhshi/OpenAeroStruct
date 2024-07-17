import openmdao.api as om
import numpy as np
from openaerostruct.aerodynamics.compressible_states import CompressibleVLMStates
from openaerostruct.aerodynamics.geometry import VLMGeometry
from openaerostruct.aerodynamics.states import VLMStates
from openaerostruct.aerodynamics.functionals import VLMFunctionals
from openaerostruct.functionals.total_aero_performance import TotalAeroPerformance


class AeroPoint(om.Group):
    """
    This group contains all the components needed for a single-point aerodynamic
    analysis. You would have one instance of `AeroPoint` for each flight
    condition you want to study.
    """

    def initialize(self):
        self.options.declare("surfaces", types=list)
        self.options.declare("user_specified_Sref", types=bool, default=False)
        self.options.declare(
            "rotational", False, types=bool, desc="Set to True to turn on support for computing angular velocities"
        )
        self.options.declare(
            "compressible",
            types=bool,
            default=False,
            desc="Turns on compressibility correction for moderate Mach number " "flows. Defaults to False.",
        )
        self.options.declare(
            "multiSection",
            types=bool,
            default = False,
            desc="Set to True to turn on support for multi section surfaces"
        )
        self.options.declare(
            "unifiedMesh",
            types=np.ndarray,
            desc="Provide a unified mesh if multiSection is enabled."
        )

    def setup(self):
        surfaces = self.options["surfaces"]
        rotational = self.options["rotational"]
        multiSurface = self.options["multiSection"]

        #If multisection mesh then build a single surface with the unified mesh data
        if multiSurface:
            surf_name = "surface"
            uniMesh = self.options["unifiedMesh"]
            # Define input surface dictionary for our wing
            surface = {
                # Wing definition
                "name": surf_name,  # name of the surface
                "symmetry": True,  # if true, model one half of wing
                # reflected across the plane y = 0
                "S_ref_type": "projected",  # how we compute the wing area,
                "mesh": uniMesh,
                "CL0": 0.0,  # CL of the surface at alpha=0
                "CD0": 0.0,  # CD of the surface at alpha=0
                # Airfoil properties for viscous drag calculation
                "k_lam": 0.05,  # percentage of chord with laminar
                "c_max_t": 0.303,  # chordwise location of maximum (NACA0015)
                # flow, used for viscous drag
                # thickness
                "with_viscous": False,  # if true, compute viscous drag,
                "with_wave": False,
            }  # end of surface dictionary

            surfaces = []
            surfaces.append(surface)

        # Loop through each surface and connect relevant parameters
        for surface in surfaces:
            name = surface["name"]

            self.connect(name + ".normals", "aero_states." + name + "_normals")

            # Connect the results from 'aero_states' to the performance groups
            self.connect("aero_states." + name + "_sec_forces", name + "_perf" + ".sec_forces")

            # Connect S_ref for performance calcs
            self.connect(name + ".S_ref", name + "_perf.S_ref")
            self.connect(name + ".widths", name + "_perf.widths")
            self.connect(name + ".chords", name + "_perf.chords")
            self.connect(name + ".lengths", name + "_perf.lengths")
            self.connect(name + ".lengths_spanwise", name + "_perf.lengths_spanwise")

            # Connect S_ref for performance calcs
            self.connect(name + ".S_ref", "total_perf." + name + "_S_ref")
            self.connect(name + ".widths", "total_perf." + name + "_widths")
            self.connect(name + ".chords", "total_perf." + name + "_chords")
            self.connect(name + ".b_pts", "total_perf." + name + "_b_pts")
            self.connect(name + "_perf" + ".CL", "total_perf." + name + "_CL")
            self.connect(name + "_perf" + ".CD", "total_perf." + name + "_CD")
            self.connect("aero_states." + name + "_sec_forces", "total_perf." + name + "_sec_forces")

            self.add_subsystem(name, VLMGeometry(surface=surface))

        # Add a single 'aero_states' component that solves for the circulations
        # and forces from all the surfaces.
        # While other components only depends on a single surface,
        # this component requires information from all surfaces because
        # each surface interacts with the others.

        # check for ground effect and if so, promote
        ground_effect = False
        for surface in surfaces:
            if surface.get("groundplane", False):
                ground_effect = True

        if self.options["compressible"] is True:
            aero_states = CompressibleVLMStates(surfaces=surfaces, rotational=rotational)
            prom_in = ["v", "alpha", "beta", "rho", "Mach_number"]
        else:
            aero_states = VLMStates(surfaces=surfaces, rotational=rotational)
            prom_in = ["v", "alpha", "beta", "rho"]
        if ground_effect:
            prom_in.append("height_agl")

        aero_states.linear_solver = om.LinearRunOnce()

        if rotational:
            prom_in.extend(["omega", "cg"])

        self.add_subsystem("aero_states", aero_states, promotes_inputs=prom_in, promotes_outputs=["circulations"])

        # Explicitly connect parameters from each surface's group and the common
        # 'aero_states' group.
        # This is necessary because the VLMStates component requires information
        # from each surface, but this information is stored within each
        # surface's group.
        for surface in surfaces:
            self.add_subsystem(
                surface["name"] + "_perf",
                VLMFunctionals(surface=surface),
                promotes_inputs=["v", "alpha", "beta", "Mach_number", "re", "rho"],
            )

        # Add the total aero performance group to compute the CL, CD, and CM
        # of the total aircraft. This accounts for all lifting surfaces.
        self.add_subsystem(
            "total_perf",
            TotalAeroPerformance(surfaces=surfaces, user_specified_Sref=self.options["user_specified_Sref"]),
            promotes_inputs=["v", "rho", "cg", "S_ref_total"],
            promotes_outputs=["CM", "CL", "CD"],
        )

        # Need to set the default value/unit for beta since it is often unused (unconnected)
        self.set_input_defaults("beta", val=0.0, units="deg")
