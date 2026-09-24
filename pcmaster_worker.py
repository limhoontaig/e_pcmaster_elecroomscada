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

# --- pymodbus 버전 충돌 방지용 만능 호환 함수 ---
# --- pymodbus 버전 충돌 방지용 만능 호환 함수 ---
# 💡 1. 괄호 안에 values=None 을 추가합니다.
def safe_modbus_call(func, address, count=None, value=None, values=None, slave_id=1):
    for key in ["slave", "unit", "slave_id", "device_id"]:
        kwargs = {key: slave_id}
        if count is not None: kwargs['count'] = count
        if value is not None: kwargs['value'] = value
        
        # 💡 2. 여러 개의 데이터(values)가 들어오면 처리해주는 코드를 한 줄 추가합니다.
        if values is not None: kwargs['values'] = values 
        
        try:
            return func(address=address, **kwargs)
        except TypeError as e:
            if "unexpected keyword argument" in str(e):
                continue
            raise e
    return None

config_path = os.path.join(os.path.dirname(__file__), 'config.ini')

def get_com_port():
    config = configparser.ConfigParser()
    if os.path.exists(config_path):
        config.read(config_path, encoding='utf-8')
        return config['SETTINGS'].get('COM_PORT', 'COM3')
    return 'COM3'

COM_PORT = get_com_port()
BAUD_RATE = 19200         

class CommSignal(QObject):
    status_changed = pyqtSignal(bool)

comm_signal = CommSignal()
last_db_save_time = 0
pending_tr_fan_values = None

client = ModbusSerialClient(
        port=COM_PORT, 
        baudrate=BAUD_RATE, 
        timeout=0.3, 
        stopbits=1,
        bytesize=8,
        parity='N'
    )

