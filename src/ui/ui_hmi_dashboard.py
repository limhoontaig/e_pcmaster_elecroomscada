# ui_hmi_dashboard.py
from PyQt5.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QGridLayout, 
                             QLabel, QGroupBox, QPushButton, QFrame, QSplitter, 
                             QSizePolicy, QMessageBox)
from PyQt5.QtCore import Qt, QTimer
from PyQt5.QtGui import QFont, QPainter, QColor, QPen, QBrush, QCursor

from src import pcmaster_worker
from src.tr_controller import TRFanSettingsDialog
from src.ui.ui_ventilation import VentilationSettingsDialog
from src.ui.ui_ac_settings import ACSettingsDialog


# ==============================================================================
# 애니메이션 모터 클래스
# ==============================================================================
class FanGraphicWidget(QWidget):
    def __init__(self, parent=None, fan_type="TR"):
        super().__init__(parent)
        self.setMinimumSize(120, 110)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding) 
        self.is_running = False
        self.angle = 0
        self.fan_type = fan_type
        
        self.timer = QTimer(self)
        self.timer.timeout.connect(self.update_animation)

    def set_fan_state(self, state):
        self.is_running = state
        if self.is_running:
            self.timer.start(150)
        else:
            self.timer.stop()
        self.update()

    def update_animation(self):
        self.angle = (self.angle + 20) % 360
        self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        w, h = self.width(), self.height()

        if self.fan_type == "TR":
            painter.setBrush(QBrush(QColor("#444444"))); painter.setPen(Qt.NoPen)
            painter.drawRect(10, 40, w - 20, 10); painter.drawRect(10, h - 20, w - 20, 10)
            coil_w = (w - 40) / 3; coil_h = h - 70
            painter.setBrush(QBrush(QColor("#900000"))); painter.setPen(QPen(QColor("#111111"), 2))
            gap = 5; start_x = 10 + gap
            for i in range(3):
                painter.drawRoundedRect(int(start_x + (coil_w + gap)*i), 50, int(coil_w), int(coil_h), 4, 4)
            fan_cy = 20
        else:
            painter.setBrush(QBrush(QColor("#7f8c8d"))); painter.setPen(QPen(QColor("#2c3e50"), 3))
            painter.drawEllipse(int(w/2 - 45), int(h/2 - 45), 90, 90)
            fan_cy = h / 2

        fan_cx = w / 2
        fan_radius = 16 if self.fan_type == "TR" else 40
        
        if self.fan_type == "TR":
            painter.setBrush(QBrush(QColor("#111111"))); painter.setPen(QPen(QColor("#7f8c8d"), 2))
            painter.drawEllipse(int(fan_cx - fan_radius), int(fan_cy - fan_radius), fan_radius*2, fan_radius*2)
        
        painter.translate(fan_cx, fan_cy)
        painter.rotate(self.angle) 
        
        painter.setBrush(QBrush(QColor("#3498db" if self.is_running else "#555555"))) 
        painter.setPen(Qt.NoPen)
        for _ in range(4): 
            painter.drawPie(int(-fan_radius*0.8), int(-fan_radius*0.8), int(fan_radius*1.6), int(fan_radius*1.6), 0 * 16, 40 * 16)
            painter.rotate(90)
        painter.resetTransform()


