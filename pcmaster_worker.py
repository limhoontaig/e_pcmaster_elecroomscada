# pcmaster_worker.py
import time
import os
import struct
import configparser
from datetime import datetime
from PyQt5.QtCore import QObject, pyqtSignal

from pymodbus.client import ModbusSerialClient 

from db_manager import DATA_LABELS, get_db_raw_connection
from ac_controller import ac_manager 

def safe_modbus_call(func, address, count=None, value=None, values=None, slave_id=1):
    for key in ["slave", "unit", "slave_id", "device_id"]:
        kwargs = {key: slave_id}
        if count is not None: kwargs['count'] = count
        if value is not None: kwargs['value'] = value
        if values is not None: kwargs['values'] = values 
        
        try:
            return func(address=address, **kwargs)
        except TypeError as e:
            if "unexpected keyword argument" in str(e):
                continue
            raise e
    return None

config_path = os.path.join(os.path.dirname(__file__), 'config.ini')

def get_com_ports():
    config = configparser.ConfigParser()
    if os.path.exists(config_path):
        config.read(config_path, encoding='utf-8')
        return config['SETTINGS'].get('COM_PORT_RELAY', 'COM3'), config['SETTINGS'].get('COM_PORT_PLC', 'COM4')
    return 'COM3', 'COM4'

COM_PORT_RELAY, COM_PORT_PLC = get_com_ports()
BAUD_RATE = 19200         

class CommSignal(QObject):
    status_changed = pyqtSignal(bool)
    plc_status_update = pyqtSignal(list)

comm_signal = CommSignal()
last_db_save_time = 0
pending_ac_fan_values = None

tr1_buffer = []
tr2_buffer = []
tr3_buffer = []
last_max_calc_time = 0

client_relay = ModbusSerialClient(port=COM_PORT_RELAY, baudrate=BAUD_RATE, timeout=0.3, stopbits=1, bytesize=8, parity='N')
client_plc = ModbusSerialClient(port=COM_PORT_PLC, baudrate=BAUD_RATE, timeout=0.3, stopbits=1, bytesize=8, parity='N')

def write_plc_bit(address, state):
    """UI에서 마우스로 비트 스위치를 누를 때 실행 (예: M0100 대역)"""
    if client_plc and client_plc.is_socket_open():
        safe_modbus_call(client_plc.write_coil, address=address, value=state, slave_id=5)
        print(f"👉 [비트 제어] M{address:04d} 번지에 {state} 전송 완료")

def write_plc_register(address, value):
    """🌟 [신규 추가] UI에서 실내/외기 온도 4가지 설정값을 변경할 때 실행 (D00906~909)"""
    if client_plc and client_plc.is_socket_open():
        safe_modbus_call(client_plc.write_register, address=address, value=int(value * 10), slave_id=5)
        print(f"🌡️ [워드 제어] D{address:04d} 번지에 설정값 {value} 전송 완료")

