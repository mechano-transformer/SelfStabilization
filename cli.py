"""
PAMC-204 + オートコリメータ CLI ツール

使い方:
  python cli.py status                    -- AC読み取り + 現在位置表示
  python cli.py move <ch> <pulses>        -- 相対移動 (例: move 1 3000)
  python cli.py move_inf <ch> <dir> <sec> -- 無限移動 (例: move_inf 1 + 2.0)
  python cli.py stop <ch>                 -- 軸停止
  python cli.py stop_all                  -- 全軸停止
  python cli.py read [count] [interval]   -- AC連続読み取り (例: read 10 0.5)
  python cli.py test_dir <ch> <pulses>    -- 方向テスト: 駆動前後のAC値を表示
  python cli.py adc [--target_x X] [--target_y Y] [--kp KP] [--max_iter N]
                                          -- ADC制御ループ実行

環境:
  --ac_port  : オートコリメータCOMポート (default: COM11)
  --addr     : PAMC-204 アドレス (default: 2)
  --distance : センサー距離 mm (default: 50)
"""
import argparse
import ctypes
from ctypes import wintypes, c_char_p, c_char, c_int
import math
import os
import serial
import sys
import time


class PAMC204CLI:
    """PAMC-204 DLL の軽量ラッパー (CLI用)。"""

    def __init__(self, address: int = 2):
        self.address = address
        dll_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "pamc204.dll")
        self.lib = ctypes.CDLL(dll_path)
        self._setup()

    def _setup(self):
        lib = self.lib
        lib.pamc204_check_device.restype = wintypes.BOOL
        lib.pamc204_check_device.argtypes = [wintypes.INT]
        lib.pamc204_move_relative.restype = wintypes.BOOL
        lib.pamc204_move_relative.argtypes = [wintypes.INT, wintypes.INT, wintypes.INT]
        lib.pamc204_move_infinite.restype = wintypes.BOOL
        lib.pamc204_move_infinite.argtypes = [wintypes.INT, wintypes.INT, c_char]
        lib.pamc204_stop_motion.restype = wintypes.BOOL
        lib.pamc204_stop_motion.argtypes = [wintypes.INT, wintypes.INT]
        lib.pamc204_stop_motion_all_channels.restype = wintypes.BOOL
        lib.pamc204_stop_motion_all_channels.argtypes = [wintypes.INT]
        lib.pamc204_set_velocity.restype = wintypes.BOOL
        lib.pamc204_set_velocity.argtypes = [wintypes.INT, wintypes.INT, wintypes.INT]
        lib.pamc204_send_command.restype = wintypes.BOOL
        lib.pamc204_send_command.argtypes = [c_char_p, c_char_p, c_int]

    def connect(self) -> bool:
        ok = bool(self.lib.pamc204_check_device(self.address))
        if ok:
            for ch in (1, 2):
                self.lib.pamc204_set_velocity(self.address, ch, 1500)
        return ok

    def move_relative(self, ch: int, pulses: int) -> bool:
        return bool(self.lib.pamc204_move_relative(self.address, ch, pulses))

    def move_infinite(self, ch: int, direction: str) -> bool:
        d = b'+' if direction == '+' else b'-'
        return bool(self.lib.pamc204_move_infinite(self.address, ch, d))

    def stop_motion(self, ch: int) -> bool:
        return bool(self.lib.pamc204_stop_motion(self.address, ch))

    def stop_all(self) -> bool:
        return bool(self.lib.pamc204_stop_motion_all_channels(self.address))

    def send_command(self, cmd: str) -> tuple[bool, str]:
        resp = ctypes.create_string_buffer(256)
        ok = bool(self.lib.pamc204_send_command(cmd.encode('ascii'), resp, 256))
        return ok, resp.value.decode('ascii', errors='replace').strip()


class AutocollimatorCLI:
    """オートコリメータ シリアル通信 (CLI用)。"""

    def __init__(self, port: str = "COM11", distance_mm: float = 50.0):
        self.distance_mm = distance_mm
        self.ser = serial.Serial(
            port=port, baudrate=38400, timeout=0.5,
            bytesize=serial.EIGHTBITS, parity=serial.PARITY_NONE,
            stopbits=serial.STOPBITS_ONE
        )

    def read(self) -> dict | None:
        """1回読み取り。position (um) と angle (mrad) を返す。"""
        try:
            self.ser.write(b"G\r\n")
            line = self.ser.readline().decode("ascii")
            parts = line.split(",")
            ang_x = float(parts[2].strip())
            ang_y = float(parts[3].strip())
            dis = self.distance_mm
            pos_x = dis * 1000 * math.tan(ang_x / 1000)
            pos_y = dis * 1000 * math.tan(ang_y / 1000)
            return {"pos_x": pos_x, "pos_y": pos_y, "ang_x": ang_x, "ang_y": ang_y}
        except Exception as e:
            print(f"AC read error: {e}")
            return None

    def close(self):
        self.ser.close()


