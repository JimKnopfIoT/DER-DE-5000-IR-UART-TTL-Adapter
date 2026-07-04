#!/usr/bin/env python3
"""Liest 15s lang Spannung+Strom vom BB3 CH1 (max-Rate)."""
import socket, time, sys, os

CH = int(sys.argv[1]) if len(sys.argv) > 1 else 1
DURATION = float(sys.argv[2]) if len(sys.argv) > 2 else 15.0

s = socket.create_connection((os.environ.get('BB3_HOST','192.0.2.10'), 5025), timeout=3)
s.settimeout(2)

def cmd(c):
    s.sendall((c + '\n').encode())

def query(c):
    cmd(c)
    return s.recv(128).decode().strip()

cmd(f'INST:NSEL {CH}')
time.sleep(0.05)
print(f'CH{CH} OUTP={query("OUTP?")} VSET={query("VOLT?")}V ILIM={query("CURR?")}A')
print(f'\nZeit[s]  V[V]    I[mA]   maxI[mA]')
print('-'*40)

t0 = time.time()
imax = 0.0
while time.time() - t0 < DURATION:
    v = float(query('MEAS:VOLT?'))
    i = float(query('MEAS:CURR?'))
    if i > imax: imax = i
    t = time.time() - t0
    print(f'{t:6.2f}   {v:.3f}   {i*1000:6.2f}   {imax*1000:6.2f}')

s.close()
