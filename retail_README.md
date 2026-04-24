# Retail Corporate Network Lab — Enterprise LAN/WAN/WLAN

Two-site enterprise corporate network built in Cisco Modeling Labs.
Simulates a retail company with HQ and one branch store.
Built as hands-on preparation for network technician roles covering LAN/WAN/WLAN environments.

---

## Topology

```
        INTERNET
            |
       [HQ-ROUTER]  ─── WAN 172.16.0.0/30 ───  [BRANCH-ROUTER]
            |                                          |
     [HQ-CORE-SW L3]                            [BRANCH-SW]
      /           \                             /        \
[HQ-ACC-SW1]  [HQ-ACC-SW2]          [BRANCH-POS-PC]  [BRANCH-STAFF-PC]
  |   |   |      |    |                VLAN 30           VLAN 20
 V20 V30 V40    V60  V50
```

**10 nodes · 10 links · IOSv + IOSvL2 + Desktop**

---

## Devices

| Device | Type | Role |
|---|---|---|
| HQ-ROUTER | IOSv | Internet uplink, NAT/PAT, WAN, OSPF |
| HQ-CORE-SW | IOSvL2 | Layer 3 core — inter-VLAN routing, DHCP server |
| HQ-ACC-SW1 | IOSvL2 | Access switch — Staff, POS, Guest WiFi VLANs |
| HQ-ACC-SW2 | IOSvL2 | Access switch — Servers, Cameras VLANs |
| HQ-STAFF-PC | Desktop | End device — VLAN 20 |
| HQ-SERVER | Desktop | End device — VLAN 60 |
| BRANCH-ROUTER | IOSv | Branch WAN, router-on-a-stick, DHCP |
| BRANCH-SW | IOSvL2 | Branch access switch |
| BRANCH-POS-PC | Desktop | End device — VLAN 30 |
| BRANCH-STAFF-PC | Desktop | End device — VLAN 20 |

---

## Technologies

- **VLANs** — 6 VLANs at HQ, 3 at branch, 802.1Q trunking
- **Inter-VLAN routing** — Layer 3 switching on HQ-CORE-SW (SVI per VLAN)
- **Router-on-a-stick** — subinterfaces on BRANCH-ROUTER for branch VLANs
- **OSPF area 0** — dynamic routing between HQ and branch over WAN link
- **DHCP** — separate pool per VLAN, excluded addresses, DNS pushed to clients
- **NAT/PAT** — internet access for all internal devices via HQ-ROUTER
- **ACLs** — Guest WiFi isolated from all internal networks, POS isolated (PCI principle)
- **STP RSTP** — rapid spanning tree on all switches, PortFast on access ports
- **Static default route** — redistributed into OSPF so branch learns internet path

---

## VLAN Table

| VLAN | Name | Purpose | HQ Subnet | Branch Subnet |
|---|---|---|---|---|
| 10 | MANAGEMENT | Switch management | 10.10.10.0/24 | — |
| 20 | STAFF | Office computers | 10.20.20.0/24 | 10.20.21.0/24 |
| 30 | POS | Point of Sale terminals | 10.30.30.0/24 | 10.30.31.0/24 |
| 40 | GUEST-WIFI | Customer WiFi (internet only) | 10.40.40.0/24 | 10.40.41.0/24 |
| 50 | CAMERAS | IP cameras / IoT | 10.50.50.0/24 | — |
| 60 | SERVERS | File and application servers | 10.60.60.0/24 | — |

---

## IP Addressing

| Link | Subnet | Side A | Side B |
|---|---|---|---|
| HQ-ROUTER G0/0 — Internet | 203.0.113.0/30 | .2 | .1 (ISP) |
| HQ-ROUTER G0/1 — HQ-CORE-SW | 10.0.0.0/30 | .1 | .2 |
| HQ-ROUTER G0/2 — BRANCH-ROUTER | 172.16.0.0/30 | .1 | .2 |

---

## Security Design

### Guest WiFi isolation (VLAN 40)
```
ip access-list extended GUEST-ISOLATION
 deny   ip 10.40.40.0 0.0.0.255 10.0.0.0 0.255.255.255
 permit ip 10.40.40.0 0.0.0.255 any

interface Vlan40
 ip access-group GUEST-ISOLATION in
```
Guest devices can reach the internet but cannot access any internal subnet.

### POS isolation (VLAN 30 — PCI compliance principle)
```
ip access-list extended POS-ISOLATION
 permit ip 10.30.30.0 0.0.0.255 10.60.60.0 0.0.0.255
 deny   ip 10.30.30.0 0.0.0.255 10.0.0.0 0.255.255.255
 permit ip 10.30.30.0 0.0.0.255 any

interface Vlan30
 ip access-group POS-ISOLATION in
```
POS terminals can reach servers (for payment processing) and the internet, but nothing else internal.

---

## OSPF Design

```
HQ-ROUTER (router-id 1.1.1.1)
  - G0/1 to HQ-CORE-SW  → area 0
  - G0/2 to BRANCH-ROUTER → area 0
  - passive-interface G0/0 (internet facing)
  - default-information originate always

HQ-CORE-SW (router-id 3.3.3.3)
  - G0/0 to HQ-ROUTER → area 0
  - Vlan10, Vlan20, Vlan60 → area 0
  - passive-interface on all user-facing VLANs

BRANCH-ROUTER (router-id 2.2.2.2)
  - G0/0 to HQ-ROUTER WAN → area 0
  - G0/1.20, G0/1.30 → area 0
  - passive-interface on all subinterfaces
```

All sites learn each other's subnets automatically. Branch learns default route via OSPF from HQ.

---

## Key Lessons Learned

1. **VLAN must exist before it can be assigned** — create vlan X before switchport access vlan X
2. **Trunk must explicitly allow VLANs** — forgetting a VLAN in the allowed list silently drops traffic
3. **`ip routing` is mandatory on Layer 3 switch** — without it, SVIs exist but cannot route between them
4. **DHCP `excluded-address` must come before the pool** — otherwise the gateway IP gets handed out
5. **OSPF `passive-interface` on user VLANs** — prevents OSPF hello packets flooding to end devices
6. **`no switchport` on routed port** — required on L3 switch uplink before assigning an IP address
7. **Loopback0 for OSPF router-id** — always configure explicitly, do not rely on automatic selection
8. **ACL direction `in` on source VLAN** — wrong direction means the rule never matches real traffic
9. **`default-information originate always`** — the `always` keyword is required when the default route is static (not learned via OSPF)
10. **Router-on-a-stick subinterface** — parent interface must be `no shutdown` even if only subinterfaces carry traffic

---

## Verification Commands

```bash
# OSPF neighbors
show ip ospf neighbor

# Routing table
show ip route

# VLAN status
show vlan brief

# Trunk interfaces
show interfaces trunk

# DHCP assignments
show ip dhcp binding

# ACL hit counters
show ip access-lists

# Interface status
show ip interface brief

# Spanning tree
show spanning-tree summary
```

---

## How to Import

1. Download `retail_corporate_lab.yaml`
2. CML UI → **Tools → Import Lab** → select the file
3. Start the lab — all configs load automatically
4. Verify: `show ip ospf neighbor` on HQ-ROUTER — expect FULL with both neighbors
5. Test: ping from BRANCH-STAFF-PC to HQ Staff subnet (10.20.20.x)

---

## Related Lab

Also see: [Africa SP NOC Lab](../africa-sp-noc-lab) — service provider MPLS/BGP/VPN network
simulating multi-country African connectivity.

---

*Built as part of network technician interview preparation.*
*CCNA certified — hands-on lab portfolio.*