# ── コマンド実装 ──

def cmd_status(ac: AutocollimatorCLI, pamc: PAMC204CLI):
    data = ac.read()
    if data:
        print(f"X-Pos: {data['pos_x']:+.4f} um   X-Ang: {data['ang_x']:+.4f} mrad")
        print(f"Y-Pos: {data['pos_y']:+.4f} um   Y-Ang: {data['ang_y']:+.4f} mrad")
    else:
        print("AC read failed")


def cmd_read(ac: AutocollimatorCLI, count: int, interval: float):
    print(f"{'#':>4}  {'X-Pos':>12}  {'Y-Pos':>12}  {'X-Ang':>10}  {'Y-Ang':>10}")
    for i in range(count):
        data = ac.read()
        if data:
            print(f"{i:4d}  {data['pos_x']:+12.4f}  {data['pos_y']:+12.4f}  "
                  f"{data['ang_x']:+10.4f}  {data['ang_y']:+10.4f}")
        else:
            print(f"{i:4d}  READ ERROR")
        if i < count - 1:
            time.sleep(interval)


def cmd_move(pamc: PAMC204CLI, ch: int, pulses: int):
    ok = pamc.move_relative(ch, pulses)
    drive_time = abs(pulses) / 1500.0
    print(f"move_relative(ch={ch}, pulses={pulses:+d}): {'OK' if ok else 'FAIL'}")
    print(f"Waiting {drive_time:.2f}s for completion...")
    time.sleep(drive_time + 0.1)
    print("Done")


def cmd_move_inf(pamc: PAMC204CLI, ch: int, direction: str, seconds: float):
    ok = pamc.move_infinite(ch, direction)
    print(f"move_infinite(ch={ch}, dir='{direction}'): {'OK' if ok else 'FAIL'}")
    print(f"Running for {seconds:.2f}s...")
    time.sleep(seconds)
    pamc.stop_motion(ch)
    print("Stopped")


def cmd_stop(pamc: PAMC204CLI, ch: int):
    ok = pamc.stop_motion(ch)
    print(f"stop_motion(ch={ch}): {'OK' if ok else 'FAIL'}")


def cmd_stop_all(pamc: PAMC204CLI):
    ok = pamc.stop_all()
    print(f"stop_all: {'OK' if ok else 'FAIL'}")


def cmd_test_dir(ac: AutocollimatorCLI, pamc: PAMC204CLI, ch: int, pulses: int):
    """駆動前後のAC値を表示して、方向を確認する。"""
    before = ac.read()
    if not before:
        print("AC read failed"); return

    print(f"BEFORE: X={before['pos_x']:+.4f}  Y={before['pos_y']:+.4f}")
    ok = pamc.move_relative(ch, pulses)
    print(f"move_relative(ch={ch}, pulses={pulses:+d}): {'OK' if ok else 'FAIL'}")

    drive_time = abs(pulses) / 1500.0
    time.sleep(drive_time + 0.5)

    after = ac.read()
    if not after:
        print("AC read failed after move"); return

    dx = after['pos_x'] - before['pos_x']
    dy = after['pos_y'] - before['pos_y']
    print(f"AFTER:  X={after['pos_x']:+.4f}  Y={after['pos_y']:+.4f}")
    print(f"DIFF:   dX={dx:+.4f}  dY={dy:+.4f}")
    print(f"=> ch{ch} {pulses:+d} pulses moves X by {dx:+.4f}, Y by {dy:+.4f}")


