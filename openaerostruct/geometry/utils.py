from __future__ import print_function, division
import numpy as np
from numpy import cos, sin, tan

from openaerostruct.geometry.CRM_definitions import get_crm_points


def rotate(mesh, theta_y, symmetry, rotate_x=True):
    """
    Compute rotation matrices given mesh and rotation angles in degrees.

    Parameters
    ----------
    mesh[nx, ny, 3] : numpy array
        Nodal mesh defining the initial aerodynamic surface.
    theta_y[ny] : numpy array
        1-D array of rotation angles about y-axis for each wing slice in degrees.
    symmetry : boolean
        Flag set to True if surface is reflected about y=0 plane.
    rotate_x : boolean
        Flag set to True if the user desires the twist variable to always be
        applied perpendicular to the wing (say, in the case of a winglet).

    Returns
    -------
    mesh[nx, ny, 3] : numpy array
        Nodal mesh defining the twisted aerodynamic surface.

    """
    te = mesh[-1]
    le = mesh[ 0]
    quarter_chord = 0.25 * te + 0.75 * le

    ny = mesh.shape[1]
    nx = mesh.shape[0]

    if rotate_x:
        # Compute spanwise z displacements along quarter chord
        if symmetry:
            dz_qc = quarter_chord[:-1,2] - quarter_chord[1:,2]
            dy_qc = quarter_chord[:-1,1] - quarter_chord[1:,1]
            theta_x = np.arctan(dz_qc/dy_qc)

            # Prepend with 0 so that root is not rotated
            rad_theta_x = np.append(theta_x, 0.0)
        else:
            root_index = int((ny - 1) / 2)
            dz_qc_left = quarter_chord[:root_index,2] - quarter_chord[1:root_index+1,2]
            dy_qc_left = quarter_chord[:root_index,1] - quarter_chord[1:root_index+1,1]
            theta_x_left = np.arctan(dz_qc_left/dy_qc_left)
            dz_qc_right = quarter_chord[root_index+1:,2] - quarter_chord[root_index:-1,2]
            dy_qc_right = quarter_chord[root_index+1:,1] - quarter_chord[root_index:-1,1]
            theta_x_right = np.arctan(dz_qc_right/dy_qc_right)

            # Concatenate thetas
            rad_theta_x = np.concatenate((theta_x_left, np.zeros(1), theta_x_right))

    else:
        rad_theta_x = 0.0

    rad_theta_y = theta_y * np.pi / 180.

    mats = np.zeros((ny, 3, 3), dtype="complex")
    mats[:, 0, 0] = cos(rad_theta_y)
    mats[:, 0, 2] = sin(rad_theta_y)
    mats[:, 1, 0] = sin(rad_theta_x)*sin(rad_theta_y)
    mats[:, 1, 1] = cos(rad_theta_x)
    mats[:, 1, 2] = -sin(rad_theta_x)*cos(rad_theta_y)
    mats[:, 2, 0] = -cos(rad_theta_x)*sin(rad_theta_y)
    mats[:, 2, 1] = sin(rad_theta_x)
    mats[:, 2, 2] = cos(rad_theta_x)*cos(rad_theta_y)
    for ix in range(nx):
        row = mesh[ix]
        row[:] = np.einsum("ikj, ij -> ik", mats, row - quarter_chord)
        row += quarter_chord

def scale_x(mesh, chord_dist):
    """
    Modify the chords along the span of the wing by scaling only the x-coord.

    Parameters
    ----------
    mesh[nx, ny, 3] : numpy array
        Nodal mesh defining the initial aerodynamic surface.
    chord_dist[ny] : numpy array
        Chord length for each panel edge.

    Returns
    -------
    mesh[nx, ny, 3] : numpy array
        Nodal mesh with the new chord lengths.
    """
    te = mesh[-1]
    le = mesh[ 0]
    quarter_chord = 0.25 * te + 0.75 * le

    ny = mesh.shape[1]

    for i in range(ny):
        mesh[:, i, 0] = (mesh[:, i, 0] - quarter_chord[i, 0]) * chord_dist[i] + \
            quarter_chord[i, 0]

