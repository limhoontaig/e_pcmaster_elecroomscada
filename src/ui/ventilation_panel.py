# src/ui/ventilation_panel.py
from PyQt5.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QGridLayout, 
                             QLabel, QGroupBox, QPushButton, QFrame, QSizePolicy)
from PyQt5.QtCore import Qt
from PyQt5.QtGui import QCursor

# 분리해둔 FanGraphicWidget 임포트
from src.ui.fan_graphic import FanGraphicWidget

class VentilationPanel(QFrame):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.parent_dashboard = parent
        self.setStyleSheet("QFrame { background-color: #111111; border: 1px solid #333; }")
        self.init_ui()

    def init_ui(self):
        layout = QVBoxLayout(self)
        
        lbl_title = QLabel("<h3 style='color:#f39c12; margin:0;'>💨 환기설비 (SF/EF) 현황 및 제어</h3>")
        lbl_title.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Maximum)
        lbl_title.setAlignment(Qt.AlignCenter)
        if hasattr(self.parent_dashboard, "open_ventilation_settings_dialog"):
            lbl_title.mouseDoubleClickEvent = self.parent_dashboard.open_ventilation_settings_dialog
        layout.addWidget(lbl_title)

        equip_layout = QHBoxLayout()
        self.sf_graphic, sf_ctrl = self.create_fan_control_unit("급기휀 (SF)", "SF")
        equip_layout.addLayout(sf_ctrl)
        
        self.ef_graphic, ef_ctrl = self.create_fan_control_unit("배기휀 (EF)", "EF")
        equip_layout.addLayout(ef_ctrl)

        layout.addLayout(equip_layout)

    def create_fan_control_unit(self, title, prefix):
        vbox = QVBoxLayout()
        group = QGroupBox(title)
        group.setStyleSheet("QGroupBox { font-size: 16px; font-weight: bold; border: 1px solid #555; margin-top: 10px;} QGroupBox::title { subcontrol-origin: margin; left: 10px; }")
        glayout = QVBoxLayout(group)
        glayout.setSpacing(12) 

        top_fan_layout = QHBoxLayout()
        top_fan_layout.setSpacing(8)

        fan_graphic = FanGraphicWidget(fan_type="VENT")
        top_fan_layout.addWidget(fan_graphic, 1)

        temp_box = QFrame()
        temp_box.setStyleSheet("background-color: #080d14; border: 1px solid #2c3e50; border-radius: 6px;")
        temp_layout = QVBoxLayout(temp_box)
        temp_layout.setContentsMargins(6, 8, 6, 8)
        temp_layout.setSpacing(2)

        is_sf = (prefix == "SF")
        temp_name = "외기 온도" if is_sf else "실내 온도"
        temp_color = "#00e5ff" if is_sf else "#2ecc71"

        lbl_t_title = QLabel(f"<b>{temp_name}</b>")
        lbl_t_title.setAlignment(Qt.AlignCenter)
        lbl_t_title.setStyleSheet("color: #95a5a6; font-size: 13px; border: none;")

        lbl_t_val = QLabel("--.- ℃")
        lbl_t_val.setAlignment(Qt.AlignCenter)
        lbl_t_val.setStyleSheet(f"""
            QLabel {{
                color: {temp_color};
                font-family: 'Consolas', '맑은 고딕', sans-serif;
                font-size: 26px;
                font-weight: bold;
                border: none;
            }}
        """)
        
        # 부모 대시보드에 온도 라벨 참조 연결
        setattr(self.parent_dashboard, f"lbl_{prefix.lower()}_temp", lbl_t_val)

        temp_layout.addWidget(lbl_t_title)
        temp_layout.addWidget(lbl_t_val)
        top_fan_layout.addWidget(temp_box, 1)

        glayout.addLayout(top_fan_layout, 1)

        lamp_layout = QHBoxLayout()
        
        run_lamp = QPushButton("정지중")
        run_lamp.setCursor(QCursor(Qt.PointingHandCursor))
        run_lamp.setFixedHeight(40)
        run_lamp.setStyleSheet("background-color: #555; color: white; padding: 5px; font-weight: bold; border-radius: 3px; border: 1px solid #222;")
        run_lamp.clicked.connect(lambda: self.parent_dashboard.on_system_stop_clicked(prefix))
        
        trip_lamp = QPushButton("정상")
        trip_lamp.setCursor(QCursor(Qt.PointingHandCursor))
        trip_lamp.setFixedHeight(40)
        trip_lamp.setStyleSheet("background-color: #27ae60; color: white; padding: 5px; font-weight: bold; border-radius: 3px; border: 1px solid #222;")
        trip_lamp.clicked.connect(lambda: self.parent_dashboard.on_thermal_reset_clicked(prefix))
        
        setattr(self.parent_dashboard, f"lbl_{prefix}_run", run_lamp)
        setattr(self.parent_dashboard, f"lbl_{prefix}_trip", trip_lamp)
        
        lamp_layout.addWidget(run_lamp)
        lamp_layout.addWidget(trip_lamp)
        glayout.addLayout(lamp_layout, 0)

        ctrl_lbl = QLabel("<b>[제어 스위치]</b>")
        ctrl_lbl.setFixedHeight(40)
        ctrl_lbl.setAlignment(Qt.AlignCenter)
        glayout.addWidget(ctrl_lbl)
        
        btn_layout = QGridLayout()
        btn_layout.setHorizontalSpacing(8)
        btn_layout.setVerticalSpacing(8)
        
        btn_remote = self.parent_dashboard.create_momentary_button("방재실", f"{prefix}_op_room_start")
        btn_auto = self.parent_dashboard.create_momentary_button("현장 자동", f"{prefix}_local_auto_start")
        btn_manual = self.parent_dashboard.create_momentary_button("현장 수동", f"{prefix}_local_manual_start")
        btn_stop = self.parent_dashboard.create_momentary_button("정   지", f"{prefix}_stop", color_type="danger")

        btn_manual_run = QPushButton("수동 기동")
        btn_manual_run.setCheckable(True)
        
        btn_remote.setFixedHeight(40)
        btn_auto.setFixedHeight(40)
        btn_manual.setFixedHeight(40)
        btn_stop.setFixedHeight(40)
        btn_manual_run.setFixedHeight(40)

        btn_manual_run.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        btn_manual_run.setStyleSheet(self.parent_dashboard.get_toggle_style(False))
        btn_manual_run.clicked.connect(lambda checked, p=prefix: self.parent_dashboard.on_manual_run_toggled(p, checked))

        btn_layout.addWidget(btn_remote, 0, 0)
        btn_layout.addWidget(btn_auto, 0, 1)
        btn_layout.addWidget(btn_manual, 0, 2)
        
        btn_layout.addWidget(btn_stop, 1, 0, 1, 2) 
        btn_layout.addWidget(btn_manual_run, 1, 2) 

        setattr(self.parent_dashboard, f"btn_{prefix}_remote", btn_remote)
        setattr(self.parent_dashboard, f"btn_{prefix}_auto", btn_auto)
        setattr(self.parent_dashboard, f"btn_{prefix}_manual", btn_manual)
        setattr(self.parent_dashboard, f"btn_{prefix}_stop", btn_stop)
        setattr(self.parent_dashboard, f"btn_{prefix}_manual_run", btn_manual_run) 
        
        glayout.addLayout(btn_layout, 0)
        vbox.addWidget(group)
        
        return fan_graphic, vbox