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

def get_com_port():
    config = configparser.ConfigParser()
    if os.path.exists(config_path):
        config.read(config_path, encoding='utf-8')
        return config['SETTINGS'].get('COM_PORT', 'COM3')
    return 'COM3'

COM_PORT = get_com_port()
BAUD_RATE = 19200         

# 🌟 [신규 추가] UI로 피드백을 전달할 시그널 추가
class CommSignal(QObject):
    status_changed = pyqtSignal(bool)
    plc_status_update = pyqtSignal(list) # M0200~M0222 상태 비트 업데이트용

comm_signal = CommSignal()
last_db_save_time = 0
pending_ac_fan_values = None
pending_tr_fan_values = None
current_dynamic_fan_off = 28.0

# 🌟 [신규 추가] 1분 최대값 연산용 전역 변수
tr1_buffer = []
tr2_buffer = []
tr3_buffer = []
last_max_calc_time = 0

client = ModbusSerialClient(
        port=COM_PORT, 
        baudrate=BAUD_RATE, 
        timeout=0.3, 
        stopbits=1,
        bytesize=8,
        parity='N'
    )

# 🌟 [신규 추가] UI 화면에서 버튼을 누를 때 호출될 함수 (M0100 대역 조작)
def write_plc_bit(address, state):
    if client and client.is_socket_open():
        safe_modbus_call(client.write_coil, address=address, value=state, slave_id=5)
        print(f"👉 [비트 제어] M{address:04d} 번지에 {state} 전송 완료")


