"""pyATS job - Retail WAN HA validation.

    export PYATS_USERNAME=netauto
    export PYATS_PASSWORD='<your-password>'
    export PYATS_ENABLE='<your-password>'
    pyats run job jobs/full_test_job.py --testbed-file testbed/testbed.yaml
"""
import os
from pyats.easypy import run

HERE = os.path.dirname(os.path.abspath(__file__))
TESTS = os.path.normpath(os.path.join(HERE, "..", "tests"))


def main(runtime):
    run(testscript=os.path.join(TESTS, "test_control_plane.py"), runtime=runtime)
    run(testscript=os.path.join(TESTS, "test_wan_ha.py"), runtime=runtime)
