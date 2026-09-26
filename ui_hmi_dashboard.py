# ui_hmi_dashboard.py
from PyQt5.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QGridLayout, 
                             QLabel, QGroupBox, QPushButton, QFrame, QSplitter)
from PyQt5.QtCore import Qt, QTimer
from PyQt5.QtGui import QFont, QPainter, QColor, QPen, QBrush, QCursor

import pcmaster_worker

# ==============================================================================
# 애니메이션 모터 클래스 (변압기 팬 및 환기설비 팬 공용 사용)
# ==============================================================================
class FanGraphicWidget(QWidget):
    def __init__(self, parent=None, fan_type="TR"):
        super().__init__(parent)
        self.setMinimumSize(120, 150) 
        self.is_running = False
        self.angle = 0
        self.fan_type = fan_type
        
        self.timer = QTimer(self)
        self.timer.timeout.connect(self.update_animation)

    def set_fan_state(self, state):
        self.is_running = state
        if self.is_running:
            self.timer.start(30)
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

        self.plc_addresses = {
            # --- TR 변압기 냉각 (PLC FF 로직 - 누를때 토글) ---
            "tr_cooling_auto": 100,      # M00100
            "tr_cooling_start": 101,     # M00101
            "tr_manual_start_1": 102,    # M00102
            "tr_manual_start_2": 103,    # M00103
            "tr_manual_start_3": 104,    # M00104
            
            # --- 환기설비 EF 배기 (누를때 ON, PLC 자체 리셋) ---
            "EF_local_auto_start": 105,  # M00105
            "EF_local_manual_start": 106,# M00106 (selection)
            "EF_op_room_start": 107,     # M00107
            "EF_stop": 108,              # M00108
            "EF_trip_reset": 109,        # M00109

            # --- 환기설비 SF 급기 (누를때 ON, PLC 자체 리셋) ---
            "SF_local_auto_start": 110,  # M00110
            "SF_local_manual_start": 111,# M00111 (selection)
            "SF_op_room_start": 112,     # M00112
            "SF_stop": 113,              # M00113
            "SF_trip_reset": 114,        # M00114
        }
        
        # --- 상단 타이틀 ---
        top_layout = QHBoxLayout()
        title_label = QLabel("⚡ 전기실 통합 제어 대시보드 (환기/변압기)")
        title_label.setStyleSheet("font-size: 24px; font-weight: bold; color: #00FFCC;")
        top_layout.addWidget(title_label); top_layout.addStretch()
        main_layout.addLayout(top_layout)

        # --- 중단: 5:5 화면 강제 분할 ---
        mid_layout = QHBoxLayout()
        
        # [좌측] 환기설비 제어판
        vent_panel = self.create_ventilation_panel()
        mid_layout.addWidget(vent_panel, 1)

        # [우측] 변압기 제어판
        tr_panel = self.create_transformer_panel()
        mid_layout.addWidget(tr_panel, 1)

        main_layout.addLayout(mid_layout, 2) 

        # --- 하단: 실시간 데이터 표 ---
        data_frame = QFrame()
        data_frame.setStyleSheet("background-color: #0a0a0a; border: 2px solid #444;")
        grid = QGridLayout(data_frame)
        grid.setSpacing(2)

        headers = ["설비 구분", "운전 전압 (V)", "운전 전류 (A)", "운전 전력 (kW)", "부하율 (%)", "운전 온도 (℃)"]
        for col, h_text in enumerate(headers):
            lbl = QLabel(h_text); lbl.setAlignment(Qt.AlignCenter)
            lbl.setStyleSheet("background-color: #222; font-weight: bold; padding: 5px; border: 1px solid #555;")
            grid.addWidget(lbl, 0, col)

        self.data_labels = {}
        rows_config = [("TR-1 (1,000kVA)", "1"), ("TR-2 (1,250kVA)", "2"), ("TR-3 (1,250kVA)", "3")]
        keys = ["v", "a", "kw", "load", "temp"]
        colors = ["#3498db", "#f1c40f", "#e67e22", "#e74c3c", "#2ecc71"]

        for row_idx, (tr_name, tr_num) in enumerate(rows_config, start=1):
            r_lbl = QLabel(tr_name)
            r_lbl.setAlignment(Qt.AlignCenter)
            r_lbl.setStyleSheet("background-color: #1a1a1a; font-weight: bold; padding: 5px; border: 1px solid #444;")
            grid.addWidget(r_lbl, row_idx, 0)
            
            for col_idx, key in enumerate(keys):
                color = colors[col_idx]
                label_key = f"tr{tr_num}_{key}"
                lcd = self.create_lcd_label("0.0", color)
                self.data_labels[label_key] = lcd
                grid.addWidget(lcd, row_idx, col_idx + 1)

        main_layout.addWidget(data_frame, 1)

    # ==========================================================================
    # 환기설비 패널 
    # ==========================================================================
    def create_ventilation_panel(self):
        frame = QFrame()
        frame.setStyleSheet("background-color: #111111; border: 1px solid #333;")
        layout = QVBoxLayout(frame)
        layout.addWidget(QLabel("<h3 style='color:#f39c12; margin:0;'>💨 환기설비 (SF/EF) 현황 및 제어</h3>"))

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
        
        fan_graphic = FanGraphicWidget(fan_type="VENT")
        glayout.addWidget(fan_graphic)

        lamp_layout = QHBoxLayout()
        
        run_lamp = QPushButton("정지중")
        run_lamp.setCursor(QCursor(Qt.PointingHandCursor))
        run_lamp.setStyleSheet("background-color: #555; color: white; padding: 5px; font-weight: bold; border-radius: 3px; border: 1px solid #222;")
        run_lamp.clicked.connect(lambda: self.on_system_stop_clicked(prefix))
        
        trip_lamp = QPushButton("정상")
        trip_lamp.setCursor(QCursor(Qt.PointingHandCursor))
        trip_lamp.setStyleSheet("background-color: #27ae60; color: white; padding: 5px; font-weight: bold; border-radius: 3px; border: 1px solid #222;")
        trip_lamp.clicked.connect(lambda: self.on_thermal_reset_clicked(prefix))
        
        setattr(self, f"lbl_{prefix}_run", run_lamp)
        setattr(self, f"lbl_{prefix}_trip", trip_lamp)
        
        lamp_layout.addWidget(run_lamp)
        lamp_layout.addWidget(trip_lamp)
        glayout.addLayout(lamp_layout)

        glayout.addWidget(QLabel("<b>[제어 스위치]</b>"))
        btn_layout = QGridLayout()
        
        # 버튼 생성 호출
        btn_remote = self.create_momentary_button("방재실 원격", f"{prefix}_op_room_start")
        btn_auto = self.create_momentary_button("현장 자동", f"{prefix}_local_auto_start")
        btn_manual = self.create_momentary_button("현장 수동", f"{prefix}_local_manual_start")
        btn_stop = self.create_momentary_button("정 지", f"{prefix}_stop", color_type="danger")

        btn_layout.addWidget(btn_remote, 0, 0)
        btn_layout.addWidget(btn_auto, 0, 1)
        btn_layout.addWidget(btn_manual, 1, 0)
        btn_layout.addWidget(btn_stop, 1, 1)
        
        glayout.addLayout(btn_layout)
        vbox.addWidget(group)
        
        return fan_graphic, vbox

    # 💡 [핵심 변경 1] 운전/트립 램프 버튼 클릭 시에도 '1'만 쏘도록 수정
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
            print(f"⚠️ [테스트] {prefix} 강제 써멀 트립 발생!")
            lamp.setText("써멀 트립")
            lamp.setStyleSheet("background-color: #e74c3c; color: yellow; padding: 5px; font-weight: bold; border-radius: 3px; border: 2px solid red;")    # 💡 [핵심 변경 2] 버튼 이벤트 통합 (released 삭제, clicked 시 '1' 펄스 전송)
    
    def create_momentary_button(self, text, signal_name, color_type="normal"):
        btn = QPushButton(text)
        if color_type == "danger":
            btn.setStyleSheet("""
                QPushButton { background-color: #c0392b; color: white; padding: 8px; font-weight: bold; border-radius: 4px; }
                QPushButton:pressed { background-color: #e74c3c; border: 2px solid white; }
            """)
        else:
            btn.setStyleSheet("""
                QPushButton { background-color: #2980b9; color: white; padding: 8px; font-weight: bold; border-radius: 4px; }
                QPushButton:pressed { background-color: #3498db; border: 2px solid white; }
            """)
        
        # 마우스를 뗄 때(released) 0을 보내던 기존 코드를 삭제하고, 클릭 시 단일 전송
        btn.clicked.connect(lambda: self.on_momentary_pressed(signal_name))
        return btn

    def on_momentary_pressed(self, signal_name):
        addr = self.plc_addresses.get(signal_name)
        if addr is not None:
            self.safe_write_bit(addr, True, f"{signal_name} 단일 펄스")
        else:
            print(f"⚠️ 에러: {signal_name}에 매핑된 주소가 없습니다.")

    # ==========================================================================
    # [우측] 변압기(TR) 패널 생성부 
    # ==========================================================================
    def create_transformer_panel(self):
        frame = QFrame()
        frame.setStyleSheet("background-color: #111111; border: 1px solid #333;")
        layout = QVBoxLayout(frame)
        layout.addWidget(QLabel("<h3 style='color:#3498db; margin:0;'>⚡ 변압기(TR) 현황 및 휀 제어</h3>"))

        ctrl_layout = QHBoxLayout()
        
        self.btn_master = QPushButton("전체 냉각설비 가동중")
        self.btn_master.setCheckable(True); self.btn_master.setChecked(True)
        self.btn_master.setStyleSheet(self.get_master_style(True))
        self.btn_master.clicked.connect(self.on_master_toggled)
        ctrl_layout.addWidget(self.btn_master)

        self.sub_ctrl = QWidget()
        sub_layout = QHBoxLayout(self.sub_ctrl)
        sub_layout.setContentsMargins(0, 0, 0, 0)
        
        self.btn_auto = QPushButton("자동 운전")
        self.btn_auto.setCheckable(True); self.btn_auto.setChecked(True)
        self.btn_auto.setStyleSheet(self.get_auto_manual_style(True))
        self.btn_auto.clicked.connect(self.on_auto_manual_toggled)
        sub_layout.addWidget(self.btn_auto)

        self.btn_tr1 = self.create_toggle_button("TR-1 휀 OFF")
        self.btn_tr2 = self.create_toggle_button("TR-2 휀 OFF")
        self.btn_tr3 = self.create_toggle_button("TR-3 휀 OFF")
        
        sub_layout.addWidget(self.btn_tr1)
        sub_layout.addWidget(self.btn_tr2)
        sub_layout.addWidget(self.btn_tr3)
        
        self.set_individual_buttons_enabled(False) 
        
        ctrl_layout.addWidget(self.sub_ctrl)
        layout.addLayout(ctrl_layout)

        tr_layout = QHBoxLayout()
        self.tr1_graphic, self.lbl_tr1_status = self.create_tr_panel("TR-1", tr_layout)
        self.tr2_graphic, self.lbl_tr2_status = self.create_tr_panel("TR-2", tr_layout)
        self.tr3_graphic, self.lbl_tr3_status = self.create_tr_panel("TR-3", tr_layout)
        
        self.btn_tr1.toggled.connect(lambda checked: self.update_tr_fan_status(1, checked))
        self.btn_tr2.toggled.connect(lambda checked: self.update_tr_fan_status(2, checked))
        self.btn_tr3.toggled.connect(lambda checked: self.update_tr_fan_status(3, checked))

        layout.addLayout(tr_layout)
        return frame

    def create_tr_panel(self, title, parent_layout):
        group = QGroupBox(title)
        group.setStyleSheet("QGroupBox { border: 1px solid #555; margin-top: 10px; font-weight: bold; } QGroupBox::title { subcontrol-origin: margin; left: 10px; }")
        layout = QVBoxLayout(group)
        
        graphic_widget = FanGraphicWidget(fan_type="TR")
        status_lbl = QLabel("정지중")
        status_lbl.setAlignment(Qt.AlignCenter)
        status_lbl.setStyleSheet("background-color: #555; color: white; padding: 5px; font-weight: bold;")
        
        layout.addWidget(graphic_widget)
        layout.addWidget(status_lbl)
        parent_layout.addWidget(group)
        return graphic_widget, status_lbl

    def get_master_style(self, is_on):
        return "background-color: #27ae60; color: white; padding: 10px; font-weight: bold; border-radius: 5px;" if is_on else "background-color: #7f8c8d; color: white; padding: 10px; font-weight: bold; border-radius: 5px;"

    def get_auto_manual_style(self, is_auto):
        return "background-color: #2980b9; color: white; padding: 10px; font-weight: bold; border-radius: 5px;" if is_auto else "background-color: #d35400; color: white; padding: 10px; font-weight: bold; border-radius: 5px;"

    def on_master_toggled(self):
        is_on = self.btn_master.isChecked()
        self.btn_master.setText("전체 냉각설비 가동중" if is_on else "❄️ 겨울철 냉각설비 정지")
        self.btn_master.setStyleSheet(self.get_master_style(is_on))
        
        # 방어막 함수 적용
        self.safe_write_bit(101, is_on, "냉각설비 마스터")

        self.sub_ctrl.setVisible(is_on) 
        if not is_on:
            self.btn_auto.setChecked(True)
            self.btn_tr1.setChecked(False)
            self.btn_tr2.setChecked(False)
            self.btn_tr3.setChecked(False)

    def on_auto_manual_toggled(self):
        is_auto = self.btn_auto.isChecked()
        self.btn_auto.setText("자동 운전" if is_auto else "수동 운전")
        self.btn_auto.setStyleSheet(self.get_auto_manual_style(is_auto))
        
        # 방어막 함수 적용
        self.safe_write_bit(100, is_auto, "TR 자동/수동 모드")

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
        
        # 💡 [핵심 해결] 글자수가 변해도 버튼 크기가 줄어들지 않도록 최소 너비 140 고정
        btn.setMinimumWidth(100)
        from PyQt5.QtWidgets import QSizePolicy
        btn.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        
        btn.setStyleSheet("""
            QPushButton { background-color: #34495e; color: white; border: 2px solid #2c3e50; padding: 10px; border-radius: 5px; font-weight: bold; }
            QPushButton:hover { background-color: #3d566e; }
            QPushButton:checked { background-color: #c0392b; color: yellow; border: 2px solid #e74c3c; } 
            QPushButton:disabled { background-color: #222222; color: #555555; border: 1px solid #333333; }
        """)
        return btn

    def update_tr_fan_status(self, tr_idx, is_running):
        """사용자가 화면에서 수동 기동 버튼을 눌렀을 때 실행됩니다."""
        btn = getattr(self, f"btn_tr{tr_idx}")
        
        # 💡 [핵심 해결] 글자 길이를 비슷하게 맞춰서 시각적인 안정감 부여
        btn.setText(f"TR-{tr_idx} 수동 ON" if is_running else f"TR-{tr_idx} 수동 OFF")
        
        # 애니메이션은 건드리지 않고 오직 통신 명령만 전송합니다.
        addr = 101 + tr_idx # M00102, M00103, M00104
        self.safe_write_bit(addr, is_running, f"TR-{tr_idx} 수동 조작")

    # ==========================================================================
    # 📡 [신규 추가] PLC 피드백 수신 및 애니메이션 구동 전용 함수
    # ==========================================================================
    def update_plc_status(self, coils):
        """
        pcmaster_worker 에서 0.5초마다 읽어오는 M0200 ~ M0222 상태 리스트를 받아
        실제 램프 색상과 휀 애니메이션을 구동합니다.
        (coils[0]이 M0200, coils[12]가 M0212 에 해당)
        """
        # --- 1. 환기설비(SF/EF) 상태 피드백 반영 ---
        # EF (배기) 피드백 (M0203: 운전확인, M0205: 트립)
        if len(coils) > 5:
            ef_run = coils[3]  # M0203
            ef_trip = coils[5] # M0205
            self.ef_graphic.set_fan_state(ef_run)
            self.update_lamp_ui(self.lbl_EF_run, ef_run, "가동중", "정지중", "#3498db")
            self.update_lamp_ui(self.lbl_EF_trip, ef_trip, "써멀 트립", "정상", "#e74c3c")

        # SF (급기) 피드백 (M0209: 운전확인, M0211: 트립)
        if len(coils) > 11:
            sf_run = coils[9]  # M0209
            sf_trip = coils[11]# M0211
            self.sf_graphic.set_fan_state(sf_run)
            self.update_lamp_ui(self.lbl_SF_run, sf_run, "가동중", "정지중", "#3498db")
            self.update_lamp_ui(self.lbl_SF_trip, sf_trip, "써멀 트립", "정상", "#e74c3c")

        # --- 2. 변압기(TR) 휀 상태 피드백 반영 ---
        # TR1~3 휀 운전 확인 (M0212, M0213, M0214)
        if len(coils) > 14:
            tr_status_list = [coils[12], coils[13], coils[14]]
            
            for i, is_running in enumerate(tr_status_list, start=1):
                graphic = getattr(self, f"tr{i}_graphic")
                lbl = getattr(self, f"lbl_tr{i}_status")
                
                # 💡 [핵심] 실제 피드백이 들어왔을 때만 애니메이션이 돌아갑니다!
                graphic.set_fan_state(is_running)
                
                lbl.setText("가동중 (동작확인)" if is_running else "정지중")
                lbl.setStyleSheet(f"background-color: {'#3498db' if is_running else '#555'}; color: white; padding: 5px; font-weight: bold;")

    def update_lamp_ui(self, label, state, on_text, off_text, on_color):
        """램프 색상 변경 헬퍼 함수"""
        if state:
            label.setText(on_text)
            label.setStyleSheet(f"background-color: {on_color}; color: white; padding: 5px; font-weight: bold; border-radius: 3px; border: 1px solid #222;")
        else:
            label.setText(off_text)
            # 트립이 아닐 때(정상)는 녹색, 가동 중이 아닐 때(정지)는 회색
            default_color = "#27ae60" if off_text == "정상" else "#555"
            label.setStyleSheet(f"background-color: {default_color}; color: white; padding: 5px; font-weight: bold; border-radius: 3px; border: 1px solid #222;")
    
    def create_lcd_label(self, init_text, color):
        lbl = QLabel(init_text); lbl.setAlignment(Qt.AlignCenter)
        lbl.setStyleSheet(f"QLabel {{ background-color: #001111; color: {color}; font-family: 'Consolas'; font-size: 20px; font-weight: bold; border: 1px inset #333; }}")
        return lbl

    # ==========================================================================
    # 🛡️ [신규 추가] 통신 에러 방어막 (프로그램 튕김 방지)
    # ==========================================================================
    def safe_write_bit(self, addr, state, log_msg=""):
        """UI에서 통신을 쏠 때 에러가 나도 프로그램이 죽지 않도록 보호합니다."""
        print(f"👉 [명령] {log_msg} (M0{addr:03d}) ➡️ {state}")
        try:
            # 실제 통신 시도
            pcmaster_worker.write_plc_bit(addr, state)
        except Exception as e:
            # 통신 에러가 터져도 프로그램을 죽이지 않고 경고창/로그만 띄움
            error_msg = f"장비와 통신할 수 없습니다.\n통신선 연결이나 포트 상태를 확인하세요.\n(상세 에러: {e})"
            print(f"⚠️ [통신 에러 차단] {error_msg}")
            # 필요하다면 아래 주석을 풀어 팝업창을 띄울 수도 있습니다.
            # QMessageBox.warning(self, "통신 오류", error_msg)