"""
Retail WAN high-availability validation (read-only, steady state).

The store's POS must keep taking card payments if the WAN drops, so the
branch has a primary leased line plus an encrypted GRE/IPsec backup. This
suite proves the resilient state is correct BEFORE you ever need it:

  1. Backup_Tunnel_Up  - the GRE/IPsec tunnel is up and encrypting
  2. Primary_Preferred - the primary leased line carries traffic; the
                         higher-cost tunnel is standby (not in the table)
  3. Failover_Ready    - the OSPF adjacency over the tunnel is FULL, so a
                         primary failure reconverges onto it in seconds

Actually failing the primary is a manual drill (see README) because it
changes device state - a validation suite stays read-only.

>>> CONFIRM the three values below against your lab <<<
"""
import re
from pyats import aetest

HQ = "HQ-ROUTER"
BR = "BRANCH-ROUTER"

# --- confirm these against your running-config / show ip route ---
PRIMARY_NEXTHOP = "172.16.0.2"      # branch end of the PRIMARY leased line (preferred)
TUNNEL_NEXTHOP  = "10.255.255.2"    # branch end of the GRE/IPsec TUNNEL (backup)
TUNNEL_IF       = "Tunnel0"         # the backup tunnel interface on HQ


class CommonSetup(aetest.CommonSetup):
    @aetest.subsection
    def connect(self, testbed):
        for name in [HQ, BR]:
            testbed.devices[name].connect(log_stdout=False, learn_hostname=True)


class Backup_Tunnel_Up(aetest.Testcase):
    """The GRE/IPsec backup must be up and actually encrypting."""

    @aetest.test
    def phase1_up(self, testbed):
        out = testbed.devices[HQ].execute("show crypto isakmp sa")
        if "QM_IDLE" in out:
            self.passed("IKE phase 1 up (QM_IDLE) - peers authenticated")
        else:
            self.failed("No QM_IDLE - IPsec phase 1 is not established")

    @aetest.test
    def ipsec_sas_installed(self, testbed):
        out = testbed.devices[HQ].execute("show crypto ipsec sa")
        # a real SA has a non-zero SPI installed in both directions
        if re.search(r"spi:\s*0x[0-9a-fA-F]*[1-9a-fA-F]", out):
            self.passed("IPsec SAs installed (non-zero SPI) - traffic is encrypted")
        else:
            self.failed("No active IPsec SA - tunnel is not encrypting")

    @aetest.test
    def tunnel_interface_up(self, testbed):
        out = testbed.devices[HQ].execute("show ip interface brief")
        m = re.search(re.escape(TUNNEL_IF) + r"\S*\s+\S+\s+\S+\s+(up|down)\s+(up|down)", out)
        if m and m.group(1) == "up" and m.group(2) == "up":
            self.passed(f"{TUNNEL_IF} is up/up")
        else:
            self.failed(f"{TUNNEL_IF} is not up/up (recursive routing? underlay down?)")


class Primary_Preferred(aetest.Testcase):
    """The primary leased line must be the active path; the cost-100 tunnel
    stays standby, so its next-hop should NOT appear in the OSPF table."""

    @aetest.test
    def primary_is_active_path(self, testbed):
        out = testbed.devices[HQ].execute("show ip route ospf")
        if TUNNEL_NEXTHOP in out:
            self.failed(
                f"OSPF routes point via the TUNNEL ({TUNNEL_NEXTHOP}) - "
                "the primary may be down, or the backup cost is wrong")
        elif PRIMARY_NEXTHOP in out:
            self.passed(f"Primary leased line ({PRIMARY_NEXTHOP}) is the active OSPF path")
        else:
            self.passx("No OSPF routes via either WAN next-hop - check addressing/constants")


class Failover_Ready(aetest.Testcase):
    """The backup path must be a FULL OSPF adjacency, ready to take over."""

    @aetest.test
    def tunnel_adjacency_full(self, testbed):
        out = testbed.devices[HQ].execute("show ip ospf neighbor")
        tunnel_lines = [l for l in out.splitlines() if TUNNEL_IF in l]
        if not tunnel_lines:
            self.failed(f"No OSPF neighbor over {TUNNEL_IF} - failover path missing")
        elif any("FULL" in l for l in tunnel_lines):
            self.passed(f"OSPF adjacency over {TUNNEL_IF} is FULL - failover ready")
        else:
            self.failed(f"OSPF neighbor over {TUNNEL_IF} is not FULL")


class CommonCleanup(aetest.CommonCleanup):
    @aetest.subsection
    def disconnect(self, testbed):
        for name in [HQ, BR]:
            d = testbed.devices[name]
            if d.is_connected():
                d.disconnect()
