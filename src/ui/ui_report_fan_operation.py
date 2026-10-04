# src/ui/ui_report_fan_operation.py
import datetime
from PyQt5.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout, QWidget, QLabel, 
                             QPushButton, QTableWidget, QTableWidgetItem, QHeaderView, 
                             QComboBox, QMessageBox, QRadioButton, QFileDialog)
from PyQt5.QtCore import Qt
from PyQt5 import QtGui

from shared import db_manager

try:
    import openpyxl
    from openpyxl.styles import Font, Alignment, Border, Side, PatternFill
except ImportError:
    openpyxl = None

# =====================================================================
# 🔍 1. 원자료 상세 보기 팝업창 (날짜 및 기기 셀 더블클릭 시 실행)
# =====================================================================
class FanDataDetailDialog(QDialog):
    # 🌟 수정: 특정 기기(target_equip) 정보도 받을 수 있도록 파라미터 추가
    def __init__(self, target_date, target_equip=None, equip_kor_name="", parent=None):
        super().__init__(parent)
        self.target_date = target_date
        self.target_equip = target_equip
        self.equip_kor_name = equip_kor_name
        
        # 기기명이 있으면 창 제목에 기기명 표시, 없으면 전체 표시
        title_suffix = f" - {self.equip_kor_name}" if self.equip_kor_name else " (전체 설비)"
        self.setWindowTitle(f"🔍 {target_date} 냉각/환기설비 상세 가동 이력{title_suffix}")
        self.resize(900, 600)
        self.init_ui()
        self.load_detail_data()

    def init_ui(self):
        layout = QVBoxLayout(self)
        
        title_suffix = f" [{self.equip_kor_name}]" if self.equip_kor_name else " 전체 설비"
        lbl_title = QLabel(f"[{self.target_date}]{title_suffix} 상세 가동(ON/OFF) 이력")
        lbl_title.setStyleSheet("font-size: 16px; font-weight: bold; color: #2980b9;")
        layout.addWidget(lbl_title)

        self.table = QTableWidget()
        self.table.setColumnCount(5)
        self.table.setHorizontalHeaderLabels(["발생 시간", "종료 시간", "설비명", "가동 시간(초)", "가동 시간(분)"])
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        layout.addWidget(self.table)

        btn_close = QPushButton("닫기")
        btn_close.clicked.connect(self.accept)
        layout.addWidget(btn_close)

    def load_detail_data(self):
        try:
            conn = db_manager.get_db_raw_connection()
            c = conn.cursor()
            
            # 🌟 수정: 특정 기기가 선택되었으면 해당 기기만, 아니면 전체 기기를 필터링 조건으로 설정
            if self.target_equip:
                equip_in_clause = self.target_equip
            else:
                equip_names = ['SF_operation', 'EF_operation', 'aircon01_operation', 'aircon02_operation', 'tr1_fan_on', 'tr2_fan_on', 'tr3_fan_on']
                equip_in_clause = "','".join(equip_names)
            
            query = f"""
                SELECT 
                    DATE_FORMAT(occurred_at, '%%H:%%i:%%s') as start_time,
                    IFNULL(DATE_FORMAT(cleared_at, '%%H:%%i:%%s'), '가동중') as end_time,
                    equipment_name,
                    duration_seconds,
                    ROUND(duration_seconds / 60.0, 1) as duration_min
                FROM alarm_event_logs 
                WHERE DATE_FORMAT(occurred_at, '%%Y-%%m-%%d') = %s 
                  AND equipment_name IN ('{equip_in_clause}')
                  AND event_type = 'OPERATION'
                ORDER BY occurred_at ASC
            """
            c.execute(query, (self.target_date,))
            rows = c.fetchall()
            
            self.table.setRowCount(len(rows))
            for r_idx, row in enumerate(rows):
                for c_idx, val in enumerate(row):
                    txt = str(val) if val is not None else "-"
                    item = QTableWidgetItem(txt)
                    item.setTextAlignment(Qt.AlignCenter)
                    self.table.setItem(r_idx, c_idx, item)
                    
            c.close(); conn.close()
        except Exception as e:
            print(f"상세 데이터 로딩 에러: {e}")


