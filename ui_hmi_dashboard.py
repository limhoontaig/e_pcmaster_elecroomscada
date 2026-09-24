# ui_hmi_dashboard.py
from PyQt5.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QGridLayout, 
                             QLabel, QGroupBox, QPushButton, QFrame, QSplitter)
from PyQt5.QtCore import Qt, QTimer
from PyQt5.QtGui import QFont, QPainter, QColor, QPen, QBrush, QCursor

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
    # 🌟 [수정됨] 환기설비 패널 (상태 램프를 버튼으로 교체) 🌟
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

        # 💡 [핵심 변경] 상태 램프를 단순 라벨(QLabel)에서 클릭 가능한 버튼(QPushButton)으로 변경
        lamp_layout = QHBoxLayout()
        
        run_lamp = QPushButton("정지중")
        run_lamp.setCursor(QCursor(Qt.PointingHandCursor)) # 마우스 올리면 손가락 모양으로 변경
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

    def on_system_stop_clicked(self, prefix):
        """운전 램프를 클릭했을 때 실행: 전체 시스템 중지 명령"""
        print(f"🚨 [명령 전송] {prefix} 설비 마스터 강제 정지 신호 전송!")
        # 추후 PLC 통신 로직 연결

    def on_thermal_reset_clicked(self, prefix):
        """트립 램프를 클릭했을 때 실행: 써멀 트립 리셋(Reset) 명령 및 화면 복구"""
        lamp = getattr(self, f"lbl_{prefix}_trip")
        # 상태가 트립(붉은색)일 때만 리셋 동작이 먹히도록 처리
        if "써멀" in lamp.text():
            print(f"♻️ [명령 전송] {prefix} 마그네트 써멀 트립 리셋(Reset) 신호 전송!")
            # 임시로 즉시 UI를 '정상'으로 복구해 보여줌 (추후 PLC 피드백과 연동)
            lamp.setText("정상")
            lamp.setStyleSheet("background-color: #27ae60; color: white; padding: 5px; font-weight: bold; border-radius: 3px; border: 1px solid #222;")
        else:
            # 테스트를 위해 '정상'일 때 누르면 강제로 트립을 발생시켜 봅니다.
            print(f"⚠️ [테스트] {prefix} 강제 써멀 트립 발생!")
            lamp.setText("써멀 트립")
            lamp.setStyleSheet("background-color: #e74c3c; color: yellow; padding: 5px; font-weight: bold; border-radius: 3px; border: 2px solid red;")

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
        btn.pressed.connect(lambda: self.on_momentary_pressed(signal_name, True))
        btn.released.connect(lambda: self.on_momentary_pressed(signal_name, False))
        return btn

    def on_momentary_pressed(self, signal_name, state):
        val = "1 (ON)" if state else "0 (OFF)"
        print(f"👉 [비트 제어 전송] {signal_name} 신호: {val}")

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
        btn.setStyleSheet("""
            QPushButton { background-color: #34495e; color: white; border: 2px solid #2c3e50; padding: 10px; border-radius: 5px; font-weight: bold; }
            QPushButton:hover { background-color: #3d566e; }
            QPushButton:checked { background-color: #c0392b; color: yellow; border: 2px solid #e74c3c; } 
            QPushButton:disabled { background-color: #222222; color: #555555; border: 1px solid #333333; }
        """)
        return btn

    def update_tr_fan_status(self, tr_idx, is_running):
        graphic = getattr(self, f"tr{tr_idx}_graphic")
        lbl = getattr(self, f"lbl_tr{tr_idx}_status")
        btn = getattr(self, f"btn_tr{tr_idx}")
        
        graphic.set_fan_state(is_running)
        lbl.setText("가동중" if is_running else "정지중")
        lbl.setStyleSheet(f"background-color: {'#3498db' if is_running else '#555'}; color: white; padding: 5px; font-weight: bold;")
        btn.setText(f"TR-{tr_idx} 휀 ON" if is_running else f"TR-{tr_idx} 휀 OFF")

    def create_lcd_label(self, init_text, color):
        lbl = QLabel(init_text); lbl.setAlignment(Qt.AlignCenter)
        lbl.setStyleSheet(f"QLabel {{ background-color: #001111; color: {color}; font-family: 'Consolas'; font-size: 20px; font-weight: bold; border: 1px inset #333; }}")
        return lbl