"""Retail WAN - control-plane health: OSPF adjacencies FULL on HQ and Branch.

With the WAN-HA upgrade, HQ and Branch have TWO OSPF adjacencies each:
one over the primary leased line, one over the GRE/IPsec backup tunnel.
Both must be FULL for failover to be ready.
"""
import re
from pyats import aetest

ROUTERS = ["HQ-ROUTER", "BRANCH-ROUTER"]


class CommonSetup(aetest.CommonSetup):
    @aetest.subsection
    def connect(self, testbed):
        for name in ROUTERS:
            testbed.devices[name].connect(log_stdout=False, learn_hostname=True)


class OSPF_Adjacencies(aetest.Testcase):
    """Every OSPF neighbor must be FULL (primary link AND backup tunnel)."""
    @aetest.test
    def all_full(self, testbed, steps):
        for name in ROUTERS:
            dev = testbed.devices[name]
            with steps.start(f"{name} OSPF FULL", continue_=True) as step:
                out = dev.execute("show ip ospf neighbor")
                full = re.findall(r"\bFULL\b", out)
                bad = re.findall(r"\b(INIT|EXSTART|EXCHANGE|LOADING|2WAY|DOWN|ATTEMPT)\b", out)
                if not full:
                    step.failed(f"{name}: no FULL neighbors")
                elif bad:
                    step.failed(f"{name}: non-FULL states {set(bad)}")
                else:
                    step.passed(f"{name}: {len(full)} FULL (expect 2 - primary + tunnel)")


class CommonCleanup(aetest.CommonCleanup):
    @aetest.subsection
    def disconnect(self, testbed):
        for name in ROUTERS:
            d = testbed.devices[name]
            if d.is_connected():
                d.disconnect()
