#!/usr/bin/env python
"""
@author: Jesse Haviland
"""

import copy
import numpy as np
from spatialmath import SE3
from spatialmath.base.argcheck import getvector, \
    isscalar, isvector, ismatrix
import roboticstoolbox as rp
from roboticstoolbox.robot.Link import Link
from functools import wraps

_eps = np.finfo(np.float64).eps

# --------------------------------------------------------------#

try:  # pragma: no cover
    # print('Using SymPy')
    import sympy as sym

    def _issymbol(x):
        return isinstance(x, sym.Expr)
except ImportError:
    def _issymbol(x):  # pylint: disable=unused-argument
        return False


def _cos(theta):
    if _issymbol(theta):
        return sym.cos(theta)
    else:
        return np.cos(theta)


def _sin(theta):
    if _issymbol(theta):
        return sym.sin(theta)
    else:
        return np.sin(theta)

# --------------------------------------------------------------#


class DHLink(Link):
    """
    A link superclass for all link types. A Link object holds all information
    related to a robot joint and link such as kinematics parameters,
    rigid-body inertial parameters, motor and transmission parameters.

    :param theta: kinematic: joint angle
    :type theta: float
    :param d: kinematic - link offset
    :type d: float
    :param alpha: kinematic - link twist
    :type alpha: float
    :param a: kinematic - link length
    :type a: float
    :param sigma: kinematic - 0 if revolute, 1 if prismatic
    :type sigma: int
    :param mdh: kinematic - 0 if standard D&H, else 1
    :type mdh: int
    :param offset: kinematic - joint variable offset
    :type offset: float

    :param qlim: joint variable limits [min, max]
    :type qlim: ndarray(2,)
    :param flip: joint moves in opposite direction
    :type flip: bool

    :param m: dynamic - link mass
    :type m: float
    :param r: dynamic - position of COM with respect to link frame
    :type r:  ndarray(3,)
    :param I: dynamic - inertia of link with respect to COM
    :type I: ndarray
    :param Jm: dynamic - motor inertia
    :type Jm: float
    :param B: dynamic - motor viscous friction: B=B⁺=B⁻, [B⁺, B⁻]
    :type B: float, or ndarray(2,)
    :param Tc: dynamic - motor Coulomb friction [Tc⁺, Tc⁻]
    :type Tc: ndarray(2,)
    :param G: dynamic - gear ratio
    :type G: float

    :references:
        - Robotics, Vision & Control, P. Corke, Springer 2011, Chap 7.

    """

    def __init__(
            self,
            d=0.0,
            alpha=0.0,
            theta=0.0,
            a=0.0,
            sigma=0,
            mdh=False,
            offset=0.0,
            qlim=np.zeros(2),
            flip=False,
            m=0.0,
            r=np.zeros(3),
            I=np.zeros((3, 3)),       # noqa
            Jm=0.0,
            B=0.0,
            Tc=np.zeros(2),
            G=1.0,
            **kwargs):

        # TODO
        #  probably should make DHLink(link) return a copy
        #  probably should enforce keyword arguments, easy to make an
        #    error with positional args
        super().__init__(**kwargs)
        self._robot = None

        # Kinematic parameters
        self.sigma = sigma
        self.theta = theta
        self.d = d
        self.alpha = alpha
        self.a = a
        self.mdh = mdh
        self.id = None
        self.offset = offset

        self.flip = flip
        self.qlim = qlim

        # Dynamic Parameters
        self.m = m
        self.r = r
        self.I = I    # noqa
        self.Jm = Jm
        self.B = B
        self.Tc = Tc
        self.G = G

    def __add__(self, L):
        if isinstance(L, DHLink):
            return rp.DHRobot([self, L])

        elif isinstance(L, rp.DHRobot):
            nlinks = [self]

            # TODO - Should I do a deep copy here a physically copy the Links
            # and not just the references?
            # Copy Link references to new list
            for i in range(L.n):
                nlinks.append(L.links[i])

            return rp.DHRobot(
                nlinks,
                name=L.name,
                manufacturer=L.manufacturer,
                base=L.base,
                tool=L.tool,
                gravity=L.gravity)

        else:
            raise TypeError("Cannot add a Link with a non Link object")

    def __str__(self):

        if not self.sigma:
            s = "Revolute   theta=q{} +{: .2f},  d={: .2f},  a={: .2f},  " \
                "alpha={: .2f}".format(
                    self.id, self.offset, self.d, self.a, self.alpha)
        else:
            s = "Prismatic  theta={: .2f},  d=q{} +{: .2f},  a={: .2f},  " \
                "alpha={: .2f}".format(
                    self.theta, self.id, self.offset, self.a, self.alpha, )

        return s

    def __repr__(self):
        return str(self)

    def _listen_dyn(func):
        @wraps(func)
        def wrapper_listen_dyn(*args):
            if args[0]._robot is not None:
                args[0]._robot.dynchanged()
            return func(*args)
        return wrapper_listen_dyn

    @property
    def d(self):
        """
        Get/set link offset

        - ``link.d`` is the link offset
            :return: link offset
            :rtype: float
        - ``link.d = ...`` checks and sets the link offset

        """
        return self._d

    @property
    def alpha(self):
        """
        Get/set link twist

        - ``link.d`` is the link twist
            :return: link twist
            :rtype: float
        - ``link.d = ...`` checks and sets the link twist

        """
        return self._alpha

    @property
    def theta(self):
        """
        Get/set joint angle

        - ``link.theta`` is the joint angle
            :return: joint angle
            :rtype: float
        - ``link.theta = ...`` checks and sets the joint angle

        """
        return self._theta

    @property
    def a(self):
        """
        Get/set link length

        - ``link.a`` is the link length
            :return: link length
            :rtype: float
        - ``link.a = ...`` checks and sets the link length

        """
        return self._a

    @property
    def sigma(self):
        """
        Get/set joint type

        - ``link.sigma`` is the joint type
            :return: joint type
            :rtype: int
        - ``link.sigma = ...`` checks and sets the joint type

        The joint type is 0 for a revolute joint, and 1 for a prismatic joint.

        :seealso: :func:`isrevolute`, :func:`isprismatic`
        """
        return self._sigma

    @property
    def mdh(self):
        """
        Get/set kinematic convention

        - ``link.mdh`` is the kinematic convention
            :return: kinematic convention
            :rtype: bool
        - ``link.mdh = ...`` checks and sets the kinematic convention

        The kinematic convention is True for modified Denavit-Hartenberg
        notation (eg. Craig's textbook) and False for Denavit-Hartenberg
        notation (eg. Siciliano, Spong, Paul textbooks).
        """
        return self._mdh

    @property
    def offset(self):
        """
        Get/set joint variable offset

        - ``link.offset`` is the joint variable offset
            :return: joint variable offset
            :rtype: float
        - ``link.offset = ...`` checks and sets the joint variable offset

        The offset is added to the joint angle before forward kinematics, and
        subtracted after inverse kinematics.  It is used to define the joint
        configuration for zero joint coordinates.

        """
        return self._offset

    @property
    def qlim(self):
        """
        Get/set joint limits

        - ``link.qlim`` is the joint limits
            :return: joint limits
            :rtype: ndarray(2,)
        - ``link.a = ...`` checks and sets the joint limits

        .. note:: The limits are not widely enforced within the toolbox.

        :seealso: :func:`~islimit`
        """
        return self._qlim

    @property
    def flip(self):
        """
        Get/set joint flip

        - ``link.flip`` is the joint flip status
            :return: joint flip
            :rtype: bool
        - ``link.flip = ...`` checks and sets the joint flip status

        Joint flip defines the direction of motion of the joint.
        
        ``flip = False`` is conventional motion direction:

            - revolute motion is a positive rotation about the z-axis
            - prismatic motion is a positive translation along the z-axis

        ``flip = True`` is the opposite motion direction:

            - revolute motion is a negative rotation about the z-axis
            - prismatic motion is a negative translation along the z-axis

        """
        return self._flip

    @property
    def m(self):
        """
        Get/set link mass

        - ``link.m`` is the link mass
            :return: link mass
            :rtype: float
        - ``link.m = ...`` checks and sets the link mass

        """
        return self._m

    @property
    def r(self):
        """
        Get/set link centre of mass

        - ``link.r`` is the link centre of mass
            :return: link centre of mass
            :rtype: ndarray(3,)
        - ``link.r = ...`` checks and sets the link centre of mass

        The link centre of mass is a 3-vector defined with respect to the link
        frame.
        """
        return self._r

    @property
    def I(self):    # noqa
        r"""
        Get/set link inertia

        - ``link.I`` is the link inertia
            :return: link inertia
            :rtype: ndarray(3,3)
        - ``link.I = ...`` checks and sets the link inertia

        Link inertia is a symmetric 3x3 matrix describing the inertia with respect
        to a frame with its origin at the centre of mass, and with axes parallel to those of
        the link frame.

        The inertia matrix is
        
        .. math::

            \begin{bmatrix} I_{xx} & I_{xy} & I_{xz} \\
                            I_{xy} & I_{yy} & I_{yz} \\
                            I_{xz} & I_{yz} & I_{zz} \end{bmatrix}

        and can be specified as either:

        - a :math:`3 \times 3` symmetric matrix
        - a 3-vector :math:`(I_{xx}, I_{yy}, I_{zz})`
        - a 6-vector :math:`(I_{xx}, I_{yy}, I_{zz}, I_{xy}, I_{yz}, I_{xz})`
        """
        return self._I

    @property
    def Jm(self):
        """
        Get/set motor inertia

        - ``link.Jm`` is the motor inertia
            :return: motor inertia
            :rtype: float
        - ``link.Jm = ...`` checks and sets the motor inertia

        """
        return self._Jm

    @property
    def B(self):
        """
        Get/set motor viscous friction

        - ``link.B`` is the motor viscous friction
            :return: motor viscous friction
            :rtype: float
        - ``link.B = ...`` checks and sets the motor viscous friction

        .. note:: Viscous friction is the same for positive and negative motion.
        """
        return self._B

    @property
    def Tc(self):
        r"""
        Get/set motor Coulomb friction

        - ``link.Tc`` is the motor Coulomb friction
            :return: motor Coulomb friction 
            :rtype: ndarray(2)
        - ``link.Tc = ...`` checks and sets the motor Coulomb friction. If a
          scalar is given the value is set to [T, -T], if a 2-vector it is
          assumed to be in the order [Tc⁺, Tc⁻]

        Coulomb friction is a non-linear friction effect defined by two
        parameters such that

        .. math::

            \tau = \left\{ \begin{array}{ll}
                \tau_C^+ & \mbox{if $\dot{q} > 0$} \\
                \tau_C^- & \mbox{if $\dot{q} < 0$} \end{array} \right.

        .. note:: :math:`\tau_C^+` must be :math:`> 0`, and :math:`\tau_C^-` must be :math:`< 0`.
        """
        return self._Tc

    @property
    def G(self):
        """
        Get/set gear ratio

        - ``link.G`` is the transmission gear ratio
            :return: gear ratio
            :rtype: float
        - ``link.G = ...`` checks and sets the gear ratio

        .. note:: The gear ratio can be negative.

        """
        return self._G

    @d.setter
    @_listen_dyn
    def d(self, d_new):
        if self.sigma and d_new != 0.0:
            raise ValueError("f is not valid for prismatic joints")
        else:
            self._d = d_new

    @alpha.setter
    @_listen_dyn
    def alpha(self, alpha_new):
        self._alpha = alpha_new

    @theta.setter
    @_listen_dyn
    def theta(self, theta_new):
        if not self.sigma and theta_new != 0.0:
            raise ValueError("theta is not valid for revolute joints")
        else:
            self._theta = theta_new

    @a.setter
    @_listen_dyn
    def a(self, a_new):
        self._a = a_new

    @sigma.setter
    @_listen_dyn
    def sigma(self, sigma_new):
        self._sigma = sigma_new

    @mdh.setter
    @_listen_dyn
    def mdh(self, mdh_new):
        self._mdh = int(mdh_new)

    @offset.setter
    def offset(self, offset_new):
        self._offset = offset_new

    @qlim.setter
    def qlim(self, qlim_new):
        self._qlim = getvector(qlim_new, 2)

    @flip.setter
    def flip(self, flip_new):
        self._flip = flip_new

    @m.setter
    @_listen_dyn
    def m(self, m_new):
        self._m = m_new

    @r.setter
    @_listen_dyn
    def r(self, r_new):
        self._r = getvector(r_new, 3)

    @I.setter
    @_listen_dyn
    def I(self, I_new):  # noqa

        if ismatrix(I_new, (3, 3)):
            # 3x3 matrix passed
            if np.any(np.abs(I_new - I_new.T) > 1e-8):
                raise ValueError('3x3 matrix is not symmetric')

        elif isvector(I_new, 9):
            # 3x3 matrix passed as a 1d vector
            I_new = I_new.reshape(3, 3)
            if np.any(np.abs(I_new - I_new.T) > 1e-8):
                raise ValueError('3x3 matrix is not symmetric')

        elif isvector(I_new, 6):
            # 6-vector passed, moments and products of inertia,
            # [Ixx Iyy Izz Ixy Iyz Ixz]
            I_new = np.array([
                [I_new[0], I_new[3], I_new[5]],
                [I_new[3], I_new[1], I_new[4]],
                [I_new[5], I_new[4], I_new[2]]
            ])

        elif isvector(I_new, 3):
            # 3-vector passed, moments of inertia [Ixx Iyy Izz]
            I_new = np.diag(I_new)

        else:
            raise ValueError('invalid shape passed: must be (3,3), (6,), (3,)')

        self._I = I_new

    @Jm.setter
    @_listen_dyn
    def Jm(self, Jm_new):
        self._Jm = Jm_new

    @B.setter
    @_listen_dyn
    def B(self, B_new):
        if isscalar(B_new):
            self._B = B_new
        else:
            raise TypeError("B must be a scalar")

    @Tc.setter
    @_listen_dyn
    def Tc(self, Tc_new):

        try:
            # sets Coulomb friction parameters to [F -F], for a symmetric
            # Coulomb friction model.
            Tc = getvector(Tc_new, 1)
            Tc_new = np.array([Tc[0], -Tc[0]])
        except ValueError:
            # [FP FM] sets Coulomb friction to [FP FM], for an asymmetric
            # Coulomb friction model. FP>0 and FM<0.  FP is applied for a
            # positive joint velocity and FM for a negative joint
            # velocity.
            Tc_new = getvector(Tc_new, 2)

        self._Tc = Tc_new

    @G.setter
    @_listen_dyn
    def G(self, G_new):
        self._G = G_new

    def _copy(self):
        # Copy the Link
        # link = DHLink(
        #     d=self.d,
        #     alpha=self.alpha,
        #     theta=self.theta,
        #     a=self.a,
        #     sigma=self.sigma,
        #     mdh=self.mdh,
        #     offset=self.offset,
        #     qlim=self.qlim,
        #     flip=self.flip,
        #     m=self.m,
        #     r=self.r,
        #     I=self.I,
        #     Jm=self.Jm,
        #     B=self.B,
        #     Tc=self.Tc,
        #     G=self.G)

        # TODO how many places is this called?

        return copy.copy(self)

    def dyn(self, indent=0):
        """
        Show inertial properties of link

        s = dyn() returns a string representation the inertial properties of
        the link object in a multi-line format. The properties shown are mass,
        centre of mass, inertia, friction, gear ratio and motor properties.

        :param indent: indent each line by this many spaces
        :type indent: int
        :return s: The string representation of the link dynamics
        :rtype s: string
        """

        s = "m     =  {:8.2g} \n" \
            "r     =  {:8.2g} {:8.2g} {:8.2g} \n" \
            "        | {:8.2g} {:8.2g} {:8.2g} | \n" \
            "I     = | {:8.2g} {:8.2g} {:8.2g} | \n" \
            "        | {:8.2g} {:8.2g} {:8.2g} | \n" \
            "Jm    =  {:8.2g} \n" \
            "B     =  {:8.2g} \n" \
            "Tc    =  {:8.2g}(+) {:8.2g}(-) \n" \
            "G     =  {:8.2g} \n" \
            "qlim  =  {:8.2g} to {:8.2g}".format(
                self.m,
                self.r[0], self.r[1], self.r[2],
                self.I[0, 0], self.I[0, 1], self.I[0, 2],
                self.I[1, 0], self.I[1, 1], self.I[1, 2],
                self.I[2, 0], self.I[2, 1], self.I[2, 2],
                self.Jm,
                self.B,
                self.Tc[0], self.Tc[1],
                self.G,
                self.qlim[0], self.qlim[1]
            )

        if indent > 0:
            # insert indentations into the string
            # TODO there is probably a tidier way to integrate this step with
            # above
            sp = ' ' * indent
            s = sp + s.replace('\n', '\n' + sp)

        return s

    def A(self, q):
        r"""
        Link transform matrix

        :param q: Joint coordinate
        :type q: float
        :return T: SE(3) link homogeneous transformation
        :rtype T: SE3 instance

        ``A(q)`` is an ``SE3`` instance representing the SE(3) homogeneous
        transformation matrix corresponding to the link's joint variable ``q``
        which is either the Denavit-Hartenberg parameter :math:`\theta_j`
        (revolute) or :math:`d_j` (prismatic). 
        
        This is the relative pose of the current link frame with respect to the
        previous link frame.



        For details of the computation see the documentation for the subclasses,
        click on the right side of the class boxes below. 

        .. inheritance-diagram:: roboticstoolbox.RevoluteDH roboticstoolbox.PrismaticDH roboticstoolbox.RevoluteMDH roboticstoolbox.PrismaticMDH
            :top-classes: roboticstoolbox.robot.DHLink.DHLink
            :parts: 2

        .. note::

            - For a revolute joint the ``theta`` parameter of the link is 
              ignored, and ``q`` used instead.
            - For a prismatic joint the ``d`` parameter of the link is ignored,
              and ``q`` used instead.
            - The joint ``offset`` parameter is added to ``q`` before 
              computation of the transformation matrix.
            - The computation is different for standard and modified 
              Denavit-Hartenberg parameters.

        :seealso: :class:`RevoluteDH`, :class:`PrismaticDH`, :class:`RevoluteMDH`, :class:`PrismaticMDH`
        """

        sa = _sin(self.alpha)
        ca = _cos(self.alpha)

        if self.flip:
            q = -q + self.offset
        else:
            q = q + self.offset

        if self.sigma == 0:
            # revolute
            st = _sin(q)
            ct = _cos(q)
            d = self.d
        else:
            # prismatic
            st = _sin(self.theta)
            ct = _cos(self.theta)
            d = q

        if self.mdh == 0:
            # standard DH
            T = np.array([
                [ct, -st * ca, st * sa, self.a * ct],
                [st, ct * ca, -ct * sa, self.a * st],
                [0, sa, ca, d],
                [0, 0, 0, 1]
            ])
        else:
            # modified DH
            T = np.array([
                [ct, -st, 0, self.a],
                [st * ca, ct * ca, -sa, -sa * d],
                [st * sa, ct * sa, ca, ca * d],
                [0, 0, 0, 1]
            ])

        return SE3(T, check=False)

    def islimit(self, q):
        """
        Checks if the joint is exceeding a joint limit

        :return: True if joint is exceeded
        :rtype: bool

        :seealso: :func:`qlim`
        """

        if q < self.qlim[0] or q > self.qlim[1]:
            return True
        else:
            return False

    def isrevolute(self):
        """
        Checks if the joint is of revolute type

        :return: Ture if is revolute
        :rtype: bool

        :seealso: :func:`sigma`
        """

        if not self.sigma:
            return True
        else:
            return False

    def isprismatic(self):
        """
        Checks if the joint is of prismatic type

        :return: Ture if is prismatic
        :rtype: bool

        :seealso: :func:`sigma`
        """

        if self.sigma:
            return True
        else:
            return False

    def nofriction(self, coulomb=True, viscous=False):
        """
        ``l2 = nofriction(coulomb, viscous)`` copies the link and returns a
        link with the same parameters except, the Coulomb and/or viscous
        friction parameter to zero.

        ``l2 = nofriction()`` as above except the the Coulomb parameter is set
        to zero.

        :param coulomb: if True, will set the Coulomb friction to 0
        :type coulomb: bool
        :param viscous: if True, will set the viscous friction to 0
        :type viscous: bool
        """

        # Copy the Link
        link = self._copy()

        if viscous:
            link.B = 0.0

        if coulomb:
            link.Tc = [0.0, 0.0]

        return link

    def friction(self, qd, coulomb=True):
        r"""
        Compute joint friction

        :param qd: The joint velocity
        :type qd: float
        :param coulomb: include Coulomb friction
        :type coloumb: bool, default True
        :return tau: the friction force/torque
        :rtype tau: float

        ``friction(qd)`` is the joint friction force/torque
        for joint velocity ``qd``. The friction model includes:

        - Viscous friction which is a linear function of velocity.
        - Coulomb friction which is proportional to sign(qd).

        .. math::

            \tau = G^2 B \dot{q} + |G| \left\{ \begin{array}{ll}
                \tau_C^+ & \mbox{if $\dot{q} > 0$} \\
                \tau_C^- & \mbox{if $\dot{q} < 0$} \end{array} \right.

        .. notes::

            - The friction value should be added to the motor output torque,
              it has a negative value when qd > 0.
            - The returned friction value is referred to the output of the
              gearbox.
            - The friction parameters in the Link object are referred to the
              motor.
            - Motor viscous friction is scaled up by G^2.
            - Motor Coulomb friction is scaled up by G.
            - The appropriate Coulomb friction value to use in the
              non-symmetric case depends on the sign of the joint velocity,
              not the motor velocity.
            - The absolute value of the gear ratio is used.  Negative gear
              ratios are tricky: the Puma560 has negative gear ratio for
              joints 1 and 3.

        """

        tau = self.B * np.abs(self.G) * qd

        if coulomb:
            if qd > 0:
                tau += self.Tc[0]
            elif qd < 0:
                tau += self.Tc[1]

        # Scale up by gear ratio
        tau = -np.abs(self.G) * tau

        return tau

