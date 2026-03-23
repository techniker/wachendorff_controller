"""
Wachendorff URDR0001 Modbus Register Map

Based on URDR0001 User Manual Version 1.02.
Protocol: Modbus RTU, Function codes 0x03, 0x04 (read), 0x06 (write single), 0x10 (write multiple).
Default: 19200 baud, 8 data bits, no parity, 1 stop bit.
"""

from dataclasses import dataclass
from enum import IntEnum


@dataclass(frozen=True)
class Register:
    address: int
    name: str
    description: str
    read_only: bool = True
    scale: float = 1.0  # Divide raw value by this to get real value
    unit: str = ""
    signed: bool = True


# --- System / Identification Registers ---

DEVICE_TYPE = Register(0, "device_type", "Device type", read_only=True)
SOFTWARE_VERSION = Register(1, "software_version", "Software version", read_only=True)
SLAVE_ADDRESS = Register(5, "slave_address", "Slave address", read_only=True)
BOOT_VERSION = Register(6, "boot_version", "Boot version", read_only=True)
AUTOMATIC_ADDRESSING = Register(50, "auto_addressing", "Automatic addressing", read_only=False)
SYSTEM_CODE_COMPARISON = Register(51, "system_code", "System code comparison", read_only=False)
LOAD_DEFAULTS = Register(500, "load_defaults", "Loading default values (write 9999)", read_only=False)
SETPOINT_STORE_TIME = Register(510, "sp_store_time", "Setpoints storing time in EEPROM (0-60s)", read_only=False, unit="s")

# --- Process Values ---

PROCESS_VALUE = Register(999, "process_value", "Process value (visualization filter applied)", read_only=True, scale=10.0, unit="°C")
DECIMAL_POINT_INFO = Register(1000, "decimal_info", "Decimal point info for process/temp sensors", read_only=True)

# --- Setpoints ---

SETPOINT_1 = Register(1001, "setpoint_1", "Setpoint 1", read_only=False, scale=10.0, unit="°C")
SETPOINT_2 = Register(1002, "setpoint_2", "Setpoint 2", read_only=False, scale=10.0, unit="°C")
SETPOINT_3 = Register(1003, "setpoint_3", "Setpoint 3", read_only=False, scale=10.0, unit="°C")
SETPOINT_4 = Register(1004, "setpoint_4", "Setpoint 4", read_only=False, scale=10.0, unit="°C")

# --- Alarms ---

ALARM_1 = Register(1005, "alarm_1", "Alarm 1 value", read_only=False, scale=10.0, unit="°C")
ALARM_2 = Register(1006, "alarm_2", "Alarm 2 value", read_only=False, scale=10.0, unit="°C")

# --- Status ---

SETPOINT_GRADIENT = Register(1008, "setpoint_gradient", "Setpoint gradient", read_only=True)

# Relay status: Bit0=Q1, Bit1=Q2, Bit2=Reserved, Bit3=SSR (0=Off, 1=On)
RELAY_STATUS = Register(1009, "relay_status", "Relay status (bitmask)", read_only=True, signed=False)

HEATING_OUTPUT = Register(1010, "heating_output", "Heating output percentage (0-10000)", read_only=True, scale=100.0, unit="%")
COOLING_OUTPUT = Register(1011, "cooling_output", "Cooling output percentage (0-10000)", read_only=True, scale=100.0, unit="%")

# Alarms status: Bit0=Alarm1, Bit1=Alarm2 (0=None, 1=Active)
ALARMS_STATUS = Register(1012, "alarms_status", "Alarms active status (bitmask)", read_only=True, signed=False)

# In reading: Bit0=Alarm1, Bit1=Alarm2 (0=Resettable, 1=Not resettable)
ALARM_RESET = Register(1013, "alarm_reset", "Alarm reset control", read_only=False, signed=False)

# Error flags bitmask
ERROR_FLAGS = Register(1014, "error_flags", "Error flags (bitmask)", read_only=True, signed=False)

