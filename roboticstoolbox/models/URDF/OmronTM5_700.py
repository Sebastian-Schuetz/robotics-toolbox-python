#!/usr/bin/env python

import numpy as np
from roboticstoolbox.robot.ERobot import ERobot
from math import pi


class OmronTM5_700(ERobot):
    """
    Class that imports a Omron/Techman TM5 700 URDF model

    ``OmronTM5()`` is a class which imports a Omron/Techman TM5 700 robot definition
    from a URDF file.  The model describes its kinematic and graphical
    characteristics.

    .. runblock:: pycon

        >>> import roboticstoolbox as rtb
        >>> robot = rtb.models.URDF.OmronTM5()
        >>> print(robot)

    Defined joint configurations are:

    - qz, zero joint angle configuration, 'L' shaped configuration
    - qr, vertical 'READY' configuration
    - qs, arm is stretched out in the x-direction
    - qn, arm is at a nominal non-singular configuration


    .. note:: The original file is from https://github.com/TechmanRobotInc/tmr_ros1/blob/master/tm5_description/urdf/tm5_700_robot.urdf.xacro

    .. codeauthor:: Jesse Haviland, mod. by Sebastian Schuetz
    .. sectionauthor:: Peter Corke
    """

    def __init__(self):

        links, name = self.URDF_read(
            "tm5_description/urdf/tm5_700_robot.urdf.xacro")

        super().__init__(
            links,
            name=name)

        self.manufacturer = "Omron"
        # self.ee_link = self.ets[9]

        # zero angles, straight standing up
        self.addconfiguration("qz", np.array([0, 0, 0, 0, 0, 0]))

        # ready pose, arm 90°
        self.addconfiguration("qr", np.array([-pi/4, 0, pi/2, 0, pi/2, pi]))

        # straight and horizontal -> same as qr
        self.addconfiguration("qs", np.array([-pi/4, 0, pi/2, 0, pi/2, pi]))

        # nominal table top picking pose -> same as qr
        self.addconfiguration("qn", np.array([-pi/4, 0, pi/2, 0, pi/2, pi]))


if __name__ == '__main__':   # pragma nocover

    robot = OmronTM5_700()
    print(robot)