def cmd_adc(ac: AutocollimatorCLI, pamc: PAMC204CLI, args):
    """ADC制御ループ (CLI版)。"""
    target_x = args.target_x
    target_y = args.target_y
    kp = args.kp
    max_iter = args.max_iter
    threshold = args.threshold
    ppu = args.ppu
    max_step = args.max_step
    swap = args.swap
    rev1 = args.rev1
    rev2 = args.rev2

    if swap:
        axis_x, axis_y = 1, 2
    else:
        axis_x, axis_y = 2, 1

    print(f"ADC CLI: target=({target_x}, {target_y}) kp={kp} ppu={ppu} "
          f"threshold={threshold} max_step={max_step}")
    print(f"  axis_x=ch{axis_x} axis_y=ch{axis_y} swap={swap} rev1={rev1} rev2={rev2}")
    print(f"{'iter':>4}  {'err_x':>10}  {'err_y':>10}  {'pls_x':>8}  {'pls_y':>8}  {'status'}")
    print("-" * 70)

    prev_err_x = 0.0
    prev_err_y = 0.0

    for i in range(max_iter):
        data = ac.read()
        if not data:
            print(f"{i:4d}  AC READ ERROR"); continue

        err_x = data['pos_x'] - target_x
        err_y = data['pos_y'] - target_y

        if abs(err_x) <= threshold and abs(err_y) <= threshold:
            print(f"{i:4d}  {err_x:+10.4f}  {err_y:+10.4f}  {'---':>8}  {'---':>8}  CONVERGED")
            print(f"\n===== CONVERGED =====")
            print(f"  Iterations : {i}")
            print(f"  Final X    : {data['pos_x']:+.4f} um (err {err_x:+.4f})")
            print(f"  Final Y    : {data['pos_y']:+.4f} um (err {err_y:+.4f})")
            print(f"  Target     : ({target_x}, {target_y})")
            print(f"  Threshold  : {threshold}")
            print(f"=====================")
            return

        # X
        pulses_x = -int(round(kp * err_x * ppu))
        pulses_x = max(-max_step, min(max_step, pulses_x))
        if axis_x == 1 and rev1:
            pulses_x = -pulses_x
        elif axis_x == 2 and rev2:
            pulses_x = -pulses_x

        # Y
        pulses_y = -int(round(kp * err_y * ppu))
        pulses_y = max(-max_step, min(max_step, pulses_y))
        if axis_y == 1 and rev1:
            pulses_y = -pulses_y
        elif axis_y == 2 and rev2:
            pulses_y = -pulses_y

        status = "FAR" if abs(err_x) > threshold * 5 or abs(err_y) > threshold * 5 else "NEAR"
        print(f"{i:4d}  {err_x:+10.4f}  {err_y:+10.4f}  {pulses_x:+8d}  {pulses_y:+8d}  {status}")

        # X 駆動
        if abs(err_x) > threshold and pulses_x != 0:
            pamc.move_relative(axis_x, pulses_x)
            time.sleep(abs(pulses_x) / 1500.0 + 0.5)

        # Y 駆動
        if abs(err_y) > threshold and pulses_y != 0:
            pamc.move_relative(axis_y, pulses_y)
            time.sleep(abs(pulses_y) / 1500.0 + 0.5)

        prev_err_x = err_x
        prev_err_y = err_y

    print(f"\nMax iterations ({max_iter}) reached without convergence")


def main():
    parser = argparse.ArgumentParser(description="PAMC-204 + Autocollimator CLI")
    parser.add_argument("--ac_port", default="COM11", help="Autocollimator COM port")
    parser.add_argument("--addr", type=int, default=2, help="PAMC-204 address")
    parser.add_argument("--distance", type=float, default=50.0, help="Distance to sensor (mm)")

    sub = parser.add_subparsers(dest="command")

    sub.add_parser("status")

    p_read = sub.add_parser("read")
    p_read.add_argument("count", type=int, nargs="?", default=10)
    p_read.add_argument("interval", type=float, nargs="?", default=0.5)

    p_move = sub.add_parser("move")
    p_move.add_argument("ch", type=int)
    p_move.add_argument("pulses", type=int)

    p_mi = sub.add_parser("move_inf")
    p_mi.add_argument("ch", type=int)
    p_mi.add_argument("direction", choices=["+", "-"])
    p_mi.add_argument("seconds", type=float)

    p_stop = sub.add_parser("stop")
    p_stop.add_argument("ch", type=int)

    sub.add_parser("stop_all")

    p_td = sub.add_parser("test_dir")
    p_td.add_argument("ch", type=int)
    p_td.add_argument("pulses", type=int)

    p_adc = sub.add_parser("adc")
    p_adc.add_argument("--target_x", type=float, default=0.0)
    p_adc.add_argument("--target_y", type=float, default=0.0)
    p_adc.add_argument("--kp", type=float, default=0.5)
    p_adc.add_argument("--max_iter", type=int, default=200)
    p_adc.add_argument("--threshold", type=float, default=0.1)
    p_adc.add_argument("--ppu", type=float, default=9996.0)
    p_adc.add_argument("--max_step", type=int, default=50000)
    p_adc.add_argument("--swap", action="store_true")
    p_adc.add_argument("--rev1", action="store_true")
    p_adc.add_argument("--rev2", action="store_true")

    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        return

    # PAMC接続
    pamc = PAMC204CLI(address=args.addr)
    if not pamc.connect():
        print(f"PAMC-204 not found at address {args.addr}")
        return

    # ACが不要なコマンド
    if args.command == "stop":
        cmd_stop(pamc, args.ch); return
    if args.command == "stop_all":
        cmd_stop_all(pamc); return
    if args.command == "move":
        cmd_move(pamc, args.ch, args.pulses); return
    if args.command == "move_inf":
        cmd_move_inf(pamc, args.ch, args.direction, args.seconds); return

    # AC接続
    ac = AutocollimatorCLI(port=args.ac_port, distance_mm=args.distance)
    try:
        if args.command == "status":
            cmd_status(ac, pamc)
        elif args.command == "read":
            cmd_read(ac, args.count, args.interval)
        elif args.command == "test_dir":
            cmd_test_dir(ac, pamc, args.ch, args.pulses)
        elif args.command == "adc":
            cmd_adc(ac, pamc, args)
    finally:
        ac.close()


if __name__ == "__main__":
    main()