COLD_JUNCTION_TEMP = Register(1015, "cold_junction_temp", "Cold junction temperature", read_only=True, scale=10.0, unit="°C")

# --- Control ---

CONTROLLER_START_STOP = Register(1016, "start_stop", "Controller start/stop (0=Stop, 1=Start)", read_only=False, signed=False)
LOCK_CONVERSION = Register(1017, "lock_conversion", "Lock conversion on/off", read_only=False, signed=False)
TUNING_ON_OFF = Register(1018, "tuning", "Tuning on/off (0=Off, 1=On)", read_only=False, signed=False)
AUTO_MANUAL = Register(1019, "auto_manual", "Automatic/Manual (0=Auto, 1=Manual)", read_only=False, signed=False)

# --- Ampere readings ---

TA_CURRENT_ON = Register(1020, "ta_current_on", "T.A. current ON (Ampere with tenths)", read_only=True, scale=10.0, unit="A")
TA_CURRENT_OFF = Register(1021, "ta_current_off", "T.A. current OFF (Ampere with tenths)", read_only=True, scale=10.0, unit="A")
OFF_LINE_TIME = Register(1022, "off_line_time", "OFF LINE time (ms)", read_only=False, unit="ms")
INSTANT_CURRENT = Register(1023, "instant_current", "Instant current (Ampere)", read_only=False)
DIGITAL_INPUT_STATE = Register(1024, "digital_input", "Digital input state", read_only=False)

# Synchronized tuning for multizone
SYNC_TUNING = Register(1025, "sync_tuning", "Synchronized tuning control", read_only=False, signed=False)

# --- Decimal point selection ---

DECIMAL_FILTER = Register(1099, "decimal_filter", "Visualization filter and decimal point", read_only=True)
PROCESS_DECIMAL = Register(1100, "process_decimal", "Process with decimal point selection", read_only=True)
SP1_DECIMAL = Register(1101, "sp1_decimal", "Setpoint 1 with decimal point", read_only=False)
SP2_DECIMAL = Register(1102, "sp2_decimal", "Setpoint 2 with decimal point", read_only=False)
SP3_DECIMAL = Register(1103, "sp3_decimal", "Setpoint 3 with decimal point", read_only=False)
SP4_DECIMAL = Register(1104, "sp4_decimal", "Setpoint 4 with decimal point", read_only=False)
AL1_DECIMAL = Register(1105, "al1_decimal", "Alarm 1 with decimal point", read_only=False)
AL2_DECIMAL = Register(1106, "al2_decimal", "Alarm 2 with decimal point", read_only=False)
GRADIENT_DECIMAL = Register(1108, "gradient_decimal", "Gradient setpoint with decimal", read_only=True)
HEATING_PCT_RAW = Register(1109, "heating_pct_raw", "Heating percentage output (0-10000)", read_only=False, scale=100.0, unit="%")
HEATING_PCT_100 = Register(1110, "heating_pct_100", "Heating percentage output (0-100)", read_only=True, unit="%")
COOLING_PCT_RAW = Register(1111, "cooling_pct_raw", "Cooling percentage output (0-10000)", read_only=True, scale=100.0, unit="%")
COOLING_PCT_100 = Register(1112, "cooling_pct_100", "Cooling percentage output (0-100)", read_only=True, unit="%")

# --- Configuration Parameters (via Modbus word addresses 2001-2072) ---
# These map to front-panel parameters 1-72. Changes saved to EEPROM after 10s.