# -------------------------------------------------------------------------- #
class RevoluteDH(DHLink):
    r"""
    Class for revolute links using standard DH convention

    :param d: kinematic - link offset
    :type d: float
    :param alpha: kinematic - link twist
    :type alpha: float
    :param a: kinematic - link length
    :type a: float
    :param offset: kinematic - joint variable offset
    :type offset: float

    :param qlim: joint variable limits [min, max]
    :type qlim: float ndarray(1,2)
    :param flip: joint moves in opposite direction
    :type flip: bool

    :param m: dynamic - link mass
    :type m: float
    :param r: dynamic - position of COM with respect to link frame
    :type r:  float ndarray(3)
    :param I: dynamic - inertia of link with respect to COM
    :type I: ndarray
    :param Jm: dynamic - motor inertia
    :type Jm: float
    :param B: dynamic - motor viscous friction: B=B⁺=B⁻, [B⁺, B⁻]
    :type B: float, or ndarray(2,)
    :param Tc: dynamic - motor Coulomb friction [Tc⁺, Tc⁻]
    :type Tc: ndarray(2,)
    :param G: dynamic - gear ratio
    :type G: float

    A subclass of the :class:`DHLink` class for a revolute joint that holds all
    information related to a robot link such as kinematics parameters,
    rigid-body inertial parameters, motor and transmission parameters.

    The link transform is

    :math:`\underbrace{\mathbf{T}_{rz}(q_i)}_{\mbox{variable}} \cdot \mathbf{T}_{tz}(d_i) \cdot \mathbf{T}_{tx}(a_i) \cdot \mathbf{T}_{rx}(\alpha_i)`

    where :math:`q_i` is the joint variable.

    :references:
        - Robotics, Vision & Control, P. Corke, Springer 2011, Chap 7.

    :seealso: :func:`PrismaticDH`, :func:`DHLink`, :func:`RevoluteMDH`
    """

    def __init__(
            self,
            d=0.0,
            a=0.0,
            alpha=0.0,
            offset=0.0,
            qlim=np.zeros(2),
            flip=False,
            **kwargs
            ):

        theta = 0.0
        sigma = 0
        mdh = False

        super().__init__(
            d=d, alpha=alpha, theta=theta, a=a, sigma=sigma, mdh=mdh,
            offset=offset, qlim=qlim, flip=flip, **kwargs)


