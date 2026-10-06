# tr_controller.py
import os
import sys
import configparser
from PyQt5.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout, QLabel, 
                             QDoubleSpinBox, QPushButton, QMessageBox, QGroupBox)

from src import pcmaster_worker 

class TRFanSettingsDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("변압기 개별 환기팬 온도 설정")
        self.setFixedSize(350, 380)

        appdata_dir = os.path.join(os.environ.get('APPDATA', os.path.expanduser('~')), 'ElecRoomSCADA')
        if not os.path.exists(appdata_dir):
            os.makedirs(appdata_dir, exist_ok=True)
        self.config_path = os.path.join(appdata_dir, 'config.ini')

        self.config = configparser.ConfigParser()
        self.load_settings()

        main_layout = QVBoxLayout()

        self.spin_tr1_on, self.spin_tr1_off = self.create_tr_group("TR1 (1호기)", self.tr1_on, self.tr1_off, main_layout)
        self.spin_tr2_on, self.spin_tr2_off = self.create_tr_group("TR2 (2호기)", self.tr2_on, self.tr2_off, main_layout)
        self.spin_tr3_on, self.spin_tr3_off = self.create_tr_group("TR3 (3호기)", self.tr3_on, self.tr3_off, main_layout)

        btn_layout = QHBoxLayout()
        self.btn_save = QPushButton("PLC에 일괄 적용")
        self.btn_cancel = QPushButton("취소")
        btn_layout.addWidget(self.btn_save)
        btn_layout.addWidget(self.btn_cancel)

        main_layout.addLayout(btn_layout)
        self.setLayout(main_layout)

        self.btn_save.clicked.connect(self.save_and_send_to_plc)
        self.btn_cancel.clicked.connect(self.reject)

    def load_settings(self):
        self.tr1_on, self.tr1_off = 55.0, 50.0
        self.tr2_on, self.tr2_off = 55.0, 50.0
        self.tr3_on, self.tr3_off = 55.0, 50.0

        if os.path.exists(self.config_path):
            self.config.read(self.config_path, encoding='utf-8')
            if 'TR_SETTINGS' in self.config:
                sec = self.config['TR_SETTINGS']
                self.tr1_on = sec.getfloat('tr1_on', 55.0)
                self.tr1_off = sec.getfloat('tr1_off', 50.0)
                self.tr2_on = sec.getfloat('tr2_on', 55.0)
                self.tr2_off = sec.getfloat('tr2_off', 50.0)
                self.tr3_on = sec.getfloat('tr3_on', 55.0)
                self.tr3_off = sec.getfloat('tr3_off', 50.0)
        self.update_worker()

    def update_worker(self):
        pcmaster_worker.pending_tr_fan_values = [
            int(self.tr1_on * 10),
            int(self.tr1_off * 10),
            int(self.tr2_on * 10),
            int(self.tr2_off * 10),
            int(self.tr3_on * 10),
            int(self.tr3_off * 10)
        ]

    def create_tr_group(self, title, current_on, current_off, parent_layout):
        group = QGroupBox(title)
        layout = QHBoxLayout()

        layout.addWidget(QLabel("기동(℃):"))
        spin_on = QDoubleSpinBox()
        spin_on.setRange(20.0, 80.0)
        spin_on.setSingleStep(0.5)
        spin_on.setValue(current_on)
        layout.addWidget(spin_on)

        layout.addWidget(QLabel("정지(℃):"))
        spin_off = QDoubleSpinBox()
        spin_off.setRange(15.0, 75.0)
        spin_off.setSingleStep(0.5)
        spin_off.setValue(current_off)
        layout.addWidget(spin_off)

        group.setLayout(layout)
        parent_layout.addWidget(group)
        
        return spin_on, spin_off

    def save_and_send_to_plc(self):
        tr1_on, tr1_off = self.spin_tr1_on.value(), self.spin_tr1_off.value()
        tr2_on, tr2_off = self.spin_tr2_on.value(), self.spin_tr2_off.value()
        tr3_on, tr3_off = self.spin_tr3_on.value(), self.spin_tr3_off.value()

        if tr1_off >= tr1_on or tr2_off >= tr2_on or tr3_off >= tr3_on:
            QMessageBox.warning(self, "설정 오류", "모든 변압기의 '정지 온도'는 '기동 온도'보다 낮아야 합니다!")
            return

        if 'TR_SETTINGS' not in self.config:
            self.config['TR_SETTINGS'] = {}
            
        sec = self.config['TR_SETTINGS']
        sec['tr1_on'] = str(tr1_on)
        sec['tr1_off'] = str(tr1_off)
        sec['tr2_on'] = str(tr2_on)
        sec['tr2_off'] = str(tr2_off)
        sec['tr3_on'] = str(tr3_on)
        sec['tr3_off'] = str(tr3_off)

        try:
            with open(self.config_path, 'w', encoding='utf-8') as f:
                self.config.write(f)
        except Exception as e:
            QMessageBox.critical(self, "저장 실패", f"변압기 설정 파일을 저장하는 중 오류가 발생했습니다.\n{e}")
            return

        plc_values = [
            int(tr1_on * 10), int(tr1_off * 10),
            int(tr2_on * 10), int(tr2_off * 10),
            int(tr3_on * 10), int(tr3_off * 10)
        ]

        pcmaster_worker.pending_tr_fan_values = plc_values

        QMessageBox.information(self, "적용 중", "설정값을 시스템에 저장하고 PLC로 전송합니다.")
        self.accept()