PARAM_C_OUT = Register(2001, "c_out", "Command output type selection (Param 1)", read_only=False)
PARAM_SENSOR = Register(2002, "sensor", "Sensor/input configuration (Param 2)", read_only=False)
PARAM_DECIMAL_POINT = Register(2003, "d_p", "Decimal point (Param 3)", read_only=False)
PARAM_LO_LIMIT_SP = Register(2004, "lo_l_s", "Lower limit setpoint (Param 4)", read_only=False)
PARAM_UP_LIMIT_SP = Register(2005, "up_l_s", "Upper limit setpoint (Param 5)", read_only=False)
PARAM_LO_LINEAR = Register(2006, "lo_l_i", "Lower linear input range (Param 6)", read_only=False)
PARAM_UP_LINEAR = Register(2007, "up_l_i", "Upper linear input range (Param 7)", read_only=False)
PARAM_LATCH = Register(2008, "latch", "Latch on function (Param 8)", read_only=False)
PARAM_OFFSET_CAL = Register(2009, "o_cal", "Offset calibration (Param 9)", read_only=False)
PARAM_GAIN_CAL = Register(2010, "g_cal", "Gain calibration (Param 10)", read_only=False)
PARAM_ACTION_TYPE = Register(2011, "act_t", "Action type - HEAT/cool/H.o.S.S (Param 11)", read_only=False)
PARAM_CMD_RESET = Register(2012, "c_re", "Command reset type (Param 12)", read_only=False)
PARAM_CMD_STATE_ERR = Register(2013, "c_se", "Command state error (Param 13)", read_only=False)
PARAM_CMD_LED = Register(2014, "c_ld", "Command LED state (Param 14)", read_only=False)
PARAM_CMD_HYSTERESIS = Register(2015, "c_hy", "Command hysteresis (Param 15)", read_only=False)
PARAM_CMD_DELAY = Register(2016, "c_de", "Command delay (Param 16)", read_only=False)
PARAM_CMD_SP_PROTECT = Register(2017, "c_sp", "Command setpoint protection (Param 17)", read_only=False)
PARAM_PROP_BAND = Register(2018, "p_b", "Proportional band (Param 18)", read_only=False, scale=10.0, unit="°C")
PARAM_INTEGRAL_TIME = Register(2019, "t_i", "Integral time (Param 19)", read_only=False, scale=10.0, unit="s")
PARAM_DERIVATIVE_TIME = Register(2020, "t_d", "Derivative time (Param 20)", read_only=False, scale=10.0, unit="s")
PARAM_CYCLE_TIME = Register(2021, "t_c", "Cycle time (Param 21)", read_only=False, unit="s")
PARAM_OUTPUT_POWER_LIM = Register(2022, "o_pol", "Output power limit (Param 22)", read_only=False, unit="%")

# Alarm 1 parameters
PARAM_ALARM1 = Register(2023, "al_1", "Alarm 1 selection (Param 23)", read_only=False)
PARAM_AL1_OUTPUT = Register(2024, "al1_so", "Alarm 1 state output (Param 24)", read_only=False)
PARAM_AL1_RESET = Register(2025, "al1_re", "Alarm 1 reset (Param 25)", read_only=False)
PARAM_AL1_STATE_ERR = Register(2026, "al1_se", "Alarm 1 state error (Param 26)", read_only=False)
PARAM_AL1_LED = Register(2027, "al1_ld", "Alarm 1 LED (Param 27)", read_only=False)
PARAM_AL1_HYSTERESIS = Register(2028, "al1_hy", "Alarm 1 hysteresis (Param 28)", read_only=False)
PARAM_AL1_DELAY = Register(2029, "al1_de", "Alarm 1 delay (Param 29)", read_only=False)
PARAM_AL1_SP_PROTECT = Register(2030, "al1_sp", "Alarm 1 setpoint protection (Param 30)", read_only=False)

# Alarm 2 parameters
PARAM_ALARM2 = Register(2031, "al_2", "Alarm 2 selection (Param 31)", read_only=False)
PARAM_AL2_OUTPUT = Register(2032, "al2_so", "Alarm 2 state output (Param 32)", read_only=False)
PARAM_AL2_RESET = Register(2033, "al2_re", "Alarm 2 reset (Param 33)", read_only=False)
PARAM_AL2_STATE_ERR = Register(2034, "al2_se", "Alarm 2 state error (Param 34)", read_only=False)
PARAM_AL2_LED = Register(2035, "al2_ld", "Alarm 2 LED (Param 35)", read_only=False)
PARAM_AL2_HYSTERESIS = Register(2036, "al2_hy", "Alarm 2 hysteresis (Param 36)", read_only=False)
PARAM_AL2_DELAY = Register(2037, "al2_de", "Alarm 2 delay (Param 37)", read_only=False)
PARAM_AL2_SP_PROTECT = Register(2038, "al2_sp", "Alarm 2 setpoint protection (Param 38)", read_only=False)

