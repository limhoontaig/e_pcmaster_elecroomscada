# ui_report_temp.py
import datetime
from PyQt5.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout, QTabWidget, 
                             QWidget, QLabel, QPushButton, QTableWidget, QTableWidgetItem,
                             QHeaderView, QComboBox, QMessageBox, QRadioButton, QFileDialog)
from PyQt5.QtCore import Qt
from PyQt5 import QtGui
import db_manager

# 엑셀 출력을 위한 openpyxl
try:
    import openpyxl
    from openpyxl.styles import Font, Alignment, Border, Side, PatternFill
except ImportError:
    openpyxl = None

# 그래프 시각화를 위한 pyqtgraph
try:
    import pyqtgraph as pg
except ImportError:
    pg = None


class TempReportDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("🌡 온도 및 부하 최고/최저 상관관계 분석 보고서")
        self.resize(1400, 850)
        self.setWindowFlags(self.windowFlags() | Qt.WindowMaximizeButtonHint | Qt.WindowMinimizeButtonHint)
        self.init_ui()

    def init_ui(self):
        main_layout = QVBoxLayout(self)
        
        title = QLabel("변압기 부하(kW) 및 실내/외/변압기 운전 온도(℃) 최고·최저 분석")
        title.setStyleSheet("font-size: 20px; font-weight: bold; color: #2c3e50;")
        title.setAlignment(Qt.AlignCenter)
        main_layout.addWidget(title)

        self.tabs = QTabWidget()
        self.tabs.setStyleSheet("QTabBar::tab { font-size: 14px; font-weight: bold; padding: 10px 20px; }")
        
        self.tab_table = QWidget()
        self.init_table_tab()
        self.tabs.addTab(self.tab_table, "📋 온도 및 부하 통계 데이터")
        
        self.tab_graph = QWidget()
        self.init_graph_tab()
        self.tabs.addTab(self.tab_graph, "📈 온도 추이 시각화 그래프")

        main_layout.addWidget(self.tabs)

        btn_layout = QHBoxLayout()
        btn_layout.addStretch()
        
        self.btn_export = QPushButton("📊 이 통계를 엑셀로 내보내기")
        self.btn_export.setStyleSheet("background-color: #27ae60; color: white; font-weight: bold; padding: 8px 15px;")
        self.btn_export.clicked.connect(self.export_to_excel)
        btn_layout.addWidget(self.btn_export)
        
        btn_close = QPushButton("닫기")
        btn_close.setStyleSheet("background-color: #7f8c8d; color: white; font-weight: bold; padding: 8px 30px;")
        btn_close.clicked.connect(self.accept)
        btn_layout.addWidget(btn_close)
        
        main_layout.addLayout(btn_layout)
        
        # 💡 UI 구성이 모두 끝난 후 마지막에 데이터 로딩 (에러 방지)
        self.load_data()

    def init_table_tab(self):
        layout = QVBoxLayout(self.tab_table)
        ctrl_layout = QHBoxLayout()
        
        self.radio_month = QRadioButton("월간 조회 (일별 최고/최저)")
        self.radio_year = QRadioButton("연간 조회 (월별 최고/최저)")
        self.radio_month.setChecked(True)
        self.radio_month.toggled.connect(self.toggle_search_ui)
        
        ctrl_layout.addWidget(self.radio_month)
        ctrl_layout.addWidget(self.radio_year)
        ctrl_layout.addSpacing(20)
        
        self.combo_month = QComboBox()
        self.combo_year = QComboBox()
        
        now = datetime.datetime.now()
        for i in range(12):
            self.combo_month.addItem((now - datetime.timedelta(days=30*i)).strftime("%Y-%m"))
        for i in range(5): 
            self.combo_year.addItem(str(now.year - i))
            
        self.combo_year.setVisible(False) 
        
        ctrl_layout.addWidget(self.combo_month)
        ctrl_layout.addWidget(self.combo_year)
        
        btn_search = QPushButton("조회")
        btn_search.clicked.connect(self.load_data)
        ctrl_layout.addWidget(btn_search)
        ctrl_layout.addStretch()
        layout.addLayout(ctrl_layout)

        self.table = QTableWidget()
        headers = [
            "구분(날짜/월)", 
            "외기 최저(℃)", "외기 최고(℃)", 
            "실내 최저(℃)", "실내 최고(℃)", 
            "TR1부하 최저", "TR1부하 최고", "TR1온도 최저", "TR1온도 최고", 
            "TR2부하 최저", "TR2부하 최고", "TR2온도 최저", "TR2온도 최고", 
            "TR3부하 최저", "TR3부하 최고", "TR3온도 최저", "TR3온도 최고"
        ]
        self.table.setColumnCount(len(headers))
        self.table.setHorizontalHeaderLabels(headers)
        
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeToContents)
        
        warning_lbl = QLabel("※ 주의: 실내 최고온도 35℃ 이상, 변압기 최고온도 90℃ 이상 도달 시 적색으로 경고 표시됩니다.")
        warning_lbl.setStyleSheet("color: #c0392b; font-weight: bold;")
        layout.addWidget(warning_lbl)
        layout.addWidget(self.table)

    def toggle_search_ui(self):
        if self.radio_month.isChecked():
            self.combo_month.setVisible(True)
            self.combo_year.setVisible(False)
        else:
            self.combo_month.setVisible(False)
            self.combo_year.setVisible(True)

    def init_graph_tab(self):
        layout = QVBoxLayout(self.tab_graph)
        
        if pg is None:
            layout.addWidget(QLabel("pyqtgraph 라이브러리가 설치되지 않아 그래프를 표시할 수 없습니다.\n'pip install pyqtgraph'를 실행해 주세요."))
            return
            
        pg.setConfigOption('background', 'w')
        pg.setConfigOption('foreground', 'k')
        
        self.plot_widget = pg.PlotWidget(title="기간별 최고/최저 온도 추이 (외기/실내/변압기)")
        
        # 💡 [수정] 범례가 그래프 선을 가리지 않도록 위치(오프셋) 조정
        self.plot_widget.addLegend(offset=(-20, 20))
        
        self.plot_widget.showGrid(x=True, y=True, alpha=0.3)
        self.plot_widget.setLabel('left', '온도 (℃)')
        self.plot_widget.setLabel('bottom', '조회 날짜')
        
        layout.addWidget(self.plot_widget)

    def load_data(self):
        is_monthly = self.radio_month.isChecked()
        try:
            conn = db_manager.get_db_raw_connection()
            c = conn.cursor()
            
            if is_monthly:
                target = self.combo_month.currentText()
                query = """
                    SELECT DATE_FORMAT(log_date, '%%Y-%%m-%%d'), 
                           MIN(`외기온도`), MAX(`외기온도`), 
                           MIN(`실내온도`), MAX(`실내온도`),
                           MIN(`Tr1_P_kW`), MAX(`Tr1_P_kW`), MIN(`Tr1_Temp`), MAX(`Tr1_Temp`), 
                           MIN(`Tr2_P_kW`), MAX(`Tr2_P_kW`), MIN(`Tr2_Temp`), MAX(`Tr2_Temp`), 
                           MIN(`Tr3_P_kW`), MAX(`Tr3_P_kW`), MIN(`Tr3_Temp`), MAX(`Tr3_Temp`)
                    FROM raw_data 
                    WHERE log_date LIKE %s 
                    GROUP BY log_date 
                    ORDER BY log_date ASC
                """
                c.execute(query, (f"{target}%",))
            else:
                target = self.combo_year.currentText()
                query = """
                    SELECT DATE_FORMAT(log_date, '%%Y-%%m'), 
                           MIN(`외기온도`), MAX(`외기온도`), 
                           MIN(`실내온도`), MAX(`실내온도`),
                           MIN(`Tr1_P_kW`), MAX(`Tr1_P_kW`), MIN(`Tr1_Temp`), MAX(`Tr1_Temp`), 
                           MIN(`Tr2_P_kW`), MAX(`Tr2_P_kW`), MIN(`Tr2_Temp`), MAX(`Tr2_Temp`), 
                           MIN(`Tr3_P_kW`), MAX(`Tr3_P_kW`), MIN(`Tr3_Temp`), MAX(`Tr3_Temp`)
                    FROM raw_data 
                    WHERE log_date LIKE %s 
                    GROUP BY DATE_FORMAT(log_date, '%%Y-%%m') 
                    ORDER BY DATE_FORMAT(log_date, '%%Y-%%m') ASC
                """
                c.execute(query, (f"{target}%",))
                
            rows = c.fetchall()
            
            self.table.setRowCount(len(rows))
            for r_idx, row in enumerate(rows):
                for c_idx, val in enumerate(row):
                    item = QTableWidgetItem(f"{val:.1f}" if isinstance(val, float) else str(val))
                    item.setTextAlignment(Qt.AlignCenter)
                    
                    if isinstance(val, float):
                        if c_idx == 4 and val >= 35.0: 
                            item.setForeground(Qt.red)
                            item.setFont(QtGui.QFont("Arial", 10, QtGui.QFont.Bold))
                        elif c_idx in [8, 12, 16] and val >= 90.0: 
                            item.setForeground(Qt.red)
                            item.setFont(QtGui.QFont("Arial", 10, QtGui.QFont.Bold))
                            
                    self.table.setItem(r_idx, c_idx, item)
            
            self.update_graph(rows)
            c.close(); conn.close()
            
        except Exception as e:
            print(f"온도 데이터 로딩 에러: {e}")
            QMessageBox.warning(self, "데이터 조회 오류", f"데이터베이스 조회 중 문제가 발생했습니다.\n에러: {e}")

    def update_graph(self, rows):
        if pg is None: return
        if not hasattr(self, 'plot_widget'): return
        
        self.plot_widget.clear()
        if not rows: return
        
        x_data = list(range(len(rows)))
        
        # 💡 [핵심 추가] X축에 실제 날짜(MM-DD)를 표기하기 위한 라벨 매핑 적용
        x_labels = []
        for i, r in enumerate(rows):
            date_str = str(r[0])
            display_str = date_str[5:] if len(date_str) == 10 else date_str
            x_labels.append((i, display_str))
            
        ax = self.plot_widget.getAxis('bottom')
        ax.setTicks([x_labels])
        
        # 최고/최저 리스트 분리
        out_min = [r[1] if r[1] is not None else 0 for r in rows]
        out_max = [r[2] if r[2] is not None else 0 for r in rows]
        in_min  = [r[3] if r[3] is not None else 0 for r in rows]
        in_max  = [r[4] if r[4] is not None else 0 for r in rows]
        tr1_min = [r[7] if r[7] is not None else 0 for r in rows]
        tr1_max = [r[8] if r[8] is not None else 0 for r in rows]
        
        self.plot_widget.plot(x_data, out_max, pen=pg.mkPen(color='g', width=2), name="외기 최고")
        self.plot_widget.plot(x_data, out_min, pen=pg.mkPen(color='g', width=1, style=Qt.DashLine), name="외기 최저")
        
        self.plot_widget.plot(x_data, in_max, pen=pg.mkPen(color='b', width=2), name="실내 최고")
        self.plot_widget.plot(x_data, in_min, pen=pg.mkPen(color='b', width=1, style=Qt.DashLine), name="실내 최저")
        
        self.plot_widget.plot(x_data, tr1_max, pen=pg.mkPen(color='r', width=2), name="TR1 온도 최고")
        self.plot_widget.plot(x_data, tr1_min, pen=pg.mkPen(color='r', width=1, style=Qt.DashLine), name="TR1 온도 최저")

    def export_to_excel(self):
        if openpyxl is None:
            QMessageBox.critical(self, "라이브러리 누락", "openpyxl 라이브러리가 설치되어 있지 않습니다.\n명령 프롬프트에서 'pip install openpyxl'을 실행하세요.")
            return

        timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M")
        
        if self.radio_month.isChecked():
            search_target = self.combo_month.currentText()
            report_title = f"온도부하_운전통계_월간({search_target})"
        else:
            search_target = self.combo_year.currentText()
            report_title = f"온도부하_운전통계_연간({search_target}년)"

        default_filename = f"{report_title}_{timestamp}.xlsx"
        save_path, _ = QFileDialog.getSaveFileName(self, "엑셀 파일 저장 위치 선택", default_filename, "Excel Files (*.xlsx)")
        
        if not save_path: return

        try:
            wb = openpyxl.Workbook()
            ws = wb.active
            ws.title = "온도 부하 데이터 통계"

            ws.page_setup.paperSize = ws.PAPERSIZE_A4
            ws.page_setup.orientation = ws.ORIENTATION_LANDSCAPE
            ws.page_setup.fitToWidth = 1
            ws.page_setup.fitToHeight = 0 
            
            ws.page_margins.left = 0.25
            ws.page_margins.right = 0.25
            ws.page_margins.top = 0.75
            ws.page_margins.bottom = 0.75

            col_count = self.table.columnCount()
            last_col_letter = openpyxl.utils.get_column_letter(col_count)
            
            title_range = f'A1:{last_col_letter}1'
            ws.merge_cells(title_range)
            cell_title = ws['A1']
            cell_title.value = "래미안개포루체하임아파트 전기설비 운전 온도(최고/최저) 데이터 통계"
            cell_title.font = Font(size=18, bold=True)
            cell_title.alignment = Alignment(horizontal="center", vertical="center")
            ws.row_dimensions[1].height = 35

            ws.merge_cells(f'A2:F2')
            ws['A2'].value = f"■ 조회 기준: {search_target}"
            ws['A2'].font = Font(bold=True)
            ws['A2'].alignment = Alignment(horizontal="left", vertical="center")
            
            date_range = f'G2:{last_col_letter}2'
            ws.merge_cells(date_range)
            print_time = datetime.datetime.now().strftime("%Y년 %m월 %d일 %H:%M")
            ws['G2'].value = f"■ 출력 일시: {print_time}"
            ws['G2'].font = Font(bold=True)
            ws['G2'].alignment = Alignment(horizontal="right", vertical="center")
            ws.row_dimensions[2].height = 20

            ws.row_dimensions[3].height = 10

            header_fill = PatternFill(start_color="D9E1F2", end_color="D9E1F2", fill_type="solid")
            header_font = Font(bold=True)
            thin_border = Border(left=Side(style='thin'), right=Side(style='thin'), 
                                 top=Side(style='thin'), bottom=Side(style='thin'))

            headers = [self.table.horizontalHeaderItem(c).text() for c in range(col_count)]
            for col_idx, h_text in enumerate(headers, start=1):
                cell = ws.cell(row=4, column=col_idx, value=h_text)
                cell.fill = header_fill
                cell.font = header_font
                cell.alignment = Alignment(horizontal="center", vertical="center", wrap_text=True)
                cell.border = thin_border
                ws.column_dimensions[openpyxl.utils.get_column_letter(col_idx)].width = 11 
                
            ws.column_dimensions['A'].width = 15 

            row_count = self.table.rowCount()
            for r in range(row_count):
                current_row = r + 5
                for c in range(col_count):
                    item = self.table.item(r, c)
                    text = item.text() if item else ""
                    
                    try:
                        val = float(text.replace(',', ''))
                    except ValueError:
                        val = text
                        
                    cell = ws.cell(row=current_row, column=c+1, value=val)
                    cell.alignment = Alignment(horizontal="center", vertical="center")
                    cell.border = thin_border
                    
                    if isinstance(val, float):
                        if (c == 4 and val >= 35.0) or (c in [8, 12, 16] and val >= 90.0):
                            cell.font = Font(color="FF0000", bold=True)

            wb.save(save_path)
            QMessageBox.information(self, "출력 완료", f"A4 인쇄용 온도(최고/최저) 통계 엑셀 파일이 저장되었습니다.\n\n저장 위치:\n{save_path}")

        except Exception as e:
            QMessageBox.critical(self, "출력 실패", f"엑셀 파일 생성 중 오류가 발생했습니다.\n\n에러 내용: {e}")