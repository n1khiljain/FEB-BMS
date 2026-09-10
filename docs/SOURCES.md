# BMS Reference Rules/Sources


## Cell / module limits (datasheet Table 1, rated at 25 °C)

| Parameter | Value |
|---|---|
| Cell voltage range | 2.50 V min · 3.60 V nominal · 4.20 V max |
| Capacity | 10.2 Ah typ (36.7 Wh) at 10 A; 9.8 Ah at 100 A |
| Charge current, max | 15 A (no cooling, in a pack) · 20 A (forced air) · 120 A 10 s pulse |
| Discharge current, max | 60 A (no cooling, in a pack) · 120 A (forced air) · 180 A 10 s pulse |
| Internal fuse holding current | 180 A |
| Internal impedance | 5.4 mΩ typ, 6.0 mΩ max |
| Discharge temperature | −20 °C to 60 °C |
| Charge temperature | 0 °C to 45 °C |
| Temp sensor range | −40 °C to 120 °C (non-linear voltage output, ~2.17 V at 0 °C, 1.51 V at 60 °C) |

## Rules (FSAE 2026)

| Requirement | Value | Rule |
|---|---|---|
| High Voltage definition | > 60 V DC or > 25 V AC RMS | T.9.1.1 |
| Low Voltage definition | ≤ 60 V DC or ≤ 25 V AC RMS | T.9.1.2 |
| Max tractive system voltage | 600 V DC between any two points | EV.3.3.2 |
| Max power at Energy Meter | 80 kW | EV.3.3.1 |
| No regen at low speed | 0–5 km/h | EV.3.3.3 |
| Isolation Relays | ≥ 2, normally open, open both poles | EV.5.4.1–5.4.2 |
| IR hold after shutdown opens | Capacitor may hold IRs closed ≤ 250 ms | EV.5.4.5 |
| Precharge target | ≥ 90 % of TS voltage before closing second IR; end of precharge must be feedback-controlled by measuring intermediate-circuit voltage | EV.5.6.1–5.6.2 |
| Precharge relay | Mechanical relay; supplied from Shutdown Circuit | EV.5.6.5, EV.5.6.1.b |
| Discharge circuit | Always active when Shutdown Circuit open; unfused; survives max TS voltage ≥ 15 s | EV.5.6.3 |
| Shutdown Circuit members | BMS, IMD, BSPD, interlocks, master switches, shutdown buttons, BOTS, inertia switch — in series | EV.7.1.1 |
| BMS/IMD/BSPD contacts | Normally open, fully independent circuits | EV.7.1.3–7.1.4 |
| When Shutdown Circuit opens | TS shuts down, battery current stops immediately, TS ≤ 60 V within 5 s, motors spin free | EV.7.2.2 |
| BMS fault latch / reset | TS stays disabled until manual reset by a person at the vehicle; driver cannot reset from inside; buttons/TSMS cannot re-close it | EV.7.2.3 |
| BMS must monitor when | TS Active, or battery connected to charger | EV.7.3.1 |
| Cell balancing | Not allowed while Shutdown Circuit is open | EV.7.3.3 |
| BMS must monitor for | (a) voltage out of range (b) voltage-sense fuse blown (c) temp out of range (d) missing/interrupted V or T measurement (e) BMS internal fault | EV.7.3.4 |
| BMS fault action | Open Shutdown Circuit + turn on red "BMS" light and TS Status Indicator; lights stay on until manual reset | EV.7.3.5 |
| Voltage measurement | Every cell; one measurement per parallel group is fine | EV.7.4.1 |
| Voltage limits | Datasheet min/max; measurement accuracy must be considered | EV.7.4.2 |
| Temperature limit | Lower of datasheet max or 60 °C (→ 60 °C discharge, 45 °C charge); accuracy considered | EV.7.5.2 |
| Temp sensor placement | Negative terminal, or busbar < 10 mm from it | EV.7.5.3–7.5.4 |
| Temp sensor coverage | ≥ 20 % of cells, evenly distributed; every cell recommended | EV.7.5.5 |
| Charging faults | BMS/IMD open Charging Shutdown Circuit; current stops immediately, TS ≤ 60 V in 5 s, charger off and disabled until manual reset | EV.8.4 |
| Activation sequence | GLV on → Shutdown Circuit closed → TS Active → Ready to Drive | EV.9.2–9.4 |
| Ready to Drive gate | TS Active + brake pedal held + driver presses a button | EV.9.6.2 |
| Ready to Drive sound | 1–3 s, ≥ 80 dBA | EV.9.7 |

## Team-specific (ask the team)
- Number of modules in series on SN4 / SN5 (pack voltage = N × 3.6 V nominal, N × 4.2 V max)
- Precharge resistor R and intermediate-circuit capacitance C (sets precharge time ≈ 5·R·C)

## Thresholds to use in code (limits minus sensor margin, per EV.7.4.2 / EV.7.5.2)

| Check | Hard limit | Code trip point |
|---|---|---|
| Cell over-voltage | 4.20 V | 4.15 V |
| Cell under-voltage | 2.50 V | 2.60 V |
| Over-temp, discharge | 60 °C | 55 °C |
| Over-temp, charge | 45 °C | 40 °C |
| Under-temp, charge | 0 °C | 3 °C |
| Under-temp, discharge | −20 °C | −15 °C |
| Over-current, discharge | 60 A / module (no cooling) | 55 A |
| Over-current, charge | 15 A / module (no cooling) | 13 A |
| Precharge complete | ≥ 90 % pack V | 90 % + timeout |
| Sensor missing / stale | any | fault (EV.7.3.4.d) |