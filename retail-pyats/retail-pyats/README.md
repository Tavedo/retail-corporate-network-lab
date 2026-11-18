# Retail WAN HA — pyATS Validation

Automated validation for the **WAN high-availability** upgrade on the Retail
Corporate lab: a branch that keeps taking card payments even if its primary
circuit — or its whole provider — goes down, via a primary leased line plus an
**encrypted GRE/IPsec backup** with OSPF failover.

This suite proves the resilient state is correct **before** you need it —
green = ready to fail over, red = a gap.

> Personal interview-prep lab — keep this repo **private**.

---

## What it validates

**`tests/test_control_plane.py`**

| Testcase | Proves |
|---|---|
| `OSPF_Adjacencies` | OSPF neighbors FULL on HQ and Branch (expect **2 each** — primary link + backup tunnel) |

**`tests/test_wan_ha.py`**

| Testcase | Proves |
|---|---|
| `Backup_Tunnel_Up` | IKE phase 1 up (`QM_IDLE`), IPsec SAs installed (non-zero SPI), `Tunnel0` up/up |
| `Primary_Preferred` | the primary leased line is the active OSPF path; the cost-100 tunnel is standby (its next-hop is **absent** from the table) |
| `Failover_Ready` | the OSPF adjacency **over the tunnel** is FULL, so a primary failure reconverges in seconds |

The suite is **read-only** — it validates steady state. Failing the primary is
a deliberate manual drill (below), not something a validation run should do.

---

## Before you run — confirm 3 values

I built this from the WAN-HA design we verified together, but the exact
addresses live in your lab. Open the two files and confirm:

1. `testbed/testbed.yaml` → the **management IPs** for `HQ-ROUTER` and `BRANCH-ROUTER`.
2. `tests/test_wan_ha.py` → the three constants at the top:
   ```python
   PRIMARY_NEXTHOP = "172.16.0.2"      # branch end of the PRIMARY leased line
   TUNNEL_NEXTHOP  = "10.255.255.2"    # branch end of the GRE/IPsec TUNNEL
   TUNNEL_IF       = "Tunnel0"
   ```
   Get them from `show ip route ospf` and `show crypto session` on HQ-ROUTER.

---

## Run

On a Linux NOC control node that can reach the device management IPs (same
model as the SP lab — a node wired to the core, its mgmt subnet advertised
into OSPF):

```bash
python3 -m venv ~/venv && source ~/venv/bin/activate
pip install -r requirements.txt

export PYATS_USERNAME=netauto
export PYATS_PASSWORD='<your-password>'
export PYATS_ENABLE='<your-password>'

pyats run job jobs/full_test_job.py --testbed-file testbed/testbed.yaml
```

---

## The failover drill (manual)

To actually watch it fail over — the thing you demo in an interview:

```
! on a PC behind the branch, start a continuous ping to an HQ server
ping 10.60.60.x -t            (Windows)   /   ping 10.60.60.x   (IOS, repeat 1000)

! on HQ or branch, drop the primary leased line
interface <primary-WAN>
 shutdown

! expect ~2-3 lost packets, then recovery. Confirm the backup took over:
show ip route ospf            # branch subnets now via the Tunnel0 next-hop
show crypto ipsec sa          # #pkts encaps / decaps climbing - traffic is encrypted now
```

Re-run the pyATS job while the primary is shut and `Primary_Preferred` will go
**red** on purpose (traffic is on the tunnel) — proof the test actually detects
the failed-over state. Bring the primary back up and it returns to green.

---

## Why GRE *and* IPsec

IPsec alone can't carry OSPF (it doesn't do multicast); GRE tunnels the routing,
IPsec encrypts it. *"GRE for the ride, IPsec for the lock."* And the tunnel
destination must be reachable over the **physical** transport, never through the
tunnel itself, or it flaps (`%TUN-5-RECURDOWN`) — keep the underlay subnet
connected-only, out of OSPF.

---

## Layout

```
retail-pyats/
├── README.md
├── requirements.txt
├── testbed/testbed.yaml          # HQ + Branch, telnet, env-var credentials
├── tests/
│   ├── test_control_plane.py     # OSPF adjacencies
│   └── test_wan_ha.py            # tunnel/IPsec + primary-preferred + failover-ready
└── jobs/full_test_job.py
```