def shear_x(mesh, xshear):
    """
    Shear the wing in the x direction (distributed sweep).

    Parameters
    ----------
    mesh[nx, ny, 3] : numpy array
        Nodal mesh defining the initial aerodynamic surface.
    xshear[ny] : numpy array
        Distance to translate wing in x direction.

    Returns
    -------
    mesh[nx, ny, 3] : numpy array
        Nodal mesh with the new chord lengths.
    """
    mesh[:, :, 0] += xshear

def shear_z(mesh, zshear):
    """
    Shear the wing in the z direction (distributed dihedral).

    Parameters
    ----------
    mesh[nx, ny, 3] : numpy array
        Nodal mesh defining the initial aerodynamic surface.
    zshear[ny] : numpy array
        Distance to translate wing in z direction.

    Returns
    -------
    mesh[nx, ny, 3] : numpy array
        Nodal mesh with the new chord lengths.
    """
    mesh[:, :, 2] += zshear

def sweep(mesh, sweep_angle, symmetry):
    """
    Apply shearing sweep. Positive sweeps back.

    Parameters
    ----------
    mesh[nx, ny, 3] : numpy array
        Nodal mesh defining the initial aerodynamic surface.
    sweep_angle : float
        Shearing sweep angle in degrees.
    symmetry : boolean
        Flag set to true if surface is reflected about y=0 plane.

    Returns
    -------
    mesh[nx, ny, 3] : numpy array
        Nodal mesh defining the swept aerodynamic surface.

    """

    # Get the mesh parameters and desired sweep angle
    num_x, num_y, _ = mesh.shape
    le = mesh[0]
    p180 = np.pi / 180
    tan_theta = tan(p180*sweep_angle)

    # If symmetric, simply vary the x-coord based on the distance from the
    # center of the wing
    if symmetry:
        y0 = le[-1, 1]
        dx = -(le[:, 1] - y0) * tan_theta

    # Else, vary the x-coord on either side of the wing
    else:
        ny2 = (num_y - 1) // 2
        y0 = le[ny2, 1]

        dx_right = (le[ny2:, 1] - y0) * tan_theta
        dx_left = -(le[:ny2, 1] - y0) * tan_theta
        dx = np.hstack((dx_left, dx_right))

    for i in range(num_x):
        mesh[i, :, 0] += dx

def dihedral(mesh, dihedral_angle, symmetry):
    """
    Apply dihedral angle. Positive angles up.

    Parameters
    ----------
    mesh[nx, ny, 3] : numpy array
        Nodal mesh defining the initial aerodynamic surface.
    dihedral_angle : float
        Dihedral angle in degrees.
    symmetry : boolean
        Flag set to true if surface is reflected about y=0 plane.

    Returns
    -------
    mesh[nx, ny, 3] : numpy array
        Nodal mesh defining the aerodynamic surface with dihedral angle.

    """

    # Get the mesh parameters and desired sweep angle
    num_x, num_y, _ = mesh.shape
    le = mesh[0]
    p180 = np.pi / 180
    tan_theta = tan(p180*dihedral_angle)

    # If symmetric, simply vary the z-coord based on the distance from the
    # center of the wing
    if symmetry:
        y0 = le[-1, 1]
        dz = -(le[:, 1] - y0) * tan_theta

    else:
        ny2 = (num_y-1) // 2
        y0 = le[ny2, 1]
        dz_right = (le[ny2:, 1] - y0) * tan_theta
        dz_left = -(le[:ny2, 1] - y0) * tan_theta
        dz = np.hstack((dz_left, dz_right))

    for i in range(num_x):
        mesh[i, :, 2] += dz


