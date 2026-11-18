## WAN High Availability (resilience upgrade)

The original design had a **single WAN link** from the branch to HQ — a single
point of failure. In retail that is business-critical: if the link drops, the
store's POS cannot reach the payment/inventory servers and **the tills stop
taking card payments**. This upgrade removes that gap in two stages.

### Stage 1 — Redundant WAN path with OSPF failover

A second WAN link is added and made a **backup** using OSPF cost. The primary
carries all traffic; if it fails, OSPF reconverges onto the backup in a few
seconds (≈2–3 packets lost).

```
                 ┌── Primary WAN 172.16.0.0/30  (low cost, preferred) ──┐
   HQ-ROUTER ────┤                                                      ├──── BRANCH-ROUTER
                 └── Backup  WAN 172.16.1.0/30  (cost 100, standby)  ───┘
```

```
! HQ-ROUTER G0/3  (and BRANCH-ROUTER G0/2, mirror)
interface GigabitEthernet0/3
 description BACKUP-WAN
 ip address 172.16.1.1 255.255.255.252
 ip ospf 1 area 0
 ip ospf cost 100
 no shutdown
```

### Stage 2 — Diverse transport: encrypted internet backup (GRE/IPsec)

Two links between the same routers prove failover but are not *diverse* — a
single provider outage could take both. The backup is upgraded to ride the
**public internet as an encrypted GRE/IPsec VPN**, so the two paths use
independent transport. OSPF runs **inside** the tunnel as the backup route.

```
Primary : 172.16.0.0/30  — plain OSPF over the trusted leased line (preferred)
Backup  : GRE + IPsec Tunnel0 over "broadband" 172.16.1.0/30 — OSPF inside, cost 100
```

```
! Both routers (mirror the peer/source/destination)
crypto isakmp policy 10
 encryption aes 256
 hash sha256
 authentication pre-share
 group 14
crypto isakmp key RetailVPNKey123 address <peer-transport-ip>
crypto ipsec transform-set TSET esp-aes 256 esp-sha256-hmac
 mode transport
crypto ipsec profile RETAIL-VPN
 set transform-set TSET
!
interface Tunnel0
 description BACKUP-VPN
 ip address 10.255.255.1 255.255.255.252     ! .2 on branch
 ip ospf 1 area 0
 ip ospf cost 100
 tunnel source GigabitEthernet0/3            ! G0/2 on branch
 tunnel destination <peer-transport-ip>
 tunnel protection ipsec profile RETAIL-VPN
```

### Verification / failover test

```
show crypto isakmp sa        # QM_IDLE — backup tunnel encrypted and up
show ip ospf neighbor        # neighbour over Tunnel0 + the primary
show ip route ospf           # HQ subnets via primary (low cost); tunnel is standby

# Demo: continuous ping BRANCH-POS-PC -> HQ server (10.60.60.x),
# then shut the primary WAN. Expect ~2-3 packets lost, then recovery:
show crypto ipsec sa         # encaps/decaps climbing — traffic now encrypted over backup
```

### Why this matters (retail)

> The store now has a primary leased line and an encrypted internet backup,
> with OSPF failing over automatically. The POS keeps processing card payments
> even if the primary circuit — or the entire primary provider — goes down.

### Additional lessons learned

11. **OSPF cost makes a backup** — raise the backup link/tunnel cost so it stays idle until the primary fails. Lowest total cost wins.
12. **GRE + IPsec together** — IPsec alone can't carry OSPF (multicast); GRE tunnels the routing, IPsec encrypts it. "GRE for the ride, IPsec for the lock."
13. **Recursive routing** — the tunnel destination must be reachable over the *physical* transport, never learned through the tunnel itself, or the tunnel flaps (`%TUN-5-RECURDOWN`). Keep the underlay subnet connected-only, out of OSPF.
14. **Diverse transport** — true WAN resilience means the backup uses a different provider/path, not just a second cable to the same place.
