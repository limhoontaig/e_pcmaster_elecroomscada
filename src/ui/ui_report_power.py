# ui_report_power.py
import datetime
import os
from PyQt5.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout, QTabWidget, 
                             QWidget, QLabel, QPushButton, QTableWidget, QTableWidgetItem,
                             QHeaderView, QComboBox, QMessageBox, QRadioButton, QFileDialog)
from PyQt5.QtCore import Qt
from PyQt5 import QtGui
import db_manager

# 🌟 엑셀 출력을 위한 openpyxl (PC에 설치되어 있어야 합니다: pip install openpyxl)
try:
    import openpyxl
    from openpyxl.styles import Font, Alignment, Border, Side, PatternFill
except ImportError:
    openpyxl = None

# =====================================================================
# 🔍 1. 원자료 상세 보기 팝업창 (더블클릭 시 실행)
# =====================================================================
class RawDataDetailDialog(QDialog):
    def __init__(self, target_date, parent=None):
        super().__init__(parent)
        self.target_date = target_date
        self.setWindowTitle(f"🔍 {target_date} 전력 피크 상세 원자료 (1분 단위)")
        self.resize(700, 600)
        self.init_ui()
        self.load_detail_data()

    def init_ui(self):
        layout = QVBoxLayout(self)
        
        lbl_title = QLabel(f"[{self.target_date}] 시간대별 전력(kW) 부하 상세 기록")
        lbl_title.setStyleSheet("font-size: 16px; font-weight: bold; color: #c0392b;")
        layout.addWidget(lbl_title)

        self.table = QTableWidget()
        self.table.setColumnCount(5)
        self.table.setHorizontalHeaderLabels(["시간", "한전총전력(KEP)", "TR1 전력", "TR2 전력", "TR3 전력"])
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        layout.addWidget(self.table)

        btn_close = QPushButton("닫기")
        btn_close.clicked.connect(self.accept)
        layout.addWidget(btn_close)

    def load_detail_data(self):
        try:
            conn = db_manager.get_db_raw_connection()
            c = conn.cursor()
            query = """
                SELECT TIME_FORMAT(log_time, '%%H:%%i:%%s'), KEP_P_kW, Tr1_P_kW, Tr2_P_kW, Tr3_P_kW 
                FROM raw_data 
                WHERE log_date = %s 
                ORDER BY log_time ASC
            """
            c.execute(query, (self.target_date,))
            rows = c.fetchall()
            
            self.table.setRowCount(len(rows))
            for r_idx, row in enumerate(rows):
                for c_idx, val in enumerate(row):
                    item = QTableWidgetItem(f"{val:.2f}" if isinstance(val, float) else str(val))
                    item.setTextAlignment(Qt.AlignCenter)
                    
                    if c_idx == 1 and isinstance(val, float) and val > 1000.0:
                        item.setForeground(Qt.red)
                    elif c_idx > 1 and isinstance(val, float) and val > 400.0:
                        item.setForeground(Qt.red)
                        
                    self.table.setItem(r_idx, c_idx, item)
                    
            c.close(); conn.close()
        except Exception as e:
            print(f"상세 데이터 로딩 에러: {e}")

