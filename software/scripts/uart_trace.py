#!/usr/bin/env python3
"""Live UART-Trace vom RN4871 + BB3 Strom parallel.
Zeigt Connection-Events, advertising-Strom, Crash-Bytes.

Aufruf: python3 uart_trace.py [Dauer_in_Sekunden]"""

import serial, socket, time, threading, sys, os

PORT = '/dev/ttyUSB0'
BB3_HOST = os.environ.get('BB3_HOST', '192.0.2.10')
BB3_PORT = 5025
DURATION = float(sys.argv[1]) if len(sys.argv) > 1 else 120.0

def bb3_query(cmd):
    for _ in range(3):
        try:
            s = socket.create_connection((BB3_HOST, BB3_PORT), timeout=2)
            s.settimeout(1.5)
            s.sendall((cmd+'\n').encode())
            time.sleep(0.05)
            r = s.recv(256).decode().strip()
            s.close()
            return r
        except:
            time.sleep(0.2)
    return None

bb3_query('INST:NSEL 1')

stop = threading.Event()
START = time.time()

def bb3_logger():
    while not stop.is_set():
        v = bb3_query('MEAS:CURR?')
        if v is not None:
            i_ma = float(v) * 1000
            t = time.time() - START
            print(f'  [{t:6.2f}] I={i_ma:5.2f} mA', flush=True)
        time.sleep(0.4)

bb3_thread = threading.Thread(target=bb3_logger, daemon=True)
bb3_thread.start()

EVENTS = [b'%REBOOT%', b'%CONNECT,', b'%DISCONNECT%',
          b'%STREAM_OPEN%', b'%STREAM_CLOSE%',
          b'%CONN_PARAM,', b'%SECURED%', b'%BONDED%',
          b'%LSTREAM_OPEN%', b'%ERR_SEC%']

def fmt_bytes(data):
    out = []
    for b in data:
        if 32 <= b < 127:
            out.append(chr(b))
        elif b == 13:
            out.append('\\r')
        elif b == 10:
            out.append('\\n')
        else:
            out.append(f'<{b:02X}>')
    return ''.join(out)

print(f'Trace {DURATION:.0f}s. Drück Reset, dann auf Windows verbinden.\n')

with serial.Serial(PORT, 115200, timeout=0.05, dsrdtr=False, rtscts=False) as ser:
    ser.reset_input_buffer()
    buf = b''
    last_chunk_time = time.time()
    try:
        while time.time() - START < DURATION:
            x = ser.read(ser.in_waiting or 1)
            if x:
                t = time.time() - START
                buf += x
                # Group display: alle bytes bis 200ms ohne Daten als eine Zeile
                while True:
                    # Look for event match
                    found_event = None
                    found_pos = -1
                    for ev in EVENTS:
                        p = buf.find(ev)
                        if p >= 0 and (found_pos < 0 or p < found_pos):
                            found_pos = p
                            found_event = ev
                    if found_event is None:
                        break
                    # alles vor Event als raw
                    if found_pos > 0:
                        print(f'  [{t:6.2f}] UART: {fmt_bytes(buf[:found_pos])}', flush=True)
                    # Event finden mit eventuell weiterem Inhalt bis \r oder %
                    end = found_pos + len(found_event)
                    # Manche events haben Daten danach: %CONNECT,1,MAC%
                    if found_event.endswith(b','):
                        ep = buf.find(b'%', end)
                        if ep > 0:
                            end = ep + 1
                    print(f'  [{t:6.2f}] >>> EVENT: {fmt_bytes(buf[found_pos:end])} <<<', flush=True)
                    buf = buf[end:]
                # Falls Buffer wächst aber kein Event: ggf. Flush nach Stille
                if len(buf) > 0 and time.time() - last_chunk_time > 0.3:
                    print(f'  [{t:6.2f}] UART: {fmt_bytes(buf)}', flush=True)
                    buf = b''
                last_chunk_time = time.time()
            else:
                # Stille — Buffer flushen falls was drinsteht und > 300ms alt
                if len(buf) > 0 and time.time() - last_chunk_time > 0.3:
                    t = time.time() - START
                    print(f'  [{t:6.2f}] UART: {fmt_bytes(buf)}', flush=True)
                    buf = b''
    except KeyboardInterrupt:
        print('\nAbbruch durch User.')
    finally:
        stop.set()
        if buf:
            t = time.time() - START
            print(f'  [{t:6.2f}] UART (final): {fmt_bytes(buf)}', flush=True)
print('\nTrace beendet.')
