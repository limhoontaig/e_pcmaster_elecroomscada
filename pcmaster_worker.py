# pcmaster_worker.py
import time
import os
import struct
import configparser

import event_manager
from datetime import datetime
from PyQt5.QtCore import QObject, pyqtSignal

from pymodbus.client import ModbusSerialClient 

from db_manager import DATA_LABELS, get_db_raw_connection
from ac_controller import ac_manager 

# 🌟 [신규 추가] PC 수동 조작 이벤트 매핑 딕셔너리
COMMAND_MAP = {
    100: "TR 냉각 자동(ON)/수동(OFF) 모드 전환",
    101: "TR 냉각 전체 수동 기동",
    102: "TR1 수동 기동 스위치",
    103: "TR2 수동 기동 스위치",
    104: "TR3 수동 기동 스위치",
    116: "배기휀(EF) 수동 기동 스위치",
    117: "급기휀(SF) 수동 기동 스위치"
}

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

# 🌟 [최종 수정] 실수(Real/Float) 형식으로 변환하는 함수
def to_32bit(regs, idx):
    """16비트 레지스터 2개를 32비트 실수(Float/Real)로 변환"""
    # 워드 스왑(Word Swap) 방식을 유지하면서 'f' 기호를 사용하여 실수로 읽어냅니다.
    packed = struct.pack('>HH', regs[idx+1], regs[idx])
    return struct.unpack('>f', packed)[0]

def to_64bit(regs, idx):
    """16비트 레지스터 4개를 64비트 실수(Double)로 변환 (총사용량 등)"""
    packed = struct.pack('>HHHH', regs[idx+3], regs[idx+2], regs[idx+1], regs[idx])
    return struct.unpack('>d', packed)[0]

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
    plc_data_update = pyqtSignal(dict)
    plc_initial_sync = pyqtSignal(bool, bool)

comm_signal = CommSignal()
last_db_save_time = 0
pending_ac_fan_values = None
pending_tr_fan_values = None
vent_settings = None
last_sent_vent_targets = None
is_running = True

tr1_buffer = []
tr2_buffer = []
tr3_buffer = []
last_max_calc_time = 0
is_first_tr_send = True

client_relay = ModbusSerialClient(port=COM_PORT_RELAY, baudrate=BAUD_RATE, timeout=0.3, stopbits=1, bytesize=8, parity='N')

if COM_PORT_RELAY == COM_PORT_PLC:
    client_plc = client_relay
else:
    client_plc = ModbusSerialClient(port=COM_PORT_PLC, baudrate=BAUD_RATE, timeout=0.3, stopbits=1, bytesize=8, parity='N')
    
def write_plc_bit(address, state):
    if client_plc and client_plc.is_socket_open():
        # 기존 모드버스 주소 변환 및 전송 로직
        word = address // 10
        bit = address % 10
        real_modbus_address = (word * 16) + bit
        
        safe_modbus_call(client_plc.write_coil, address=real_modbus_address, value=state, slave_id=5)
        # print(f"👉 [비트 제어] M{address:04d} (Modbus {real_modbus_address}번지)에 {state} 전송 완료")
        
        # 🌟 [신규 추가] 조작 즉시 DB에 이벤트 로그로 박제
        if address in COMMAND_MAP:
            action_str = "ON(동작/켜짐)" if state else "OFF(정지/꺼짐)"
            msg = f"화면 수동 제어: {COMMAND_MAP[address]} -> {action_str}"
            
            import db_manager
            # 분류를 'COMMAND'로 하고, 조작자(operator)를 'SCADA_PC'로 명시
            event_id = db_manager.log_event_start("COMMAND", f"M{address:04d}", msg, operator="SCADA_PC")
            
            # 명령 하달은 상태 유지가 아닌 '순간의 조작'이므로, 기록 즉시 마감하여 duration을 0으로 만듦
            if event_id:
                db_manager.log_event_end(event_id, "COMMAND")

def write_plc_register(address, value):
    if client_plc and client_plc.is_socket_open():
        safe_modbus_call(client_plc.write_register, address=address, value=int(value * 10), slave_id=5)
        #print(f"🌡️ [워드 제어] D{address:04d} 번지에 설정값 {value} 전송 완료")