def serial_receive_thread():
    global last_db_save_time
    
    current_status = None
    
    while True:
        try:
            if not client.is_socket_open():
                client.connect()
                print(f"PC 마스터 연결 시도: {COM_PORT}")
                time.sleep(1)
                continue

            통신성공_여부 = False
            수집데이터 = [0] * len(DATA_LABELS) 

            # -------------------------------------------------------------
            # [1] KEP 한전 계전기 - 국번 6
            # -------------------------------------------------------------
            res_kep = safe_modbus_call(client.read_input_registers, address=4, count=32, slave_id=6)
            if res_kep and not res_kep.isError():
                통신성공_여부 = True
                # 나눔수 1000 적용 및 주석 추가
                수집데이터[4]  = res_kep.registers[0] / 1000.0   # KEP_V_R
                수집데이터[5]  = res_kep.registers[2] / 1000.0   # KEP_V_S
                수집데이터[6]  = res_kep.registers[4] / 1000.0   # KEP_V_T
                수집데이터[7]  = res_kep.registers[6] / 1000.0   # KEP_V_R_S
                수집데이터[8]  = res_kep.registers[8] / 1000.0   # KEP_V_S_T
                수집데이터[9]  = res_kep.registers[10] / 1000.0  # KEP_V_T_R
                수집데이터[10] = res_kep.registers[14]           # KEP_A_R (나눔수 없음)
                수집데이터[11] = res_kep.registers[16]           # KEP_A_S
                수집데이터[12] = res_kep.registers[18]           # KEP_A_T
                수집데이터[13] = res_kep.registers[20]           # KEP_frequency
                수집데이터[14] = res_kep.registers[24] / 1000.0  # KEP_P_kW
                # 32비트 결합 후 나눔수 1000 적용
                수집데이터[15] = ((res_kep.registers[30] << 16) + res_kep.registers[31]) / 1000.0 # KEP_P_kWh 
                
            # -------------------------------------------------------------
            # [2] TR1 계전기 - 국번 1
            # -------------------------------------------------------------
            res_tr1 = safe_modbus_call(client.read_input_registers, address=4, count=38, slave_id=1)
            if res_tr1 and not res_tr1.isError():
                통신성공_여부 = True
                수집데이터[16] = res_tr1.registers[0]            # Tr1_A_R
                수집데이터[17] = res_tr1.registers[2]            # Tr1_A_S
                수집데이터[18] = res_tr1.registers[4]            # Tr1_A_T
                수집데이터[19] = res_tr1.registers[6]            # Tr1_V_R
                수집데이터[20] = res_tr1.registers[8]            # Tr1_V_S
                수집데이터[21] = res_tr1.registers[10]           # Tr1_V_T
                수집데이터[22] = res_tr1.registers[12]           # Tr1_V_R_S
                수집데이터[23] = res_tr1.registers[14]           # Tr1_V_S_T
                수집데이터[24] = res_tr1.registers[16]           # Tr1_V_T_R
                수집데이터[25] = res_tr1.registers[20] / 1000.0  # Tr1_P_kW (나눔수 1000)

            # -------------------------------------------------------------
            # [3] TR2 계전기 - 국번 2
            # -------------------------------------------------------------
            res_tr2 = safe_modbus_call(client.read_input_registers, address=4, count=38, slave_id=2)
            if res_tr2 and not res_tr2.isError():
                통신성공_여부 = True
                수집데이터[27] = res_tr2.registers[0]            # Tr2_A_R
                수집데이터[28] = res_tr2.registers[2]            # Tr2_A_S
                수집데이터[29] = res_tr2.registers[4]            # Tr2_A_T
                수집데이터[30] = res_tr2.registers[6]            # Tr2_V_R
                수집데이터[31] = res_tr2.registers[8]            # Tr2_V_S
                수집데이터[32] = res_tr2.registers[10]           # Tr2_V_T
                수집데이터[33] = res_tr2.registers[12]           # Tr2_V_R_S
                수집데이터[34] = res_tr2.registers[14]           # Tr2_V_S_T
                수집데이터[35] = res_tr2.registers[16]           # Tr2_V_T_R
                수집데이터[36] = res_tr2.registers[20] / 1000.0  # Tr2_P_kW (나눔수 1000)

            # -------------------------------------------------------------
            # [4] TR3 계전기 - 국번 3
            # -------------------------------------------------------------
            res_tr3 = safe_modbus_call(client.read_input_registers, address=4, count=38, slave_id=3)
            if res_tr3 and not res_tr3.isError():
                통신성공_여부 = True
                수집데이터[38] = res_tr3.registers[0]            # Tr3_A_R
                수집데이터[39] = res_tr3.registers[2]            # Tr3_A_S
                수집데이터[40] = res_tr3.registers[4]            # Tr3_A_T
                수집데이터[41] = res_tr3.registers[6]            # Tr3_V_R
                수집데이터[42] = res_tr3.registers[8]            # Tr3_V_S
                수집데이터[43] = res_tr3.registers[10]           # Tr3_V_T
                수집데이터[44] = res_tr3.registers[12]           # Tr3_V_R_S
                수집데이터[45] = res_tr3.registers[14]           # Tr3_V_S_T
                수집데이터[46] = res_tr3.registers[16]           # Tr3_V_T_R
                수집데이터[47] = res_tr3.registers[20] / 1000.0  # Tr3_P_kW (나눔수 1000)

            # -------------------------------------------------------------
            # [5] LS PLC - 국번 5 (온도 수집 및 환기팬 제어명령 쓰기)
            # -------------------------------------------------------------
            res_plc = safe_modbus_call(client.read_holding_registers, address=900, count=52, slave_id=5)
            if res_plc and not res_plc.isError():
                통신성공_여부 = True
                # 모든 온도 및 운전시간에 나눔수 10 적용
                수집데이터[0]  = res_plc.registers[0] / 10.0     # 실내온도
                수집데이터[1]  = res_plc.registers[1] / 10.0     # 외기온도
                
                # 🚨 오타 수정: res_tr1, res_tr2 등이 아닌 res_plc 통신 결과에서 뽑아야 합니다!
                수집데이터[26] = res_plc.registers[2] / 10.0     # Tr1_Temp
                수집데이터[37] = res_plc.registers[3] / 10.0     # Tr2_Temp
                수집데이터[48] = res_plc.registers[4] / 10.0     # Tr3_Temp
                
                수집데이터[49] = res_plc.registers[5] / 10.0     # 에어콘01온도
                수집데이터[50] = res_plc.registers[6] / 10.0     # 에어콘02온도
                수집데이터[2]  = res_plc.registers[7] / 10.0     # SF운전시간
                수집데이터[3]  = res_plc.registers[8] / 10.0     # EF운전시간
                
                ac_manager.check_and_control(
                    indoor_temp=수집데이터[0],      # 이미 /10.0이 되었으므로 바로 투입
                    outdoor_temp=수집데이터[1], 
                    dis_temp1=수집데이터[49], 
                    dis_temp2=수집데이터[50], 
                    total_load=수집데이터[14]       # KEP_P_kW 연동
                )
                safe_modbus_call(client.write_register, address=2000, value=ac_manager.fan_control_cmd, slave_id=5)

                # 👇👇👇 [여기에 신규 추가] 순회 중 메모장에 값이 있으면 PLC로 쏘고 메모장 지우기 👇👇👇
                global pending_tr_fan_values
                if pending_tr_fan_values is not None:
                    safe_modbus_call(client.write_registers, address=2010, values=pending_tr_fan_values, slave_id=5)
                    pending_tr_fan_values = None # 전송 완료했으니 메모장 비우기
                # 👆👆👆

            # -------------------------------------------------------------
            # [6] UI 화면 아이콘 연동 및 1분 로깅 방어막
            # -------------------------------------------------------------
            if 통신성공_여부 and current_status != True:
                comm_signal.status_changed.emit(True)
                current_status = True
            elif not 통신성공_여부 and current_status != False:
                comm_signal.status_changed.emit(False)
                current_status = False

            now_time = time.time()
            if 통신성공_여부 and (now_time - last_db_save_time >= 58.0):
                insert_raw_data(수집데이터)
                last_db_save_time = now_time

            time.sleep(0.5)

        except Exception as e:
            print(f"마스터 루프 에러: {e}")
            if client: client.close()
            time.sleep(1)

# 💡 DB 저장 함수 간소화: 위에서 나누기를 다 했으므로 바로 DB에 꽂아 넣습니다!
def insert_raw_data(values):
    if len(values) < len(DATA_LABELS): return
    try:
        conn = get_db_raw_connection()
        c = conn.cursor()
        now = datetime.now()
        l_date, l_time = now.strftime('%Y-%m-%d'), now.strftime('%H:%M:%S')
        
        # 복잡했던 DIV_BY_10, DIV_BY_100 로직 완전 삭제!
        adjusted_values = [round(float(val), 1) for val in values]
        
        placeholders = ", ".join(["%s"] * len(adjusted_values))
        col_names = ", ".join([f"`{name}`" for name in DATA_LABELS])
        
        c.execute(f"INSERT INTO raw_data (log_date, log_time, {col_names}) VALUES (%s, %s, {placeholders})", [l_date, l_time] + adjusted_values)
        conn.commit(); conn.close()
    except Exception as e:
        pass