# =====================================================================
# 📊 2. 메인 팬 가동 통계 보고서 창
# =====================================================================
class FanOperationReportDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("💨 냉각 및 환기 설비(팬/에어컨) 가동 통계 보고서")
        self.resize(1500, 800)
        self.setWindowFlags(self.windowFlags() | Qt.WindowMaximizeButtonHint | Qt.WindowMinimizeButtonHint)
        self.init_ui()

    def init_ui(self):
        main_layout = QVBoxLayout(self)

        # 1. 타이틀
        title = QLabel("냉각 및 환기 설비 가동 통계 (기기별 누계 적용)")
        title.setStyleSheet("font-size: 20px; font-weight: bold; color: #2980b9;")
        title.setAlignment(Qt.AlignCenter)
        main_layout.addWidget(title)

        # 2. 조회 컨트롤 영역
        ctrl_layout = QHBoxLayout()
        
        # 2-1. 기간 선택 라디오 버튼
        self.radio_monthly = QRadioButton("월간 조회 (일별 데이터)")
        self.radio_yearly = QRadioButton("연간 조회 (월별 데이터)")
        self.radio_monthly.setChecked(True) # 기본값

        self.radio_monthly.toggled.connect(self.toggle_ui)
        self.radio_yearly.toggled.connect(self.toggle_ui)

        ctrl_layout.addWidget(self.radio_monthly)
        ctrl_layout.addWidget(self.radio_yearly)
        ctrl_layout.addSpacing(20)

        # 2-2. 날짜/연월 콤보박스
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

        # 2-3. 조회 버튼
        btn_search = QPushButton("통계 조회")
        btn_search.setStyleSheet("background-color: #34495e; color: white; font-weight: bold; padding: 5px 15px;")
        btn_search.clicked.connect(self.load_statistics_data)
        ctrl_layout.addWidget(btn_search)
        
        # 2-4. 누계 표시 안내 라벨
        self.lbl_total_summary = QLabel("※ 표 맨 아랫줄에서 각 기기별 가동 횟수 및 누계 시간을 확인할 수 있습니다.")
        self.lbl_total_summary.setStyleSheet("font-size: 13px; font-weight: bold; color: #d35400; margin-left: 20px;")
        ctrl_layout.addWidget(self.lbl_total_summary)
        
        ctrl_layout.addStretch()
        main_layout.addLayout(ctrl_layout)

        # 3. 통계 테이블 (QTableWidget)
        self.table = QTableWidget()
        
        # [헤더 정의] 기기별 컬럼 (총 17열)
        self.headers = [
            "조회 기준\n(날짜/월)", 
            "외기온도\n(최고/최저 ℃)", "실내온도\n(최고/최저 ℃)", 
            "급기휀(SF)\n횟수", "급기휀(SF)\n가동(분)", 
            "배기휀(EF)\n횟수", "배기휀(EF)\n가동(분)", 
            "에어컨01\n횟수", "에어컨01\n가동(분)", 
            "에어컨02\n횟수", "에어컨02\n가동(분)",
            "TR1 휀\n횟수", "TR1 휀\n가동(분)", 
            "TR2 휀\n횟수", "TR2 휀\n가동(분)", 
            "TR3 휀\n횟수", "TR3 휀\n가동(분)"
        ]
        self.table.setColumnCount(len(self.headers))
        self.table.setHorizontalHeaderLabels(self.headers)
        
        header = self.table.horizontalHeader()
        header.setSectionResizeMode(QHeaderView.Interactive)
        
        self.table.setColumnWidth(0, 110) # 날짜
        self.table.setColumnWidth(1, 110) # 외기온도
        self.table.setColumnWidth(2, 110) # 실내온도
        for i in range(3, len(self.headers)):
            self.table.setColumnWidth(i, 85) # 횟수 및 가동분 열 너비 고정
            
        self.table.setAlternatingRowColors(True)
        
        # 🌟 더블클릭 이벤트 연결 (상세보기)
        self.table.cellDoubleClicked.connect(self.on_row_double_clicked)
        
        main_layout.addWidget(QLabel("※ [월간 조회] 표의 특정 '기기' 셀을 더블클릭하면 해당 날짜의 그 기기 상세 원자료만 확인할 수 있습니다."))
        main_layout.addWidget(self.table)

        # 4. 하단 버튼 영역 (엑셀 출력, 닫기)
        bottom_layout = QHBoxLayout()
        bottom_layout.addStretch()

        self.btn_export = QPushButton("📊 엑셀 내보내기")
        self.btn_export.setStyleSheet("background-color: #27ae60; color: white; font-weight: bold; padding: 8px 15px;")
        self.btn_export.clicked.connect(self.export_to_excel)
        bottom_layout.addWidget(self.btn_export)

        btn_close = QPushButton("닫기")
        btn_close.setStyleSheet("background-color: #7f8c8d; color: white; font-weight: bold; padding: 8px 30px;")
        btn_close.clicked.connect(self.accept)
        bottom_layout.addWidget(btn_close)

        main_layout.addLayout(bottom_layout)

        # 초기 데이터 로드
        self.load_statistics_data()

    def toggle_ui(self):
        if self.radio_monthly.isChecked():
            self.combo_month.setVisible(True)
            self.combo_year.setVisible(False)
        else:
            self.combo_month.setVisible(False)
            self.combo_year.setVisible(True)
        self.load_statistics_data()

    def load_statistics_data(self):
        is_monthly = self.radio_monthly.isChecked()
        
        if is_monthly:
            target = self.combo_month.currentText()
            date_format = "%%Y-%%m-%%d"
            like_pattern = f"{target}-%"
        else:
            target = self.combo_year.currentText()
            date_format = "%%Y-%%m"
            like_pattern = f"{target}-%"

        try:
            conn = db_manager.get_db_raw_connection()
            c = conn.cursor()

            # [Step 1] 온도 데이터 조회
            temp_query = f"""
                SELECT DATE_FORMAT(log_date, '{date_format}') as grp_date,
                       MAX(`외기온도`), MIN(`외기온도`),
                       MAX(`실내온도`), MIN(`실내온도`)
                FROM raw_data
                WHERE log_date LIKE %s
                GROUP BY grp_date
                ORDER BY grp_date ASC
            """
            c.execute(temp_query, (like_pattern,))
            temp_rows = c.fetchall()
            
            temp_data_dict = {}
            for row in temp_rows:
                grp_date, out_max, out_min, in_max, in_min = row
                temp_data_dict[grp_date] = {
                    "out_max": out_max, "out_min": out_min,
                    "in_max": in_max, "in_min": in_min
                }

            # [Step 2] 가동 이력(횟수/시간) 데이터 조회
            equip_names = ['SF_operation', 'EF_operation', 'aircon01_operation', 'aircon02_operation', 'tr1_fan_on', 'tr2_fan_on', 'tr3_fan_on']
            equip_in_clause = "','".join(equip_names)

            event_query = f"""
                SELECT DATE_FORMAT(occurred_at, '{date_format}') as grp_date,
                       equipment_name,
                       COUNT(event_id) as run_count,
                       SUM(duration_seconds) as total_sec
                FROM alarm_event_logs
                WHERE DATE_FORMAT(occurred_at, '{date_format}') LIKE %s
                  AND equipment_name IN ('{equip_in_clause}')
                  AND event_type = 'OPERATION'
                GROUP BY grp_date, equipment_name
            """
            c.execute(event_query, (like_pattern,))
            event_rows = c.fetchall()

            event_data_dict = {}
            for row in event_rows:
                grp_date, eq_name, run_count, total_sec = row
                if grp_date not in event_data_dict:
                    event_data_dict[grp_date] = {}
                event_data_dict[grp_date][eq_name] = {"count": run_count, "sec": total_sec or 0}

            c.close(); conn.close()

            # [Step 3] UI 테이블에 데이터 렌더링 및 누계 행 추가
            all_dates = sorted(list(set(temp_data_dict.keys()) | set(event_data_dict.keys())))
            
            self.table.setRowCount(len(all_dates) + 1)
            equip_totals = {eq: {"count": 0, "min": 0.0} for eq in equip_names}
            
            for r_idx, d_str in enumerate(all_dates):
                # 1. 날짜
                self.set_table_item(r_idx, 0, d_str)

                # 2. 온도
                t_data = temp_data_dict.get(d_str, {})
                out_txt = f"{t_data.get('out_max', '-')} / {t_data.get('out_min', '-')}" if t_data else "- / -"
                in_txt = f"{t_data.get('in_max', '-')} / {t_data.get('in_min', '-')}" if t_data else "- / -"
                self.set_table_item(r_idx, 1, out_txt)
                self.set_table_item(r_idx, 2, in_txt)

                # 3. 각 설비별 횟수 및 분
                e_data = event_data_dict.get(d_str, {})
                col_idx = 3
                
                for eq_name in equip_names:
                    if eq_name in e_data:
                        count = e_data[eq_name]["count"]
                        minutes = round(float(e_data[eq_name]["sec"]) / 60.0, 1)
                    else:
                        count = 0
                        minutes = 0.0
                    
                    equip_totals[eq_name]["count"] += count
                    equip_totals[eq_name]["min"] += minutes
                    
                    self.set_table_item(r_idx, col_idx, str(count))
                    self.set_table_item(r_idx, col_idx + 1, f"{minutes:.1f}")
                    col_idx += 2

            # [Step 4] 표 맨 아랫줄에 기기별 "총계 (누계)" 행 그리기
            total_row_idx = len(all_dates)
            
            item_lbl = QTableWidgetItem("총계 (누계)")
            item_lbl.setTextAlignment(Qt.AlignCenter)
            item_lbl.setFont(QtGui.QFont("Arial", 10, QtGui.QFont.Bold))
            item_lbl.setForeground(Qt.darkRed)
            item_lbl.setBackground(QtGui.QColor("#f2f2f2"))
            self.table.setItem(total_row_idx, 0, item_lbl)
            
            for c in (1, 2):
                item_dash = QTableWidgetItem("-")
                item_dash.setTextAlignment(Qt.AlignCenter)
                item_dash.setBackground(QtGui.QColor("#f2f2f2"))
                self.table.setItem(total_row_idx, c, item_dash)
                
            col_idx = 3
            for eq_name in equip_names:
                c_tot = equip_totals[eq_name]["count"]
                m_tot = equip_totals[eq_name]["min"]
                
                item_c = QTableWidgetItem(str(c_tot))
                item_m = QTableWidgetItem(f"{m_tot:.1f}")
                
                for item in (item_c, item_m):
                    item.setTextAlignment(Qt.AlignCenter)
                    item.setFont(QtGui.QFont("Arial", 10, QtGui.QFont.Bold))
                    item.setForeground(Qt.darkBlue)
                    item.setBackground(QtGui.QColor("#e8f4f8"))
                    
                self.table.setItem(total_row_idx, col_idx, item_c)
                self.table.setItem(total_row_idx, col_idx + 1, item_m)
                col_idx += 2

        except Exception as e:
            print(f"팬/냉각설비 통계 로딩 에러: {e}")
            QMessageBox.warning(self, "데이터 조회 오류", f"통계 데이터를 불러오는 중 오류가 발생했습니다.\n{e}")

    def set_table_item(self, row, col, text):
        item = QTableWidgetItem(text)
        item.setTextAlignment(Qt.AlignCenter)
        self.table.setItem(row, col, item)

    def on_row_double_clicked(self, row, column):
        """날짜 또는 특정 기기 셀을 더블클릭하면 1분 단위 상세 데이터 팝업 호출"""
        # "총계 (누계)" 행(가장 마지막 줄)을 더블클릭한 경우 무시
        if row == self.table.rowCount() - 1:
            return 
            
        if not self.radio_monthly.isChecked():
            QMessageBox.information(self, "안내", "상세 원자료(1분 단위) 조회는 '월간 조회' 모드에서 날짜를 클릭할 때만 가능합니다.")
            return
            
        # 첫 번째 열(날짜) 데이터 가져오기
        target_date = self.table.item(row, 0).text()
        
        # 🌟 수정: 클릭한 '열(Column)'을 기준으로 어떤 기기인지 판별합니다.
        target_equip = None
        equip_kor_name = ""
        
        if column >= 3:
            equip_names = ['SF_operation', 'EF_operation', 'aircon01_operation', 'aircon02_operation', 'tr1_fan_on', 'tr2_fan_on', 'tr3_fan_on']
            kor_names = ['급기휀(SF)', '배기휀(EF)', '에어컨01', '에어컨02', 'TR1 휀', 'TR2 휀', 'TR3 휀']
            
            # 3번째 열부터 기기별로 2칸씩(횟수, 분) 짝지어 있으므로 인덱스 역산
            equip_idx = (column - 3) // 2 
            if 0 <= equip_idx < len(equip_names):
                target_equip = equip_names[equip_idx]
                equip_kor_name = kor_names[equip_idx]
        
        # 팝업 호출 (선택된 기기가 있으면 해당 기기만, 날짜/온도칸(column 0~2)을 누르면 None이 넘어가서 전체 기기를 보여줌)
        dialog = FanDataDetailDialog(target_date, target_equip, equip_kor_name, self)
        dialog.exec_()

    def export_to_excel(self):
        """현재 테이블에 표시된 통계를 엑셀 파일로 출력"""
        if openpyxl is None:
            QMessageBox.critical(self, "라이브러리 누락", "openpyxl 라이브러리가 설치되어 있지 않습니다.")
            return

        if self.radio_monthly.isChecked():
            target_str = self.combo_month.currentText()
            period = "월간"
        else:
            target_str = self.combo_year.currentText()
            period = "연간"

        timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M")
        default_filename = f"냉각환기설비_{period}통계_{target_str}_{timestamp}.xlsx"
        
        save_path, _ = QFileDialog.getSaveFileName(self, "엑셀 파일 저장 위치 선택", default_filename, "Excel Files (*.xlsx)")
        
        if not save_path:
            return

        try:
            wb = openpyxl.Workbook()
            ws = wb.active
            ws.title = f"{period} 통계"

            col_count = self.table.columnCount()
            headers = [self.table.horizontalHeaderItem(c).text().replace('\n', ' ') for c in range(col_count)]
            ws.append(headers)

            header_fill = PatternFill(start_color="D9E1F2", end_color="D9E1F2", fill_type="solid")
            thin_border = Border(left=Side(style='thin'), right=Side(style='thin'), 
                                 top=Side(style='thin'), bottom=Side(style='thin'))

            for col_idx in range(1, col_count + 1):
                cell = ws.cell(row=1, column=col_idx)
                cell.fill = header_fill
                cell.font = Font(bold=True)
                cell.alignment = Alignment(horizontal="center", vertical="center")
                cell.border = thin_border
                ws.column_dimensions[openpyxl.utils.get_column_letter(col_idx)].width = 12

            ws.column_dimensions['A'].width = 15
            ws.column_dimensions['B'].width = 18
            ws.column_dimensions['C'].width = 18

            row_count = self.table.rowCount()
            for r in range(row_count):
                row_data = []
                for c in range(col_count):
                    item = self.table.item(r, c)
                    text = item.text() if item else ""
                    
                    if c > 2 and text != "-":
                        try:
                            val = float(text.replace(',', ''))
                            if val.is_integer():
                                val = int(val)
                            row_data.append(val)
                        except ValueError:
                            row_data.append(text)
                    else:
                        row_data.append(text)
                
                ws.append(row_data)
                
                current_row = r + 2
                for col_idx in range(1, col_count + 1):
                    cell = ws.cell(row=current_row, column=col_idx)
                    cell.alignment = Alignment(horizontal="center", vertical="center")
                    cell.border = thin_border
                    
                    if r == row_count - 1:
                        cell.fill = PatternFill(start_color="E8F4F8", end_color="E8F4F8", fill_type="solid")
                        cell.font = Font(bold=True)

            wb.save(save_path)
            QMessageBox.information(self, "출력 완료", f"통계 데이터가 엑셀로 저장되었습니다.\n\n위치: {save_path}")

        except Exception as e:
            QMessageBox.critical(self, "출력 실패", f"엑셀 파일 생성 중 오류가 발생했습니다.\n{e}")