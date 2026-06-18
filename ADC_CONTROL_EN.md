# ADC Control Method Documentation

## Overview

A P-control loop that converges autocollimator reading errors to zero.
CLI (`cli.py adc`) and GUI (`adc_thread.py`) use identical logic.

## Control Method: Simple P-Control + Sequential Drive

```
AC read → error calculation → pulse calculation → X-axis drive+wait → Y-axis drive+wait → repeat
```

PAMC-204 does not support simultaneous 2-axis drive, so axes are driven sequentially: X then Y.

### Pulse Calculation

```
pulses = -round(Kp × error_um × ppu)
pulses = clamp(pulses, -max_step, +max_step)
if reverse: pulses = -pulses
```

- `error_um`: current position - target position (in um)
- `ppu`: pulses per um (measured value ≈ 37)
- `Kp`: proportional gain (recommended 0.7)

### Wait Time

After each axis drive: `|pulses| / 1500 + 0.5s`

- 1500 Hz = motor drive speed (hardware limit)
- 0.5s = mechanical settling + AC read stabilization

### Convergence Criterion

Both axes |error| ≤ threshold → converged. CLI auto-exits, GUI auto-stops with display update.

## Parameters

| Parameter | Value | Description |
|---|---|---|
| `Kp` | 0.7 | Proportional gain (GUI/CLI shared default) |
| `ppu` | 37.0 | pulses/um (measured calibration value) |
| `threshold` | 0.1 um | Convergence threshold |
| `max_step` | 50000 | Max pulses per step |
| Motor speed | 1500 Hz | Hardware limit, fixed |
| Settle time | 0.5s | Post-drive wait time |

## Axis Configuration (Current Hardware)

| Setting | Value | Meaning |
|---|---|---|
| PAMC-204 Address | 2 (E02) | Device address |
| Swap X/Y | OFF | X→ch2, Y→ch1 |
| Reverse Axis 1 | **ON** | ch1 +pulses → Y decreases |
| Reverse Axis 2 | OFF | ch2 +pulses → X increases |
| AC Port | COM11 | Autocollimator (38400 bps) |
| PAMC-204 Port | COM10 | USB Serial (FTDI) |

## PAMC-204 Commands Used

| Command | Syntax | Purpose |
|---|---|---|
| Relative move | `ExxmPRnnnn` | Step drive via P-control |
| Set velocity | `ExxmVAnnnn` | Fixed to 1500 Hz on connect() |
| Stop all axes | `ExxAB` | Emergency stop |

## Control Flow Diagram

```
Start ADC
  │
  ▼
AC read (pos_x, pos_y in um) ←─────────┐
  │                                      │
  ├─ err_x = pos_x - target_x           │
  ├─ err_y = pos_y - target_y           │
  │                                      │
  ├─ Both |err| ≤ threshold             │
  │   → CONVERGED → auto-stop           │
  │                                      │
  ├─ |err_x| > threshold                │
  │   → pulses = -round(Kp*err*ppu)     │
  │   → move_relative(ch_x, pulses)     │
  │   → sleep(|pulses|/1500 + 0.5)      │
  │                                      │
  ├─ |err_y| > threshold                │
  │   → pulses = -round(Kp*err*ppu)     │
  │   → move_relative(ch_y, pulses)     │
  │   → sleep(|pulses|/1500 + 0.5)      │
  │                                      │
  └──────────────────────────────────────┘
```
