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

# 🌟 분리된 위젯 및 패널 클래스들 임포트
from src.ui.fan_graphic import FanGraphicWidget
from src.ui.ventilation_panel import VentilationPanel
from src.ui.transformer_panel import TransformerPanel


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

        self.is_ef_manual = False
        self.is_sf_manual = False
        
        top_layout = QHBoxLayout()
        top_layout.setContentsMargins(0, 0, 0, 0)
        title_label = QLabel("⚡ 전기실 통합 제어 대시보드 (환기/변압기)")
        title_label.setFixedHeight(30)
        title_label.setStyleSheet("font-size: 22px; font-weight: bold; color: #00FFCC;")
        top_layout.addWidget(title_label); top_layout.addStretch()

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
        
        btn_ac.clicked.connect(self.open_ac_settings_dialog)
        btn_vent.clicked.connect(self.open_ventilation_settings_dialog)
        btn_tr.clicked.connect(self.open_tr_settings_dialog)
        
        top_layout.addWidget(btn_ac)
        top_layout.addWidget(btn_vent)
        top_layout.addWidget(btn_tr)

        main_layout.addLayout(top_layout)

        # ======================================================================
        # 🌟 환기 및 변압기 패널을 분리된 클래스로 호출하여 배치
        # ======================================================================
        mid_layout = QHBoxLayout()
        mid_layout.setContentsMargins(0, 5, 0, 5)
        
        vent_panel = VentilationPanel(self)
        tr_panel = TransformerPanel(self)
        
        self.sf_graphic = vent_panel.sf_graphic
        self.ef_graphic = vent_panel.ef_graphic
        
        vent_panel.setSizePolicy(QSizePolicy.Ignored, QSizePolicy.Preferred)
        tr_panel.setSizePolicy(QSizePolicy.Ignored, QSizePolicy.Preferred)
        mid_layout.addWidget(vent_panel, 1)
        mid_layout.addWidget(tr_panel, 1)

        main_layout.addLayout(mid_layout, 2) 

        # 하단 계측 데이터 테이블 그리드 영역
        data_frame = QFrame()
        data_frame.setStyleSheet("background-color: #0a0a0a; border: 2px solid #444;")
        grid = QGridLayout(data_frame)
        grid.setSpacing(2)
        grid.setContentsMargins(5, 5, 5, 5)

        headers = ["설비 구분", "운전 전압 (V)", "운전 전류 (A)", "TR별 부하 (kW)", "부하율 (%)", "총 부하( kW )", "운전 온도 (℃)", "2분 최대온도 (℃)"]
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
            
            for col_idx in range(4):
                key = keys[col_idx]
                db_key = db_keys[col_idx]
                color = colors[col_idx]
                label_key = f"{db_prefix}_{db_key}" if key != "load" else f"tr{tr_num}_load"
                lcd = self.create_lcd_label("0.0", color)
                self.data_labels[label_key] = lcd
                grid.addWidget(lcd, row_idx, col_idx + 1)

            if row_idx == 1:
                total_lcd = self.create_lcd_label("0.0", "#f39c12")
                self.data_labels["total_kw"] = total_lcd
                grid.addWidget(total_lcd, 1, 5, 3, 1)

            temp_lcd = self.create_lcd_label("0.0", "#2ecc71")
            self.data_labels[f"{db_prefix}_Temp"] = temp_lcd
            grid.addWidget(temp_lcd, row_idx, 6)

            max_temp_lcd = self.create_lcd_label("0.0", "#e74c3c")
            self.data_labels[f"{db_prefix}_max_temp"] = max_temp_lcd
            grid.addWidget(max_temp_lcd, row_idx, 7)

        main_layout.addWidget(data_frame, 1)
        pcmaster_worker.comm_signal.plc_control_sync.connect(self.sync_control_ui)

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

    def sync_control_ui(self, control_bits):
        """
        PLC에서 정제되어 넘어온 제어 비트 배열을 받아 대시보드 버튼들과 양방향으로 동기화합니다.
        (마스터 가동 여부, 자동/수동 모드에 따른 버튼 가시성 및 컬러 변화 포함)
        """
        if not control_bits or len(control_bits) < 18:
            return

        try:
            # 1. TR 냉각 전체 마스터 버튼 동기화 (M0101)
            # 래더 B접점 특성상 0일 때 마스터 켜짐(True)
            is_master_on = not control_bits[1]
            
            # 현재 대시보드의 마스터 버튼 상태와 다를 때만 연동 메서드 실행
            if self.btn_master.isChecked() != is_master_on:
                self.btn_master.blockSignals(True)
                self.btn_master.setChecked(is_master_on)
                self.btn_master.setText("전체 냉각설비 가동중" if is_master_on else "❄️ 겨울철 냉각설비 정지")
                self.btn_master.setStyleSheet(self.get_master_style(is_master_on))
                self.btn_master.blockSignals(False)
                
                # 🌟 마스터 토글 시 하위 버튼들 보이기/숨기기 처리 (기존 대시보드 로직 연동)
                for btn in [self.btn_auto, self.btn_tr1, self.btn_tr2, self.btn_tr3]:
                    btn.setVisible(is_master_on)
                if not is_master_on:
                    self.set_individual_buttons_enabled(False)

            # 마스터가 꺼져 있다면 하위 상태 동기화는 스킵
            if not is_master_on:
                return

            # 2. TR 자동/수동 토글 버튼 동기화 (M0100)
            # 래더 B접점 특성상 0일 때 자동(True)
            is_auto = not control_bits[0]
            
            if self.btn_auto.isChecked() != is_auto:
                self.btn_auto.blockSignals(True)
                self.btn_auto.setChecked(is_auto)
                self.btn_auto.setText("자동 운전" if is_auto else "수동 운전")
                self.btn_auto.setStyleSheet(self.get_auto_manual_style(is_auto))
                self.btn_auto.blockSignals(False)
                
                # 🌟 자동/수동 전환 시 개별 수동 버튼 활성화/비활성화 처리 연동
                self.set_individual_buttons_enabled(not is_auto)
                if is_auto:
                    for tr_num in [1, 2, 3]:
                        tr_btn = getattr(self, f"btn_tr{tr_num}")
                        tr_btn.blockSignals(True)
                        tr_btn.setChecked(False)
                        tr_btn.blockSignals(False)

            # 3. TR 개별 수동 조작 버튼 동기화 (M0102 ~ M0104) 및 자체 버튼 컬러/텍스트 변경
            for idx, tr_num in enumerate([1, 2, 3], start=2):
                if idx < len(control_bits):
                    is_tr_manual_on = bool(control_bits[idx])
                    btn = getattr(self, f"btn_tr{tr_num}")
                    
                    if btn.isChecked() != is_tr_manual_on:
                        btn.blockSignals(True)
                        btn.setChecked(is_tr_manual_on)
                        # 🌟 수동 ON 상태일 때 버튼 텍스트 및 자체 컬러 스타일 반영 (체크되면 QSS의 :checked 스타일에 의해 빨간색+노란글씨로 자동 변환됨)
                        btn.setText(f"TR-{tr_num} 수동 ON" if is_tr_manual_on else f"TR-{tr_num} 수동 OFF")
                        btn.blockSignals(False)

            # 4. 배기휀(EF) 수동 기동 토글 스위치 동기화 (M0116)
            if len(control_bits) > 16 and hasattr(self, 'btn_EF_manual_run'):
                ef_sw_state = bool(control_bits[16])
                if self.btn_EF_manual_run.isChecked() != ef_sw_state:
                    self.btn_EF_manual_run.blockSignals(True)
                    self.btn_EF_manual_run.setChecked(ef_sw_state)
                    self.btn_EF_manual_run.setText("수동 운전" if ef_sw_state else "수동 정지")
                    self.btn_EF_manual_run.setStyleSheet(self.get_toggle_style(ef_sw_state))
                    self.btn_EF_manual_run.blockSignals(False)

            # 5. 급기휀(SF) 수동 기동 토글 스위치 동기화 (M0117)
            if len(control_bits) > 17 and hasattr(self, 'btn_SF_manual_run'):
                sf_sw_state = bool(control_bits[17])
                if self.btn_SF_manual_run.isChecked() != sf_sw_state:
                    self.btn_SF_manual_run.blockSignals(True)
                    self.btn_SF_manual_run.setChecked(sf_sw_state)
                    self.btn_SF_manual_run.setText("수동 운전" if sf_sw_state else "수동 정지")
                    self.btn_SF_manual_run.setStyleSheet(self.get_toggle_style(sf_sw_state))
                    self.btn_SF_manual_run.blockSignals(False)

        except Exception as e:
            pass

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