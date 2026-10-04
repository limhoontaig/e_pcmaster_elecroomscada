# ui_main_window.py
import os
import sqlite3
import configparser
from datetime import datetime

from PyQt5.QtWidgets import (QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QGroupBox, 
                             QLabel, QDateEdit, QPushButton, QStackedWidget, QSplitter, 
                             QTableWidget, QTableWidgetItem, QMessageBox, QFileDialog, 
                             QDialog, QDoubleSpinBox)
from PyQt5.QtCore import QTimer, QDate, Qt
from PyQt5.QtGui import QIcon


from shared import db_manager
from src import excel_report
from src import pcmaster_worker 

from src.tr_controller import TRFanSettingsDialog
from src.ui.ui_graph_manager import GraphManager
from src.ui.ui_dialogs import ManualMeterInputDialog, FieldInspectionDialog 
from src.ui.ui_ac_settings import ACSettingsDialog
from src.ui.ui_hmi_dashboard import HMIDashboardWidget
from src.ui.ui_report_power import PowerReportDialog
from src.ui.ui_report_temp import TempReportDialog
from tools.db_tools import mariadb_backup

class SCADAWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.initUI()

        # 1. 기존 화면 리프레시 타이머 (10초 주기)
        self.timer = QTimer(self)
        self.timer.timeout.connect(self.auto_refresh)
        self.timer.start(10000) 
        self.last_hour = datetime.now().hour

        # 2. 정기 자동 백업 타이머 추가 (1시간 주기)
        self.backup_timer = QTimer(self)
        self.backup_timer.timeout.connect(self.check_daily_backup)
        self.backup_timer.start(3600000)         
        self.last_backup_date = datetime.now().strftime("%Y-%m-%d")

        # 🌟 3. 신규: 1초 단위 실시간 시계 타이머
        self.clock_timer = QTimer(self)
        self.clock_timer.timeout.connect(self.update_clock)
        self.clock_timer.start(1000) # 1초마다 틱
        
        # 👈 [핵심 추가] 1초를 기다리지 않고 프로그램 시작 즉시 시계 표시
        self.update_clock()

    def initUI(self):
        icon_path = self.resource_path("free-icon-folder-2015058.ico")
        self.setWindowIcon(QIcon(icon_path))
        self.setWindowTitle("래미안개포루체하임아파트 변전실 데이터 통합 관리 시스템 (Developed by 관리과장 임훈택)")
        self.resize(1500, 1000)
        
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        main_layout = QVBoxLayout(central_widget)

        # =====================================================================
        # 🌟 [개편됨] 1. 상단 메인 타이틀 바 (통신확인 - 타이틀 - DB수동백업) 🌟
        # =====================================================================
        title_layout = QHBoxLayout()
        
        # [좌측] RS485 통신 상태 라벨
        self.lbl_rs485_status = QLabel("⚫ 통신 확인 중...")
        self.lbl_rs485_status.setAlignment(Qt.AlignCenter)
        self.lbl_rs485_status.setStyleSheet("""
            background-color: #7f8c8d; color: white; font-weight: bold; 
            padding: 8px 15px; border-radius: 5px; font-size: 14px;
        """)
        title_layout.addWidget(self.lbl_rs485_status)
        
        title_layout.addStretch() # 좌우 균형을 위한 스프링

        # [중앙] 메인 타이틀
        self.lbl_main_title = QLabel("래미안개포루체하임아파트 변전실 통합 SCADA 시스템")
        self.lbl_main_title.setAlignment(Qt.AlignCenter)
        self.lbl_main_title.setStyleSheet("font-size: 24px; font-weight: bold; color: #2c3e50; margin: 5px 0;")
        title_layout.addWidget(self.lbl_main_title)

        title_layout.addStretch() # 좌우 균형을 위한 스프링

        # [우측] DB 수동 백업 버튼
        self.btn_backup_db = QPushButton("💾 DB 수동 백업")
        self.btn_backup_db.setStyleSheet("""
            QPushButton { background-color: #2c3e50; color: white; font-weight: bold; padding: 8px 15px; border-radius: 5px; font-size: 14px; }
            QPushButton:hover { background-color: #34495e; }
        """)
        self.btn_backup_db.clicked.connect(self.slot_backup_database)
        title_layout.addWidget(self.btn_backup_db)

        main_layout.addLayout(title_layout) # 타이틀 바를 화면 최상단에 부착

        # =====================================================================
        # 2. 상단 제어 센터 (버튼 재배치)
        # =====================================================================
        top_ctrl = QGroupBox("운영 제어 센터")
        top_layout = QHBoxLayout(top_ctrl)
        top_layout.setSpacing(10) # 간격을 살짝 좁혀서 공간 확보
        
        self.qdate = QDateEdit(QDate.currentDate())
        self.qdate.setCalendarPopup(True)
        self.qdate.setMinimumWidth(120) 
        self.qdate.setAlignment(Qt.AlignCenter) 
        self.qdate.setStyleSheet("font-size: 14px; padding: 3px; font-weight: bold;") 

        min_db_date = QDate(2026, 5, 26)
        self.qdate.setMinimumDate(min_db_date)
        max_db_date = QDate.currentDate()
        self.qdate.setMaximumDate(max_db_date)
        
        lbl_date_title = QLabel("<b>선택 날짜:</b>")
        lbl_date_title.setStyleSheet("font-size: 14px; font-weight: bold;")

        self.btn_show_hmi = QPushButton("HMI 대시보드")
        self.btn_show_hmi.setStyleSheet("background-color: #f39c12; color: white; font-weight: bold; min-height: 35px;")
        
        self.btn_show_table = QPushButton("종합 데이터 표")
        self.btn_show_table.setStyleSheet("background-color: #2980b9; color: white; font-weight: bold; min-height: 35px;")
        
        self.btn_show_graph = QPushButton("부하 변동 그래프")
        self.btn_show_graph.setStyleSheet("background-color: #8e44ad; color: white; font-weight: bold; min-height: 35px;")
        
        # 🌟 [신규 추가] 통계 보고서 버튼
        self.btn_show_report = QPushButton("전력 통계 보고서")
        self.btn_show_report.setStyleSheet("background-color: #16a085; color: white; font-weight: bold; min-height: 35px;")
        
        self.btn_export_excel = QPushButton("엑셀 운영일지 출력")
        self.btn_export_excel.setStyleSheet("background-color: #27ae60; color: white; font-weight: bold; min-height: 35px;")
        
        self.btn_meter_input = QPushButton("전력량계 검침량 입력") 
        self.btn_meter_input.setStyleSheet("background-color: #2196F3; color: white; font-weight: bold; min-height: 35px;")
        
        self.btn_field_inspection = QPushButton("현장 점검 입력")
        self.btn_field_inspection.setStyleSheet("background-color: #E67E22; color: white; font-weight: bold; min-height: 35px;")
        self.btn_field_inspection.clicked.connect(self.click_open_inspection_popup) 
        
        # 레이아웃에 위젯 등록
        top_layout.addWidget(lbl_date_title)
        top_layout.addWidget(self.qdate)
        top_layout.addWidget(self.btn_show_hmi)
        top_layout.addWidget(self.btn_show_table)
        top_layout.addWidget(self.btn_show_graph)
        top_layout.addWidget(self.btn_show_report) # 👈 신규 보고서 버튼
        top_layout.addWidget(self.btn_export_excel)
        top_layout.addWidget(self.btn_meter_input)
        top_layout.addWidget(self.btn_field_inspection)
        
        main_layout.addWidget(top_ctrl)

        self.stack = QStackedWidget()
        main_layout.addWidget(self.stack)

        # ==================== [페이지 0] HMI 대시보드 ====================
        self.hmi_dashboard = HMIDashboardWidget()
        self.stack.addWidget(self.hmi_dashboard)

        # ==================== [페이지 1] 테이블 ====================
        self.page_table = QWidget()
        table_layout = QVBoxLayout(self.page_table)
        splitter = QSplitter(Qt.Vertical)
        
        self.raw_table = QTableWidget()
        self.raw_table.setColumnCount(len(db_manager.COLUMN_LABELS))
        self.raw_table.setHorizontalHeaderLabels(db_manager.COLUMN_LABELS)
        
        self.avg_table = QTableWidget()
        self.avg_table.setColumnCount(len(db_manager.COLUMN_LABELS))
        self.avg_table.setHorizontalHeaderLabels(db_manager.COLUMN_LABELS)

        self.extreme_table = QTableWidget()
        self.extreme_table.setColumnCount(len(db_manager.COLUMN_LABELS))
        self.extreme_table.setHorizontalHeaderLabels(db_manager.COLUMN_LABELS)

        self.manual_table = QTableWidget()
        manual_headers = ["기록 일자"] + db_manager.METER_FIELDS 
        self.manual_table.setColumnCount(len(manual_headers))
        self.manual_table.setHorizontalHeaderLabels(manual_headers)

        self.inspection_table = QTableWidget()
        self.inspection_table.setColumnCount(3)
        self.inspection_table.setHorizontalHeaderLabels(["점검 차수", "점검자 성명", "점검 시간"])

        splitter.addWidget(QLabel("● 실시간 계측 데이터 로그"))
        splitter.addWidget(self.raw_table)
        splitter.addWidget(QLabel("● 시간별 평균 전력 추이"))
        splitter.addWidget(self.avg_table)
        splitter.addWidget(QLabel("● 일일 최고(MAX) / 최저(MIN) 값 설비 통계"))
        splitter.addWidget(self.extreme_table)
        splitter.addWidget(QLabel("● 독립 계량장치 일일 지침 수동 로그 (manual_meter_logs)"))
        splitter.addWidget(self.manual_table)
        splitter.addWidget(QLabel("● 일일 현장점검 결과 로그"))
        splitter.addWidget(self.inspection_table)

        table_layout.addWidget(splitter)
        self.stack.addWidget(self.page_table)

        # ==================== [페이지 2] 그래프 ====================
        self.graph_manager = GraphManager(self) 
        self.stack.addWidget(self.graph_manager)

        # =====================================================================
        # 🌟 [페이지 3] 개편: 전력 통계 보고서 대시보드 (메뉴판 역할) 🌟
        # =====================================================================
        self.page_report = QWidget()
        report_layout = QVBoxLayout(self.page_report)
        
        report_header = QLabel("📊 SCADA 종합 통계 및 분석 보고서 포털")
        report_header.setAlignment(Qt.AlignCenter)
        report_header.setStyleSheet("font-size: 24px; font-weight: bold; color: #2c3e50; margin: 15px 0;")
        report_layout.addWidget(report_header)

        # --- [1] 중간 메뉴 버튼 4개를 가로 1줄로 배치 (세로 공간 확보) ---
        menu_layout = QHBoxLayout()
        menu_layout.setSpacing(15) # 버튼 사이 간격

        self.btn_rep_power = QPushButton("⚡ 전력 사용량 통계")
        self.btn_rep_power.setMinimumHeight(60)
        self.btn_rep_power.setStyleSheet("font-size: 15px; font-weight: bold; background-color: #34495e; color: white; border-radius: 8px;")
        self.btn_rep_power.clicked.connect(self.open_power_report_dialog)
        
        self.btn_rep_temp = QPushButton("🌡 온도 추이 분석")
        self.btn_rep_temp.setMinimumHeight(60)
        self.btn_rep_temp.setStyleSheet("font-size: 15px; font-weight: bold; background-color: #e67e22; color: white; border-radius: 8px;")
        self.btn_rep_temp.clicked.connect(self.open_temp_report_dialog)

        self.btn_rep_fan = QPushButton("💨 냉각/환기설비 분석")
        self.btn_rep_fan.setMinimumHeight(60)
        self.btn_rep_fan.setStyleSheet("font-size: 15px; font-weight: bold; background-color: #2980b9; color: white; border-radius: 8px;")
        
        self.btn_rep_alarm = QPushButton("🚨 알람/이벤트 이력")
        self.btn_rep_alarm.setMinimumHeight(60)
        self.btn_rep_alarm.setStyleSheet("font-size: 15px; font-weight: bold; background-color: #c0392b; color: white; border-radius: 8px;")

        # QHBoxLayout에 순서대로 추가하면 자동으로 1줄로 꽉 차게 들어갑니다.
        menu_layout.addWidget(self.btn_rep_power)
        menu_layout.addWidget(self.btn_rep_temp)
        menu_layout.addWidget(self.btn_rep_fan)
        menu_layout.addWidget(self.btn_rep_alarm)

        report_layout.addLayout(menu_layout)

        # --- [2] 실시간 시계 및 테이블 타이틀 ---
        event_header_layout = QHBoxLayout()
        lbl_event_title = QLabel("📢 일일 설비 가동 및 경보(이벤트) 발생 현황")
        lbl_event_title.setStyleSheet("font-size: 18px; font-weight: bold; color: #2c3e50; margin-top: 25px;")
        
        self.lbl_current_time = QLabel("🕒 현재 시간: 로딩 중...")
        self.lbl_current_time.setStyleSheet("font-size: 16px; font-weight: bold; color: #16a085; margin-top: 25px;")
        self.lbl_current_time.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        
        event_header_layout.addWidget(lbl_event_title)
        event_header_layout.addStretch()
        event_header_layout.addWidget(self.lbl_current_time)
        report_layout.addLayout(event_header_layout)

        # --- [3] 이벤트 현황 테이블 ---
        self.alarm_table = QTableWidget()
        from PyQt5.QtWidgets import QHeaderView
        alarm_headers = ["ID", "발생 시간", "분류", "설비명", "이벤트/알람 내용", "조치 내역", "해제/종료 시간", "가동(초)", "조치자"]
        self.alarm_table.setColumnCount(len(alarm_headers))
        self.alarm_table.setHorizontalHeaderLabels(alarm_headers)
        self.alarm_table.horizontalHeader().setSectionResizeMode(4, QHeaderView.Stretch) # 메시지 열 확장
        
        report_layout.addWidget(self.alarm_table)

        self.stack.addWidget(self.page_report)

        # ==================== 3. 이벤트 시그널 연결 ====================
        self.btn_show_hmi.clicked.connect(lambda: self.stack.setCurrentIndex(0))
        self.btn_show_table.clicked.connect(lambda: self.stack.setCurrentIndex(1))
        self.btn_show_graph.clicked.connect(self.on_graph_tab_changed) 
        src.pcmaster_worker.comm_signal.plc_status_update.connect(self.hmi_dashboard.update_plc_status)
        
        # 신규 보고서 버튼 연결
        self.btn_show_report.clicked.connect(lambda: self.stack.setCurrentIndex(3)) 
        
        self.btn_export_excel.clicked.connect(self.export_excel_click)
        self.btn_meter_input.clicked.connect(self.click_open_meter_popup)
        self.qdate.dateChanged.connect(self.auto_refresh)

        self.load_data()

    def update_clock(self):
        """1초마다 호출되어 화면의 현재 시간을 갱신합니다."""
        # 파일 상단에 from datetime import datetime 이 있으므로 바로 datetime.now() 사용
        now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        if hasattr(self, 'lbl_current_time'):
            self.lbl_current_time.setText(f"🕒 현재 시간: {now_str}")

    def load_alarm_data(self):
        """선택된 날짜의 이벤트 이력을 불러와 하단 테이블에 표출합니다."""
        target_date = self.qdate.date().toString("yyyy-MM-dd")
        try:
            # db_manager에서 당일 데이터 호출 (최신순)
            rows = db_manager.get_alarm_history(target_date, target_date)
            self.alarm_table.setRowCount(len(rows))
            
            for r_idx, row in enumerate(rows):
                for c_idx, val in enumerate(row):
                    txt = str(val) if val is not None else "-"
                    item = QTableWidgetItem(txt)
                    item.setTextAlignment(Qt.AlignCenter)
                    
                    # 3번째 열(분류)에 따른 색상 하이라이트 적용
                    if c_idx == 2: 
                        if val == 'ALARM': item.setForeground(Qt.darkYellow)
                        elif val == 'TRIP': item.setForeground(Qt.red)
                        elif val == 'OPERATION': item.setForeground(Qt.darkGreen)
                        
                    self.alarm_table.setItem(r_idx, c_idx, item)
        except Exception as e:
            pass
            # print(f"알람 데이터 표출 에러: {e}")
    
    def open_power_report_dialog(self):
        """전력 통계 보고서 전용 독립 창을 띄웁니다."""
        dialog = PowerReportDialog(self)
        dialog.exec_()

    def open_temp_report_dialog(self):
        """온도 보고서 전용 독립 창을 띄웁니다."""
        dialog = TempReportDialog(self)
        dialog.exec_()

    def open_ac_settings_dialog(self, event):
        dialog = ACSettingsDialog(self)
        dialog.exec_()

    def open_tr_fan_settings_dialog(self, event):
        dialog = TRFanSettingsDialog(parent=self)
        dialog.exec_()

    def check_daily_backup(self):
        current_date_str = datetime.now().strftime("%Y-%m-%d")
        current_hour = datetime.now().hour
        
        if current_date_str != self.last_backup_date and current_hour == 0:
            print(f"[자동 정기 백업 시작] 현재 날짜: {current_date_str}")
            success = mariadb_backup.auto_backup_by_year()
            if success:
                self.last_backup_date = current_date_str
                self.statusBar().showMessage(f"✅ 정기 자동 백업 완료 ({current_date_str} 자정 기준)", 10000)

    def resource_path(self, relative_path):
        import sys, os
        try:
            base_path = sys._MEIPASS
        except Exception:
            base_path = os.path.abspath(".")
        return os.path.join(base_path, relative_path)

    def on_graph_tab_changed(self):
        self.stack.setCurrentIndex(2)
        self.graph_manager.update_graph()

    def load_data(self):
        selected_date = self.qdate.date().toString("yyyy-MM-dd")
        shared.db_manager.calculate_daily_extremes(selected_date)
        
        try:
            conn = shared.db_manager.get_db_raw_connection()
            c = conn.cursor()
            
            query_raw = f"SELECT DATE_FORMAT(log_date, '%%Y-%%m-%%d'), TIME_FORMAT(log_time, '%%H:%%i:%%s'), {', '.join([f'`{n}`' for n in shared.db_manager.DATA_LABELS])} FROM raw_data WHERE log_date = %s ORDER BY log_time DESC"
            c.execute(query_raw, (selected_date,))
            self.display_table(self.raw_table, c.fetchall())
            
            query_avg = f"SELECT DATE_FORMAT(log_date, '%%Y-%%m-%%d'), TIME_FORMAT(log_time, '%%H:%%i:%%s'), {', '.join([f'`{n}`' for n in shared.db_manager.DATA_LABELS])} FROM hourly_avg WHERE log_date = %s ORDER BY log_time DESC"
            c.execute(query_avg, (selected_date,))
            self.display_table(self.avg_table, c.fetchall())
            
            query_ext = f"SELECT DATE_FORMAT(log_date, '%%Y-%%m-%%d'), extreme_type, {', '.join([f'`{n}`' for n in shared.db_manager.DATA_LABELS])} FROM daily_extremes WHERE log_date = %s ORDER BY extreme_type DESC"
            c.execute(query_ext, (selected_date,))
            self.display_table(self.extreme_table, c.fetchall(), is_extreme=True)
            
            c.close()
            conn.close()

            if hasattr(shared.db_manager, 'get_manual_meter_log_for_table'):
                manual_row = shared.db_manager.get_manual_meter_log_for_table(selected_date)
                self.display_manual_table([manual_row])

            if hasattr(shared.db_manager, 'get_field_inspections_for_date'):
                inspection_data = shared.db_manager.get_field_inspections_for_date(selected_date)
                self.display_inspection_table(inspection_data)

            self.load_alarm_data()
            
        except Exception as e:
            pass
            # print(f"UI 로딩 실패: {e}")

    def display_manual_table(self, rows):
        self.manual_table.setRowCount(len(rows))
        for r_idx, row in enumerate(rows):
            for c_idx, val in enumerate(row):
                item = QTableWidgetItem(str(val))
                item.setTextAlignment(Qt.AlignCenter)
                if c_idx > 0 and val != "-":
                    item.setForeground(Qt.darkGreen)
                self.manual_table.setItem(r_idx, c_idx, item)

    def display_table(self, table, rows, is_extreme=False):
        table.setRowCount(len(rows))
        for r_idx, row in enumerate(rows):
            for c_idx, val in enumerate(row):
                txt = f"{val:.1f}" if isinstance(val, float) else str(val)
                item = QTableWidgetItem(txt)
                item.setTextAlignment(Qt.AlignCenter)

                if is_extreme and c_idx > 1:
                    if row[1] == 'MAX': item.setForeground(Qt.red)
                    elif row[1] == 'MIN': item.setForeground(Qt.blue)
                table.setItem(r_idx, c_idx, item)

    def export_excel_click(self):
        target_date_str = self.qdate.date().toString("yyyy-MM-dd")
        reply = QMessageBox.question(
            self, 
            "운영일지 엑셀 출력 안내", 
            f"선택하신 날짜 [{target_date_str}]의 운영일지를 엑셀 파일로 출력합니다.\n\n"
            "다음 화면에서 엑셀 파일이 저장될 '컴퓨터 폴더(디렉토리)'를 지정해 주세요.\n"
            "진행하시겠습니까?",
            QMessageBox.Yes | QMessageBox.No, 
            QMessageBox.Yes
        )
        if reply == QMessageBox.No: return

        dir_path = QFileDialog.getExistingDirectory(self, "엑셀 파일 저장 폴더 선택", "D:\\전기실_운전일지")
        if not dir_path:
            QMessageBox.warning(self, "출력 취소", "저장할 폴더가 선택되지 않아 엑셀 출력을 취소합니다.")
            return

        try:
            excel_report.generate_excel_report(target_date_str, target_dir=dir_path)
            QMessageBox.information(
                self, 
                "출력 완료", 
                f"[{target_date_str}] 운영일지가 성공적으로 저장되었습니다.\n\n"
                f"저장위치: {dir_path}"
            )
        except Exception as e:
            QMessageBox.critical(self, "오류 발생", f"엑셀 운영일지 생성 중 오류가 발생했습니다.\n에러 내용: {e}")
        
    def auto_refresh(self):
        try:
            # 기존 코드를 모두 try 안으로 한 칸(Tab) 들여쓰기 합니다.
            self.qdate.setMaximumDate(QDate.currentDate())
            curr_hour = datetime.now().hour
            
            if curr_hour != self.last_hour:
                self.last_hour = curr_hour
                shared.db_manager.calculate_hourly_avg()
                
            self.load_data()
            self.graph_manager.update_graph()
            
        except Exception as e:
            # 🌟 에러가 발생해도 프로그램이 뻗지 않고 경고창만 띄우도록 처리
            # print(f"⚠ 날짜 갱신 중 에러 발생 (프로그램 다운 방어): {e}")
            from PyQt5.QtWidgets import QMessageBox
            QMessageBox.warning(None, "데이터 갱신 지연", "데이터베이스 연결이 지연되었습니다. 잠시 후 다시 조작해 주세요.")

    def click_open_meter_popup(self):
        current_date_str = self.qdate.date().toString("yyyy-MM-dd")
        dialog = ManualMeterInputDialog(None, self)
        result = dialog.exec_()
        
        if result == 1: 
            save_date = dialog.date_edit.date().toString("yyyy-MM-dd")
            final_data = {field: edit.text().strip() for field, edit in dialog.inputs.items()}

            msg_box = QMessageBox(self)
            msg_box.setWindowTitle("데이터 처리 방식 선택")
            msg_box.setText(f"[{save_date}] 수동 입력 지침 데이터를 어떻게 처리하시겠습니까?")
            btn_save_only = msg_box.addButton("데이터 저장만", QMessageBox.ActionRole)
            btn_save_and_export = msg_box.addButton("데이터 저장 및 출력", QMessageBox.ActionRole)
            btn_cancel = msg_box.addButton("취소", QMessageBox.RejectRole)
            msg_box.setDefaultButton(btn_save_and_export) 
            msg_box.exec_() 
            
            clicked_button = msg_box.clickedButton()

            if clicked_button == btn_cancel: return

            try:
                shared.db_manager.save_manual_meter_data(save_date, final_data)
                
                if clicked_button == btn_save_only:
                    self.load_data() 
                    QMessageBox.information(self, "저장 완료", "데이터가 데이터베이스(DB)에 성공적으로 기록되었습니다.")
                    return
                
                elif clicked_button == btn_save_and_export:
                    folder_guide = QMessageBox.question(
                        self, "운영일지 저장 폴더 안내", 
                        "데이터 저장이 완료되었습니다.\n\n이어서 엑셀 파일 생성을 진행합니다.\n폴더를 선택해 주세요.",
                        QMessageBox.Yes | QMessageBox.No, QMessageBox.Yes
                    )
                    if folder_guide == QMessageBox.No:
                        self.load_data()
                        return

                    selected_dir = QFileDialog.getExistingDirectory(self, "운영일지 저장 폴더 선택", "D:\\전기실_운전일지")
                    if not selected_dir: 
                        self.load_data()
                        return
                    
                    excel_report.generate_excel_report(save_date, target_dir=selected_dir)
                    self.load_data()
                    QMessageBox.information(self, "처리 완료", f"데이터 반영 및 엑셀 일지 작성이 완료되었습니다.\n\n저장위치: {selected_dir}")
                    
            except Exception as e:
                QMessageBox.critical(self, "오류 발생", f"데이터 처리 중 에러가 발생했습니다: {e}")
    
    def click_open_inspection_popup(self):
        today_date_str = datetime.now().strftime("%Y-%m-%d")
        dialog = FieldInspectionDialog(today_date_str, self)
        result = dialog.exec_()
        
        if result == 1: 
            save_date = today_date_str 
            round_idx = dialog.combo_round.currentIndex() + 1 
            inspector = dialog.input_name.text().strip()
            
            existing_inspections = shared.db_manager.get_field_inspections_for_date(save_date)
            target_round_data = existing_inspections.get(round_idx, {"name": "", "time": ""})
            
            if target_round_data["name"] != "":
                old_name = target_round_data["name"]
                old_time = target_round_data["time"]
                reply = QMessageBox.question(
                    self, '⚠️ 오늘 점검 기록 중복 경고',
                    f"오늘({save_date}) 해당 차수에는 이미 등록된 점검 기록이 존재합니다.\n\n"
                    f"현재 입력하신 [{inspector}] 성명으로 기존 기록을 덮어쓰시겠습니까?",
                    QMessageBox.Yes | QMessageBox.No, QMessageBox.No
                )
                if reply == QMessageBox.No: return
            else:
                reply = QMessageBox.question(
                    self, '점검 등록 확인', f"오늘 날짜 [{save_date}] 기준으로 {round_idx}차 현장점검을 완료 처리하시겠습니까?",
                    QMessageBox.Yes | QMessageBox.No, QMessageBox.Yes
                )
                if reply == QMessageBox.No: return
            
            success = shared.db_manager.save_field_inspection(save_date, round_idx, inspector)
            if success:
                QMessageBox.information(self, "저장 완료", f"오늘자({save_date}) {round_idx}차 현장 점검 기록이 완료되었습니다.")
                current_view_date = self.qdate.date().toString("yyyy-MM-dd")
                if current_view_date == save_date:
                    self.load_data()
            else:
                QMessageBox.critical(self, "저장 실패", "데이터베이스 저장 중 에러가 발생했습니다.")

    def display_inspection_table(self, data_dict):
        self.inspection_table.setRowCount(3) 
        for i, round_num in enumerate([1, 2, 3]):
            info = data_dict.get(round_num, {"name": "", "time": ""})
            name_str = info["name"] if info["name"] else "-"
            time_str = info["time"] if info["time"] else "-"
            
            item_round = QTableWidgetItem(f"{round_num}차 점검")
            item_round.setTextAlignment(Qt.AlignCenter)
            item_round.setFlags(item_round.flags() & ~Qt.ItemIsEditable) 
            
            item_name = QTableWidgetItem(name_str)
            item_name.setTextAlignment(Qt.AlignCenter)
            if name_str != "-": item_name.setForeground(Qt.darkBlue) 
            
            item_time = QTableWidgetItem(time_str)
            item_time.setTextAlignment(Qt.AlignCenter)
            
            self.inspection_table.setItem(i, 0, item_round)
            self.inspection_table.setItem(i, 1, item_name)
            self.inspection_table.setItem(i, 2, item_time)

    def slot_backup_database(self):
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        default_filename = f"elecroomscada_{timestamp}.sql"
        default_start_path = os.path.join(r"D:\db_backups", default_filename)
        
        save_path, _ = QFileDialog.getSaveFileName(self, "DB 백업 파일 저장 위치 선택", default_start_path, "SQL 파일 (*.sql);;모든 파일 (*.*)")
        
        if not save_path: return
            
        success, message = mariadb_backup.backup_mariadb(save_path)
        
        if success:
            QMessageBox.information(self, "백업 완료", f"성공적으로 DB 데이터 내보내기가 완료되었습니다!\n\n저장 위치:\n{message}")
        else:
            QMessageBox.critical(self, "백업 실패", f"DB 백업 중 오류가 발생했습니다.\n\n에러 내용:\n{message}")

    def update_rs485_status(self, is_connected: bool):
        if is_connected:
            self.lbl_rs485_status.setText("🟢 통신 정상")
            self.lbl_rs485_status.setStyleSheet("background-color: #27ae60; color: white; font-weight: bold; padding: 6px 12px; border-radius: 4px; font-size: 14px;")
        else:
            self.lbl_rs485_status.setText("🔴 통신 단절")
            self.lbl_rs485_status.setStyleSheet("background-color: #c0392b; color: yellow; font-weight: bold; padding: 6px 12px; border-radius: 4px; font-size: 14px;")