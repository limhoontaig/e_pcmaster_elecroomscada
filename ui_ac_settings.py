# ui_ac_settings.py

import os
import configparser
from PyQt5.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout, QGroupBox, 
                             QLabel, QPushButton, QDoubleSpinBox, QMessageBox)
from ac_controller import ac_manager  # 분리된 에어컨 매니저 호출
import pcmaster_worker # 💡 PLC 통신 일꾼 추가

class ACSettingsDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("⚙️ 에어컨 및 환기팬 종합 제어 (관리자 전용)")
        # 💡 내용이 많아졌으므로 세로 높이를 420에서 580으로 살짝 키웠습니다.
        self.setFixedSize(380, 580)
        self.config_path = os.path.join(os.path.dirname(__file__), 'config.ini')
        self.config = configparser.ConfigParser()
        self.init_ui()
        self.load_settings()

    def init_ui(self):
        layout = QVBoxLayout()
        
        # ---------------------------------------------------------
        # 1. 에어컨 자동 제어 그룹 (기존)
        # ---------------------------------------------------------
        group_auto = QGroupBox("에어컨(AC) 자동 제어 설정")
        auto_layout = QVBoxLayout()
        
        self.spin_start1 = QDoubleSpinBox(); self.spin_start1.setRange(20.0, 35.0); self.spin_start1.setSingleStep(0.5)
        self.spin_start2 = QDoubleSpinBox(); self.spin_start2.setRange(20.0, 35.0); self.spin_start2.setSingleStep(0.5)
        self.spin_stop = QDoubleSpinBox(); self.spin_stop.setRange(15.0, 35.0); self.spin_stop.setSingleStep(0.5)
        self.spin_cold = QDoubleSpinBox(); self.spin_cold.setRange(10.0, 35.0); self.spin_cold.setSingleStep(0.5)
        self.spin_hours = QDoubleSpinBox(); self.spin_hours.setRange(1.0, 24.0); self.spin_hours.setSingleStep(1.0)

        self.add_row(auto_layout, "1단계 기동 온도 (℃):", self.spin_start1)
        self.add_row(auto_layout, "2단계 기동 온도 (℃):", self.spin_start2)
        self.add_row(auto_layout, "정지 (교대) 온도 (℃):", self.spin_stop)
        self.add_row(auto_layout, "찬바람 인식 온도 (℃):", self.spin_cold)
        self.add_row(auto_layout, "최대 연속 가동 교대 (시간):", self.spin_hours)
        group_auto.setLayout(auto_layout)
        layout.addWidget(group_auto)

        # ---------------------------------------------------------
        # 2. 환기팬 및 외기온도 연동 그룹 (💡 신규)
        # ---------------------------------------------------------
        group_fan = QGroupBox("환기팬(급/배기) 및 계절 온도 연동 설정")
        fan_layout = QVBoxLayout()
        
        self.spin_fan_on = QDoubleSpinBox(); self.spin_fan_on.setRange(20.0, 50.0); self.spin_fan_on.setSingleStep(0.5)
        self.spin_fan_off = QDoubleSpinBox(); self.spin_fan_off.setRange(15.0, 45.0); self.spin_fan_off.setSingleStep(0.5)
        self.spin_supply_stop = QDoubleSpinBox(); self.spin_supply_stop.setRange(10.0, 40.0); self.spin_supply_stop.setSingleStep(0.5)

        self.add_row(fan_layout, "배기 휀 가동 실내온도 (℃):", self.spin_fan_on)
        self.add_row(fan_layout, "배기 휀 정지 실내온도 (℃):", self.spin_fan_off)
        self.add_row(fan_layout, "급기 휀 강제차단 외기온도 (℃):", self.spin_supply_stop)
        
        group_fan.setLayout(fan_layout)
        layout.addWidget(group_fan)

        # ---------------------------------------------------------
        # 💡 통합 저장 버튼 (에어컨 + 환기팬 일괄 저장)
        # ---------------------------------------------------------
        btn_save = QPushButton("💾 설정 통합 저장 및 PLC 반영")
        btn_save.setStyleSheet("font-weight: bold; background-color: #4CAF50; color: white; padding: 10px; margin-top: 5px;")
        btn_save.clicked.connect(self.save_settings)
        layout.addWidget(btn_save)

        # ---------------------------------------------------------
        # 3. 수동 제어 그룹 (기존)
        # ---------------------------------------------------------
        group_manual = QGroupBox("에어컨 수동 원격 제어 (즉시 동작)")
        manual_layout = QHBoxLayout()
        
        btn_on_1 = QPushButton("1호기 켜기")
        btn_on_1.setStyleSheet("background-color: #3498db; color: white; padding: 8px;")
        btn_on_1.clicked.connect(lambda: self.trigger_manual("ON_1"))
        
        btn_on_2 = QPushButton("2호기 켜기")
        btn_on_2.setStyleSheet("background-color: #9b59b6; color: white; padding: 8px;")
        btn_on_2.clicked.connect(lambda: self.trigger_manual("ON_2"))
        
        btn_off_all = QPushButton("전체 끄기")
        btn_off_all.setStyleSheet("background-color: #e74c3c; color: white; padding: 8px; font-weight: bold;")
        btn_off_all.clicked.connect(lambda: self.trigger_manual("OFF_ALL"))
        
        manual_layout.addWidget(btn_on_1)
        manual_layout.addWidget(btn_on_2)
        manual_layout.addWidget(btn_off_all)
        group_manual.setLayout(manual_layout)
        layout.addWidget(group_manual)
        
        self.setLayout(layout)

    def add_row(self, layout, label_text, widget):
        row = QHBoxLayout()
        row.addWidget(QLabel(label_text))
        row.addWidget(widget)
        layout.addLayout(row)

    def load_settings(self):
        if os.path.exists(self.config_path):
            self.config.read(self.config_path, encoding='utf-8')
            if 'AC_SETTINGS' in self.config:
                self.spin_start1.setValue(self.config['AC_SETTINGS'].getfloat('START_TEMP_1', 28.5))
                self.spin_start2.setValue(self.config['AC_SETTINGS'].getfloat('START_TEMP_2', 31.0))
                self.spin_stop.setValue(self.config['AC_SETTINGS'].getfloat('STOP_TEMP', 27.5))
                self.spin_cold.setValue(self.config['AC_SETTINGS'].getfloat('COLD_WIND_TEMP', 26.0))
                self.spin_hours.setValue(self.config['AC_SETTINGS'].getfloat('MAX_RUN_HOURS', 3.0))
            
            # 신규 환기팬 설정값 로드
            if 'FAN_SETTINGS' in self.config:
                self.spin_fan_on.setValue(self.config['FAN_SETTINGS'].getfloat('FAN_ON', 30.0))
                self.spin_fan_off.setValue(self.config['FAN_SETTINGS'].getfloat('FAN_OFF', 28.0))
                self.spin_supply_stop.setValue(self.config['FAN_SETTINGS'].getfloat('SUPPLY_STOP', 25.0))
            else:
                self.spin_fan_on.setValue(30.0)
                self.spin_fan_off.setValue(28.0)
                self.spin_supply_stop.setValue(25.0)

    def save_settings(self):
        # 1. 환기팬 온도 유효성 검사
        if self.spin_fan_off.value() >= self.spin_fan_on.value():
            QMessageBox.warning(self, "설정 오류", "환기팬 '정지 실내온도'는 '가동 실내온도'보다 낮아야 합니다!")
            return

        # 2. Config 저장 (다음 실행 시 값을 기억하기 위함)
        if 'AC_SETTINGS' not in self.config:
            self.config['AC_SETTINGS'] = {}
        self.config['AC_SETTINGS']['START_TEMP_1'] = str(self.spin_start1.value())
        self.config['AC_SETTINGS']['START_TEMP_2'] = str(self.spin_start2.value())
        self.config['AC_SETTINGS']['STOP_TEMP'] = str(self.spin_stop.value())
        self.config['AC_SETTINGS']['COLD_WIND_TEMP'] = str(self.spin_cold.value())
        self.config['AC_SETTINGS']['MAX_RUN_HOURS'] = str(self.spin_hours.value())

        if 'FAN_SETTINGS' not in self.config:
            self.config['FAN_SETTINGS'] = {}
        self.config['FAN_SETTINGS']['FAN_ON'] = str(self.spin_fan_on.value())
        self.config['FAN_SETTINGS']['FAN_OFF'] = str(self.spin_fan_off.value())
        self.config['FAN_SETTINGS']['SUPPLY_STOP'] = str(self.spin_supply_stop.value())

        with open(self.config_path, 'w', encoding='utf-8') as f:
            self.config.write(f)
        
        # 3. 에어컨 매니저 자동 업데이트
        ac_manager.load_settings()

        # 4. 💡 PLC로 환기팬 설정값 비동기 전송 (소수점 1자리 제거를 위해 * 10)
        plc_fan_values = [
            int(self.spin_fan_on.value() * 10),       # D2020: 배기 휀 가동
            int(self.spin_fan_off.value() * 10),      # D2021: 배기 휀 정지
            int(self.spin_supply_stop.value() * 10)   # D2022: 급기 휀 강제 차단 외기온도
        ]
        pcmaster_worker.pending_ac_fan_values = plc_fan_values

        QMessageBox.information(
            self, 
            "저장 완료", 
            "에어컨 타이머 설정이 파이썬에 반영되었으며,\n환기팬(급/배기) 설정값이 PLC 통신 대기열에 등록되었습니다."
        )
        self.accept() # 완료 후 자동으로 창을 닫아줍니다.

    def trigger_manual(self, action):
        ac_manager.force_manual_control(action)  
        action_names = {"ON_1": "1호기 켜기", "ON_2": "2호기 켜기", "OFF_ALL": "전체 에어컨 끄기"}
        QMessageBox.information(self, "수동 제어", f"[{action_names[action]}] 명령이 전송되었습니다.\n자동 타이머가 초기화됩니다.")