# ==============================================================================
# 메인 대시보드
# ==============================================================================
class HMIDashboardWidget(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setStyleSheet("background-color: #000000; color: #ffffff;")
        self.init_ui()

    def init_ui(self):
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(10, 5, 10, 5) 
        main_layout.setSpacing(5) 

        self.plc_addresses = {
            "tr_cooling_auto": 100,      
            "tr_cooling_start": 101,     
            "tr_manual_start_1": 102,    
            "tr_manual_start_2": 103,    
            "tr_manual_start_3": 104,    
            
            "EF_local_auto_start": 105,  
            "EF_local_manual_start": 106,
            "EF_local_manual_start_sw": 116, 
            "EF_op_room_start": 107,     
            "EF_stop": 108,              
            "EF_trip_reset": 109,        

            "SF_local_auto_start": 110,  
            "SF_local_manual_start": 111,
            "SF_local_manual_start_sw": 117, 
            "SF_op_room_start": 112,     
            "SF_stop": 113,              
            "SF_trip_reset": 114,        
        }

        # 👇 여기에 수동 모드 상태를 기록할 변수 두 줄을 추가합니다.
        self.is_ef_manual = False
        self.is_sf_manual = False
        
        top_layout = QHBoxLayout()
        top_layout.setContentsMargins(0, 0, 0, 0)
        title_label = QLabel("⚡ 전기실 통합 제어 대시보드 (환기/변압기)")
        title_label.setFixedHeight(30)
        title_label.setStyleSheet("font-size: 22px; font-weight: bold; color: #00FFCC;")
        top_layout.addWidget(title_label); top_layout.addStretch()

        # 👇 3개의 셋팅 버튼 생성 및 스타일 적용
        btn_style = """
            QPushButton { background-color: #34495e; color: white; font-weight: bold; padding: 5px 15px; border-radius: 4px; border: 1px solid #2c3e50; }
            QPushButton:hover { background-color: #2c3e50; border: 1px solid #1abc9c; }
        """
        btn_ac = QPushButton("❄️ 에어컨 세팅")
        btn_vent = QPushButton("💨 환기 세팅")
        btn_tr = QPushButton("⚡ 변압기 세팅")
        
        btn_ac.setStyleSheet(btn_style)
        btn_vent.setStyleSheet(btn_style)
        btn_tr.setStyleSheet(btn_style)
        
        # 버튼을 함수와 연결
        btn_ac.clicked.connect(self.open_ac_settings_dialog)
        btn_vent.clicked.connect(self.open_ventilation_settings_dialog)
        btn_tr.clicked.connect(self.open_tr_settings_dialog)
        
        top_layout.addWidget(btn_ac)
        top_layout.addWidget(btn_vent)
        top_layout.addWidget(btn_tr)

        main_layout.addLayout(top_layout)

        mid_layout = QHBoxLayout()
        mid_layout.setContentsMargins(0, 5, 0, 5)
        
        vent_panel = self.create_ventilation_panel()
        tr_panel = self.create_transformer_panel()
        
        vent_panel.setSizePolicy(QSizePolicy.Ignored, QSizePolicy.Preferred)
        tr_panel.setSizePolicy(QSizePolicy.Ignored, QSizePolicy.Preferred)
        mid_layout.addWidget(vent_panel, 1)
        mid_layout.addWidget(tr_panel, 1)

        main_layout.addLayout(mid_layout, 2) 

        data_frame = QFrame()
        data_frame.setStyleSheet("background-color: #0a0a0a; border: 2px solid #444;")
        grid = QGridLayout(data_frame)
        grid.setSpacing(2)
        grid.setContentsMargins(5, 5, 5, 5)

        headers = ["설비 구분", "운전 전압 (V)", "운전 전류 (A)", "TR별 부하 (kW)", "부하율 (%)", "총 부하( kW )", "운전 온도 (℃)", "1분 최대온도 (℃)"]
        for col, h_text in enumerate(headers):
            lbl = QLabel(h_text); lbl.setAlignment(Qt.AlignCenter)
            lbl.setStyleSheet("background-color: #222; font-weight: bold; padding: 5px; border: 1px solid #555;")
            grid.addWidget(lbl, 0, col)

        self.data_labels = {}
        rows_config = [("TR-1 (1,000kVA)", "1", "Tr1"), ("TR-2 (1,250kVA)", "2", "Tr2"), ("TR-3 (1,250kVA)", "3", "Tr3")]
        
        keys = ["v", "a", "kw", "load", "temp", "max_temp"]
        db_keys = ["V_R_S", "A_R", "P_kW", "load", "Temp", "max_temp"] 
        colors = ["#3498db", "#f1c40f", "#e67e22", "#e74c3c", "#2ecc71", "#e74c3c"]

        for row_idx, (tr_name, tr_num, db_prefix) in enumerate(rows_config, start=1):
            r_lbl = QLabel(tr_name)
            r_lbl.setAlignment(Qt.AlignCenter)
            r_lbl.setStyleSheet("background-color: #1a1a1a; font-weight: bold; padding: 5px; border: 1px solid #444;")
            grid.addWidget(r_lbl, row_idx, 0)
            
            # 전압, 전류, 전력, 부하율 컬럼 배치
            for col_idx in range(4):
                key = keys[col_idx]
                db_key = db_keys[col_idx]
                color = colors[col_idx]
                label_key = f"{db_prefix}_{db_key}" if key != "load" else f"tr{tr_num}_load"
                lcd = self.create_lcd_label("0.0", color)
                self.data_labels[label_key] = lcd
                grid.addWidget(lcd, row_idx, col_idx + 1)

            # 🌟 운전전력 총합계 (TR-1 행 위치에 3개 행 병합으로 배치, 데이터 키는 'total_kw')
            if row_idx == 1:
                total_lcd = self.create_lcd_label("0.0", "#f39c12")
                self.data_labels["total_kw"] = total_lcd
                grid.addWidget(total_lcd, 1, 5, 3, 1)

            # 운전 온도 및 1분간 최대온도 배치
            temp_lcd = self.create_lcd_label("0.0", "#2ecc71")
            self.data_labels[f"{db_prefix}_Temp"] = temp_lcd
            grid.addWidget(temp_lcd, row_idx, 6)

            max_temp_lcd = self.create_lcd_label("0.0", "#e74c3c")
            self.data_labels[f"{db_prefix}_max_temp"] = max_temp_lcd
            grid.addWidget(max_temp_lcd, row_idx, 7)

        main_layout.addWidget(data_frame, 1)
        # 🌟 [신규 추가] 워커에서 쏜 시그널을 내 함수(sync_ui_from_plc)와 연결 (init_ui 맨 마지막 줄에 추가)
        pcmaster_worker.comm_signal.plc_initial_sync.connect(self.sync_ui_from_plc)

    def create_ventilation_panel(self):
        frame = QFrame()
        frame.setStyleSheet("QFrame { background-color: #111111; border: 1px solid #333; }")
        layout = QVBoxLayout(frame)
        
        lbl_title = QLabel("<h3 style='color:#f39c12; margin:0;'>💨 환기설비 (SF/EF) 현황 및 제어</h3>")
        lbl_title.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Maximum)
        lbl_title.setAlignment(Qt.AlignCenter)
        lbl_title.mouseDoubleClickEvent = self.open_ventilation_settings_dialog
        layout.addWidget(lbl_title)

        equip_layout = QHBoxLayout()
        self.sf_graphic, sf_ctrl = self.create_fan_control_unit("급기휀 (SF)", "SF")
        equip_layout.addLayout(sf_ctrl)
        
        self.ef_graphic, ef_ctrl = self.create_fan_control_unit("배기휀 (EF)", "EF")
        equip_layout.addLayout(ef_ctrl)

        layout.addLayout(equip_layout)
        return frame

    def create_fan_control_unit(self, title, prefix):
        vbox = QVBoxLayout()
        group = QGroupBox(title)
        group.setStyleSheet("QGroupBox { font-size: 16px; font-weight: bold; border: 1px solid #555; margin-top: 10px;} QGroupBox::title { subcontrol-origin: margin; left: 10px; }")
        glayout = QVBoxLayout(group)
        glayout.setSpacing(12) 

        top_fan_layout = QHBoxLayout()
        top_fan_layout.setSpacing(8)

        # 1. 휀 애니메이션
        fan_graphic = FanGraphicWidget(fan_type="VENT")
        top_fan_layout.addWidget(fan_graphic, 1)

        # 2. 대형 디지털 온도 표시 박스
        temp_box = QFrame()
        temp_box.setStyleSheet("background-color: #080d14; border: 1px solid #2c3e50; border-radius: 6px;")
        temp_layout = QVBoxLayout(temp_box)
        temp_layout.setContentsMargins(6, 8, 6, 8)
        temp_layout.setSpacing(2)

        # SF는 외기(하늘색), EF는 실내(에메랄드 녹색) 테마
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
        
        # 외부에서 갱신할 수 있도록 객체 변수로 저장 (self.lbl_sf_temp, self.lbl_ef_temp)
        setattr(self, f"lbl_{prefix.lower()}_temp", lbl_t_val)

        temp_layout.addWidget(lbl_t_title)
        temp_layout.addWidget(lbl_t_val)
        top_fan_layout.addWidget(temp_box, 1)

        glayout.addLayout(top_fan_layout, 1)

        lamp_layout = QHBoxLayout()
        
        run_lamp = QPushButton("정지중")
        run_lamp.setCursor(QCursor(Qt.PointingHandCursor))
        run_lamp.setFixedHeight(40)
        run_lamp.setStyleSheet("background-color: #555; color: white; padding: 5px; font-weight: bold; border-radius: 3px; border: 1px solid #222;")
        run_lamp.clicked.connect(lambda: self.on_system_stop_clicked(prefix))
        
        trip_lamp = QPushButton("정상")
        trip_lamp.setCursor(QCursor(Qt.PointingHandCursor))
        trip_lamp.setFixedHeight(40)
        trip_lamp.setStyleSheet("background-color: #27ae60; color: white; padding: 5px; font-weight: bold; border-radius: 3px; border: 1px solid #222;")
        trip_lamp.clicked.connect(lambda: self.on_thermal_reset_clicked(prefix))
        
        setattr(self, f"lbl_{prefix}_run", run_lamp)
        setattr(self, f"lbl_{prefix}_trip", trip_lamp)
        
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
        
        btn_layout.setColumnStretch(0, 1)
        btn_layout.setColumnStretch(1, 1)
        btn_layout.setColumnStretch(2, 1)
        
        btn_remote = self.create_momentary_button("방재실", f"{prefix}_op_room_start")
        btn_auto = self.create_momentary_button("현장 자동", f"{prefix}_local_auto_start")
        btn_manual = self.create_momentary_button("현장 수동", f"{prefix}_local_manual_start")
        btn_stop = self.create_momentary_button("정   지", f"{prefix}_stop", color_type="danger")

        btn_manual_run = QPushButton("수동 기동")
        btn_manual_run.setCheckable(True)
        
        btn_remote.setFixedHeight(40)
        btn_auto.setFixedHeight(40)
        btn_manual.setFixedHeight(40)
        btn_stop.setFixedHeight(40)
        btn_manual_run.setFixedHeight(40)

        btn_manual_run.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        btn_manual_run.setStyleSheet(self.get_toggle_style(False))
        btn_manual_run.clicked.connect(lambda checked, p=prefix: self.on_manual_run_toggled(p, checked))

        btn_layout.addWidget(btn_remote, 0, 0)
        btn_layout.addWidget(btn_auto, 0, 1)
        btn_layout.addWidget(btn_manual, 0, 2)
        
        btn_layout.addWidget(btn_stop, 1, 0, 1, 2) 
        btn_layout.addWidget(btn_manual_run, 1, 2) 

        setattr(self, f"btn_{prefix}_remote", btn_remote)
        setattr(self, f"btn_{prefix}_auto", btn_auto)
        setattr(self, f"btn_{prefix}_manual", btn_manual)
        setattr(self, f"btn_{prefix}_stop", btn_stop)
        setattr(self, f"btn_{prefix}_manual_run", btn_manual_run) 
        
        glayout.addLayout(btn_layout, 0)
        vbox.addWidget(group)
        
        return fan_graphic, vbox

    def get_toggle_style(self, is_on):
        if is_on:
            return "background-color: #d35400; color: yellow; font-weight: bold; border-radius: 4px; border: 2px solid white;"
        else:
            return "background-color: #34495e; color: #bdc3c7; font-weight: bold; border-radius: 4px; border: 2px solid transparent;"

    def on_manual_run_toggled(self, prefix, checked):
        # 👇 1. 접두어(EF/SF)에 맞는 수동 모드 상태 변수를 가져옵니다.
        is_manual = getattr(self, f"is_{prefix.lower()}_manual", False)
        
        btn = getattr(self, f"btn_{prefix}_manual_run")

        # 👇 2. 수동 모드가 아닌데 켜기(ON)를 시도할 경우 원천 차단합니다.
        if checked and not is_manual:
            QMessageBox.warning(self, "조작 불가", f"[{prefix}] 현장 수동 모드가 아닙니다.\n먼저 '현장 수동' 버튼을 눌러 모드를 전환하세요.")
            # 버튼 상태를 강제로 원상복구 (시그널 무한 루프 방지)
            btn.blockSignals(True) 
            btn.setChecked(False)
            btn.setStyleSheet(self.get_toggle_style(False))
            btn.blockSignals(False)
            return # 여기서 함수를 종료하여 통신 신호가 나가는 것을 막습니다.

        # 정상적인 경우 (수동 모드이거나, 끄는 동작일 때)
        btn.setText("수동 운전" if checked else "수동 정지")
        btn.setStyleSheet(self.get_toggle_style(checked))
        
        signal_name = f"{prefix}_local_manual_start_sw"
        addr = self.plc_addresses.get(signal_name)
        if addr is not None:
            self.safe_write_bit(addr, checked, f"{prefix} 수동 기동 토글")

    def on_system_stop_clicked(self, prefix):
        signal_name = f"{prefix}_stop"
        addr = self.plc_addresses.get(signal_name)
        if addr is not None:
            self.safe_write_bit(addr, True, f"{prefix} 강제 정지 펄스")

    def on_thermal_reset_clicked(self, prefix):
        lamp = getattr(self, f"lbl_{prefix}_trip")
        signal_name = f"{prefix}_trip_reset"
        addr = self.plc_addresses.get(signal_name)
        
        if "써멀" in lamp.text():
            if addr is not None:
                self.safe_write_bit(addr, True, f"{prefix} 트립 리셋 펄스")
            
            lamp.setText("정상")
            lamp.setStyleSheet("background-color: #27ae60; color: white; padding: 5px; font-weight: bold; border-radius: 3px; border: 1px solid #222;")
        else:
            lamp.setText("써멀 트립")
            lamp.setStyleSheet("background-color: #e74c3c; color: yellow; padding: 5px; font-weight: bold; border-radius: 3px; border: 2px solid red;")

    def create_momentary_button(self, text, signal_name, color_type="normal"):
        btn = QPushButton(text)
        if color_type == "danger":
            btn.setStyleSheet("""
                QPushButton { background-color: #c0392b; color: white; font-weight: bold; border-radius: 4px; border: 2px solid transparent; }
                QPushButton:pressed { background-color: #e74c3c; border: 2px solid white; }
            """)
        else:
            btn.setStyleSheet("""
                QPushButton { background-color: #2980b9; color: white; font-weight: bold; border-radius: 4px; border: 2px solid transparent; }
                QPushButton:pressed { background-color: #3498db; border: 2px solid white; }
            """)
        
        btn.clicked.connect(lambda: self.on_momentary_pressed(signal_name))
        return btn

    def on_momentary_pressed(self, signal_name):
        addr = self.plc_addresses.get(signal_name)
        if addr is not None:
            self.safe_write_bit(addr, True, f"{signal_name} 단일 펄스")

    # ==========================================================================
    # [우측] 변압기(TR) 패널 생성부 
    # ==========================================================================
    def create_transformer_panel(self):
        frame = QFrame()
        frame.setStyleSheet("QFrame { background-color: #111111; border: 1px solid #333; }")
        layout = QVBoxLayout(frame)
        
        lbl_title = QLabel("<h3 style='color:#3498db; margin:0;'>⚡ 변압기(TR) 현황 및 휀 제어</h3>")
        lbl_title.setAlignment(Qt.AlignCenter)
        lbl_title.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Maximum)
        lbl_title.mouseDoubleClickEvent = self.open_tr_settings_dialog
        layout.addWidget(lbl_title)

        # 1. TR 그래픽 및 가동상태 (TR1, TR2, TR3)
        tr_layout = QHBoxLayout()
        self.tr1_graphic, self.lbl_tr1_status = self.create_tr_panel("TR-1", tr_layout)
        self.tr2_graphic, self.lbl_tr2_status = self.create_tr_panel("TR-2", tr_layout)
        self.tr3_graphic, self.lbl_tr3_status = self.create_tr_panel("TR-3", tr_layout)
        layout.addLayout(tr_layout, 1) 

        # 2. 통합 제어 스위치 영역
        ctrl_lbl = QLabel("<b>[제어 스위치]</b>")
        ctrl_lbl.setFixedHeight(40)
        ctrl_lbl.setAlignment(Qt.AlignCenter)
        layout.addWidget(ctrl_lbl, 0)

        ctrl_layout = QGridLayout()
        ctrl_layout.setSpacing(8)
        ctrl_layout.setColumnStretch(0, 1)
        ctrl_layout.setColumnStretch(1, 1)
        ctrl_layout.setColumnStretch(2, 1)
        
        self.btn_master = QPushButton("전체 냉각설비 가동중")
        self.btn_master.setCheckable(True); self.btn_master.setChecked(True)
        self.btn_master.setStyleSheet(self.get_master_style(True))
        self.btn_master.setFixedHeight(40) # 환기설비와 통일
        self.btn_master.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        self.btn_master.clicked.connect(self.on_master_toggled)

        self.btn_auto = QPushButton("자동 운전")
        self.btn_auto.setCheckable(True); self.btn_auto.setChecked(True)
        self.btn_auto.setStyleSheet(self.get_auto_manual_style(True))
        self.btn_auto.setFixedHeight(40) # 환기설비와 통일
        self.btn_auto.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        self.btn_auto.clicked.connect(self.on_auto_manual_toggled)

        self.btn_tr1 = self.create_toggle_button("TR-1 수동 OFF")
        self.btn_tr2 = self.create_toggle_button("TR-2 수동 OFF")
        self.btn_tr3 = self.create_toggle_button("TR-3 수동 OFF")
        self.btn_tr1.setFixedHeight(40) # 환기설비와 통일
        self.btn_tr2.setFixedHeight(40)
        self.btn_tr3.setFixedHeight(40)

        # 1행: 마스터, 자동 버튼
        ctrl_layout.addWidget(self.btn_master, 0, 0, 1, 2)
        ctrl_layout.addWidget(self.btn_auto, 0, 2, 1, 1)
        
        # 2행: TR별 수동 버튼
        ctrl_layout.addWidget(self.btn_tr1, 1, 0)
        ctrl_layout.addWidget(self.btn_tr2, 1, 1)
        ctrl_layout.addWidget(self.btn_tr3, 1, 2)

        layout.addLayout(ctrl_layout, 0)

        self.btn_tr1.toggled.connect(lambda checked: self.update_tr_fan_status(1, checked))
        self.btn_tr2.toggled.connect(lambda checked: self.update_tr_fan_status(2, checked))
        self.btn_tr3.toggled.connect(lambda checked: self.update_tr_fan_status(3, checked))

        for btn in [self.btn_auto, self.btn_tr1, self.btn_tr2, self.btn_tr3]:
            sp = btn.sizePolicy()
            sp.setRetainSizeWhenHidden(True)
            btn.setSizePolicy(sp)

        self.set_individual_buttons_enabled(False) 
        
        return frame

    def create_tr_panel(self, title, parent_layout):
        group = QGroupBox(title)
        group.setStyleSheet("QGroupBox { border: 1px solid #555; margin-top: 10px; font-weight: bold; } QGroupBox::title { subcontrol-origin: margin; left: 10px; }")
        
        layout = QVBoxLayout(group)
        layout.setSpacing(12) 
        
        graphic_widget = FanGraphicWidget(fan_type="TR")
        layout.addWidget(graphic_widget, 1)

        status_lbl = QLabel("정지중")
        status_lbl.setAlignment(Qt.AlignCenter)
        status_lbl.setFixedHeight(40) 
        status_lbl.setStyleSheet("background-color: #555; color: white; padding: 5px; font-weight: bold;")
        layout.addWidget(status_lbl, 0)
        
        parent_layout.addWidget(group)
        return graphic_widget, status_lbl

    def get_master_style(self, is_on):
        if is_on:
            return "background-color: #27ae60; color: white; padding: 10px; font-weight: bold; border-radius: 5px; border: 2px solid white;"
        else:
            return "background-color: #7f8c8d; color: white; padding: 10px; font-weight: bold; border-radius: 5px; border: 2px solid transparent;"

    def get_auto_manual_style(self, is_auto):
        if is_auto:
            return "background-color: #2980b9; color: white; padding: 10px; font-weight: bold; border-radius: 5px; border: 2px solid white;"
        else:
            return "background-color: #d35400; color: white; padding: 10px; font-weight: bold; border-radius: 5px; border: 2px solid transparent;"

    def on_master_toggled(self):
        is_on = self.btn_master.isChecked()
        self.btn_master.setText("전체 냉각설비 가동중" if is_on else "❄️ 겨울철 냉각설비 정지")
        self.btn_master.setStyleSheet(self.get_master_style(is_on))
        
        self.safe_write_bit(101, not is_on, "냉각설비 마스터")

        for btn in [self.btn_auto, self.btn_tr1, self.btn_tr2, self.btn_tr3]:
            btn.setVisible(is_on)
            
        if not is_on:
            self.btn_auto.setChecked(True)
            self.btn_tr1.setChecked(False)
            self.btn_tr2.setChecked(False)
            self.btn_tr3.setChecked(False)
        else:
            self.btn_auto.setChecked(True)
            self.on_auto_manual_toggled()

    def on_auto_manual_toggled(self):
        is_auto = self.btn_auto.isChecked()
        self.btn_auto.setText("자동 운전" if is_auto else "수동 운전")
        self.btn_auto.setStyleSheet(self.get_auto_manual_style(is_auto))
        
        self.safe_write_bit(100, not is_auto, "TR 자동/수동 모드")

        if is_auto:
            self.btn_tr1.setChecked(False)
            self.btn_tr2.setChecked(False)
            self.btn_tr3.setChecked(False)
        self.set_individual_buttons_enabled(not is_auto)

    def set_individual_buttons_enabled(self, enabled):
        for btn in [self.btn_tr1, self.btn_tr2, self.btn_tr3]:
            btn.setEnabled(enabled)

    def create_toggle_button(self, text):
        btn = QPushButton(text)
        btn.setCheckable(True) 
        btn.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        
        btn.setStyleSheet("""
            QPushButton { background-color: #34495e; color: white; border: 2px solid transparent; font-weight: bold; }
            QPushButton:hover { background-color: #3d566e; }
            QPushButton:checked { background-color: #c0392b; color: yellow; border: 2px solid white; } 
            QPushButton:disabled { background-color: #222222; color: #555555; border: 2px solid #333333; }
        """)
        return btn

    def update_tr_fan_status(self, tr_idx, is_running):
        btn = getattr(self, f"btn_tr{tr_idx}")
        btn.setText(f"TR-{tr_idx} 수동 ON" if is_running else f"TR-{tr_idx} 수동 OFF")
        
        addr = 101 + tr_idx
        self.safe_write_bit(addr, is_running, f"TR-{tr_idx} 수동 조작")

    # --------------------------------------------------------------------------
    # 통신 피드백 수신부 
    # --------------------------------------------------------------------------
    def update_plc_status(self, coils):
        if len(coils) > 5:
            ef_auto   = coils[0] 
            ef_manual = coils[1] 
            ef_remote = coils[2] 
            ef_run    = coils[3] 
            ef_stop   = coils[4] 
            ef_trip   = coils[5]

            self.is_ef_manual = ef_manual 

            if not ef_manual:
                self.btn_EF_manual_run.setChecked(False)
                self.btn_EF_manual_run.setText("수동 정지")
                self.btn_EF_manual_run.setStyleSheet(self.get_toggle_style(False))

            self.ef_graphic.set_fan_state(ef_run)
            self.update_lamp_ui(self.lbl_EF_run, ef_run, "가동중", "정지중", "#3498db")
            self.update_lamp_ui(self.lbl_EF_trip, ef_trip, "써멀 트립", "정상", "#e74c3c")
            
            self.update_selector_btn(self.btn_EF_auto, ef_auto)
            self.update_selector_btn(self.btn_EF_manual, ef_manual)
            self.update_selector_btn(self.btn_EF_remote, ef_remote)
            self.update_selector_btn_stop(self.btn_EF_stop, ef_stop)

        if len(coils) > 11:
            sf_auto   = coils[6]  
            sf_manual = coils[7]  
            sf_remote = coils[8]  
            sf_run    = coils[9]  
            sf_stop   = coils[10] 
            sf_trip   = coils[11] 

            self.is_sf_manual = sf_manual

            if not sf_manual:
                self.btn_SF_manual_run.setChecked(False)
                self.btn_SF_manual_run.setText("수동 정지")
                self.btn_SF_manual_run.setStyleSheet(self.get_toggle_style(False))

            self.sf_graphic.set_fan_state(sf_run)
            self.update_lamp_ui(self.lbl_SF_run, sf_run, "가동중", "정지중", "#3498db")
            self.update_lamp_ui(self.lbl_SF_trip, sf_trip, "써멀 트립", "정상", "#e74c3c")
            
            self.update_selector_btn(self.btn_SF_auto, sf_auto)
            self.update_selector_btn(self.btn_SF_manual, sf_manual)
            self.update_selector_btn(self.btn_SF_remote, sf_remote)
            self.update_selector_btn_stop(self.btn_SF_stop, sf_stop)

        if len(coils) > 14:
            tr_status_list = [coils[12], coils[13], coils[14]] 
            for i, is_running in enumerate(tr_status_list, start=1):
                graphic = getattr(self, f"tr{i}_graphic")
                lbl = getattr(self, f"lbl_tr{i}_status")
                graphic.set_fan_state(is_running)
                lbl.setText("가동중" if is_running else "정지중")
                lbl.setStyleSheet(f"background-color: {'#3498db' if is_running else '#555'}; color: white; padding: 5px; font-weight: bold;")

    def update_plc_data(self, data):
        lower_labels = {k.lower(): v for k, v in self.data_labels.items()}
        
        # 데이터 일괄 갱신 (total_kw, 각 변압기 최대 온도 등 자동 매핑)
        for key, value in data.items():
            lower_key = key.lower()
            if lower_key in lower_labels:
                formatted_value = f"{value:.1f}" if isinstance(value, float) else str(value)
                lower_labels[lower_key].setText(formatted_value)
                
        # 각 변압기 용량별 부하율(%) 계산 및 갱신
        try:
            if 'Tr1_P_kW' in data and 'tr1_load' in lower_labels:
                lower_labels['tr1_load'].setText(f"{(float(data['Tr1_P_kW']) / 1000.0) * 100.0:.1f}")
            if 'Tr2_P_kW' in data and 'tr2_load' in lower_labels:
                lower_labels['tr2_load'].setText(f"{(float(data['Tr2_P_kW']) / 1250.0) * 100.0:.1f}")
            if 'Tr3_P_kW' in data and 'tr3_load' in lower_labels:
                lower_labels['tr3_load'].setText(f"{(float(data['Tr3_P_kW']) / 1250.0) * 100.0:.1f}")
        except Exception:
            pass

        # ======================================================================
        # 🌟 [추가] 3. 환기설비 SF(외기온도) / EF(실내온도) 라벨 실시간 갱신
        # ======================================================================
        if hasattr(self, 'lbl_sf_temp') and 'outdoor_temp' in data:
            self.lbl_sf_temp.setText(f"{float(data['outdoor_temp']):.1f} ℃")

        if hasattr(self, 'lbl_ef_temp') and 'indoor_temp' in data:
            self.lbl_ef_temp.setText(f"{float(data['indoor_temp']):.1f} ℃")

    def sync_ui_from_plc(self, m100_state, m101_state):
        """프로그램 시작 시 PLC의 M0100(자동/수동), M0101(마스터) 상태를 읽어와 화면에 동기화"""
        
        # 🌟 PLC 래더를 b접점으로 짰으므로, PLC 값이 0(False)일 때 UI는 켜짐(True) 상태가 됩니다.
        is_auto = not m100_state
        is_master_on = not m101_state

        # 1. 무한 루프 방지: UI 버튼 상태를 바꿀 때 클릭 이벤트(통신 송신)가 발생하지 않도록 신호 차단
        self.btn_auto.blockSignals(True)
        self.btn_master.blockSignals(True)

        # 2. 버튼 상태(체크 여부, 텍스트, 색상) 업데이트
        self.btn_auto.setChecked(is_auto)
        self.btn_auto.setText("자동 운전" if is_auto else "수동 운전")
        self.btn_auto.setStyleSheet(self.get_auto_manual_style(is_auto))

        self.btn_master.setChecked(is_master_on)
        self.btn_master.setText("전체 냉각설비 가동중" if is_master_on else "❄️ 겨울철 냉각설비 정지")
        self.btn_master.setStyleSheet(self.get_master_style(is_master_on))
        
        # 3. 하위 개별 TR 수동 버튼 활성화/비활성화 처리
        self.set_individual_buttons_enabled(not is_auto)
        if not is_master_on:
            for btn in [self.btn_auto, self.btn_tr1, self.btn_tr2, self.btn_tr3]:
                btn.setVisible(False)
        else:
            for btn in [self.btn_auto, self.btn_tr1, self.btn_tr2, self.btn_tr3]:
                btn.setVisible(True)

        # 4. 업데이트가 끝나면 다시 클릭 이벤트를 활성화하여 사용자가 조작할 수 있게 복구
        self.btn_auto.blockSignals(False)
        self.btn_master.blockSignals(False)

    # --------------------------------------------------------------------------
    # 버튼 색상 점등 처리기
    # --------------------------------------------------------------------------
    def update_selector_btn(self, btn, state):
        if state:
            btn.setStyleSheet("background-color: #c0392b; color: yellow; padding: 8px; font-weight: bold; border-radius: 4px; border: 2px solid white;")
        else:
            btn.setStyleSheet("background-color: #2980b9; color: white; padding: 8px; font-weight: bold; border-radius: 4px; border: 2px solid transparent;")

    def update_selector_btn_stop(self, btn, state):
        if state:
            btn.setStyleSheet("background-color: #e74c3c; color: yellow; padding: 8px; font-weight: bold; border-radius: 4px; border: 2px solid white;")
        else:
            btn.setStyleSheet("background-color: #2980b9; color: white; padding: 8px; font-weight: bold; border-radius: 4px; border: 2px solid transparent;")
    
    def update_lamp_ui(self, label, state, on_text, off_text, on_color):
        if state:
            label.setText(on_text)
            label.setStyleSheet(f"background-color: {on_color}; color: white; padding: 5px; font-weight: bold; border-radius: 3px; border: 1px solid #222;")
        else:
            label.setText(off_text)
            default_color = "#27ae60" if off_text == "정상" else "#555"
            label.setStyleSheet(f"background-color: {default_color}; color: white; padding: 5px; font-weight: bold; border-radius: 3px; border: 1px solid #222;")
    
    def create_lcd_label(self, init_text, color):
        lbl = QLabel(init_text); lbl.setAlignment(Qt.AlignCenter)
        lbl.setStyleSheet(f"QLabel {{ background-color: #001111; color: {color}; font-family: 'Consolas'; font-size: 20px; font-weight: bold; border: 1px inset #333; }}")
        return lbl

    # ==========================================================================
    # 🛡️ 통신 에러 방어막
    # ==========================================================================
    def safe_write_bit(self, addr, state, log_msg=""):
        # print(f"👉 [명령] {log_msg} (M0{addr:03d}) ➡️ {state}")
        try:
            pcmaster_worker.write_plc_bit(addr, state)
        except Exception as e:
            error_msg = f"장비와 통신할 수 없습니다.\n통신선 연결이나 포트 상태를 확인하세요.\n(상세 에러: {e})"
            # print(f"⚠️ [통신 에러 차단] {error_msg}")
            QMessageBox.warning(self, "통신 오류", error_msg)

    # ==========================================================================
    # 다이얼로그 호출 함수 추가
    # ==========================================================================
    def open_tr_settings_dialog(self, event):
        """TR 팬 온도 설정 다이얼로그 띄우기"""
        # 현재 화면에 표시된 온도나 설정된 온도를 읽어와서 다이얼로그 초기값으로 줄 수 있습니다.
        # 여기서는 기본값으로 띄웁니다.
        dialog = TRFanSettingsDialog(parent=self)
        dialog.exec_()

    def open_ventilation_settings_dialog(self, event):
        """환기설비(급/배기) 외기 연동 스마트 제어 설정 다이얼로그 띄우기"""
        dialog = VentilationSettingsDialog(parent=self)
        dialog.exec_()

    def open_ac_settings_dialog(self, *args):
        """에어컨 설정 다이얼로그 띄우기"""
        dialog = ACSettingsDialog(parent=self)
        dialog.exec_()