# =====================================================================
# 📊 2. 메인 전력 보고서 창 (월간/연간 통합 + 엑셀 출력 기능)
# =====================================================================
class PowerReportDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("⚡ 전력 사용량 및 피크 종합 통계 보고서")
        self.resize(1200, 800)
        self.setWindowFlags(self.windowFlags() | Qt.WindowMaximizeButtonHint | Qt.WindowMinimizeButtonHint)
        self.init_ui()

    def init_ui(self):
        main_layout = QVBoxLayout(self)
        
        title = QLabel("변압기 부하(kW) 피크 분석 및 전력량(kWh) 청구 기준 통계")
        title.setStyleSheet("font-size: 20px; font-weight: bold; color: #2c3e50;")
        title.setAlignment(Qt.AlignCenter)
        main_layout.addWidget(title)

        self.tabs = QTabWidget()
        self.tabs.setStyleSheet("QTabBar::tab { font-size: 14px; font-weight: bold; padding: 10px 20px; }")
        
        self.tab_peak = QWidget()
        self.init_peak_tab()
        self.tabs.addTab(self.tab_peak, "📈 피크(kW) 최고/최저 분석")
        
        self.tab_billing = QWidget()
        self.init_billing_tab()
        self.tabs.addTab(self.tab_billing, "📆 전력량(kWh) 사용량 분석")

        main_layout.addWidget(self.tabs)

        btn_layout = QHBoxLayout()
        btn_layout.addStretch()
        
        # 💡 [핵심] 엑셀 내보내기 버튼 연결
        self.btn_export = QPushButton("📊 이 통계를 엑셀로 내보내기")
        self.btn_export.setStyleSheet("background-color: #27ae60; color: white; font-weight: bold; padding: 8px 15px;")
        self.btn_export.clicked.connect(self.export_to_excel)
        btn_layout.addWidget(self.btn_export)
        
        btn_close = QPushButton("닫기")
        btn_close.setStyleSheet("background-color: #7f8c8d; color: white; font-weight: bold; padding: 8px 30px;")
        btn_close.clicked.connect(self.accept)
        btn_layout.addWidget(btn_close)
        
        main_layout.addLayout(btn_layout)

    # -----------------------------------------------------------------
    # [탭 1] 피크(kW) 최고/최저 분석
    # -----------------------------------------------------------------
    def init_peak_tab(self):
        layout = QVBoxLayout(self.tab_peak)
        
        ctrl_layout = QHBoxLayout()
        
        self.radio_peak_month = QRadioButton("월간 조회 (일별 데이터)")
        self.radio_peak_year = QRadioButton("연간 조회 (월별 데이터)")
        self.radio_peak_month.setChecked(True)
        self.radio_peak_month.toggled.connect(self.toggle_peak_ui)
        
        ctrl_layout.addWidget(self.radio_peak_month)
        ctrl_layout.addWidget(self.radio_peak_year)
        ctrl_layout.addSpacing(20)
        
        self.combo_peak_month = QComboBox()
        self.combo_peak_year = QComboBox()
        
        now = datetime.datetime.now()
        for i in range(12):
            self.combo_peak_month.addItem((now - datetime.timedelta(days=30*i)).strftime("%Y-%m"))
        for i in range(5): 
            self.combo_peak_year.addItem(str(now.year - i))
            
        self.combo_peak_year.setVisible(False) 
        
        ctrl_layout.addWidget(self.combo_peak_month)
        ctrl_layout.addWidget(self.combo_peak_year)
        
        btn_search_peak = QPushButton("조회")
        btn_search_peak.clicked.connect(self.load_peak_data)
        ctrl_layout.addWidget(btn_search_peak)
        ctrl_layout.addStretch()
        layout.addLayout(ctrl_layout)

        self.table_peak = QTableWidget()
        headers = ["날짜/월", "KEP 최저", "KEP 최고", "TR1 최저", "TR1 최고", "TR2 최저", "TR2 최고", "TR3 최저", "TR3 최고"]
        self.table_peak.setColumnCount(len(headers))
        self.table_peak.setHorizontalHeaderLabels(headers)
        self.table_peak.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        
        self.table_peak.cellDoubleClicked.connect(self.on_peak_row_double_clicked)
        
        layout.addWidget(QLabel("※ [월간 조회] 모드에서 날짜 행을 더블클릭하면 1분 단위 상세 원자료를 확인할 수 있습니다."))
        layout.addWidget(self.table_peak)
        
        self.load_peak_data()

    def toggle_peak_ui(self):
        if self.radio_peak_month.isChecked():
            self.combo_peak_month.setVisible(True)
            self.combo_peak_year.setVisible(False)
        else:
            self.combo_peak_month.setVisible(False)
            self.combo_peak_year.setVisible(True)

    def load_peak_data(self):
        is_monthly = self.radio_peak_month.isChecked()
        try:
            conn = db_manager.get_db_raw_connection()
            c = conn.cursor()
            
            if is_monthly:
                target = self.combo_peak_month.currentText()
                query = """
                    SELECT DATE_FORMAT(log_date, '%%Y-%%m-%%d'), MIN(KEP_P_kW), MAX(KEP_P_kW),
                    MIN(Tr1_P_kW), MAX(Tr1_P_kW), MIN(Tr2_P_kW), MAX(Tr2_P_kW), MIN(Tr3_P_kW), MAX(Tr3_P_kW)
                    FROM raw_data WHERE log_date LIKE %s GROUP BY log_date ORDER BY log_date DESC
                """
                c.execute(query, (f"{target}%",))
            else:
                target = self.combo_peak_year.currentText()
                query = """
                    SELECT DATE_FORMAT(log_date, '%%Y-%%m'), MIN(KEP_P_kW), MAX(KEP_P_kW),
                    MIN(Tr1_P_kW), MAX(Tr1_P_kW), MIN(Tr2_P_kW), MAX(Tr2_P_kW), MIN(Tr3_P_kW), MAX(Tr3_P_kW)
                    FROM raw_data WHERE log_date LIKE %s GROUP BY DATE_FORMAT(log_date, '%%Y-%%m') ORDER BY DATE_FORMAT(log_date, '%%Y-%%m') DESC
                """
                c.execute(query, (f"{target}%",))
                
            rows = c.fetchall()
            self.table_peak.setRowCount(len(rows))
            for r_idx, row in enumerate(rows):
                for c_idx, val in enumerate(row):
                    item = QTableWidgetItem(f"{val:.2f}" if isinstance(val, float) else str(val))
                    item.setTextAlignment(Qt.AlignCenter)
                    self.table_peak.setItem(r_idx, c_idx, item)
            c.close(); conn.close()
        except Exception as e:
            print(f"피크 데이터 로딩 에러: {e}")

    def on_peak_row_double_clicked(self, row, column):
        if not self.radio_peak_month.isChecked():
            QMessageBox.information(self, "안내", "상세 원자료(1분 단위) 조회는 '월간 조회' 모드에서 날짜를 클릭할 때만 가능합니다.")
            return
        target_date = self.table_peak.item(row, 0).text()
        dialog = RawDataDetailDialog(target_date, self)
        dialog.exec_()

    # -----------------------------------------------------------------
    # [탭 2] 전력량(kWh) 사용량 분석
    # -----------------------------------------------------------------
    def init_billing_tab(self):
        layout = QVBoxLayout(self.tab_billing)
        
        ctrl_layout = QHBoxLayout()
        
        self.radio_bill_month = QRadioButton("월간 청구분 (전월 17일 ~ 당월 16일)")
        self.radio_bill_year = QRadioButton("연간 총괄 (1월 ~ 12월 청구분)")
        self.radio_bill_month.setChecked(True)
        self.radio_bill_month.toggled.connect(self.toggle_bill_ui)
        
        ctrl_layout.addWidget(self.radio_bill_month)
        ctrl_layout.addWidget(self.radio_bill_year)
        ctrl_layout.addSpacing(20)
        
        self.combo_bill_month = QComboBox()
        self.combo_bill_year = QComboBox()
        
        now = datetime.datetime.now()
        for i in range(12):
            self.combo_bill_month.addItem((now - datetime.timedelta(days=30*i)).strftime("%Y-%m"))
        for i in range(5):
            self.combo_bill_year.addItem(str(now.year - i))
            
        self.combo_bill_year.setVisible(False)
        
        ctrl_layout.addWidget(self.combo_bill_month)
        ctrl_layout.addWidget(self.combo_bill_year)
        
        btn_search_bill = QPushButton("조회")
        btn_search_bill.clicked.connect(self.load_billing_data)
        ctrl_layout.addWidget(btn_search_bill)
        
        self.lbl_total_kwh = QLabel("총 사용량: - kWh")
        self.lbl_total_kwh.setStyleSheet("font-size: 16px; font-weight: bold; color: #2980b9; margin-left: 20px;")
        ctrl_layout.addWidget(self.lbl_total_kwh)
        
        ctrl_layout.addStretch()
        layout.addLayout(ctrl_layout)

        self.table_bill = QTableWidget()
        self.table_bill.setColumnCount(5)
        self.table_bill.setHorizontalHeaderLabels(["구분 (날짜/청구월)", "시작지침(kWh)", "마감지침(kWh)", "사용량(kWh)", "누계 사용량(kWh)"])
        self.table_bill.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        layout.addWidget(self.table_bill)

        self.load_billing_data()

    def toggle_bill_ui(self):
        if self.radio_bill_month.isChecked():
            self.combo_bill_month.setVisible(True)
            self.combo_bill_year.setVisible(False)
        else:
            self.combo_bill_month.setVisible(False)
            self.combo_bill_year.setVisible(True)

    def load_billing_data(self):
        is_monthly = self.radio_bill_month.isChecked()
        try:
            conn = db_manager.get_db_raw_connection()
            c = conn.cursor()
            
            if is_monthly:
                target_month_str = self.combo_bill_month.currentText()
                year, month = map(int, target_month_str.split('-'))
                
                if month == 1: start_date = f"{year-1}-12-17"
                else: start_date = f"{year}-{month-1:02d}-17"
                end_date = f"{year}-{month:02d}-16"
                
                query = """
                    SELECT DATE_FORMAT(log_date, '%%Y-%%m-%%d'), MIN(KEP_P_kWh), MAX(KEP_P_kWh),
                    MAX(KEP_P_kWh) - MIN(KEP_P_kWh) AS daily_usage
                    FROM raw_data WHERE log_date BETWEEN %s AND %s GROUP BY log_date ORDER BY log_date ASC
                """
                c.execute(query, (start_date, end_date))
                rows = c.fetchall()
                
                self.table_bill.setRowCount(len(rows))
                total_usage = 0.0
                cumulative_usage = 0.0 
                
                for r_idx, row in enumerate(rows):
                    date_val, min_kwh, max_kwh, usage = row
                    if usage < 0: usage = 0.0 
                    total_usage += usage
                    cumulative_usage += usage 
                    
                    self.set_billing_row(r_idx, str(date_val), min_kwh, max_kwh, usage, limit=5000.0, cumulative=cumulative_usage)
                    
                self.lbl_total_kwh.setText(f"총 사용량 ({start_date} ~ {end_date}): {total_usage:,.1f} kWh")
                
            else:
                target_year = int(self.combo_bill_year.currentText())
                self.table_bill.setRowCount(12)
                total_usage = 0.0
                cumulative_usage = 0.0 
                
                for month_idx in range(1, 13):
                    if month_idx == 1: start_date = f"{target_year-1}-12-17"
                    else: start_date = f"{target_year}-{month_idx-1:02d}-17"
                    end_date = f"{target_year}-{month_idx:02d}-16"
                    
                    query = """
                        SELECT MIN(KEP_P_kWh), MAX(KEP_P_kWh), MAX(KEP_P_kWh) - MIN(KEP_P_kWh)
                        FROM raw_data WHERE log_date BETWEEN %s AND %s
                    """
                    c.execute(query, (start_date, end_date))
                    row = c.fetchone()
                    
                    if row and row[0] is not None:
                        min_kwh, max_kwh, usage = row
                        if usage < 0: usage = 0.0
                    else:
                        min_kwh, max_kwh, usage = 0.0, 0.0, 0.0
                        
                    total_usage += usage
                    cumulative_usage += usage 
                    title_str = f"{month_idx}월 청구분\n({start_date} ~ {end_date})"
                    
                    self.set_billing_row(month_idx - 1, title_str, min_kwh, max_kwh, usage, limit=150000.0, cumulative=cumulative_usage)

                self.lbl_total_kwh.setText(f"{target_year}년 총 전력 사용량: {total_usage:,.1f} kWh")

            c.close(); conn.close()
        except Exception as e:
            print(f"전력량 데이터 로딩 에러: {e}")

    def set_billing_row(self, r_idx, title, min_kwh, max_kwh, usage, limit, cumulative):
        item_title = QTableWidgetItem(title)
        item_min = QTableWidgetItem(f"{min_kwh:.1f}")
        item_max = QTableWidgetItem(f"{max_kwh:.1f}")
        item_usage = QTableWidgetItem(f"{usage:.1f}")
        item_cum = QTableWidgetItem(f"{cumulative:.1f}")
        
        for item in [item_title, item_min, item_max, item_usage, item_cum]:
            item.setTextAlignment(Qt.AlignCenter)
        
        if usage > limit:
            item_usage.setForeground(Qt.red)
            item_usage.setFont(QtGui.QFont("Arial", 10, QtGui.QFont.Bold))
            
        self.table_bill.setItem(r_idx, 0, item_title)
        self.table_bill.setItem(r_idx, 1, item_min)
        self.table_bill.setItem(r_idx, 2, item_max)
        self.table_bill.setItem(r_idx, 3, item_usage)
        self.table_bill.setItem(r_idx, 4, item_cum)

    # =====================================================================
    # 🌟 엑셀 A4 사이즈 맞춤 자동 출력 기능 (파일명 자동 지정 개선)
    # =====================================================================
    def export_to_excel(self):
        if openpyxl is None:
            QMessageBox.critical(self, "라이브러리 누락", "openpyxl 라이브러리가 설치되어 있지 않습니다.\n명령 프롬프트에서 'pip install openpyxl'을 실행하세요.")
            return

        current_tab_index = self.tabs.currentIndex()
        timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M")
        
        # 💡 [핵심] 현재 선택된 탭과 조회 조건(월간/연간)을 읽어서 파일명에 반영합니다.
        if current_tab_index == 0:
            target_table = self.table_peak
            if self.radio_peak_month.isChecked():
                search_target = self.combo_peak_month.currentText()
                report_title = f"전력_피크_월간분석_보고서({search_target})"
            else:
                search_target = self.combo_peak_year.currentText()
                report_title = f"전력_피크_연간분석_보고서({search_target}년)"
        else:
            target_table = self.table_bill
            if self.radio_bill_month.isChecked():
                search_target = self.combo_bill_month.currentText()
                report_title = f"전력량_청구월간_보고서({search_target})"
            else:
                search_target = self.combo_bill_year.currentText()
                report_title = f"전력량_청구연간_보고서({search_target}년)"

        # 완성된 기본 파일명 생성
        default_filename = f"{report_title}_{timestamp}.xlsx"
        save_path, _ = QFileDialog.getSaveFileName(self, "엑셀 파일 저장 위치 선택", default_filename, "Excel Files (*.xlsx)")
        
        if not save_path:
            return

        try:
            wb = openpyxl.Workbook()
            ws = wb.active
            ws.title = "통계 보고서"

            # A4 용지에 꽉 차게 인쇄되도록 페이지 설정 (가로 방향, 1페이지 너비 맞춤)
            ws.page_setup.paperSize = ws.PAPERSIZE_A4
            ws.page_setup.orientation = ws.ORIENTATION_LANDSCAPE
            ws.page_setup.fitToWidth = 1
            ws.page_setup.fitToHeight = 0 
            
            # 여백 최소화
            ws.page_margins.left = 0.25
            ws.page_margins.right = 0.25
            ws.page_margins.top = 0.75
            ws.page_margins.bottom = 0.75

            row_count = target_table.rowCount()
            col_count = target_table.columnCount()

            # 1. 헤더 (열 제목) 추출 및 서식 적용
            headers = [target_table.horizontalHeaderItem(c).text() for c in range(col_count)]
            ws.append(headers)
            
            header_fill = PatternFill(start_color="D9E1F2", end_color="D9E1F2", fill_type="solid")
            header_font = Font(bold=True)
            thin_border = Border(left=Side(style='thin'), right=Side(style='thin'), 
                                 top=Side(style='thin'), bottom=Side(style='thin'))

            for col_idx in range(1, col_count + 1):
                cell = ws.cell(row=1, column=col_idx)
                cell.fill = header_fill
                cell.font = header_font
                cell.alignment = Alignment(horizontal="center", vertical="center")
                cell.border = thin_border
                ws.column_dimensions[openpyxl.utils.get_column_letter(col_idx)].width = 18

            # 2. 데이터 행 삽입 및 서식 적용
            for r in range(row_count):
                row_data = []
                for c in range(col_count):
                    item = target_table.item(r, c)
                    text = item.text() if item else ""
                    try:
                        val = float(text.replace(',', ''))
                        row_data.append(val)
                    except ValueError:
                        row_data.append(text)
                
                ws.append(row_data)
                
                current_row = r + 2
                for col_idx in range(1, col_count + 1):
                    cell = ws.cell(row=current_row, column=col_idx)
                    cell.alignment = Alignment(horizontal="center", vertical="center", wrap_text=True)
                    cell.border = thin_border

            wb.save(save_path)
            QMessageBox.information(self, "출력 완료", f"A4 인쇄용 엑셀 파일이 성공적으로 저장되었습니다.\n\n저장 위치:\n{save_path}")

        except Exception as e:
            QMessageBox.critical(self, "출력 실패", f"엑셀 파일 생성 중 오류가 발생했습니다.\n\n에러 내용: {e}")