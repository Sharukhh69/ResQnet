#!/usr/bin/env python3
"""
ResQ-Mesh Tactical Base Station & Telemetry Web Server
Author: Sharukhesh S
Target Hardware: Raspberry Pi 3/4/Zero 2W + Semtech SX1278 (Ra-02) 433MHz
OS: Raspberry Pi OS (Bookworm / Bullseye)
"""

import sys
import time
import json
import threading
import spidev
from http.server import HTTPServer, BaseHTTPRequestHandler

# Bootstrap pySX127x for Raspberry Pi OS Bookworm
sys.path.insert(0, '/home/sharukh/pySX127x')
try:
    import SX127x.board_config as board_config
    _spi = spidev.SpiDev()
    _spi.open(0, 0)
    _spi.max_speed_hz = 2_000_000
    _spi.mode = 0
    board_config.BOARD.spi        = _spi
    board_config.BOARD.setup      = lambda: None
    board_config.BOARD.teardown   = lambda: None
    board_config.BOARD.add_events = lambda *a, **k: None

    from SX127x.LoRa import LoRa
    from SX127x.constants import MODE, BW, CODING_RATE, REG
except ImportError:
    print("[WARNING] pySX127x or spidev not found in path. Ensure hardware SPI is enabled.")

latest_telemetry = {
    "node_id": "ALPHA-01",
    "lat": 26.2006,
    "lon": 92.9376,
    "battery": "100%",
    "status": "AWAITING",
    "seq": 0,
    "rssi": -99,
    "snr": 0.0,
    "last_seen": "Never"
}

class BaseStation(LoRa):
    def __init__(self):
        super().__init__(do_calibration=False)
        self.set_mode(MODE.SLEEP)
        self.set_freq(433.0)
        self.set_pa_config(pa_select=1, max_power=15, output_power=15)
        self.set_spreading_factor(7)
        self.set_bw(BW.BW125)
        self.set_coding_rate(CODING_RATE.CR4_5)
        self.set_sync_word(0x12)
        self.set_preamble(8)
        self.set_rx_crc(True)
        self.reset_ptr_rx()
        self.set_mode(MODE.RXCONT)
        print("=" * 60)
        print("  ResQ-Mesh Tactical Base Station & Web Server Online")
        print("  433.0 MHz LoRa + Live Telemetry REST API (:8080)")
        print("=" * 60)

    def transmit_command(self, cmd_string):
        print(f"\n📡 [HQ DOWNLINK TX] Transmitting over LoRa: {cmd_string}")
        payload = [ord(c) for c in cmd_string]
        self.set_mode(MODE.STDBY)
        self.write_payload(payload)
        self.set_mode(MODE.TX)
        for _ in range(150):
            if self.get_irq_flags().get('tx_done'):
                break
            time.sleep(0.01)
        self.clear_irq_flags(TxDone=1)
        self.set_mode(MODE.SLEEP)
        self.reset_ptr_rx()
        self.set_mode(MODE.RXCONT)
        print("✅ Command Broadcast Complete. Returned to RXCONT.\n")

    def listen(self):
        global latest_telemetry
        packet_count = 0
        while True:
            try:
                flags = self.get_irq_flags()
                if flags.get('rx_done'):
                    raw_rssi = self.spi.xfer([REG.LORA.PKT_RSSI_VALUE, 0])[1]
                    rssi = raw_rssi - 164 if raw_rssi > 0 else -157
                    raw_snr = self.spi.xfer([REG.LORA.PKT_SNR_VALUE, 0])[1]
                    snr = (raw_snr - 256 if raw_snr > 127 else raw_snr) * 0.25

                    nb_bytes = self.spi.xfer([REG.LORA.RX_NB_BYTES, 0])[1]
                    current_addr = self.spi.xfer([REG.LORA.FIFO_RX_CURR_ADDR, 0])[1]
                    self.spi.xfer([REG.LORA.FIFO_ADDR_PTR | 0x80, current_addr])
                    raw_bytes = self.spi.xfer([REG.LORA.FIFO] + [0] * nb_bytes)[1:]

                    self.spi.xfer([REG.LORA.IRQ_FLAGS | 0x80, 0xFF])
                    self.set_mode(MODE.SLEEP)
                    self.reset_ptr_rx()
                    self.set_mode(MODE.RXCONT)

                    if raw_bytes:
                        packet_count += 1
                        try:
                            text = bytes(raw_bytes).decode('utf-8', errors='ignore').strip()
                            parts = text.split('|')
                            if len(parts) >= 6 and parts[0] == "TEL":
                                coords = parts[2].split(',')
                                latest_telemetry = {
                                    "node_id": parts[1],
                                    "lat": float(coords[0]),
                                    "lon": float(coords[1]),
                                    "battery": parts[3],
                                    "status": parts[4],
                                    "seq": parts[5],
                                    "rssi": rssi,
                                    "snr": snr,
                                    "last_seen": time.strftime("%H:%M:%S")
                                }
                        except Exception:
                            pass
                        
                        print(f"🎯 [PACKET #{packet_count}] {latest_telemetry['node_id']} | Status: {latest_telemetry['status']} | Batt: {latest_telemetry['battery']} | RSSI: {rssi}dBm | SNR: {snr:.1f}dB")
            except Exception:
                time.sleep(0.05)
            time.sleep(0.01)

class WebHandler(BaseHTTPRequestHandler):
    bs_instance = None

    def do_OPTIONS(self):
        self.send_response(200)
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Access-Control-Allow-Methods', 'GET, POST, OPTIONS')
        self.send_header('Access-Control-Allow-Headers', 'Content-Type')
        self.end_headers()

    def do_GET(self):
        if self.path == '/api/telemetry':
            self.send_response(200)
            self.send_header('Content-Type', 'application/json')
            self.send_header('Access-Control-Allow-Origin', '*')
            self.end_headers()
            self.wfile.write(json.dumps(latest_telemetry).encode('utf-8'))
        else:
            self.send_response(404)
            self.end_headers()

    def do_POST(self):
        if self.path == '/api/broadcast':
            content_length = int(self.headers.get('Content-Length', 0))
            post_data = self.rfile.read(content_length).decode('utf-8')
            try:
                data = json.loads(post_data)
                cmd_text = data.get("command", "CMD|ALPHA-01|ACK_SOS|STANDBY")
                if WebHandler.bs_instance:
                    WebHandler.bs_instance.transmit_command(cmd_text)
                self.send_response(200)
                self.send_header('Content-Type', 'application/json')
                self.send_header('Access-Control-Allow-Origin', '*')
                self.end_headers()
                self.wfile.write(b'{"status":"broadcast_sent"}')
            except Exception:
                self.send_response(500)
                self.end_headers()
        else:
            self.send_response(404)
            self.end_headers()

    def log_message(self, format, *args):
        return  # Quiet console

if __name__ == '__main__':
    bs = BaseStation()
    WebHandler.bs_instance = bs
    
    lora_thread = threading.Thread(target=bs.listen, daemon=True)
    lora_thread.start()

    server = HTTPServer(('0.0.0.0', 8080), WebHandler)
    print("🌐 Base Station Web API live at http://0.0.0.0:8080/api/telemetry\n")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nShutting down Base Station...")
        bs.set_mode(MODE.SLEEP)
