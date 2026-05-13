"""
DAC60501 Controller for brightness voltage control
"""
import smbus2
import time
from core.settings import settings


class DAC60501:
    def __init__(self, bus_number=None, address=0x48):
        self.bus_number = bus_number if bus_number is not None else settings.DAC_BUS
        self.address = address
        self.max_voltage = 2.5
        self.bus = None

    def __enter__(self):
        try:
            self.bus = smbus2.SMBus(self.bus_number)
        except Exception as e:
            if settings.DEBUG:
                print(f"[DAC] Could not open I2C bus {self.bus_number}: {e}")
            self.bus = None
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        if self.bus is not None:
            self.bus.close()

    def write_register(self, register, value):
        if self.bus is None:
            return
        try:
            msb = (value >> 8) & 0xFF
            lsb = value & 0xFF
            self.bus.write_i2c_block_data(self.address, register, [msb, lsb])
            time.sleep(0.001)
        except Exception as e:
            if settings.DEBUG:
                print(f"[DAC] Write register error: {e}")

    def read_register(self, register):
        if self.bus is None:
            return 0
        try:
            data = self.bus.read_i2c_block_data(self.address, register, 2)
            return (data[0] << 8) | data[1]
        except Exception as e:
            if settings.DEBUG:
                print(f"[DAC] Read register error: {e}")
            return 0

    def initialize(self):
        self.write_register(0x05, 0x000A)
        time.sleep(0.1)
        self.write_register(0x03, 0x0020)
        self.write_register(0x04, 0x0101)
        self.write_register(0x02, 0x0000)
        self.write_register(0x08, 0x0000)

    def set_voltage(self, voltage):
        if voltage > self.max_voltage:
            voltage = self.max_voltage
        elif voltage < 0:
            voltage = 0

        dac_code = int((voltage / self.max_voltage) * 4095)
        dac_value = dac_code << 4
        self.write_register(0x08, dac_value)
        return voltage, dac_code

    def set_dac_value(self, dac_value):
        """Direkt DAC value yaz (16-bit)"""
        self.write_register(0x08, dac_value)

    def get_status(self):
        dac_data = self.read_register(0x08)
        status = self.read_register(0x07)
        current_code = dac_data >> 4
        current_voltage = (current_code / 4095) * self.max_voltage
        return {
            'voltage': current_voltage,
            'code': current_code,
            'status': status
        }


def dac_initialize():
    """DAC'ı başlat"""
    if settings.DEBUG:
        print(f"[DAC] Initializing DAC on bus {settings.DAC_BUS}")
    
    with DAC60501() as dac:
        dac.initialize()


def dac_set_voltage_for_level(level: int):
    """
    Brightness level'a göre DAC voltajını ayarla
    - Level 0: DAC_VALUE (voltaj kesme, minimum parlaklık)
    - Level 1-9: 0V (voltaj kesme yok, normal parlaklık)
    """
    if level == 0:
        # Level 0: Voltaj kes
        voltage = settings.DAC_VALUE
    else:
        # Level 1-9: Normal
        voltage = 0.0
    
    if settings.DEBUG:
        print(f"[DAC] Setting voltage for level {level}: {voltage}V")
    
    with DAC60501() as dac:
        dac.set_voltage(voltage)

