# ui_report_temp.py
import datetime
from PyQt5.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout, QTabWidget, 
                             QWidget, QLabel, QPushButton, QTableWidget, QTableWidgetItem,
                             QHeaderView, QComboBox, QMessageBox, QRadioButton, QFileDialog,
                             QListWidget, QAbstractItemView)
from PyQt5.QtCore import Qt
from PyQt5 import QtGui
import db_manager

# 엑셀 출력을 위한 openpyxl
try:
    import openpyxl
    from openpyxl.styles import Font, Alignment, Border, Side, PatternFill
except ImportError:
    openpyxl = None

# 🌟 [신규 추가] matplotlib 및 pandas 임포트 (기존 pyqtgraph 대체)
import pandas as pd
import matplotlib.pyplot as plt
from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg as FigureCanvas
from matplotlib.figure import Figure
import matplotlib.ticker as ticker

# 한글 폰트 및 마이너스 부호 깨짐 방지
plt.rcParams['font.family'] = 'Malgun Gothic'
plt.rcParams['axes.unicode_minus'] = False


class TempReportDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("🌡 온도 및 부하 최고/최저 상관관계 분석 보고서")
        self.resize(1400, 850)
        self.setWindowFlags(self.windowFlags() | Qt.WindowMaximizeButtonHint | Qt.WindowMinimizeButtonHint)
        
        # 데이터를 임시 저장할 변수 (리스트 박스 클릭 시 매번 DB를 조회하지 않도록 함)
        self.current_rows = []
        
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
        self.tabs.addTab(self.tab_graph, "📈 온도 추이 맞춤형 시각화")

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
        
        # 마지막에 데이터 로딩
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
        # 그래프에서 사용할 데이터 항목 이름들을 멤버 변수로 정의합니다.
        self.data_labels = [
            "외기 최저(℃)", "외기 최고(℃)", 
            "실내 최저(℃)", "실내 최고(℃)", 
            "TR1부하 최저", "TR1부하 최고", "TR1온도 최저", "TR1온도 최고", 
            "TR2부하 최저", "TR2부하 최고", "TR2온도 최저", "TR2온도 최고", 
            "TR3부하 최저", "TR3부하 최고", "TR3온도 최저", "TR3온도 최고"
        ]
        
        headers = ["구분(날짜/월)"] + self.data_labels
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

    # =====================================================================
    # 🌟 [핵심 개편] matplotlib 기반의 리스트 박스 다중 선택 이중축 그래프
    # =====================================================================
    def init_graph_tab(self):
        layout = QVBoxLayout(self.tab_graph)
        
        # 1. 상단 컨트롤 영역 (리스트 박스)
        graph_ctrl = QHBoxLayout()
        
        # [왼쪽 축] 표시할 전체 데이터 선택
        self.data_selector = QListWidget()
        self.data_selector.setSelectionMode(QAbstractItemView.MultiSelection) 
        self.data_selector.addItems(self.data_labels)
        self.data_selector.setMaximumHeight(100) 
        
        # [오른쪽 이중축] 왼쪽에서 선택된 항목 중 오른쪽 축에 그릴 항목 선택
        self.right_axis_selector = QListWidget()
        self.right_axis_selector.setSelectionMode(QAbstractItemView.MultiSelection)
        self.right_axis_selector.setMaximumHeight(100) 
        
        graph_ctrl.addWidget(QLabel("<b>[1] 그래프로 그릴 항목 선택:</b><br>(기본 왼쪽 축)"))
        graph_ctrl.addWidget(self.data_selector)
        graph_ctrl.addWidget(QLabel("<b>[2] 오른쪽 보조축(이중축)으로<br>보낼 항목 선택:</b>")) 
        graph_ctrl.addWidget(self.right_axis_selector)
        
        layout.addLayout(graph_ctrl)

        # 2. matplotlib 캔버스 생성
        self.canvas = FigureCanvas(Figure(figsize=(10, 5)))
        self.ax = self.canvas.figure.add_subplot(111)
        layout.addWidget(self.canvas)

        # 3. 이벤트 연결
        self.data_selector.itemSelectionChanged.connect(self.sync_right_axis_list)
        self.right_axis_selector.itemSelectionChanged.connect(self.trigger_graph_update)

        # 4. 초기 기본 선택 세팅 (사용자가 빈 화면을 보지 않도록 유도)
        self.data_selector.blockSignals(True)
        self.data_selector.item(1).setSelected(True) # 외기 최고
        self.data_selector.item(3).setSelected(True) # 실내 최고
        self.data_selector.item(7).setSelected(True) # TR1 온도 최고
        self.data_selector.blockSignals(False)
        self.sync_right_axis_list() # 오른쪽 축 리스트 업데이트

    def sync_right_axis_list(self):
        """왼쪽에서 선택된 항목들만 오른쪽 축 선택 박스에 나타나도록 동기화"""
        self.data_selector.blockSignals(True)
        self.right_axis_selector.blockSignals(True)
        try:
            prev_selected = [item.text() for item in self.right_axis_selector.selectedItems()]
            left_selected = [item.text() for item in self.data_selector.selectedItems()]
            
            self.right_axis_selector.clear()
            if left_selected:
                self.right_axis_selector.addItems(left_selected)
                # 이전에 이중축으로 선택해둔 항목이 여전히 있다면 선택 유지
                for i in range(self.right_axis_selector.count()):
                    item = self.right_axis_selector.item(i)
                    if item.text() in prev_selected:
                        item.setSelected(True)
        finally:
            self.data_selector.blockSignals(False)
            self.right_axis_selector.blockSignals(False)
            
        self.trigger_graph_update()

    def trigger_graph_update(self):
        """리스트 박스 클릭 시 DB 조회 없이 기존 데이터(self.current_rows)로 그래프만 다시 그림"""
        if hasattr(self, 'current_rows') and self.current_rows:
            self.update_graph(self.current_rows)

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
            self.current_rows = rows # 💡 조회된 데이터를 클래스 변수에 임시 저장
            
            # 테이블 데이터 채우기
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
            
            # 테이블이 완성되면 그래프 그리기 호출
            self.update_graph(rows)
            c.close(); conn.close()
            
        except Exception as e:
            print(f"온도 데이터 로딩 에러: {e}")
            QMessageBox.warning(self, "데이터 조회 오류", f"데이터베이스 조회 중 문제가 발생했습니다.\n에러: {e}")

    def update_graph(self, rows):
        """저장된 데이터를 pandas DataFrame으로 변환하여 이중축 그래프를 그립니다."""
        if not hasattr(self, 'canvas'): return
        
        self.canvas.figure.clf()
        self.ax = self.canvas.figure.add_subplot(111)
        
        if not rows:
            self.ax.text(0.5, 0.5, "조회된 데이터가 없습니다.", ha='center', va='center')
            self.canvas.draw()
            return
            
        selected_items = self.data_selector.selectedItems()
        if not selected_items:
            self.ax.text(0.5, 0.5, "위 리스트에서 그래프로 확인할 항목을 1개 이상 선택해 주세요.", ha='center', va='center')
            self.canvas.draw()
            return

        # 1. 튜플로 된 rows를 pandas DataFrame으로 깔끔하게 변환
        cols = ["날짜"] + self.data_labels
        df = pd.DataFrame(rows, columns=cols)
        
        # 2. X축 문자열 날짜를 축소하여 표기하기 위한 전처리
        df["날짜"] = df["날짜"].astype(str).apply(lambda x: x[5:] if len(x) == 10 else x)
        
        # 3. 그릴 컬럼 분류
        target_cols = [item.text() for item in selected_items]
        right_cols = [item.text() for item in self.right_axis_selector.selectedItems()]
        right_cols = [col for col in right_cols if col in target_cols] 
        left_cols = [col for col in target_cols if col not in right_cols]

        all_lines = []
        color_cycle = plt.rcParams['axes.prop_cycle'].by_key()['color']
        color_idx = 0

        # [기본 축 - 왼쪽 렌더링]
        for col in left_cols:
            if col in df.columns:
                current_color = color_cycle[color_idx % len(color_cycle)]
                # 온도는 실선(solid)과 원형 마커(o)
                line = self.ax.plot(df["날짜"], df[col], marker='o', markersize=4, 
                                    color=current_color, label=col)
                all_lines += line
                color_idx += 1
        
        if left_cols:
            self.ax.set_ylabel("기본 온도/부하", color='#2c3e50', fontweight='bold', fontsize=11)
            self.ax.tick_params(axis='y', labelcolor='#2c3e50')
        else:
            self.ax.yaxis.set_visible(False)

        # [보조 축(이중축) - 오른쪽 렌더링]
        if right_cols:
            ax2 = self.ax.twinx()
            for col in right_cols:
                if col in df.columns:
                    current_color = color_cycle[color_idx % len(color_cycle)]
                    # 이중축은 점선(--)과 세모 마커(^)로 구분
                    line = ax2.plot(df["날짜"], df[col], marker='^', markersize=5, linestyle='--', 
                                    color=current_color, label=f"{col} (우측축)")
                    all_lines += line
                    color_idx += 1 
            
            ax2.set_ylabel("비교용 보조축 데이터", color='#c0392b', fontweight='bold', fontsize=11)
            ax2.tick_params(axis='y', labelcolor='#c0392b')
            ax2.grid(False)

        # 범례 표시 로직
        if all_lines:
            labels = [l.get_label() for l in all_lines]
            if 'ax2' in locals():
                leg = ax2.legend(all_lines, labels, loc='upper left', bbox_to_anchor=(1.05, 1))
            else:
                leg = self.ax.legend(all_lines, labels, loc='upper left', bbox_to_anchor=(1.05, 1))
            
            # 그래프 영역 밖에 범례가 그려지도록 레이아웃 자동 조절
            self.canvas.figure.tight_layout()
            
        # X축 날짜 겹침 방지 (최대 10~15개 내외로 자동 조절)
        self.ax.xaxis.set_major_locator(ticker.MaxNLocator(nbins=12))
        self.ax.grid(True, linestyle=':', alpha=0.6)
        
        # 글씨가 겹치지 않게 X축 텍스트를 약간 기울임
        self.canvas.figure.autofmt_xdate(rotation=45) 
        
        self.canvas.draw()


    # =====================================================================
    # 엑셀 출력 기능 (유지)
    # =====================================================================
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