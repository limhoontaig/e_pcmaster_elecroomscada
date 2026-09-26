# ui_report_power.py
import datetime
from PyQt5.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout, QTabWidget, 
                             QWidget, QLabel, QPushButton, QTableWidget, QTableWidgetItem,
                             QHeaderView, QComboBox, QMessageBox, QRadioButton, QButtonGroup)
from PyQt5.QtCore import Qt
from PyQt5 import QtGui
import db_manager

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
# 📊 2. 메인 전력 보고서 창 (월간/연간 통합)
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
        self.tabs.setStyleSheet("QTabBar::tab { font-size: 12px; font-weight: bold; padding: 10px 20px; }")
        
        self.tab_peak = QWidget()
        self.init_peak_tab()
        self.tabs.addTab(self.tab_peak, "📈 피크(kW) 최고/최저 분석")
        
        self.tab_billing = QWidget()
        self.init_billing_tab()
        self.tabs.addTab(self.tab_billing, "📆 전력량(kWh) 사용량 분석")

        main_layout.addWidget(self.tabs)

        btn_layout = QHBoxLayout()
        btn_layout.addStretch()
        btn_close = QPushButton("닫기")
        btn_close.setStyleSheet("background-color: #7f8c8d; color: white; font-weight: bold; padding: 8px 30px;")
        btn_close.clicked.connect(self.accept)
        btn_layout.addWidget(btn_close)
        main_layout.addLayout(btn_layout)

    # -----------------------------------------------------------------
    # [탭 1] 피크(kW) 최고/최저 분석 (월간/연간)
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
                    SELECT 
                        DATE_FORMAT(log_date, '%%Y-%%m-%%d'),
                        MIN(KEP_P_kW), MAX(KEP_P_kW),
                        MIN(Tr1_P_kW), MAX(Tr1_P_kW),
                        MIN(Tr2_P_kW), MAX(Tr2_P_kW),
                        MIN(Tr3_P_kW), MAX(Tr3_P_kW)
                    FROM raw_data 
                    WHERE log_date LIKE %s
                    GROUP BY log_date
                    ORDER BY log_date DESC
                """
                c.execute(query, (f"{target}%",))
            else:
                target = self.combo_peak_year.currentText()
                query = """
                    SELECT 
                        DATE_FORMAT(log_date, '%%Y-%%m'),
                        MIN(KEP_P_kW), MAX(KEP_P_kW),
                        MIN(Tr1_P_kW), MAX(Tr1_P_kW),
                        MIN(Tr2_P_kW), MAX(Tr2_P_kW),
                        MIN(Tr3_P_kW), MAX(Tr3_P_kW)
                    FROM raw_data 
                    WHERE log_date LIKE %s
                    GROUP BY DATE_FORMAT(log_date, '%%Y-%%m')
                    ORDER BY DATE_FORMAT(log_date, '%%Y-%%m') DESC
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
    # [탭 2] 전력량(kWh) 분석 로직 (월간/연간)
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
        # 💡 [핵심] 컬럼 개수를 5개로 늘리고 누계 사용량 추가
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
                
                if month == 1:
                    start_date = f"{year-1}-12-17"
                else:
                    start_date = f"{year}-{month-1:02d}-17"
                end_date = f"{year}-{month:02d}-16"
                
                query = """
                    SELECT 
                        DATE_FORMAT(log_date, '%%Y-%%m-%%d'),
                        MIN(KEP_P_kWh), MAX(KEP_P_kWh),
                        MAX(KEP_P_kWh) - MIN(KEP_P_kWh) AS daily_usage
                    FROM raw_data 
                    WHERE log_date BETWEEN %s AND %s
                    GROUP BY log_date
                    ORDER BY log_date ASC
                """
                c.execute(query, (start_date, end_date))
                rows = c.fetchall()
                
                self.table_bill.setRowCount(len(rows))
                total_usage = 0.0
                cumulative_usage = 0.0 # 💡 누계 사용량 변수 추가
                
                for r_idx, row in enumerate(rows):
                    date_val, min_kwh, max_kwh, usage = row
                    if usage < 0: usage = 0.0 
                    total_usage += usage
                    cumulative_usage += usage # 누적 합산
                    
                    self.set_billing_row(r_idx, str(date_val), min_kwh, max_kwh, usage, limit=5000.0, cumulative=cumulative_usage)
                    
                self.lbl_total_kwh.setText(f"총 사용량 ({start_date} ~ {end_date}): {total_usage:,.1f} kWh")
                
            else:
                target_year = int(self.combo_bill_year.currentText())
                self.table_bill.setRowCount(12)
                total_usage = 0.0
                cumulative_usage = 0.0 # 💡 연간 누계 사용량 변수 추가
                
                for month_idx in range(1, 13):
                    if month_idx == 1:
                        start_date = f"{target_year-1}-12-17"
                    else:
                        start_date = f"{target_year}-{month_idx-1:02d}-17"
                    end_date = f"{target_year}-{month_idx:02d}-16"
                    
                    query = """
                        SELECT 
                            MIN(KEP_P_kWh), MAX(KEP_P_kWh), MAX(KEP_P_kWh) - MIN(KEP_P_kWh)
                        FROM raw_data 
                        WHERE log_date BETWEEN %s AND %s
                    """
                    c.execute(query, (start_date, end_date))
                    row = c.fetchone()
                    
                    if row and row[0] is not None:
                        min_kwh, max_kwh, usage = row
                        if usage < 0: usage = 0.0
                    else:
                        min_kwh, max_kwh, usage = 0.0, 0.0, 0.0
                        
                    total_usage += usage
                    cumulative_usage += usage # 누적 합산
                    title_str = f"{month_idx}월 청구분\n({start_date} ~ {end_date})"
                    
                    self.set_billing_row(month_idx - 1, title_str, min_kwh, max_kwh, usage, limit=150000.0, cumulative=cumulative_usage)

                self.lbl_total_kwh.setText(f"{target_year}년 총 전력 사용량: {total_usage:,.1f} kWh")

            c.close(); conn.close()
        except Exception as e:
            print(f"전력량 데이터 로딩 에러: {e}")

    # 💡 [핵심] cumulative 파라미터 추가 및 5번째 컬럼(열) 데이터 삽입
    def set_billing_row(self, r_idx, title, min_kwh, max_kwh, usage, limit, cumulative):
        item_title = QTableWidgetItem(title)
        item_min = QTableWidgetItem(f"{min_kwh:.1f}")
        item_max = QTableWidgetItem(f"{max_kwh:.1f}")
        item_usage = QTableWidgetItem(f"{usage:.1f}")
        item_cum = QTableWidgetItem(f"{cumulative:.1f}") # 누계 데이터
        
        for item in [item_title, item_min, item_max, item_usage, item_cum]:
            item.setTextAlignment(Qt.AlignCenter)
        
        if usage > limit:
            item_usage.setForeground(Qt.red)
            item_usage.setFont(QtGui.QFont("Arial", 10, QtGui.QFont.Bold))
            
        self.table_bill.setItem(r_idx, 0, item_title)
        self.table_bill.setItem(r_idx, 1, item_min)
        self.table_bill.setItem(r_idx, 2, item_max)
        self.table_bill.setItem(r_idx, 3, item_usage)
        self.table_bill.setItem(r_idx, 4, item_cum) # 5번째 열에 삽입