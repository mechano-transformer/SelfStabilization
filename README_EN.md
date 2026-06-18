# Self Stabilizer

Automatic alignment convergence control system using an autocollimator and piezo motor (PAMC-204).

## Requirements

- Windows, Python 3.10+, `pamc204.dll`

```bash
pip install pyserial numpy
```

---

## CLI (Convergence Control)

```bash
# Convergence control (auto-converge to target=0,0, exits on threshold)
python cli.py adc --rev1 --kp 0.7 --ppu 37 --threshold 0.1

# Read current position
python cli.py status

# Direction test (show AC values before/after drive)
python cli.py test_dir 1 3000

# Relative move / stop
python cli.py move 1 3000
python cli.py stop_all
```

### ADC Parameters

| Parameter | Default | Description |
|---|---|---|
| `--target_x/y` | 0.0 | Target position (um) |
| `--kp` | 0.5 | Proportional gain (0.5–0.9 recommended) |
| `--ppu` | 9996.0 | Piezo calibration (pulses/um) |
| `--threshold` | 0.1 | Convergence threshold (um). Auto-exits when within range |
| `--max_step` | 50000 | Max pulses per step |
| `--max_iter` | 200 | Max iterations |
| `--swap` | off | Swap X/Y axes |
| `--rev1/--rev2` | off | Reverse Axis 1/2 |
| `--ac_port` | COM11 | Autocollimator COM port |
| `--addr` | 2 | PAMC-204 address |
| `--distance` | 50.0 | Sensor distance (mm) |

### Current Hardware Configuration

```
python cli.py adc --rev1 --kp 0.7 --ppu 37 --threshold 0.1
# addr=2, ac_port=COM11, swap=off, rev1=on, rev2=off, ppu≈37
```

---

## GUI

```bash
python main.py                             # PAMC-204 (default)
python main.py --mode pamc104 --port COM3  # PAMC-104
```

---

## File Structure

| File | Description |
|---|---|
| `cli.py` | CLI convergence control tool |
| `main.py` | GUI entry point |
| `gui.py` | GUI (ADCGUI) |
| `adc_thread.py` | ADC control thread (for GUI) |
| `ac_thread.py` | Autocollimator reader thread |
| `pamc204_wrapper.py` | PAMC-204 DLL wrapper |
| `pamc104_wrapper.py` | PAMC-104 RS232C wrapper |
| `auto_divisioner.py` | Automatic axis assignment |
| `ADC_CONTROL.md` | ADC control method documentation |