def serial_receive_thread():
    global last_db_save_time, pending_ac_fan_values, pending_tr_fan_values, last_sent_vent_targets
    global tr1_buffer, tr2_buffer, tr3_buffer, last_max_calc_time, is_first_tr_send, is_running
    
    current_status = None
    is_initial_sync_done = False
    
    try:
        while is_running:
            current_step = "통신 루프 시작 대기"
            try:
                relay_connected = client_relay.is_socket_open()
                plc_connected = client_plc.is_socket_open()

                current_step = "릴레이(계전기) 통신 포트 연결"
                if not client_relay.is_socket_open():
                    client_relay.connect()
                
                current_step = "PLC 통신 포트 연결"
                if client_plc is not client_relay and not client_plc.is_socket_open():
                    client_plc.connect()

                if not (client_relay.is_socket_open() or client_plc.is_socket_open()):
                    time.sleep(1)
                    continue
                
                통신성공_여부 = False
                수집데이터 = [0] * len(DATA_LABELS) 
                
                # =============================================================
                # ⚡ [그룹 A] 전력 계전기 통신 (국번 6, 1, 2, 3) 
                # =============================================================
                if client_relay.is_socket_open():
                    current_step = "계전기(국번 6) 데이터 읽기"
                    res_kep = safe_modbus_call(client_relay.read_input_registers, address=4, count=32, slave_id=6)
                    if res_kep and not res_kep.isError():
                        통신성공_여부 = True
                        # 🌟 32비트 조합 함수(to_32bit)를 적용하여 올바른 숫자로 복원
                        수집데이터[4] = to_32bit(res_kep.registers, 0) / 1000.0; 수집데이터[5] = to_32bit(res_kep.registers, 2) / 1000.0   
                        수집데이터[6] = to_32bit(res_kep.registers, 4) / 1000.0; 수집데이터[7] = to_32bit(res_kep.registers, 6) / 1000.0   
                        수집데이터[8] = to_32bit(res_kep.registers, 8) / 1000.0; 수집데이터[9] = to_32bit(res_kep.registers, 10) / 1000.0  
                        수집데이터[10] = to_32bit(res_kep.registers, 14);      수집데이터[11] = to_32bit(res_kep.registers, 16)           
                        수집데이터[12] = to_32bit(res_kep.registers, 18);      수집데이터[13] = to_32bit(res_kep.registers, 20)           
                        수집데이터[14] = to_32bit(res_kep.registers, 24) / 1000.0  
                        # 🌟 64비트 총사용량 조합 함수(to_64bit) 적용 (28, 29, 30, 31번 4개 레지스터 묶음)
                        수집데이터[15] = to_32bit(res_kep.registers, 30) / 1000.0 
                        
                    current_step = "계전기 TR-1(국번 1) 데이터 읽기"
                    res_tr1 = safe_modbus_call(client_relay.read_input_registers, address=4, count=38, slave_id=1)
                    if res_tr1 and not res_tr1.isError():
                        통신성공_여부 = True
                        수집데이터[16] = to_32bit(res_tr1.registers, 0);  수집데이터[17] = to_32bit(res_tr1.registers, 2);  수집데이터[18] = to_32bit(res_tr1.registers, 4)
                        수집데이터[19] = to_32bit(res_tr1.registers, 6);  수집데이터[20] = to_32bit(res_tr1.registers, 8);  수집데이터[21] = to_32bit(res_tr1.registers, 10)
                        수집데이터[22] = to_32bit(res_tr1.registers, 12); 수집데이터[23] = to_32bit(res_tr1.registers, 14); 수집데이터[24] = to_32bit(res_tr1.registers, 16)
                        수집데이터[25] = to_32bit(res_tr1.registers, 20) / 1000.0  

                    current_step = "계전기 TR-2(국번 2) 데이터 읽기"
                    res_tr2 = safe_modbus_call(client_relay.read_input_registers, address=4, count=38, slave_id=2)
                    if res_tr2 and not res_tr2.isError():
                        통신성공_여부 = True
                        수집데이터[27] = to_32bit(res_tr2.registers, 0);  수집데이터[28] = to_32bit(res_tr2.registers, 2);  수집데이터[29] = to_32bit(res_tr2.registers, 4)
                        수집데이터[30] = to_32bit(res_tr2.registers, 6);  수집데이터[31] = to_32bit(res_tr2.registers, 8);  수집데이터[32] = to_32bit(res_tr2.registers, 10)
                        수집데이터[33] = to_32bit(res_tr2.registers, 12); 수집데이터[34] = to_32bit(res_tr2.registers, 14); 수집데이터[35] = to_32bit(res_tr2.registers, 16)
                        수집데이터[36] = to_32bit(res_tr2.registers, 20) / 1000.0  

                    current_step = "계전기 TR-3(국번 3) 데이터 읽기"
                    res_tr3 = safe_modbus_call(client_relay.read_input_registers, address=4, count=38, slave_id=3)
                    if res_tr3 and not res_tr3.isError():
                        통신성공_여부 = True
                        수집데이터[38] = to_32bit(res_tr3.registers, 0);  수집데이터[39] = to_32bit(res_tr3.registers, 2);  수집데이터[40] = to_32bit(res_tr3.registers, 4)
                        수집데이터[41] = to_32bit(res_tr3.registers, 6);  수집데이터[42] = to_32bit(res_tr3.registers, 8);  수집데이터[43] = to_32bit(res_tr3.registers, 10)
                        수집데이터[44] = to_32bit(res_tr3.registers, 12); 수집데이터[45] = to_32bit(res_tr3.registers, 14); 수집데이터[46] = to_32bit(res_tr3.registers, 16)
                        수집데이터[47] = to_32bit(res_tr3.registers, 20) / 1000.0  
                
                # =============================================================
                # 🏭 [그룹 B] LS PLC 통신 (국번 5) - 새 메모리 맵 반영
                # =============================================================
                if client_plc.is_socket_open():
                    if not is_initial_sync_done:
                        current_step = "PLC 초기 상태(M100, M101) 읽기"
                        # M0100의 Modbus 주소는 160번지입니다 ((10*16)+0)
                        res_init = safe_modbus_call(client_plc.read_coils, address=160, count=2, slave_id=5)
                        if res_init and not res_init.isError():
                            m100_state = res_init.bits[0]
                            m101_state = res_init.bits[1]
                            # UI로 시그널 쏘기!
                            comm_signal.plc_initial_sync.emit(m100_state, m101_state)
                            is_initial_sync_done = True
                            #print(f"🔄 초기 동기화 완료: M100(자동/수동)={m100_state}, M101(마스터)={m101_state}")
                    
                    if pending_tr_fan_values is not None:
                        current_step = "PLC(국번 5) 온도 설정값 쓰기 (D0900)"
                        safe_modbus_call(client_plc.write_registers, address=900, values=pending_tr_fan_values, slave_id=5)
                        # print(f"✅ [워드 제어] D0900~0905 번지에 온도 설정값 {pending_tr_fan_values} 전송 완료")
                        pending_tr_fan_values = None                
                    
                    current_step = "PLC(국번 5) 상태 비트 읽기 (M0200~M0220)"
                    
                    # 🌟 M0200의 실제 Modbus 시작 번지는 320 ((20 * 16) + 0 = 320)
                    # M0220(352번지)까지 포함하여 총 33칸을 읽어옵니다.
                    res_coils = safe_modbus_call(client_plc.read_coils, address=320, count=33, slave_id=5)
                    
                    if res_coils and not res_coils.isError():
                        clean_bits = [] # A~F가 제거된 순수한 0~9 비트만 담을 리스트
                        
                        for i, state in enumerate(res_coils.bits[:33]):
                            modbus_addr = 320 + i
                            bit = modbus_addr % 16 # 현재 주소의 비트 자리수 (0~15)
                            
                            # 🌟 비트 자리가 9 이하인 경우(0~9)만 추출하고, 10~15(A~F)는 무시합니다.
                            if bit <= 9:
                                clean_bits.append(state)
                        
                        # 완성된 clean_bits는 우리가 설계한 순서(M0200...M0209, M0210...)와 정확히 일치합니다.
                        event_manager.process_plc_events(clean_bits)
                        comm_signal.plc_status_update.emit(clean_bits)
                        
                    current_step = "PLC(국번 5) 센서 워드 읽기 (D0950)"
                    res_plc = safe_modbus_call(client_plc.read_holding_registers, address=950, count=7, slave_id=5)
                    if res_plc and not res_plc.isError():
                        통신성공_여부 = True
                        
                        수집데이터[0]  = res_plc.registers[0] / 10.0    # D00950: 실내온도
                        수집데이터[1]  = res_plc.registers[1] / 10.0    # D00951: 외기온도
                        수집데이터[49] = res_plc.registers[2] / 10.0    # D00952: 에어콘01온도
                        수집데이터[50] = res_plc.registers[3] / 10.0    # D00953: 에어콘02온도
                        수집데이터[26] = res_plc.registers[4] / 10.0    # D00954: Tr1_Temp
                        수집데이터[37] = res_plc.registers[5] / 10.0    # D00955: Tr2_Temp
                        수집데이터[48] = res_plc.registers[6] / 10.0    # D00956: Tr3_Temp

                        ui_data_dict = {
                            'indoor_temp': 수집데이터[0],
                            'outdoor_temp': 수집데이터[1],
                            'Tr1_Temp': 수집데이터[26],
                            'Tr2_Temp': 수집데이터[37],
                            'Tr3_Temp': 수집데이터[48],
                            'Tr1_V_R_S': 수집데이터[22],
                            'Tr1_A_R': 수집데이터[16],
                            'Tr1_P_kW': 수집데이터[25],
                            'Tr2_V_R_S': 수집데이터[33],
                            'Tr2_A_R': 수집데이터[27],
                            'Tr2_P_kW': 수집데이터[36],
                            'Tr3_V_R_S': 수집데이터[44],
                            'Tr3_A_R': 수집데이터[38],
                            'Tr3_P_kW': 수집데이터[47],
                        }
                        comm_signal.plc_data_update.emit(ui_data_dict)

                        current_step = "PLC(국번 5) 스마트 환기 제어 판별 및 쓰기"
                        if vent_settings is not None:
                            out_temp = 수집데이터[1]
                            
                            if out_temp < 16.0:
                                target_on = vent_settings['w_on']
                                target_off = vent_settings['w_off']
                            elif out_temp < 25.0:
                                target_on = vent_settings['sp_on']
                                target_off = vent_settings['sp_off']
                            else:
                                target_on = vent_settings['su_on']
                                target_off = vent_settings['su_off']
                                
                            target_supply_stop = vent_settings['supply_stop']
                            target_supply_start = vent_settings['supply_start']

                            plc_vent_targets = [
                                int(target_on * 10),           
                                int(target_off * 10),          
                                int(target_supply_stop * 10),  
                                int(target_supply_start * 10)  
                            ]
                            if plc_vent_targets != last_sent_vent_targets:
                                safe_modbus_call(client_plc.write_registers, address=906, values=plc_vent_targets, slave_id=5)
                                # print(f"✅ [워드 제어] D0906~0909 번지에 환기 설정값 {plc_vent_targets} 전송 완료")
                                last_sent_vent_targets = plc_vent_targets
                        
                        current_step = "PLC(국번 5) 1분 변압기 최대 온도 연산 및 쓰기 (D0980~D0982)"
                        now_t = time.time()
                        tr1_buffer.append(res_plc.registers[4]) 
                        tr2_buffer.append(res_plc.registers[5])
                        tr3_buffer.append(res_plc.registers[6])

                        if is_first_tr_send or (now_t - last_max_calc_time >= 60.0):
                            if tr1_buffer:
                                max_tr1 = max(tr1_buffer); max_tr2 = max(tr2_buffer); max_tr3 = max(tr3_buffer)
                                safe_modbus_call(client_plc.write_registers, address=980, values=[max_tr1, max_tr2, max_tr3], slave_id=5)
                            tr1_buffer.clear(); tr2_buffer.clear(); tr3_buffer.clear()
                            last_max_calc_time = now_t
                            is_first_tr_send = False
                    
                    current_step = "PLC(국번 5) 에어컨 컨트롤러 로직 쓰기 (D2000)"
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
                current_step = "데이터베이스 로깅 및 시그널 전송"
                if 통신성공_여부:
                    comm_signal.status_changed.emit(True)
                else:
                    comm_signal.status_changed.emit(False)

                now_time = time.time()
                if 통신성공_여부 and (now_time - last_db_save_time >= 59.5):
                    insert_raw_data(수집데이터)
                    last_db_save_time = now_time

                time.sleep(0.1)

            except Exception as e:
                # print(f"❌ [에러 발생 구간: {current_step}] -> 상세 내용: {e}")
                if client_relay: client_relay.close()
                if client_plc: client_plc.close()

                comm_signal.status_changed.emit(False)
                current_status = False

                time.sleep(1)
    finally:
        # print("통신 포트를 안전하게 닫습니다.")
        if client_relay: client_relay.close()
        if client_plc: client_plc.close()

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