class PrismaticDH(DHLink):
    r"""
    Class for prismatic link using standard DH convention

    :param theta: kinematic: joint angle
    :type theta: float
    :param d: kinematic - link offset
    :type d: float
    :param alpha: kinematic - link twist
    :type alpha: float
    :param a: kinematic - link length
    :type a: float
    :param offset: kinematic - joint variable offset
    :type offset: float

    :param qlim: joint variable limits [min, max]
    :type qlim: float ndarray(1,2)
    :param flip: joint moves in opposite direction
    :type flip: bool

    :param m: dynamic - link mass
    :type m: float
    :param r: dynamic - position of COM with respect to link frame
    :type r:  float ndarray(3)
    :param I: dynamic - inertia of link with respect to COM
    :type I: ndarray
    :param Jm: dynamic - motor inertia
    :type Jm: float
    :param B: dynamic - motor viscous friction: B=B⁺=B⁻, [B⁺, B⁻]
    :type B: float, or ndarray(2,)
    :param Tc: dynamic - motor Coulomb friction [Tc⁺, Tc⁻]
    :type Tc: ndarray(2,)
    :param G: dynamic - gear ratio
    :type G: float

    A subclass of the DHLink class for a prismatic joint that holds all
    information related to a robot link such as kinematics parameters,
    rigid-body inertial parameters, motor and transmission parameters.

    The link transform is

    :math:`\mathbf{T}_{rz}(\theta_i) \cdot \underbrace{\mathbf{T}_{tz}(q_i)}_{\mbox{variable}} \cdot \mathbf{T}_{tx}(a_i) \cdot \mathbf{T}_{rx}(\alpha_i)`

    where :math:`q_i` is the joint variable.

    :references:
        - Robotics, Vision & Control, P. Corke, Springer 2011, Chap 7.

    :seealso: :func:`RevoluteDH`, :func:`DHLink`, :func:`PrismaticMDH`
    """

    def __init__(
            self,
            theta=0.0,
            a=0.0,
            alpha=0.0,
            offset=0.0,
            qlim=np.zeros(2),
            flip=False,
            **kwargs
            ):

        d = 0.0
        sigma = 1
        mdh = False

        super().__init__(
            theta=theta, d=d, a=a, alpha=alpha, sigma=sigma, mdh=mdh,
            offset=offset, qlim=qlim, flip=flip, **kwargs)