def stretch(mesh, span, symmetry):
    """
    Stretch mesh in spanwise direction to reach specified span.

    Parameters
    ----------
    mesh[nx, ny, 3] : numpy array
        Nodal mesh defining the initial aerodynamic surface.
    span : float
        Relative stetch ratio in the spanwise direction.
    symmetry : boolean
        Flag set to true if surface is reflected about y=0 plane.

    Returns
    -------
    mesh[nx, ny, 3] : numpy array
        Nodal mesh defining the stretched aerodynamic surface.

    """

    # Set the span along the quarter-chord line
    le = mesh[0]
    te = mesh[-1]
    quarter_chord = 0.25 * te + 0.75 * le

    # The user always deals with the full span, so if they input a specific
    # span value and have symmetry enabled, we divide this value by 2.
    if symmetry:
        span /= 2.

    # Compute the previous span and determine the scalar needed to reach the
    # desired span
    prev_span = quarter_chord[-1, 1] - quarter_chord[0, 1]
    s = quarter_chord[:,1] / prev_span
    mesh[:, :, 1] = s * span

def taper(mesh, taper_ratio, symmetry):
    """
    Alter the spanwise chord linearly to produce a tapered wing. Note that
    we apply taper around the quarter-chord line.

    Parameters
    ----------
    mesh[nx, ny, 3] : numpy array
        Nodal mesh defining the initial aerodynamic surface.
    taper_ratio : float
        Taper ratio for the wing; 1 is untapered, 0 goes to a point.
    symmetry : boolean
        Flag set to true if surface is reflected about y=0 plane.

    Returns
    -------
    mesh[nx, ny, 3] : numpy array
        Nodal mesh defining the tapered aerodynamic surface.

    """

    # Get mesh parameters and the quarter-chord
    le = mesh[0]
    te = mesh[-1]
    num_x, num_y, _ = mesh.shape
    quarter_chord = 0.25 * te + 0.75 * le

    # If symmetric, solve for the correct taper ratio, which is a linear
    # interpolation problem
    if symmetry:
        x = quarter_chord[:, 1]
        span = x[-1] - x[0]
        xp = np.array([-span, 0.])
        fp = np.array([taper_ratio, 1.])
        taper = np.interp(x.real, xp.real, fp.real)

        # Modify the mesh based on the taper amount computed per spanwise section
        for i in range(num_x):
            for ind in range(3):
                mesh[i, :, ind] = (mesh[i, :, ind] - quarter_chord[:, ind]) * \
                    taper + quarter_chord[:, ind]

    # Otherwise, we set up an interpolation problem for the entire wing, which
    # consists of two linear segments
    else:
        x = quarter_chord[:, 1]
        span = x[-1] - x[0]
        xp = np.array([-span/2, 0., span/2])
        fp = np.array([taper_ratio, 1., taper_ratio])
        taper = np.interp(x.real, xp.real, fp.real)

        for i in range(num_x):
            for ind in range(3):
                mesh[i, :, ind] = (mesh[i, :, ind] - quarter_chord[:, ind]) * \
                    taper + quarter_chord[:, ind]