def serial_receive_thread():
    global last_db_save_time, pending_ac_fan_values
    global tr1_buffer, tr2_buffer, tr3_buffer, last_max_calc_time
    
    current_status = None
    
    while True:
        try:
            relay_connected = client_relay.is_socket_open()
            plc_connected = client_plc.is_socket_open()

            if not relay_connected:
                client_relay.connect()
            if not plc_connected:
                client_plc.connect()

            if not (client_relay.is_socket_open() or client_plc.is_socket_open()):
                time.sleep(1)
                continue

            통신성공_여부 = False
            수집데이터 = [0] * len(DATA_LABELS) 
            '''
            # =============================================================
            # ⚡ [그룹 A] 전력 계전기 통신 (국번 6, 1, 2, 3) 
            # =============================================================
            if client_relay.is_socket_open():
                res_kep = safe_modbus_call(client_relay.read_input_registers, address=4, count=32, slave_id=6)
                if res_kep and not res_kep.isError():
                    통신성공_여부 = True
                    수집데이터[4] = res_kep.registers[0]/1000.0; 수집데이터[5] = res_kep.registers[2]/1000.0   
                    수집데이터[6] = res_kep.registers[4]/1000.0; 수집데이터[7] = res_kep.registers[6]/1000.0   
                    수집데이터[8] = res_kep.registers[8]/1000.0; 수집데이터[9] = res_kep.registers[10]/1000.0  
                    수집데이터[10] = res_kep.registers[14];      수집데이터[11] = res_kep.registers[16]           
                    수집데이터[12] = res_kep.registers[18];      수집데이터[13] = res_kep.registers[20]           
                    수집데이터[14] = res_kep.registers[24]/1000.0  
                    수집데이터[15] = ((res_kep.registers[30] << 16) + res_kep.registers[31])/1000.0 
                    
                res_tr1 = safe_modbus_call(client_relay.read_input_registers, address=4, count=38, slave_id=1)
                if res_tr1 and not res_tr1.isError():
                    통신성공_여부 = True
                    수집데이터[16] = res_tr1.registers[0]; 수집데이터[17] = res_tr1.registers[2]; 수집데이터[18] = res_tr1.registers[4]
                    수집데이터[19] = res_tr1.registers[6]; 수집데이터[20] = res_tr1.registers[8]; 수집데이터[21] = res_tr1.registers[10]
                    수집데이터[22] = res_tr1.registers[12]; 수집데이터[23] = res_tr1.registers[14]; 수집데이터[24] = res_tr1.registers[16]
                    수집데이터[25] = res_tr1.registers[20] / 1000.0  

                res_tr2 = safe_modbus_call(client_relay.read_input_registers, address=4, count=38, slave_id=2)
                if res_tr2 and not res_tr2.isError():
                    통신성공_여부 = True
                    수집데이터[27] = res_tr2.registers[0]; 수집데이터[28] = res_tr2.registers[2]; 수집데이터[29] = res_tr2.registers[4]
                    수집데이터[30] = res_tr2.registers[6]; 수집데이터[31] = res_tr2.registers[8]; 수집데이터[32] = res_tr2.registers[10]
                    수집데이터[33] = res_tr2.registers[12]; 수집데이터[34] = res_tr2.registers[14]; 수집데이터[35] = res_tr2.registers[16]
                    수집데이터[36] = res_tr2.registers[20] / 1000.0  

                res_tr3 = safe_modbus_call(client_relay.read_input_registers, address=4, count=38, slave_id=3)
                if res_tr3 and not res_tr3.isError():
                    통신성공_여부 = True
                    수집데이터[38] = res_tr3.registers[0]; 수집데이터[39] = res_tr3.registers[2]; 수집데이터[40] = res_tr3.registers[4]
                    수집데이터[41] = res_tr3.registers[6]; 수집데이터[42] = res_tr3.registers[8]; 수집데이터[43] = res_tr3.registers[10]
                    수집데이터[44] = res_tr3.registers[12]; 수집데이터[45] = res_tr3.registers[14]; 수집데이터[46] = res_tr3.registers[16]
                    수집데이터[47] = res_tr3.registers[20] / 1000.0  
            '''
            # =============================================================
            # 🏭 [그룹 B] LS PLC 통신 (국번 5) - 새 메모리 맵 반영
            # =============================================================
            if client_plc.is_socket_open():
                # 상태 비트 (M0200 ~ M0222) 읽어오기
                res_coils = safe_modbus_call(client_plc.read_coils, address=200, count=23, slave_id=5)
                if res_coils and not res_coils.isError():
                    comm_signal.plc_status_update.emit(res_coils.bits[:23])
                    
                # 🌟 [수정됨] 센서값 워드 읽어오기 (D00950 ~ D00956)
                res_plc = safe_modbus_call(client_plc.read_holding_registers, address=950, count=7, slave_id=5)
                if res_plc and not res_plc.isError():
                    통신성공_여부 = True
                    
                    # 새 인덱스(0~6)에 맞게 수집데이터 매핑
                    수집데이터[0]  = res_plc.registers[0] / 10.0    # D00950: 실내온도
                    수집데이터[1]  = res_plc.registers[1] / 10.0    # D00951: 외기온도
                    수집데이터[49] = res_plc.registers[2] / 10.0    # D00952: 에어콘01온도
                    수집데이터[50] = res_plc.registers[3] / 10.0    # D00953: 에어콘02온도
                    수집데이터[26] = res_plc.registers[4] / 10.0    # D00954: Tr1_Temp
                    수집데이터[37] = res_plc.registers[5] / 10.0    # D00955: Tr2_Temp
                    수집데이터[48] = res_plc.registers[6] / 10.0    # D00956: Tr3_Temp
                    
                    # 🌟 [수정됨] 1분(60초) 변압기 최대 온도 연산 및 전송 (D00980 ~ D00982)
                    now_t = time.time()
                    tr1_buffer.append(res_plc.registers[4]) 
                    tr2_buffer.append(res_plc.registers[5])
                    tr3_buffer.append(res_plc.registers[6])

                    if now_t - last_max_calc_time >= 60.0:
                        if tr1_buffer:
                            max_tr1 = max(tr1_buffer); max_tr2 = max(tr2_buffer); max_tr3 = max(tr3_buffer)
                            # 💡 바뀐 목적지 주소 980번으로 쏩니다.
                            safe_modbus_call(client_plc.write_registers, address=980, values=[max_tr1, max_tr2, max_tr3], slave_id=5)
                        tr1_buffer.clear(); tr2_buffer.clear(); tr3_buffer.clear()
                        last_max_calc_time = now_t
                
                # 에어컨 컨트롤러 로직 유지
                if 통신성공_여부:
                    ac_manager.check_and_control(
                        indoor_temp=수집데이터[0],      
                        outdoor_temp=수집데이터[1], 
                        dis_temp1=수집데이터[49], 
                        dis_temp2=수집데이터[50], 
                        total_load=수집데이터[14]       
                    )
                    safe_modbus_call(client_plc.write_register, address=2000, value=ac_manager.fan_control_cmd, slave_id=5)

            # =============================================================
            # [6] DB 로깅 (58초마다 기록)
            # =============================================================
            if 통신성공_여부 and current_status != True:
                comm_signal.status_changed.emit(True)
                current_status = True
            elif not 통신성공_여부 and current_status != False:
                comm_signal.status_changed.emit(False)
                current_status = False

            now_time = time.time()
            if 통신성공_여부 and (now_time - last_db_save_time >= 58.0):
                # insert_raw_data(수집데이터)
                last_db_save_time = now_time

            time.sleep(0.5)

        except Exception as e:
            print(f"마스터 루프 에러: {e}")
            if client_relay: client_relay.close()
            if client_plc: client_plc.close()
            time.sleep(1)

def insert_raw_data(values):
    if len(values) < len(DATA_LABELS): return
    try:
        conn = get_db_raw_connection()
        c = conn.cursor()
        now = datetime.now()
        l_date, l_time = now.strftime('%Y-%m-%d'), now.strftime('%H:%M:%S')
        
        adjusted_values = [round(float(val), 1) for val in values]
        placeholders = ", ".join(["%s"] * len(adjusted_values))
        col_names = ", ".join([f"`{name}`" for name in DATA_LABELS])
        
        c.execute(f"INSERT INTO raw_data (log_date, log_time, {col_names}) VALUES (%s, %s, {placeholders})", [l_date, l_time] + adjusted_values)
        conn.commit(); conn.close()
    except Exception as e:
        pass