class RevoluteMDH(DHLink):
    r"""
    Class for revolute links using modified DH convention

    :param d: kinematic - link offset
    :type d: float
    :param alpha: kinematic - link twist
    :type alpha: float
    :param a: kinematic - link length
    :type a: float
    :param offset: kinematic - joint variable offset
    :type offset: float

    :param qlim: joint variable limits [min, max]
    :type qlim: float ndarray(1,2)
    :param flip: joint moves in opposite direction
    :type flip: bool

    :param m: dynamic - link mass
    :type m: float
    :param r: dynamic - position of COM with respect to link frame
    :type r:  float ndarray(3)
    :param I: dynamic - inertia of link with respect to COM
    :type I: ndarray
    :param Jm: dynamic - motor inertia
    :type Jm: float
    :param B: dynamic - motor viscous friction: B=B⁺=B⁻, [B⁺, B⁻]
    :type B: float, or ndarray(2,)
    :param Tc: dynamic - motor Coulomb friction [Tc⁺, Tc⁻]
    :type Tc: ndarray(2,)
    :param G: dynamic - gear ratio
    :type G: float

    A subclass of the DHLink class for a revolute joint that holds all
    information related to a robot link such as kinematics parameters,
    rigid-body inertial parameters, motor and transmission parameters.

    The link transform is

    :math:`\mathbf{T}_{tx}(a_{i-1}) \cdot \mathbf{T}_{rx}(\alpha_{i-1}) \cdot \underbrace{\mathbf{T}_{rz}(q_i)}_{\mbox{variable}} \cdot \mathbf{T}_{tz}(d_i)`

    where :math:`q_i` is the joint variable.

    :references:
        - Robotics, Vision & Control, P. Corke, Springer 2011, Chap 7.

    :seealso: :func:`PrismaticMDH`, :func:`DHLink`, :func:`RevoluteDH`
    """

    def __init__(
            self,
            d=0.0,
            a=0.0,
            alpha=0.0,
            offset=0.0,
            qlim=np.zeros(2),
            flip=False,
            **kwargs
            ):

        theta = 0.0
        sigma = 0
        mdh = True

        super().__init__(
            d=d, alpha=alpha, theta=theta, a=a, sigma=sigma, mdh=mdh,
            offset=offset, qlim=qlim, flip=flip, **kwargs)


