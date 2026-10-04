# event_manager.py

import time
from shared import db_manager

last_plc_bits = []
active_events = {}

# 🌟 [신규 추가] 국번별 마지막 출력 시간을 저장하는 딕셔너리 (파일 상단에 선언)
_debug_print_time = {1: 0, 2: 0, 3: 0, 6: 0}

# M0200~M0220 비트 인덱스 매핑: (이벤트 분류, 영문 태그명, 화면 및 DB 기록용 한글 메시지)
PLC_TAG_MAP = {
    # --- [배기 휀 그룹] ---
    0:  ("STATUS",    "EF_local_auto_start_out",   "배기 현장 자동 모드"),
    1:  ("STATUS",    "EF_local_manual_start_out", "배기 현장 수동 모드"),
    2:  ("STATUS",    "EF_op_room_start_out",      "배기 방재실 모드"),
    3:  ("OPERATION", "EF_operation",              "배기휀 동작"),
    4:  ("STATUS",    "EF_stop_out",               "배기 운전 정지"),
    5:  ("ALARM",     "EF_trip",                   "배기휀 써멀 동작 (트립)"),
    
    # --- [급기 휀 그룹] ---
    6:  ("STATUS",    "SF_local_auto_start_out",   "급기 현장 자동 모드"),
    7:  ("STATUS",    "SF_local_manual_start_out", "급기 현장 수동 모드"),
    8:  ("STATUS",    "SF_op_room_start_out",      "급기 방재실 모드"),
    9:  ("OPERATION", "SF_operation",              "급기휀 동작"),
    10: ("STATUS",    "SF_stop_out",               "급기 운전 정지"),
    11: ("ALARM",     "SF_trip",                   "급기 휀 써멀 동작 (트립)"),
    
    # --- [변압기(TR) 휀 그룹] ---
    12: ("OPERATION", "tr1_fan_on",                "TR01 휀 동작"),
    13: ("OPERATION", "tr2_fan_on",                "TR02 휀 동작"),
    14: ("OPERATION", "tr3_fan_on",                "TR03 휀 동작"),
    
    # --- [시스템 및 센서 알람 (에러/단선)] ---
    15: ("ALARM",     "analog_mod_err",            "TR 온도입력모듈 오류"),
    16: ("ALARM",     "rtd_mod_err",               "RTD 입력모듈 에러"),
    17: ("ALARM",     "rtd_ch0_err",               "전기실 온도 센서 단선"),
    18: ("ALARM",     "rtd_ch1_err",               "외기온도 센서 단선"),
    19: ("ALARM",     "rtd_ch2_err",               "에어컨01 온도 센서 단선"),
    20: ("ALARM",     "rtd_ch3_err",               "에어컨02 온도 센서 단선"),

    21: ("OPERATION", "aircon01_operation",          "에어컨01 가동 (환기팬 연동 정지)"),
    22: ("OPERATION", "aircon02_operation",          "에어컨02 가동 (환기팬 연동 정지)")
}

def process_plc_events(current_bits):
    global last_plc_bits, active_events
    
    if not last_plc_bits:
        last_plc_bits = current_bits[:]
        return

    for idx, curr_state in enumerate(current_bits):
        prev_state = last_plc_bits[idx]
        
        if curr_state != prev_state:
            if idx in PLC_TAG_MAP:
                e_type, equip_name, start_msg = PLC_TAG_MAP[idx]
                
                if curr_state == 1:
                    event_id = db_manager.log_event_start(e_type, equip_name, start_msg)
                    if event_id:
                        # 🌟 수정: 튜플 형태로 event_id와 e_type을 함께 저장
                        active_events[idx] = (event_id, e_type)
                        # print(f"[{e_type}] {start_msg} 발생 기록")
                        
                elif curr_state == 0:
                    if idx in active_events:
                        # 🌟 수정: 저장해둔 e_type을 꺼내어 log_event_end로 전달
                        event_id, saved_e_type = active_events.pop(idx)
                        db_manager.log_event_end(event_id, saved_e_type)
                        #print(f"[{saved_e_type}] {start_msg} 해제 (시간 및 리셋 상태 저장 완료)")

    last_plc_bits = current_bits[:]

# =====================================================================
# 🌟 [신규 추가] 계전기용 이벤트 맵 및 상태 변수
# =====================================================================

# GIPAM115Fi (수전반 - 국번 6) 이벤트 맵
# 키 구성: (레지스터 오프셋, 비트 인덱스)
GIPAM_TAG_MAP = {
    # 30001번지 (오프셋 0): DI/DO 접점 상태
    (0, 4): ("STATUS", "MAIN_CB_ON", "수전반 VCB 투입(ON)"),
    (0, 5): ("STATUS", "MAIN_CB_OFF", "수전반 VCB 개방(OFF)"),
    
    # 30003번지 (오프셋 2): 보호계전기(Fault) 트립 상태
    (2, 0): ("ALARM", "OCR_R", "수전반 과전류(OCR) R상 트립"),
    (2, 1): ("ALARM", "OCR_S", "수전반 과전류(OCR) S상 트립"),
    (2, 2): ("ALARM", "OCR_T", "수전반 과전류(OCR) T상 트립"),
    (2, 3): ("ALARM", "OCGR",  "수전반 지락과전류(OCGR) 트립"),
    (2, 4): ("ALARM", "OVR_R", "수전반 과전압(OVR) R상 트립"),
    (2, 7): ("ALARM", "UVR_R", "수전반 부족전압(UVR) R상 트립"),
    (2, 11): ("ALARM", "SGR",  "수전반 선택지락(SGR) 트립")
}

