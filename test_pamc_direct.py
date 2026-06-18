"""PAMC-204 DLL直接テスト - E02"""
import ctypes
from ctypes import wintypes, c_char_p, c_int
import time
import os

dll_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "pamc204.dll")
lib = ctypes.CDLL(dll_path)

lib.pamc204_send_command.restype = wintypes.BOOL
lib.pamc204_send_command.argtypes = [c_char_p, c_char_p, c_int]

def send_cmd(cmd_str):
    cmd = cmd_str.encode('ascii')
    resp = ctypes.create_string_buffer(256)
    ok = lib.pamc204_send_command(cmd, resp, 256)
    resp_str = resp.value.decode('ascii', errors='replace').strip()
    print(f"  '{cmd_str}': ok={ok}, response='{resp_str}'")
    return ok, resp_str

print("=== E02RR15001500A ===")
send_cmd("E02RR15001500A")
print("Waiting 5 seconds...")
time.sleep(5)
print("Done.")