def serial_receive_thread():
    global last_db_save_time, current_dynamic_fan_off, pending_tr_fan_values
    global tr1_buffer, tr2_buffer, tr3_buffer, last_max_calc_time
    
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

            # [1] KEP 한전 계전기 - 국번 6
            res_kep = safe_modbus_call(client.read_input_registers, address=4, count=32, slave_id=6)
            if res_kep and not res_kep.isError():
                통신성공_여부 = True
                수집데이터[4]  = res_kep.registers[0] / 1000.0   
                수집데이터[5]  = res_kep.registers[2] / 1000.0   
                수집데이터[6]  = res_kep.registers[4] / 1000.0   
                수집데이터[7]  = res_kep.registers[6] / 1000.0   
                수집데이터[8]  = res_kep.registers[8] / 1000.0   
                수집데이터[9]  = res_kep.registers[10] / 1000.0  
                수집데이터[10] = res_kep.registers[14]           
                수집데이터[11] = res_kep.registers[16]           
                수집데이터[12] = res_kep.registers[18]           
                수집데이터[13] = res_kep.registers[20]           
                수집데이터[14] = res_kep.registers[24] / 1000.0  
                수집데이터[15] = ((res_kep.registers[30] << 16) + res_kep.registers[31]) / 1000.0 
                
            # [2] TR1 계전기 - 국번 1
            res_tr1 = safe_modbus_call(client.read_input_registers, address=4, count=38, slave_id=1)
            if res_tr1 and not res_tr1.isError():
                통신성공_여부 = True
                수집데이터[16] = res_tr1.registers[0]; 수집데이터[17] = res_tr1.registers[2]; 수집데이터[18] = res_tr1.registers[4]
                수집데이터[19] = res_tr1.registers[6]; 수집데이터[20] = res_tr1.registers[8]; 수집데이터[21] = res_tr1.registers[10]
                수집데이터[22] = res_tr1.registers[12]; 수집데이터[23] = res_tr1.registers[14]; 수집데이터[24] = res_tr1.registers[16]
                수집데이터[25] = res_tr1.registers[20] / 1000.0  

            # [3] TR2 계전기 - 국번 2
            res_tr2 = safe_modbus_call(client.read_input_registers, address=4, count=38, slave_id=2)
            if res_tr2 and not res_tr2.isError():
                통신성공_여부 = True
                수집데이터[27] = res_tr2.registers[0]; 수집데이터[28] = res_tr2.registers[2]; 수집데이터[29] = res_tr2.registers[4]
                수집데이터[30] = res_tr2.registers[6]; 수집데이터[31] = res_tr2.registers[8]; 수집데이터[32] = res_tr2.registers[10]
                수집데이터[33] = res_tr2.registers[12]; 수집데이터[34] = res_tr2.registers[14]; 수집데이터[35] = res_tr2.registers[16]
                수집데이터[36] = res_tr2.registers[20] / 1000.0  

            # [4] TR3 계전기 - 국번 3
            res_tr3 = safe_modbus_call(client.read_input_registers, address=4, count=38, slave_id=3)
            if res_tr3 and not res_tr3.isError():
                통신성공_여부 = True
                수집데이터[38] = res_tr3.registers[0]; 수집데이터[39] = res_tr3.registers[2]; 수집데이터[40] = res_tr3.registers[4]
                수집데이터[41] = res_tr3.registers[6]; 수집데이터[42] = res_tr3.registers[8]; 수집데이터[43] = res_tr3.registers[10]
                수집데이터[44] = res_tr3.registers[12]; 수집데이터[45] = res_tr3.registers[14]; 수집데이터[46] = res_tr3.registers[16]
                수집데이터[47] = res_tr3.registers[20] / 1000.0  

            # -------------------------------------------------------------
            # [5] LS PLC - 국번 5 (온도 데이터 + 상태 비트 통신)
            # -------------------------------------------------------------
            
            # 🌟 [신규 통합 1] 상태 비트 (M0200 ~ M0222) 읽어오기
            res_coils = safe_modbus_call(client.read_coils, address=200, count=23, slave_id=5)
            if res_coils and not res_coils.isError():
                comm_signal.plc_status_update.emit(res_coils.bits[:23]) # 화면 애니메이션용으로 신호 쏨
                
            # [기존 통합 2] 온도 워드 읽어오기 (D00900부터 넉넉하게 52개 읽어옵니다)
            res_plc = safe_modbus_call(client.read_holding_registers, address=900, count=52, slave_id=5)
            if res_plc and not res_plc.isError():
                통신성공_여부 = True
                
                # 🌟 [수정됨] 새 메모리 맵(D00910~D00916)에 맞추어 인덱스(10~16) 번호를 조정했습니다.
                수집데이터[0]  = res_plc.registers[10] / 10.0    # D00910: 실내온도
                수집데이터[1]  = res_plc.registers[11] / 10.0    # D00911: 외기온도
                수집데이터[49] = res_plc.registers[12] / 10.0    # D00912: 에어콘01온도
                수집데이터[50] = res_plc.registers[13] / 10.0    # D00913: 에어콘02온도
                
                수집데이터[26] = res_plc.registers[14] / 10.0    # D00914: Tr1_Temp
                수집데이터[37] = res_plc.registers[15] / 10.0    # D00915: Tr2_Temp
                수집데이터[48] = res_plc.registers[16] / 10.0    # D00916: Tr3_Temp
                
                # 운전시간 등 누락된 값이 있다면 임시로 기존 D00907, 908 위치 유지
                수집데이터[2]  = res_plc.registers[7] / 10.0     # SF운전시간 (임시)
                수집데이터[3]  = res_plc.registers[8] / 10.0     # EF운전시간 (임시)

                # ==============================================================
                # 🌟 [신규 통합 3] 1분(60초) 변압기 최대 온도 연산 및 전송 로직
                # ==============================================================
                now_t = time.time()
                # 버퍼에 원본 정수 데이터 누적
                tr1_buffer.append(res_plc.registers[14]) 
                tr2_buffer.append(res_plc.registers[15])
                tr3_buffer.append(res_plc.registers[16])

                if now_t - last_max_calc_time >= 60.0:
                    if tr1_buffer:
                        # 리스트에서 최대값 추출
                        max_tr1 = max(tr1_buffer); max_tr2 = max(tr2_buffer); max_tr3 = max(tr3_buffer)
                        # D00920, 921, 922 번지에 연속 쓰기
                        safe_modbus_call(client.write_registers, address=920, values=[max_tr1, max_tr2, max_tr3], slave_id=5)
                        print(f"📊 [1분 최대값 PLC 전송] TR1: {max_tr1/10}도, TR2: {max_tr2/10}도, TR3: {max_tr3/10}도")
                    
                    # 버퍼 비우기 및 타이머 초기화
                    tr1_buffer.clear(); tr2_buffer.clear(); tr3_buffer.clear()
                    last_max_calc_time = now_t
                # ==============================================================

                # [기존 로직 유지] 외기 온도 연동 휀 정지온도 자동 변속
                outdoor_temp = 수집데이터[1]
                new_fan_off = current_dynamic_fan_off
                
                if outdoor_temp <= 15.0: new_fan_off = 25.0
                elif 22.0 >= outdoor_temp >= 17.0: new_fan_off = 28.0
                elif outdoor_temp >= 23.0: new_fan_off = 29.0
                    
                if new_fan_off != current_dynamic_fan_off:
                    res_write = safe_modbus_call(client.write_register, address=2021, value=int(new_fan_off * 10), slave_id=5)
                    if res_write and not res_write.isError():
                        current_dynamic_fan_off = new_fan_off  
                
                # [기존 로직 유지] AC 컨트롤러 및 UI 설정값 전송
                ac_manager.check_and_control(
                    indoor_temp=수집데이터[0],      
                    outdoor_temp=수집데이터[1], 
                    dis_temp1=수집데이터[49], 
                    dis_temp2=수집데이터[50], 
                    total_load=수집데이터[14]       
                )
                safe_modbus_call(client.write_register, address=2000, value=ac_manager.fan_control_cmd, slave_id=5)

                if pending_tr_fan_values is not None:
                    safe_modbus_call(client.write_registers, address=2010, values=pending_tr_fan_values, slave_id=5)
                    pending_tr_fan_values = None 

            # -------------------------------------------------------------
            # [6] DB 로깅 (58초마다 수집데이터 한 줄 기록)
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