# Current transformer & loop break alarm
PARAM_CURRENT_TRANSFORMER = Register(2047, "t_a", "Current transformer (Param 47)", read_only=False)
PARAM_LB_THRESHOLD = Register(2048, "lb_al_t", "Loop break alarm threshold (Param 48)", read_only=False)
PARAM_LB_DELAY = Register(2049, "lb_al_d", "Loop break alarm delay (Param 49)", read_only=False)

# Cooling
PARAM_COOLING_FLUID = Register(2050, "coo_f", "Cooling fluid type (Param 50)", read_only=False)
PARAM_PB_MULTIPLIER = Register(2051, "p_b_m", "Proportional band multiplier (Param 51)", read_only=False)
PARAM_OVERLAP_DEAD = Register(2052, "ou_d_b", "Overlap / dead band (Param 52)", read_only=False)
PARAM_COOL_CYCLE_TIME = Register(2053, "co_t_c", "Cooling cycle time (Param 53)", read_only=False, unit="s")
PARAM_CONV_FILTER = Register(2054, "c_flt", "Conversion filter (Param 54)", read_only=False)
PARAM_CONV_FREQ = Register(2055, "c_frn", "Conversion frequency (Param 55)", read_only=False)
PARAM_VIS_FILTER = Register(2056, "u_flt", "Visualization filter (Param 56)", read_only=False)
PARAM_TUNE = Register(2057, "tune", "Tuning type selection (Param 57)", read_only=False)
PARAM_SD_TUNE = Register(2058, "s_d_tu", "Setpoint deviation tune (Param 58)", read_only=False)
PARAM_OP_MODE = Register(2059, "op_mo", "Operating mode (Param 59)", read_only=False)
PARAM_AUTO_MANUAL = Register(2060, "au_ma", "Automatic/Manual selection (Param 60)", read_only=False)
PARAM_DIGITAL_INPUT = Register(2061, "dgt_i", "Digital input function (Param 61)", read_only=False)
PARAM_GRADIENT = Register(2062, "grad", "Gradient (Param 62)", read_only=False)
PARAM_MAINT_TIME = Register(2063, "ma_t_i", "Maintenance time (Param 63)", read_only=False)
PARAM_USER_MENU = Register(2064, "u_m_c_p", "User menu cycle programmed (Param 64)", read_only=False)
PARAM_VIS_TYPE = Register(2065, "u_i_ey", "Visualization type (Param 65)", read_only=False)
PARAM_DEGREE = Register(2066, "degr", "Degree type C/F (Param 66)", read_only=False)
PARAM_RETRANSMISSION = Register(2067, "retr", "Retransmission function (Param 67)", read_only=False)
PARAM_LO_RETRANS = Register(2068, "lo_l_r", "Lower limit retransmission (Param 68)", read_only=False)
PARAM_UP_RETRANS = Register(2069, "up_l_r", "Upper limit retransmission (Param 69)", read_only=False)
PARAM_BAUD_RATE = Register(2070, "bd_rt", "Baud rate (Param 70)", read_only=False)
PARAM_SLAVE_ADDR = Register(2071, "sl_ad", "Slave address (Param 71)", read_only=False)
PARAM_SERIAL_DELAY = Register(2072, "se_de", "Serial delay in ms (Param 72)", read_only=False, unit="ms")

# --- EEPROM Direct Access (addresses 4001-4072 map to params 1-72) ---
# Same as 2001-2072 but writes directly to EEPROM

DISABLE_SERIAL_CONTROL = Register(3000, "disable_serial", "Disabling serial control of machine", read_only=True, signed=False)

# --- Display control registers ---