class PrismaticMDH(DHLink):
    r"""
    Class for prismatic link using modified DH convention

    :param theta: kinematic: joint angle
    :type theta: float
    :param d: kinematic - link offset
    :type d: float
    :param alpha: kinematic - link twist
    :type alpha: float
    :param a: kinematic - link length
    :type a: float
    :param offset: kinematic - joint variable offset
    :type offset: float

    :param qlim: joint variable limits [min, max]
    :type qlim: float ndarray(1,2)
    :param flip: joint moves in opposite direction
    :type flip: bool

    :param m: dynamic - link mass
    :type m: float
    :param r: dynamic - position of COM with respect to link frame
    :type r:  float ndarray(3)
    :param I: dynamic - inertia of link with respect to COM
    :type I: ndarray
    :param Jm: dynamic - motor inertia
    :type Jm: float
    :param B: dynamic - motor viscous friction: B=B⁺=B⁻, [B⁺, B⁻]
    :type B: float, or ndarray(2,)
    :param Tc: dynamic - motor Coulomb friction [Tc⁺, Tc⁻]
    :type Tc: ndarray(2,)
    :param G: dynamic - gear ratio
    :type G: float

    A subclass of the DHLink class for a prismatic joint that holds all
    information related to a robot link such as kinematics parameters,
    rigid-body inertial parameters, motor and transmission parameters.

    The link transform is

    :math:`\mathbf{T}_{tx}(a_{i-1}) \cdot \mathbf{T}_{rx}(\alpha_{i-1}) \cdot \mathbf{T}_{rz}(\theta_i) \cdot \underbrace{\mathbf{T}_{tz}(q_i)}_{\mbox{variable}}`

    where :math:`q_i` is the joint variable.

    :references:
        - Robotics, Vision & Control, P. Corke, Springer 2011, Chap 7.

    :seealso: :func:`RevoluteMDH`, :func:`DHLink`, :func:`PrismaticDH`
    """

    def __init__(
            self,
            theta=0.0,
            a=0.0,
            alpha=0.0,
            offset=0.0,
            qlim=np.zeros(2),
            flip=False,
            **kwargs
            ):

        d = 0.0
        sigma = 1
        mdh = True

        super().__init__(
            theta=theta, d=d, a=a, alpha=alpha, sigma=sigma, mdh=mdh,
            offset=offset, qlim=qlim, flip=flip, **kwargs)
