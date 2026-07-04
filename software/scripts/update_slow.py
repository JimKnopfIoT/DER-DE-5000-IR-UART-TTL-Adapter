#!/usr/bin/env python3
"""RN4871 Firmware Update mit Delays zwischen Chunks (für CP2102).
Args: <port> <hexfile>"""
import serial, struct, sys, time
from intelhex import IntelHex

CMD_PKT, ACL_PKT, EVENT_PKT = 0x01, 0x02, 0x04
CHUNK_SIZE = 128
FLASH_SIZE = 0x40000
DELAY_AFTER_CHUNK = 0.005   # 5 ms Atempause für CP2102/Modul

def pkt_connect():
    return struct.pack('<BHB', CMD_PKT, 0x0405, 13) + bytes(13)

def pkt_disconnect():
    return struct.pack('<BHB', CMD_PKT, 0x0406, 3) + struct.pack('<HB', 0x0FFF, 0x00)

def pkt_erase():
    body = struct.pack('<HHBBII', 0x0112, 10, 0x03, 0x00, 0x00000000, 0x00000000)
    return struct.pack('<BHH', ACL_PKT, 0x0FFF, len(body)) + body

def pkt_write_start(data, total):
    acl_len = 14 + len(data)
    body = struct.pack('<HHBBII', 0x0111, (acl_len-4) | 0x8000, 0x03, 0x00, 0, total) + data
    return struct.pack('<BHH', ACL_PKT, 0x0FFF, acl_len) + body

def pkt_write_cont(data, last):
    acl_len = 4 + len(data)
    body = struct.pack('<HH', 0x0001, len(data) if last else (len(data) | 0x8000)) + data
    return struct.pack('<BHH', ACL_PKT, 0x0FFF, acl_len) + body

def read_pkt(s, timeout=10.0):
    """Liest sauber EIN HCI-Paket, verwirft Junk-Bytes mit Counter."""
    s.timeout = timeout
    junk = 0
    while True:
        t = s.read(1)
        if not t:
            raise TimeoutError(f"Timeout (vorher {junk} junk bytes verworfen)")
        if t[0] == EVENT_PKT:
            ec = s.read(1)[0]; ln = s.read(1)[0]; data = s.read(ln)
            return ('E', ec, data, junk)
        elif t[0] == ACL_PKT:
            h = struct.unpack('<H', s.read(2))[0]
            ln = struct.unpack('<H', s.read(2))[0]
            data = s.read(ln)
            return ('A', h, data, junk)
        else:
            junk += 1
            if junk > 200:
                raise RuntimeError(f"Zu viele Junk-Bytes ({junk}), gebe auf")

def wait_event(s, timeout=10.0):
    while True:
        p = read_pkt(s, timeout)
        if p[0] == 'E': return p

def wait_acl(s, timeout=10.0):
    while True:
        p = read_pkt(s, timeout)
        if p[0] == 'A': return p

def main():
    port, hex_file = sys.argv[1], sys.argv[2]
    ih = IntelHex(); ih.loadhex(hex_file)
    fw = bytes(ih.tobinarray(size=FLASH_SIZE))
    chunks = [fw[i:i+CHUNK_SIZE] for i in range(0, len(fw), CHUNK_SIZE)]
    print(f'FW: {len(fw)} B, {len(chunks)} Chunks')

    with serial.Serial(port, 115200, timeout=10, dsrdtr=False, rtscts=False) as s:
        time.sleep(0.2)
        s.reset_input_buffer()

        print('Connect...')
        s.write(pkt_connect())
        wait_event(s)              # Command Status
        ev = wait_event(s)         # Connection Complete
        if ev[2][0] != 0:
            raise RuntimeError(f'Connect failed: {ev[2][0]:#x}')
        print('  OK')

        print('Erase...')
        s.write(pkt_erase())
        wait_event(s)
        wait_acl(s)
        s.reset_input_buffer()
        print('  OK')

        total = len(chunks)
        total_junk = 0
        for i, c in enumerate(chunks):
            last = (i == total - 1)
            pkt = pkt_write_start(c, len(fw)) if i == 0 else pkt_write_cont(c, last)
            s.write(pkt)
            s.flush()
            wait_event(s)
            ack = wait_acl(s)
            total_junk += ack[3]
            status = struct.unpack('<H', ack[2][4:6])[0]
            if status != 0:
                raise RuntimeError(f'Chunk {i} status {status:#x}')
            time.sleep(DELAY_AFTER_CHUNK)
            if (i+1) % 64 == 0 or last:
                print(f'  {i+1}/{total} ({(i+1)/total*100:.0f}%) junk={total_junk}')

        print('Disconnect...')
        s.write(pkt_disconnect())
        wait_event(s)
        print('\nFertig! P2_0 trennen + Reset.')

if __name__ == '__main__':
    main()
