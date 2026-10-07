# ui_ac_settings.py

import os
import sys
import configparser
from PyQt5.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout, QGroupBox, 
                             QLabel, QPushButton, QDoubleSpinBox, QMessageBox)
from src.ac_controller import ac_manager  # 분리된 에어컨 매니저 호출

class ACSettingsDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("⚙️ 에어컨 및 환기팬 종합 제어 (관리자 전용)")
        self.setFixedSize(380, 480) # 버튼 위치 이동에 따른 세로 크기 미세 조정
        
       # 🌟 권한 문제 없는 AppData 경로 적용
        appdata_dir = os.path.join(os.environ.get('APPDATA', os.path.expanduser('~')), 'ElecRoomSCADA')
        if not os.path.exists(appdata_dir):
            os.makedirs(appdata_dir, exist_ok=True)
        self.config_path = os.path.join(appdata_dir, 'config.ini')
        
        self.config = configparser.ConfigParser()
        self.init_ui()
        self.load_settings()

    def init_ui(self):
        layout = QVBoxLayout()
        
        # 1. 에어컨 자동 제어 설정 그룹 박스
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

        # 2. 설정 통합 저장 버튼
        btn_save = QPushButton("💾 설정 통합 저장")
        btn_save.setStyleSheet("font-weight: bold; background-color: #4CAF50; color: white; padding: 10px; margin-top: 5px;")
        btn_save.clicked.connect(self.save_settings)
        layout.addWidget(btn_save)

       

        # 4. 에어컨 수동 원격 제어 그룹 박스
        self.group_manual = QGroupBox("에어컨 수동 원격 제어 (즉시 동작)")
        manual_layout = QVBoxLayout() 

        row1_layout = QHBoxLayout()
        btn_on_1 = QPushButton("1호기 켜기")
        btn_on_1.setStyleSheet("background-color: #3498db; color: white; padding: 8px;")
        btn_on_1.clicked.connect(lambda: self.trigger_manual("ON_1"))

        btn_off_1 = QPushButton("1호기 끄기")
        btn_off_1.setStyleSheet("background-color: #e74c3c; color: white; padding: 8px;")
        btn_off_1.clicked.connect(lambda: self.trigger_manual("OFF_1"))
        row1_layout.addWidget(btn_on_1)
        row1_layout.addWidget(btn_off_1)

        row2_layout = QHBoxLayout()
        btn_on_2 = QPushButton("2호기 켜기")
        btn_on_2.setStyleSheet("background-color: #9b59b6; color: white; padding: 8px;")
        btn_on_2.clicked.connect(lambda: self.trigger_manual("ON_2"))

        btn_off_2 = QPushButton("2호기 끄기")
        btn_off_2.setStyleSheet("background-color: #e74c3c; color: white; padding: 8px;")
        btn_off_2.clicked.connect(lambda: self.trigger_manual("OFF_2"))
        row2_layout.addWidget(btn_on_2)
        row2_layout.addWidget(btn_off_2)

        btn_off_all = QPushButton("전체 끄기")
        btn_off_all.setStyleSheet("background-color: #e74c3c; color: white; padding: 8px; font-weight: bold;")
        btn_off_all.clicked.connect(lambda: self.trigger_manual("OFF_ALL"))
        
        manual_layout.addLayout(row1_layout)
        manual_layout.addLayout(row2_layout)
        manual_layout.addWidget(btn_off_all)
        
        self.group_manual.setLayout(manual_layout)
        layout.addWidget(self.group_manual)

         # 3. 🌟 [위치 변경됨] 모드 변경 버튼을 설정 저장 버튼 아래로 이동
        self.btn_mode_toggle = QPushButton()
        self.btn_mode_toggle.clicked.connect(self.toggle_mode)
        layout.addWidget(self.btn_mode_toggle)
        
        self.setLayout(layout)
        self.update_mode_ui()

    def add_row(self, layout, label_text, widget):
        row = QHBoxLayout()
        row.addWidget(QLabel(label_text))
        row.addWidget(widget)
        layout.addLayout(row)

    def toggle_mode(self):
        ac_manager.is_auto = not ac_manager.is_auto
        self.update_mode_ui()

    def update_mode_ui(self):
        if ac_manager.is_auto:
            self.btn_mode_toggle.setText("현재 모드: 🔄 자동 (수동 조작하려면 여기를 클릭)")
            self.btn_mode_toggle.setStyleSheet("background-color: #2ecc71; color: white; padding: 10px; font-weight: bold;")
            self.group_manual.setEnabled(False)
        else:
            self.btn_mode_toggle.setText("현재 모드: ✋ 수동 (자동으로 복귀하려면 여기를 클릭)")
            self.btn_mode_toggle.setStyleSheet("background-color: #e67e22; color: white; padding: 10px; font-weight: bold;")
            self.group_manual.setEnabled(True)

    def showEvent(self, event):
        ac_manager.is_auto = True
        self.update_mode_ui()
        super().showEvent(event)

    def closeEvent(self, event):
        ac_manager.is_auto = True
        super().closeEvent(event)

    def accept(self):
        ac_manager.is_auto = True
        super().accept()

    def reject(self):
        ac_manager.is_auto = True
        super().reject()

    def load_settings(self):
        """config.ini 파일에서 설정값을 불러오고, 없으면 기본값을 세팅합니다."""
        start1 = 32.0
        start2 = 33.0
        stop_temp = 29.0
        cold_temp = 25.0
        max_hours = 3.0

        if os.path.exists(self.config_path):
            self.config.read(self.config_path, encoding='utf-8')
            if 'AC_SETTINGS' in self.config:
                sec = self.config['AC_SETTINGS']
                start1 = sec.getfloat('START_TEMP_1', sec.getfloat('start_temp_1', 32.0))
                start2 = sec.getfloat('START_TEMP_2', sec.getfloat('start_temp_2', 33.0))
                stop_temp = sec.getfloat('STOP_TEMP', sec.getfloat('stop_temp', 29.0))
                cold_temp = sec.getfloat('COLD_WIND_TEMP', sec.getfloat('cold_wind_temp', 25.0))
                max_hours = sec.getfloat('MAX_RUN_HOURS', sec.getfloat('max_run_hours', 3.0))

        self.spin_start1.setValue(start1)
        self.spin_start2.setValue(start2)
        self.spin_stop.setValue(stop_temp)
        self.spin_cold.setValue(cold_temp)
        self.spin_hours.setValue(max_hours)
            
    def save_settings(self):
        if not (self.spin_stop.value() < self.spin_start1.value() < self.spin_start2.value()):
            QMessageBox.warning(
                self, 
                "설정 오류", 
                "온도 설정이 잘못되었습니다!\n반드시 [정지 온도] < [1차 기동 온도] < [2차 기동 온도] 순서로 점점 높게 설정해야 합니다."
            )
            return

        if 'AC_SETTINGS' not in self.config:
            self.config['AC_SETTINGS'] = {}
        self.config['AC_SETTINGS']['START_TEMP_1'] = str(self.spin_start1.value())
        self.config['AC_SETTINGS']['START_TEMP_2'] = str(self.spin_start2.value())
        self.config['AC_SETTINGS']['STOP_TEMP'] = str(self.spin_stop.value())
        self.config['AC_SETTINGS']['COLD_WIND_TEMP'] = str(self.spin_cold.value())
        self.config['AC_SETTINGS']['MAX_RUN_HOURS'] = str(self.spin_hours.value())

        try:
            with open(self.config_path, 'w', encoding='utf-8') as f:
                self.config.write(f)
        except Exception as e:
            QMessageBox.critical(self, "저장 실패", f"설정 파일을 저장하는 중 오류가 발생했습니다.\n{e}")
            return
        
        ac_manager.load_settings()

        QMessageBox.information(
            self, 
            "저장 완료", 
            "에어컨 타이머 설정이 파이썬에 반영되었습니다."
        )
        self.accept()

    def trigger_manual(self, action):
        ac_manager.force_manual_control(action)  
        action_names = {"ON_1": "1호기 켜기", "ON_2": "2호기 켜기", "OFF_1": "1호기 끄기", "OFF_2": "2호기 끄기", "OFF_ALL": "전체 에어컨 끄기"}
        QMessageBox.information(self, "수동 제어", f"[{action_names[action]}] 명령이 전송되었습니다.\n자동 타이머가 초기화됩니다.")