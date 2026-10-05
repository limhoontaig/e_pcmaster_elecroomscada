from PyQt5.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QDateEdit, 
    QComboBox, QLineEdit, QPushButton, QMessageBox, QGroupBox, QGridLayout
)
from PyQt5.QtCore import QDate, Qt
from PyQt5.QtGui import QFont

from shared.db_manager import get_db_raw_connection, calculate_daily_extremes, DATA_LABELS

class CleanDataDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("⚙️ 운영 데이터 오류 정제 및 복구 관리자")
        self.resize(750, 600)
        self.init_ui()

    def init_ui(self):
        main_layout = QVBoxLayout(self)

        # 🌟 1. 그룹박스 타이틀이 잘 보이도록 스타일시트 적용 (QGroupBox 테두리와 타이틀 여백 확보)
        group_style = """
            QGroupBox {
                font-weight: bold;
                font-size: 14px;
                border: 2px solid #bdc3c7;
                border-radius: 8px;
                margin-top: 22px;     /* 박스 위쪽 여백 (타이틀이 들어갈 공간 확보) */
                padding-top: 25px;    /* 박스 내부 맨 위 콘텐츠와 타이틀 간격 */
                padding-bottom: 15px;
                padding-left: 15px;
                padding-right: 15px;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                subcontrol-position: top left;
                left: 15px;
                padding: 6px 10px;    /* 타이틀 글자 주변의 상하좌우 여백 */
                color: #2c3e50;
            }
        """

        # 📅 [기간 설정 그룹] - 좌우 분산이 아닌 연속 배치 및 글자 크기 확대
        date_group = QGroupBox("📅 정제 대상 기간 설정")
        date_group.setStyleSheet(group_style)
        date_layout = QHBoxLayout()
        date_layout.setSpacing(15)

        # 날짜 폰트 및 크기 확대 설정
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

        # 🌟 좌우가 아닌 연속해서 나란히 배치
        date_layout.addWidget(lbl_start)
        date_layout.addWidget(self.start_date_edit)
        date_layout.addSpacing(30)
        date_layout.addWidget(lbl_end)
        date_layout.addWidget(self.end_date_edit)
        date_layout.addStretch() # 남은 공간 밀어내기

        date_group.setLayout(date_layout)
        main_layout.addWidget(date_group)

        # 🔍 [조건 설정 그룹] - AND / OR 선택 기능 추가
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
            
            # 조건 2, 3번에는 앞 조건과의 연결 관계(AND / OR) 선택 콤보박스 제공
            logic_combo = QComboBox()
            if i == 0:
                logic_combo.addItem("시작")
                logic_combo.setEnabled(False) # 첫 번째 조건은 고정
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

        # 안내 및 실행 버튼
        info_label = QLabel(
            "⚠️ **주의**: 조건에 부합하는 데이터는 `raw_data`에서 **영구 삭제**되며, "
            "해당 시간대의 `hourly_avg` 및 일일 최고/최저 통계(`daily_extremes`)가 **자동으로 재산출**됩니다."
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

        # 조건식 조립 (AND / OR 반영)
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
                cursor.close()
                conn.close()
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