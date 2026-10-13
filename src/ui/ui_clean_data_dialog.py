# ui_clean_data_dialog.py
from PyQt5.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QDateEdit, 
    QComboBox, QLineEdit, QPushButton, QMessageBox, QGroupBox, QGridLayout, QCheckBox
)
from PyQt5.QtCore import QDate, Qt
from PyQt5.QtGui import QFont

from shared.db_manager import get_db_raw_connection, calculate_daily_extremes, DATA_LABELS

class CleanDataDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("⚙️ 운영 데이터 오류 정제 및 복구 관리자")
        self.resize(750, 650)
        self.init_ui()

    def init_ui(self):
        main_layout = QVBoxLayout(self)

        # 🌟 그룹박스 스타일시트 적용
        group_style = """
            QGroupBox {
                font-weight: bold;
                font-size: 14px;
                border: 2px solid #bdc3c7;
                border-radius: 8px;
                margin-top: 22px;     
                padding-top: 25px;    
                padding-bottom: 15px;
                padding-left: 15px;
                padding-right: 15px;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                subcontrol-position: top left;
                left: 15px;
                padding: 6px 10px;    
                color: #2c3e50;
            }
        """

        # 📅 [기간 설정 그룹]
        date_group = QGroupBox("📅 정제 및 재산정 대상 기간 설정")
        date_group.setStyleSheet(group_style)
        date_layout = QHBoxLayout()
        date_layout.setSpacing(15)

        date_font = QFont("Malgun Gothic", 12)

        self.start_date_edit = QDateEdit()
        self.start_date_edit.setCalendarPopup(True)
        self.start_date_edit.setDate(QDate.currentDate())
        self.start_date_edit.setFont(date_font)
        self.start_date_edit.setMinimumWidth(140)

        self.end_date_edit = QDateEdit()
        self.end_date_edit.setCalendarPopup(True)
        self.end_date_edit.setDate(QDate.currentDate())
        self.end_date_edit.setFont(date_font)
        self.end_date_edit.setMinimumWidth(140)

        lbl_start = QLabel("시작 일자:")
        lbl_start.setFont(date_font)
        lbl_end = QLabel("종료 일자:")
        lbl_end.setFont(date_font)

        date_layout.addWidget(lbl_start)
        date_layout.addWidget(self.start_date_edit)
        date_layout.addSpacing(30)
        date_layout.addWidget(lbl_end)
        date_layout.addWidget(self.end_date_edit)
        date_layout.addStretch()

        date_group.setLayout(date_layout)
        main_layout.addWidget(date_group)

        # 🔍 [조건 설정 그룹]
        cond_group = QGroupBox("🔍 비정상 데이터 추출 조건식 설정")
        cond_group.setStyleSheet(group_style)
        cond_layout = QGridLayout()
        cond_layout.setSpacing(10)

        cond_layout.addWidget(QLabel("<b>순번</b>"), 0, 0)
        cond_layout.addWidget(QLabel("<b>연결 관계</b>"), 0, 1)
        cond_layout.addWidget(QLabel("<b>대상 컬럼</b>"), 0, 2)
        cond_layout.addWidget(QLabel("<b>조건식</b>"), 0, 3)
        cond_layout.addWidget(QLabel("<b>비교 값</b>"), 0, 4)

        self.condition_rows = []
        operators = ["=", "!=", ">", ">=", "<", "<=", "LIKE"]

        for i in range(3):
            row_label = QLabel(f"조건 {i+1}")
            logic_combo = QComboBox()
            if i == 0:
                logic_combo.addItem("시작")
                logic_combo.setEnabled(False)
            else:
                logic_combo.addItems(["AND (그리고)", "OR (또는)"])

            col_combo = QComboBox()
            col_combo.addItems(DATA_LABELS)
            
            op_combo = QComboBox()
            op_combo.addItems(operators)
            
            val_input = QLineEdit()
            val_input.setPlaceholderText("예: 0 또는 44000000")

            cond_layout.addWidget(row_label, i+1, 0)
            cond_layout.addWidget(logic_combo, i+1, 1)
            cond_layout.addWidget(col_combo, i+1, 2)
            cond_layout.addWidget(op_combo, i+1, 3)
            cond_layout.addWidget(val_input, i+1, 4)

            self.condition_rows.append((logic_combo, col_combo, op_combo, val_input))

        cond_group.setLayout(cond_layout)
        main_layout.addWidget(cond_group)

        # 🌟 [신규 추가] 통계 전면 강제 재산정 체크박스
        self.chk_recalculate_only = QCheckBox("🔄 [선택 옵션] 조건식 검사 없이, 지정 기간의 '시간 평균(hourly_avg)' 및 '일일 최고/최저(daily_extremes)' 통계만 전면 강제 재산정")
        self.chk_recalculate_only.setStyleSheet("font-weight: bold; color: #2980b9; font-size: 12px; margin-top: 5px;")
        # 체크박스 상태에 따라 조건식 그룹 활성/비활성 연동 (선택 사항)
        self.chk_recalculate_only.toggled.connect(cond_group.setDisabled)
        main_layout.addWidget(self.chk_recalculate_only)

        # 안내 및 실행 버튼
        info_label = QLabel(
            "⚠️ **안내**: 조건식 정제 시 부합하는 원본(`raw_data`)이 삭제되며 통계가 자동 재산출됩니다. "
            "그래프에만 엉뚱한 평균 노이즈가 남은 경우 아래 체크박스를 켜고 재산정 버튼을 누르세요."
        )
        info_label.setWordWrap(True)
        info_label.setStyleSheet("color: #c0392b; font-weight: bold; font-size: 11px; margin-top: 5px;")
        main_layout.addWidget(info_label)

        btn_layout = QHBoxLayout()
        self.btn_run = QPushButton("🚀 데이터 정제 및 통계 재산출 실행")
        self.btn_run.setStyleSheet("background-color: #e74c3c; color: white; font-weight: bold; padding: 12px; font-size: 13px; border-radius: 5px;")
        self.btn_run.clicked.connect(self.execute_cleaning)
        
        self.btn_close = QPushButton("닫기")
        self.btn_close.setStyleSheet("padding: 12px; font-weight: bold; font-size: 13px; border-radius: 5px;")
        self.btn_close.clicked.connect(self.close)

        btn_layout.addStretch()
        btn_layout.addWidget(self.btn_run)
        btn_layout.addWidget(self.btn_close)
        main_layout.addLayout(btn_layout)

    def execute_cleaning(self):
        start_d = self.start_date_edit.date().toString("yyyy-MM-dd")
        end_d = self.end_date_edit.date().toString("yyyy-MM-dd")

        if start_d > end_d:
            QMessageBox.warning(self, "경고", "시작 일자가 종료 일자보다 클 수 없습니다.")
            return

        is_recalc_mode = self.chk_recalculate_only.isChecked()

        if is_recalc_mode:
            # 🌟 통계 전면 강제 재산정 모드
            confirm = QMessageBox.question(
                self, "강제 재산정 확인",
                f"기간: {start_d} ~ {end_d}\n\n"
                "원본 데이터 삭제 없이, 해당 기간의 '시간별 평균(hourly_avg)' 및 '일일 최고/최저(daily_extremes)'를 처음부터 다시 계산하여 덮어씁니다.\n\n"
                "진행하시겠습니까?",
                QMessageBox.Yes | QMessageBox.No, QMessageBox.No
            )
            if confirm != QMessageBox.Yes:
                return
            self.run_force_recalculation(start_d, end_d)
        else:
            # 🔍 기존 조건식 기반 정제 모드
            query_parts = []
            for i, (logic_combo, col_combo, op_combo, val_input) in enumerate(self.condition_rows):
                val_text = val_input.text().strip()
                if val_text:
                    col_name = col_combo.currentText()
                    op = op_combo.currentText()
                    
                    try:
                        float(val_text)
                        condition_str = f"`{col_name}` {op} {val_text}"
                    except ValueError:
                        condition_str = f"`{col_name}` {op} '{val_text}'"

                    if i == 0:
                        query_parts.append(condition_str)
                    else:
                        logic_word = "AND" if "AND" in logic_combo.currentText() else "OR"
                        query_parts.append(f"{logic_word} {condition_str}")

            if not query_parts:
                QMessageBox.warning(self, "경고", "최소한 하나 이상의 유효한 조건을 입력해주세요.")
                return

            combined_condition = " ".join(query_parts)

            confirm = QMessageBox.question(
                self, "실행 확인",
                f"기간: {start_d} ~ {end_d}\n적용 조건:\n{combined_condition}\n\n해당 데이터를 삭제하고 재산출하시겠습니까?",
                QMessageBox.Yes | QMessageBox.No, QMessageBox.No
            )

            if confirm != QMessageBox.Yes:
                return

            self.run_db_cleaning(start_d, end_d, combined_condition)

    def run_force_recalculation(self, start_date, end_date):
        """특정 기간의 시간별 평균 및 일일 극값을 원본(raw_data) 기준으로 완전 재구축합니다."""
        conn = get_db_raw_connection()
        if not conn:
            QMessageBox.critical(self, "에러", "데이터베이스 연결에 실패했습니다.")
            return

        cursor = conn.cursor()
        try:
            # 1. 지정된 기간 내에 raw_data가 존재하는 모든 날짜와 시간대 추출
            find_sql = """
                SELECT DISTINCT log_date, HOUR(log_time) 
                FROM raw_data 
                WHERE log_date BETWEEN %s AND %s 
                ORDER BY log_date, log_time
            """
            cursor.execute(find_sql, (start_date, end_date))
            target_periods = cursor.fetchall()

            if not target_periods:
                QMessageBox.information(self, "결과", "해당 기간에 재산출할 원본 데이터(raw_data)가 존재하지 않습니다.")
                self.accept()
                return

            target_dates = set(row[0] for row in target_periods)

            # 2. 시간대별 평균(hourly_avg) 재산출 및 덮어쓰기 (REPLACE)
            avg_select = ", ".join([f'AVG(`{name}`)' for name in DATA_LABELS])
            col_names = ", ".join([f'`{name}`' for name in DATA_LABELS])
            placeholders = ", ".join(["%s"] * len(DATA_LABELS))

            recalculated_count = 0
            for t_date, t_hour in target_periods:
                time_pattern = f"{t_hour:02d}:%"
                query = f"SELECT {avg_select} FROM raw_data WHERE log_date = %s AND log_time LIKE %s"
                cursor.execute(query, (t_date, time_pattern))
                result = cursor.fetchone()
                
                if result and result[0] is not None:
                    rounded_result = [round(float(val), 1) if val is not None else 0.0 for val in result]
                    # 🌟 문제가 된 payload_time 코드를 제거하고 정상 쿼리만 남김
                    insert_query = f"REPLACE INTO hourly_avg (log_date, log_time, {col_names}) VALUES (%s, %s, {placeholders})"
                    cursor.execute(insert_query, [t_date, f"{t_hour:02d}:00:00"] + rounded_result)
                    recalculated_count += 1
            
            conn.commit()

            # 3. 일일 최고/최저(daily_extremes) 재산출
            for t_date in target_dates:
                calculate_daily_extremes(t_date)

            QMessageBox.information(
                self, "성공", 
                f"🎉 통계 전면 강제 재산정 완료!\n"
                f"- 재구축된 일자 수: {len(target_dates)}일\n"
                f"- 갱신된 시간대 평균 수: {recalculated_count}개"
            )
            self.accept()

        except Exception as e:
            conn.rollback()
            QMessageBox.critical(self, "에러 발생", f"재산정 작업 중 오류가 발생했습니다:\n{e}")
        finally:
            cursor.close()
            conn.close()

    def run_db_cleaning(self, start_date, end_date, combined_condition):
        conn = get_db_raw_connection()
        if not conn:
            QMessageBox.critical(self, "에러", "데이터베이스 연결에 실패했습니다.")
            return

        cursor = conn.cursor()
        try:
            target_condition = f"""
                log_date BETWEEN %s AND %s
                AND ({combined_condition})
            """

            # 1. 영향받는 시간대 추출
            find_sql = f"SELECT DISTINCT log_date, HOUR(log_time) FROM raw_data WHERE {target_condition}"
            cursor.execute(find_sql, (start_date, end_date))
            affected_periods = cursor.fetchall()

            if not affected_periods:
                QMessageBox.information(self, "결과", "조건에 일치하는 비정상 데이터가 없습니다.")
                self.accept()
                return

            affected_dates = set(row[0] for row in affected_periods)

            # 2. 비정상 데이터 삭제
            delete_sql = f"DELETE FROM raw_data WHERE {target_condition}"
            cursor.execute(delete_sql, (start_date, end_date))
            deleted_count = cursor.rowcount

            # 3. 시간대별 평균(hourly_avg) 재산출 및 덮어쓰기
            avg_select = ", ".join([f'AVG(`{name}`)' for name in DATA_LABELS])
            col_names = ", ".join([f'`{name}`' for name in DATA_LABELS])
            placeholders = ", ".join(["%s"] * len(DATA_LABELS))

            for t_date, t_hour in affected_periods:
                time_pattern = f"{t_hour:02d}:%"
                query = f"SELECT {avg_select} FROM raw_data WHERE log_date = %s AND log_time LIKE %s"
                cursor.execute(query, (t_date, time_pattern))
                result = cursor.fetchone()
                
                if result and result[0] is not None:
                    rounded_result = [round(float(val), 1) if val is not None else 0.0 for val in result]
                    insert_query = f"REPLACE INTO hourly_avg (log_date, log_time, {col_names}) VALUES (%s, %s, {placeholders})"
                    cursor.execute(insert_query, [t_date, f"{t_hour:02d}:00:00"] + rounded_result)
            
            conn.commit()

            # 4. 일일 최고/최저(daily_extremes) 재산출
            for t_date in affected_dates:
                calculate_daily_extremes(t_date)

            QMessageBox.information(
                self, "성공", 
                f"🎉 데이터 정제 완료!\n- 삭제된 원본 건수: {deleted_count}건\n- 재산출된 시간대 수: {len(affected_periods)}개"
            )
            self.accept()

        except Exception as e:
            conn.rollback()
            QMessageBox.critical(self, "에러 발생", f"작업 중 오류가 발생하여 롤백되었습니다:\n{e}")
        finally:
            cursor.close()
            conn.close()