# GIMAC-IV (변압기반 - 국번 1, 2, 3) 이벤트 맵
GIMAC_TAG_MAP = {
    # 30002번지 (오프셋 1): F111 포맷 (DO / CB 상태)
    (1, 15): ("STATUS", "TR_CB_ON", "변압기반 ACB 투입(ON)"),
    (1, 14): ("STATUS", "TR_CB_OFF", "변압기반 ACB 개방(OFF)"),
    
    # 30003번지 (오프셋 2): F112 포맷 (시스템 및 기기 알람)
    (2, 8):  ("ALARM", "TR_SYS_ERR", "변압기반 시스템 에러 발생"),
    (2, 10): ("ALARM", "TR_ALARM", "변압기반 내부 알람 발생"),
    (2, 11): ("ALARM", "TR_EVENT", "변압기반 이벤트 발생")
}

# 계전기 상태 저장을 위한 글로벌 변수 초기화
last_relay_bits = {1: {}, 2: {}, 3: {}, 6: {}}
active_relay_events = {}

def process_relay_events(slave_id, registers):
    """
    모드버스에서 읽어온 4개의 워드(30001 ~ 30004)를 분석하여
    상태 변화 시 alarm_event_logs 테이블에 기록합니다.
    """
    global last_relay_bits, active_relay_events
    
    if not registers or len(registers) < 4: 
        return
        
    tag_map = GIPAM_TAG_MAP if slave_id == 6 else GIMAC_TAG_MAP
    prefix = "수전반(MAIN)" if slave_id == 6 else f"TR-0{slave_id}반"
    
    # 4개 워드(64비트)를 (레지스터 인덱스, 비트 인덱스) 형태의 딕셔너리로 분해
    current_bits = {}
    for reg_idx, reg_val in enumerate(registers[:4]):
        for bit_idx in range(16):
            current_bits[(reg_idx, bit_idx)] = (reg_val >> bit_idx) & 1
            
    # 최초 실행 시 초기화만 하고 리턴
    if not last_relay_bits[slave_id]:
        last_relay_bits[slave_id] = current_bits
        return

    # 상태 변화 감지 및 DB 로깅
    for key, curr_state in current_bits.items():
        prev_state = last_relay_bits[slave_id].get(key, 0)
        
        if curr_state != prev_state:
            if key in tag_map:
                e_type, tag_name, msg_suffix = tag_map[key]
                
                # 변압기반의 경우 어떤 기기인지 구분하기 위해 접두사 추가
                equip_name = f"ID{slave_id}_{tag_name}"
                full_msg = msg_suffix if slave_id == 6 else f"[{prefix}] {msg_suffix}"
                
                event_key = f"{slave_id}_{key[0]}_{key[1]}"
                
                if curr_state == 1:
                    # 이벤트 시작 기록
                    event_id = db_manager.log_event_start(e_type, equip_name, full_msg)
                    if event_id:
                        active_relay_events[event_key] = (event_id, e_type)
                elif curr_state == 0:
                    # 이벤트 해제 및 마감 기록
                    if event_key in active_relay_events:
                        event_id, saved_e_type = active_relay_events.pop(event_key)
                        db_manager.log_event_end(event_id, saved_e_type)
                        
    # 현재 상태를 과거 상태로 업데이트
    last_relay_bits[slave_id] = current_bits

    # # 🌟 [수정] 현재 코드 구조(GIPAM / GIMAC)에 맞춘 10초 주기 디버그 프린트 로직
    # current_time = time.time()
    # if current_time - _debug_print_time.get(slave_id, 0) >= 10.0:
    #     print(f"\n==================================================")
    #     print(f" 📡 [디버그] 계전기(국번 {slave_id}) 통신 상태 확인")
    #     print(f"==================================================")
        
    #     # 국번에 따라 맵을 다르게 선택
    #     debug_tag_map = GIPAM_TAG_MAP if slave_id == 6 else GIMAC_TAG_MAP
        
    #     # 맵에 정의된 이벤트들의 현재 상태를 뽑아서 출력
    #     for (reg_idx, bit_idx), (evt_type, evt_code, evt_name) in debug_tag_map.items():
    #         if reg_idx < len(registers):
    #             # 해당 레지스터에서 비트값 추출
    #             bit_val = (registers[reg_idx] >> bit_idx) & 1
    #             state_str = "🔴 ON(발생)" if bit_val else "⚪ OFF"
    #             print(f" - {evt_name} [{evt_code}]: {state_str}")
                
    #     print(f"==================================================\n")
        
    #     # 마지막 출력 시간 갱신
    #     _debug_print_time[slave_id] = current_time