def gen_rect_mesh(num_x, num_y, span, chord, span_cos_spacing=0., chord_cos_spacing=0.):
    """
    Generate simple rectangular wing mesh.

    Parameters
    ----------
    num_x : float
        Desired number of chordwise node points for the final mesh.
    num_y : float
        Desired number of chordwise node points for the final mesh.
    span : float
        Total wingspan.
    chord : float
        Root chord.
    span_cos_spacing : float (optional)
        Blending ratio of uniform and cosine spacing in the spanwise direction.
        A value of 0. corresponds to uniform spacing and a value of 1.
        corresponds to regular cosine spacing. This increases the number of
        spanwise node points near the wingtips.
    chord_cos_spacing : float (optional)
        Blending ratio of uniform and cosine spacing in the chordwise direction.
        A value of 0. corresponds to uniform spacing and a value of 1.
        corresponds to regular cosine spacing. This increases the number of
        chordwise node points near the wingtips.

    Returns
    -------
    mesh[nx, ny, 3] : numpy array
        Rectangular nodal mesh defining the final aerodynamic surface with the
        specified parameters.
    """

    mesh = np.zeros((num_x, num_y, 3))
    ny2 = (num_y + 1) // 2
    beta = np.linspace(0, np.pi/2, ny2)

    # mixed spacing with span_cos_spacing as a weighting factor
    # this is for the spanwise spacing
    cosine = .5 * np.cos(beta)  # cosine spacing
    uniform = np.linspace(0, .5, ny2)[::-1]  # uniform spacing
    half_wing = cosine * span_cos_spacing + (1 - span_cos_spacing) * uniform
    full_wing = np.hstack((-half_wing[:-1], half_wing[::-1])) * span

    if chord_cos_spacing == 0.:
        full_wing_x = np.linspace(0, chord, num_x)

    else:
        nx2 = (num_x + 1) / 2
        beta = np.linspace(0, np.pi/2, nx2)

        # mixed spacing with span_cos_spacing as a weighting factor
        # this is for the chordwise spacing
        cosine = .5 * np.cos(beta)  # cosine spacing
        uniform = np.linspace(0, .5, nx2)[::-1]  # uniform spacing
        half_wing = cosine * chord_cos_spacing + (1 - chord_cos_spacing) * uniform
        full_wing_x = np.hstack((-half_wing[:-1], half_wing[::-1])) * chord

    for ind_x in range(num_x):
        for ind_y in range(num_y):
            mesh[ind_x, ind_y, :] = [full_wing_x[ind_x], full_wing[ind_y], 0]

    return mesh


def gen_crm_mesh(num_x, num_y, span, chord, span_cos_spacing=0., chord_cos_spacing=0., wing_type="CRM:jig"):
    """
    Generate Common Research Model wing mesh.

    Parameters
    ----------
    num_x : float
        Desired number of chordwise node points for the final mesh.
    num_y : float
        Desired number of chordwise node points for the final mesh.
    span : float
        Total wingspan.
    chord : float
        Root chord.
    span_cos_spacing : float (optional)
        Blending ratio of uniform and cosine spacing in the spanwise direction.
        A value of 0. corresponds to uniform spacing and a value of 1.
        corresponds to regular cosine spacing. This increases the number of
        spanwise node points near the wingtips.
    chord_cos_spacing : float (optional)
        Blending ratio of uniform and cosine spacing in the chordwise direction.
        A value of 0. corresponds to uniform spacing and a value of 1.
        corresponds to regular cosine spacing. This increases the number of
        chordwise node points near the wingtips.
    wing_type : string (optional)
        Describes the desired CRM shape. Current options are:
        "CRM:jig" (undeformed jig shape),
        "CRM:alpha_2.75" (shape from wind tunnel testing at a=2.75 from DPW6)

    Returns
    -------
    mesh[nx, ny, 3] : numpy array
        Rectangular nodal mesh defining the final aerodynamic surface with the
        specified parameters.
    eta : numpy array
        Spanwise locations of the airfoil slices. Later used in the
        interpolation function to obtain correct twist values at
        points along the span that are not aligned with these slices.
    twist : numpy array
        Twist along the span at the spanwise eta locations. We use these twists
        as training points for interpolation to obtain twist values at
        arbitrary points along the span.

    """

    # Call an external function to get the data points for the specific CRM
    # type requested. See `CRM_definitions.py` for more information and the
    # raw data.
    raw_crm_points = get_crm_points(wing_type)

    # Get the leading edge of the raw crm points
    le = np.vstack((raw_crm_points[:,1],
                    raw_crm_points[:,2],
                    raw_crm_points[:,3]))

    # Get the chord, twist(in correct order), and eta values from the points
    chord = raw_crm_points[:, 5]
    twist = raw_crm_points[:, 4][::-1]
    eta = raw_crm_points[:, 0]

    # Get the trailing edge of the crm points, based on the chord + le distance.
    # Note that we do not account for twist here; instead we set that using
    # the twist design variable later in run_classes.py.
    te = np.vstack((raw_crm_points[:,1] + chord,
                       raw_crm_points[:,2],
                       raw_crm_points[:,3]))

    # Get the number of points that define this CRM shape and create a mesh
    # array based on this size
    n_raw_points = raw_crm_points.shape[0]
    mesh = np.empty((2, n_raw_points, 3))

    # Set the leading and trailing edges of the mesh matrix
    mesh[0, :, :] = le.T
    mesh[1, :, :] = te.T

    # Convert the mesh points to meters from inches.
    raw_mesh = mesh * 0.0254

    # Create the blended spacing using the user input for span_cos_spacing
    ny2 = (num_y + 1) // 2
    beta = np.linspace(0, np.pi/2, ny2)

    # Distribution for cosine spacing
    cosine = np.cos(beta)

    # Distribution for uniform spacing
    uniform = np.linspace(0, 1., ny2)[::-1]

    # Combine the two distrubtions using span_cos_spacing as the weighting factor.
    # span_cos_spacing == 1. is for fully cosine, 0. for uniform
    lins = cosine * span_cos_spacing + (1 - span_cos_spacing) * uniform

    # Populate a mesh object with the desired num_y dimension based on
    # interpolated values from the raw CRM points.
    mesh = np.empty((2, ny2, 3))
    for j in range(2):
        for i in range(3):
            mesh[j, :, i] = np.interp(lins[::-1], eta, raw_mesh[j, :, i].real)

    # That is just one half of the mesh and we later expect the full mesh,
    # even if we're using symmetry == True.
    # So here we mirror and stack the two halves of the wing.
    left_half = mesh.copy()
    left_half[:, :, 1] *= -1.
    mesh = np.hstack((left_half[:, ::-1, :], mesh[:, 1:, :]))

    # If we need to add chordwise panels, do so
    if num_x > 2:
        mesh = add_chordwise_panels(mesh, num_x, chord_cos_spacing)

    return mesh, eta, twist


