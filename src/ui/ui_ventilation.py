# ui_ventilation.py
import os
import sys
import configparser
from PyQt5.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout, QGroupBox, QGridLayout,
                             QLabel, QPushButton, QDoubleSpinBox, QMessageBox)
from src import pcmaster_worker

class VentilationSettingsDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("💨 환기설비(급/배기) 외기 연동 스마트 제어 설정")
        self.setFixedSize(400, 480)
        
        appdata_dir = os.path.join(os.environ.get('APPDATA', os.path.expanduser('~')), 'ElecRoomSCADA')
        if not os.path.exists(appdata_dir):
            os.makedirs(appdata_dir, exist_ok=True)
        self.config_path = os.path.join(appdata_dir, 'config.ini')
        
        self.config = configparser.ConfigParser()
        self.init_ui()
        self.load_settings()

    def init_ui(self):
        layout = QVBoxLayout()
        
        grp_winter = QGroupBox("❄️ 겨울철/환절기 (외기 16℃ 미만)")
        lyt_winter = QVBoxLayout()
        self.w_on, self.w_off = self.create_spinbox_pair(lyt_winter, 28.0, 25.0)
        grp_winter.setLayout(lyt_winter)
        layout.addWidget(grp_winter)

        grp_spring = QGroupBox("🍃 봄/가을철 (외기 16℃ ~ 25℃ 미만)")
        lyt_spring = QVBoxLayout()
        self.sp_on, self.sp_off = self.create_spinbox_pair(lyt_spring, 30.0, 27.0)
        grp_spring.setLayout(lyt_spring)
        layout.addWidget(grp_spring)

        grp_summer = QGroupBox("☀️ 여름철 (외기 25℃ 이상)")
        lyt_summer = QVBoxLayout()
        self.su_on, self.su_off = self.create_spinbox_pair(lyt_summer, 30.0, 28.0)
        grp_summer.setLayout(lyt_summer)
        layout.addWidget(grp_summer)

        grp_common = QGroupBox("⚙️ 공통 보호 (급기휀 외기 연동)")
        lyt_common = QGridLayout()

        lyt_common.addWidget(QLabel("급기 휀 강제중지 외기온도 (℃) [D908]:"), 0, 0)
        self.supply_stop = QDoubleSpinBox()
        self.supply_stop.setRange(10.0, 40.0)
        self.supply_stop.setSingleStep(0.5)
        lyt_common.addWidget(self.supply_stop, 0, 1)

        lyt_common.addWidget(QLabel("급기 휀 가동재개 외기온도 (℃) [D909]:"), 1, 0)
        self.supply_start = QDoubleSpinBox()
        self.supply_start.setRange(10.0, 40.0)
        self.supply_start.setSingleStep(0.5)
        lyt_common.addWidget(self.supply_start, 1, 1)

        grp_common.setLayout(lyt_common)
        layout.addWidget(grp_common)

        btn_save = QPushButton("💾 설정 저장 및 제어 로직 반영")
        btn_save.setStyleSheet("font-weight: bold; background-color: #4CAF50; color: white; padding: 10px; margin-top: 5px;")
        btn_save.clicked.connect(self.save_settings)
        layout.addWidget(btn_save)

        self.setLayout(layout)

    def create_spinbox_pair(self, layout, default_on, default_off):
        row1 = QHBoxLayout()
        row1.addWidget(QLabel("배기 휀 기동 실내온도 (℃):"))
        spin_on = QDoubleSpinBox(); spin_on.setRange(20.0, 50.0); spin_on.setSingleStep(0.5)
        row1.addWidget(spin_on)
        
        row2 = QHBoxLayout()
        row2.addWidget(QLabel("배기 휀 정지 실내온도 (℃):"))
        spin_off = QDoubleSpinBox(); spin_off.setRange(15.0, 45.0); spin_off.setSingleStep(0.5)
        row2.addWidget(spin_off)
        
        layout.addLayout(row1)
        layout.addLayout(row2)
        return spin_on, spin_off

    def load_settings(self):
        if os.path.exists(self.config_path):
            self.config.read(self.config_path, encoding='utf-8')
            if 'VENT_SETTINGS' in self.config:
                sec = self.config['VENT_SETTINGS']
                self.w_on.setValue(sec.getfloat('winter_on', 28.0))
                self.w_off.setValue(sec.getfloat('winter_off', 25.0))
                self.sp_on.setValue(sec.getfloat('spring_on', 30.0))
                self.sp_off.setValue(sec.getfloat('spring_off', 27.0))
                self.su_on.setValue(sec.getfloat('summer_on', 30.0))
                self.su_off.setValue(sec.getfloat('summer_off', 28.0))
                self.supply_stop.setValue(sec.getfloat('supply_stop', 25.0))
                self.supply_start.setValue(sec.getfloat('supply_start', 23.0))
                self.update_worker()
                return

        self.w_on.setValue(28.0); self.w_off.setValue(25.0)
        self.sp_on.setValue(30.0); self.sp_off.setValue(27.0)
        self.su_on.setValue(30.0); self.su_off.setValue(28.0)
        self.supply_stop.setValue(25.0)
        self.supply_start.setValue(23.0)
        self.update_worker()

    def save_settings(self):
        if (self.w_off.value() >= self.w_on.value() or 
            self.sp_off.value() >= self.sp_on.value() or 
            self.su_off.value() >= self.su_on.value()):
            QMessageBox.warning(self, "설정 오류", "모든 구간에서 '정지 온도'는 '기동 온도'보다 낮아야 합니다!")
            return

        if self.supply_start.value() >= self.supply_stop.value():
            QMessageBox.warning(self, "설정 오류", "급기팬 '강제중지' 온도는 '가동재개' 온도보다 높아야 합니다!")
            return

        if not self.config.has_section('VENT_SETTINGS'):
            self.config.add_section('VENT_SETTINGS')
            
        self.config.set('VENT_SETTINGS', 'winter_on', str(self.w_on.value()))
        self.config.set('VENT_SETTINGS', 'winter_off', str(self.w_off.value()))
        self.config.set('VENT_SETTINGS', 'spring_on', str(self.sp_on.value()))
        self.config.set('VENT_SETTINGS', 'spring_off', str(self.sp_off.value()))
        self.config.set('VENT_SETTINGS', 'summer_on', str(self.su_on.value()))
        self.config.set('VENT_SETTINGS', 'summer_off', str(self.su_off.value()))
        self.config.set('VENT_SETTINGS', 'supply_stop', str(self.supply_stop.value()))
        self.config.set('VENT_SETTINGS', 'supply_start', str(self.supply_start.value()))

        try:
            with open(self.config_path, 'w', encoding='utf-8') as f:
                self.config.write(f)
        except Exception as e:
            QMessageBox.critical(self, "저장 실패", f"config.ini 파일에 쓰는 중 오류가 발생했습니다.\n{e}")
            return

        self.update_worker()
        
        QMessageBox.information(self, "저장 완료", "외기 온도 연동 스마트 제어 설정이 저장되었습니다.\n(config.ini 파일 및 로직 업데이트 완료)")
        self.accept()

    def update_worker(self):
        pcmaster_worker.vent_settings = {
            'w_on': self.w_on.value(), 'w_off': self.w_off.value(),
            'sp_on': self.sp_on.value(), 'sp_off': self.sp_off.value(),
            'su_on': self.su_on.value(), 'su_off': self.su_off.value(),
            'supply_stop': self.supply_stop.value(),
            'supply_start': self.supply_start.value()
        }