DISPLAY1_WORDS = [Register(3001 + i, f"disp1_word{i+1}", f"Display 1 word {i+1} (ASCII)", read_only=False) for i in range(8)]
DISPLAY2_WORDS = [Register(3009 + i, f"disp2_word{i+1}", f"Display 2 word {i+1} (ASCII)", read_only=False) for i in range(8)]

WORD_LED = Register(3017, "word_led", "Word LED control (bitmask)", read_only=False, signed=False)
WORD_KEYS = Register(3018, "word_keys", "Word keys (write 1 to command)", read_only=False, signed=False)
WORD_SERIAL_RELAY = Register(3019, "word_relay", "Word serial relay (Q1/Q2)", read_only=False, signed=False)
WORD_SSR = Register(3020, "word_ssr", "Word SSR serial", read_only=False, signed=False)
WORD_VOLT_OUTPUT = Register(3021, "word_volt_out", "Word output 0..10V serial", read_only=False)
WORD_MA_OUTPUT = Register(3022, "word_ma_out", "Word output 4..20mA serial", read_only=False)
RELAY_OFFLINE = Register(3023, "relay_offline", "Relay state if serial offline", read_only=False, signed=False)
OUTPUT_OFFLINE = Register(3024, "output_offline", "Output state SSR/V/mA if offline", read_only=False)
SERIAL_PROCESS = Register(3025, "serial_process", "Serial process averaging", read_only=False)

# --- Grouped register sets for polling ---

# Registers to poll frequently (live data)
POLL_LIVE_REGISTERS = [
    PROCESS_VALUE,
    SETPOINT_1,
    HEATING_OUTPUT,
    COOLING_OUTPUT,
    RELAY_STATUS,
    ALARMS_STATUS,
    ERROR_FLAGS,
    CONTROLLER_START_STOP,
    AUTO_MANUAL,
    TUNING_ON_OFF,
]

# PID parameters to read on demand
PID_REGISTERS = [
    PARAM_PROP_BAND,
    PARAM_INTEGRAL_TIME,
    PARAM_DERIVATIVE_TIME,
    PARAM_CYCLE_TIME,
    PARAM_OUTPUT_POWER_LIM,
    PARAM_ACTION_TYPE,
    PARAM_CMD_HYSTERESIS,
]

# All setpoints
SETPOINT_REGISTERS = [SETPOINT_1, SETPOINT_2, SETPOINT_3, SETPOINT_4]

# Alarm registers
ALARM_REGISTERS = [ALARM_1, ALARM_2, PARAM_ALARM1, PARAM_ALARM2, PARAM_AL1_HYSTERESIS, PARAM_AL2_HYSTERESIS]


class ErrorFlag(IntEnum):
    """Error flag bits from register 1014."""
    EEPROM_WRITE = 0
    EEPROM_READ = 1
    COLD_JUNCTION = 2
    PROCESS_ERROR = 3
    GENERIC = 4
    HARDWARE = 5
    LBAO = 6
    LBAC = 7
    MISSING_CALIBRATION = 8


class BaudRate(IntEnum):
    """Baud rate parameter values for register 2070."""
    BAUD_4800 = 0
    BAUD_9600 = 1
    BAUD_19200 = 2  # Default
    BAUD_28800 = 3
    BAUD_38400 = 4
    BAUD_57600 = 5

    @property
    def actual_rate(self) -> int:
        return {0: 4800, 1: 9600, 2: 19200, 3: 28800, 4: 38400, 5: 57600}[self.value]


class ActionType(IntEnum):
    """Action type parameter values."""
    HEATING = 0
    COOLING = 1
    LOCK_COMMAND = 2


class OperatingMode(IntEnum):
    """Operating mode parameter values."""
    CONTROLLER = 0
    PRE_PROGRAMMED_CYCLE = 1
    SETPOINT_DIGITAL_INPUT = 2
    SP_DIGITAL_IMPULSE = 3
    FOUR_SP_DIGITAL_IMPULSE = 4
    RESET_TIME = 5
    PRE_PROGRAMMED_START_STOP = 6
