# event_manager.py

import db_manager

last_plc_bits = []
active_events = {}

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
    20: ("ALARM",     "rtd_ch3_err",               "에어컨02 온도 센서 단선")
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