def add_chordwise_panels(mesh, num_x, chord_cos_spacing):
    """
    Generate a new mesh with multiple chordwise panels.

    Parameters
    ----------
    mesh[nx, ny, 3] : numpy array
        Nodal mesh defining the initial aerodynamic surface with only
        the leading and trailing edges defined.
    num_x : float
        Desired number of chordwise node points for the final mesh.
    chord_cos_spacing : float
        Blending ratio of uniform and cosine spacing in the chordwise direction.
        A value of 0. corresponds to uniform spacing and a value of 1.
        corresponds to regular cosine spacing. This increases the number of
        chordwise node points near the wingtips.

    Returns
    -------
    new_mesh[nx, ny, 3] : numpy array
        Nodal mesh defining the final aerodynamic surface with the
        specified number of chordwise node points.

    """

    # Obtain mesh and num properties
    num_y = mesh.shape[1]
    ny2 = (num_y + 1) // 2
    nx2 = (num_x + 1) // 2

    # Create beta, an array of linear sampling points to pi/2
    beta = np.linspace(0, np.pi/2, nx2)

    # Obtain the two spacings that we will use to blend
    cosine = .5 * np.cos(beta)  # cosine spacing
    uniform = np.linspace(0, .5, nx2)[::-1]  # uniform spacing

    # Create half of the wing in the chordwise direction
    half_wing = cosine * chord_cos_spacing + (1 - chord_cos_spacing) * uniform

    if chord_cos_spacing == 0.:
        full_wing_x = np.linspace(0, 1., num_x)

    else:
        # Mirror this half wing into a full wing; offset by 0.5 so it goes 0 to 1
        full_wing_x = np.hstack((-half_wing[:-1], half_wing[::-1])) + .5

    # Obtain the leading and trailing edges
    le = mesh[ 0, :, :]
    te = mesh[-1, :, :]

    # Create a new mesh with the desired num_x and set the leading and trailing edge values
    new_mesh = np.zeros((num_x, num_y, 3))
    new_mesh[ 0, :, :] = le
    new_mesh[-1, :, :] = te

    for i in range(1, num_x-1):
        w = full_wing_x[i]
        new_mesh[i, :, :] = (1 - w) * le + w * te

    return new_mesh