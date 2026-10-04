# ac_controller.py
import time
import threading
import broadlink
import configparser
import os

from shared import db_manager

class ACController:
    def __init__(self):
        self.config_path = os.path.join(os.path.dirname(__file__), 'config.ini')
        self.config = configparser.ConfigParser()
        
        # ⚙️ 설정 기본값
        self.TEMP_START_1 = 28.5
        self.TEMP_START_2 = 31.0
        self.TEMP_STOP = 27.5
        self.TEMP_COLD = 26.0
        self.MAX_RUN_TIME = 3 * 3600  
        
        # ⚙️ 기기 정보 및 상태 변수
        self.SIMULATION_MODE = False
        self.HUB1_IP = '192.168.2.5' 
        self.HUB2_IP = '192.168.2.4' 
        self.IR_TURN_ON_29C  = "260040006200013c103211120f120f120f330f120f120f120f120f120f111011101110111011101110321033103210111011103210321011101110321011101110000d05" 
        self.IR_TURN_OFF = "260040006300013c0f330f130f120f120f330f120f120f120f3210330f120f120f1210111011101110111011101110110f120f330f120f330f120f130e130e340f000d05"

        self.ac_state = "STANDBY"
        self.ac_start_time = 0
        
        # 🌟 기존 self.fan_control_cmd = 0 삭제 후 아래와 같이 분리
        self.ac1_cmd = 0  # 1호기 기동 상태 (-> PLC D0957)
        self.ac2_cmd = 0  # 2호기 기동 상태 (-> PLC D0958)

        
        self.lead_ac = 1  
        self.is_auto = True

        self.load_settings()

    def load_settings(self):
        if os.path.exists(self.config_path):
            self.config.read(self.config_path, encoding='utf-8')
            if 'AC_SETTINGS' in self.config:
                self.TEMP_START_1 = self.config['AC_SETTINGS'].getfloat('START_TEMP_1', 28.5)
                self.TEMP_START_2 = self.config['AC_SETTINGS'].getfloat('START_TEMP_2', 31.0)
                self.TEMP_STOP = self.config['AC_SETTINGS'].getfloat('STOP_TEMP', 27.5)
                self.TEMP_COLD = self.config['AC_SETTINGS'].getfloat('COLD_WIND_TEMP', 26.0)
                self.MAX_RUN_TIME = self.config['AC_SETTINGS'].getfloat('MAX_RUN_HOURS', 3.0) * 3600

    def send_ir_task(self, ip_address, hex_code):
        if self.SIMULATION_MODE:
            print(f"   [시뮬레이션] {ip_address}로 IR 신호 전송 완료")
            self._log_individual_ac(ip_address, hex_code)
            return True
        try:
            device = broadlink.hello(ip_address)
            device.auth()
            packet = bytes.fromhex(hex_code)
            device.send_data(packet)
            print(f"[IR 발사 성공] 대상 IP: {ip_address}")
            self._log_individual_ac(ip_address, hex_code)
            return True 
        except Exception as e:
            print(f"[IR 발사 실패] ({ip_address}): {e}")
            return False

    def _log_individual_ac(self, ip_address, hex_code):
        ac_num = 1 if ip_address == self.HUB1_IP else 2
        if hex_code == self.IR_TURN_ON_29C:
            if ac_num == 1 and not getattr(self, 'ac1_event_id', None):
                self.ac1_event_id = db_manager.log_event_start("OPERATION", "에어컨 1호기", "1호기 냉방 가동", operator="SCADA_PC")
            elif ac_num == 2 and not getattr(self, 'ac2_event_id', None):
                self.ac2_event_id = db_manager.log_event_start("OPERATION", "에어컨 2호기", "2호기 냉방 가동", operator="SCADA_PC")
        elif hex_code == self.IR_TURN_OFF:
            if ac_num == 1 and getattr(self, 'ac1_event_id', None):
                db_manager.log_event_end(self.ac1_event_id, "OPERATION")
                self.ac1_event_id = None
            elif ac_num == 2 and getattr(self, 'ac2_event_id', None):
                db_manager.log_event_end(self.ac2_event_id, "OPERATION")
                self.ac2_event_id = None

    def force_manual_control(self, action):
        current_time = time.time()
        
        if action == "ON_1":
            if self.send_ir_task(self.HUB1_IP, self.IR_TURN_ON_29C):
                self.lead_ac = 1
                self.ac1_cmd = 1       # 👈 1호기 기동 신호 ON
                self.ac_state = "COOLING_1"       
                self.ac_start_time = current_time 
                return True
            return False

        elif action == "ON_2":
            if self.send_ir_task(self.HUB2_IP, self.IR_TURN_ON_29C):
                self.lead_ac = 2
                self.ac2_cmd = 1       # 👈 2호기 기동 신호 ON
                self.ac_state = "COOLING_1"      
                self.ac_start_time = current_time
                return True
            return False

        elif action == "OFF_1":
            if self.send_ir_task(self.HUB1_IP, self.IR_TURN_OFF):
                self.ac1_cmd = 0       # 👈 1호기 기동 신호 OFF
                if self.ac_state == "COOLING_1" and self.lead_ac == 1:
                    self.ac_state = "STANDBY"
                elif self.ac_state == "COOLING_2":
                    self.lead_ac = 2
                    self.ac_state = "COOLING_1"
                return True
            return False

        elif action == "OFF_2":
            if self.send_ir_task(self.HUB2_IP, self.IR_TURN_OFF):
                self.ac2_cmd = 0       # 👈 2호기 기동 신호 OFF
                if self.ac_state == "COOLING_1" and self.lead_ac == 2:
                    self.ac_state = "STANDBY"
                elif self.ac_state == "COOLING_2":
                    self.lead_ac = 1
                    self.ac_state = "COOLING_1"
                return True
            return False

        elif action == "OFF_ALL":
            res1 = self.send_ir_task(self.HUB1_IP, self.IR_TURN_OFF)
            res2 = self.send_ir_task(self.HUB2_IP, self.IR_TURN_OFF)
            if res1 or res2: 
                if res1: self.ac1_cmd = 0
                if res2: self.ac2_cmd = 0
                if self.ac1_cmd == 0 and self.ac2_cmd == 0:
                    self.ac_state = "STANDBY"
                return True
            return False        

    def check_and_control(self, indoor_temp, outdoor_temp, dis_temp1, dis_temp2, total_load):
        if indoor_temp is None: return

        lag_ac = 2 if self.lead_ac == 1 else 1
        hubs = {1: self.HUB1_IP, 2: self.HUB2_IP}
        dis_temps = {1: dis_temp1, 2: dis_temp2}
        current_time = time.time()
        is_heavy_load = (outdoor_temp >= 32.0) or (total_load >= 1200)

        if self.ac_state == "STANDBY":
            if (indoor_temp >= self.TEMP_START_1) or (is_heavy_load and indoor_temp >= 27.0):
                if indoor_temp >= self.TEMP_START_1:
                    print(f"\n[일반 기동] 실내 온도 {indoor_temp:.1f}C 도달. 선행 {self.lead_ac}호기 가동!")
                else:
                    print(f"\n[예측 기동 발동] 외기:{outdoor_temp:.1f}C, 부하:{total_load}kW (실내:{indoor_temp:.1f}C). 선행 {self.lead_ac}호기 가동!")
                threading.Thread(target=self.send_ir_task, args=(hubs[self.lead_ac], self.IR_TURN_ON_29C)).start()
                self.ac_state = "STARTING_1"
                self.ac_start_time = current_time

        elif self.ac_state == "STARTING_1":
            if dis_temps[self.lead_ac] <= self.TEMP_COLD:
                # 👈 리드 에어컨 번호에 따라 해당 cmd를 1로 변경
                if self.lead_ac == 1: self.ac1_cmd = 1
                else: self.ac2_cmd = 1
                self.ac_state = "COOLING_1"

        elif self.ac_state == "COOLING_1":
            if current_time - self.ac_start_time >= self.MAX_RUN_TIME:
                threading.Thread(target=self.send_ir_task, args=(hubs[lag_ac], self.IR_TURN_ON_29C)).start()
                time.sleep(2) 
                threading.Thread(target=self.send_ir_task, args=(hubs[self.lead_ac], self.IR_TURN_OFF)).start() 
                
                # 👈 교대 시 이전 호기 끄기 처리
                if self.lead_ac == 1: self.ac1_cmd = 0
                else: self.ac2_cmd = 0
                
                self.lead_ac = lag_ac
                self.ac_start_time = current_time 
                self.ac_state = "STARTING_1" 
                
            elif indoor_temp >= self.TEMP_START_2:
                threading.Thread(target=self.send_ir_task, args=(hubs[lag_ac], self.IR_TURN_ON_29C)).start()
                self.ac_state = "STARTING_2"
                self.ac_start_time = current_time
                
            elif (indoor_temp <= self.TEMP_STOP) and (not is_heavy_load):
                threading.Thread(target=self.send_ir_task, args=(hubs[self.lead_ac], self.IR_TURN_OFF)).start()
                
                # 👈 온도 안정화로 꺼질 때 해당 호기 cmd 끄기
                if self.lead_ac == 1: self.ac1_cmd = 0
                else: self.ac2_cmd = 0
                
                self.lead_ac = lag_ac  
                self.ac_state = "STANDBY"

        elif self.ac_state == "STARTING_2":
            if dis_temps[lag_ac] <= self.TEMP_COLD:
                # 👈 후행 에어컨도 찬바람 확인 시 cmd ON
                if lag_ac == 1: self.ac1_cmd = 1
                else: self.ac2_cmd = 1
                self.ac_state = "COOLING_2"

        elif self.ac_state == "COOLING_2":
            if (indoor_temp <= self.TEMP_STOP) and (not is_heavy_load):
                threading.Thread(target=self.send_ir_task, args=(self.HUB1_IP, self.IR_TURN_OFF)).start()
                threading.Thread(target=self.send_ir_task, args=(self.HUB2_IP, self.IR_TURN_OFF)).start()
                
                # 👈 전호기 정지 시 둘 다 끄기
                self.ac1_cmd = 0 
                self.ac2_cmd = 0 
                
                self.lead_ac = lag_ac  
                self.ac_state = "STANDBY"

# 프로그램 전체에서 하나만 공통으로 사용할 매니저 객체 생성
ac_manager = ACController()

