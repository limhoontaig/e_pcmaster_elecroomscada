# tr_controller.py
from PyQt5.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout, QLabel, 
                             QDoubleSpinBox, QPushButton, QMessageBox, QGroupBox)

# 💡 client(통신엔진)를 직접 부르지 않고, worker 모듈 전체를 부릅니다.
import pcmaster_worker 

class TRFanSettingsDialog(QDialog):
    def __init__(self, tr1_on=40.0, tr1_off=35.0, tr2_on=40.0, tr2_off=35.0, tr3_on=40.0, tr3_off=35.0, parent=None):
        super().__init__(parent)
        self.setWindowTitle("변압기 개별 환기팬 온도 설정")
        self.setFixedSize(350, 380)

        # 메인 레이아웃
        main_layout = QVBoxLayout()

        # TR1, TR2, TR3 UI 그룹 생성 함수 호출
        self.spin_tr1_on, self.spin_tr1_off = self.create_tr_group("TR1 (1호기)", tr1_on, tr1_off, main_layout)
        self.spin_tr2_on, self.spin_tr2_off = self.create_tr_group("TR2 (2호기)", tr2_on, tr2_off, main_layout)
        self.spin_tr3_on, self.spin_tr3_off = self.create_tr_group("TR3 (3호기)", tr3_on, tr3_off, main_layout)

        # 저장 및 취소 버튼
        btn_layout = QHBoxLayout()
        self.btn_save = QPushButton("PLC에 일괄 적용")
        self.btn_cancel = QPushButton("취소")
        btn_layout.addWidget(self.btn_save)
        btn_layout.addWidget(self.btn_cancel)

        main_layout.addLayout(btn_layout)
        self.setLayout(main_layout)

        # 버튼 이벤트 연결
        self.btn_save.clicked.connect(self.save_and_send_to_plc)
        self.btn_cancel.clicked.connect(self.reject)

    def create_tr_group(self, title, current_on, current_off, parent_layout):
        """각 변압기별 UI 블록을 생성하는 도우미 함수"""
        group = QGroupBox(title)
        layout = QHBoxLayout()

        # 기동 온도
        layout.addWidget(QLabel("기동(℃):"))
        spin_on = QDoubleSpinBox()
        spin_on.setRange(20.0, 80.0)
        spin_on.setSingleStep(0.5)
        spin_on.setValue(current_on)
        layout.addWidget(spin_on)

        # 정지 온도
        layout.addWidget(QLabel("정지(℃):"))
        spin_off = QDoubleSpinBox()
        spin_off.setRange(15.0, 75.0)
        spin_off.setSingleStep(0.5)
        spin_off.setValue(current_off)
        layout.addWidget(spin_off)

        group.setLayout(layout)
        parent_layout.addWidget(group)
        
        return spin_on, spin_off

    def save_and_send_to_plc(self):
        # 1. 값 읽기
        tr1_on, tr1_off = self.spin_tr1_on.value(), self.spin_tr1_off.value()
        tr2_on, tr2_off = self.spin_tr2_on.value(), self.spin_tr2_off.value()
        tr3_on, tr3_off = self.spin_tr3_on.value(), self.spin_tr3_off.value()

        # 2. 유효성 검사 (정지 온도는 기동 온도보다 무조건 낮아야 함)
        if tr1_off >= tr1_on or tr2_off >= tr2_on or tr3_off >= tr3_on:
            QMessageBox.warning(self, "설정 오류", "모든 변압기의 '정지 온도'는 '기동 온도'보다 낮아야 합니다!")
            return

        # 3. 소수점 1자리 포함 정수 변환 (예: 40.5도 -> 405)
        plc_values = [
            int(tr1_on * 10), int(tr1_off * 10),
            int(tr2_on * 10), int(tr2_off * 10),
            int(tr3_on * 10), int(tr3_off * 10)
        ]

        # 💡 [핵심 수정] 직접 통신하지 않고, 백그라운드 일꾼의 메모장에 값만 딱 적어둡니다!
        pcmaster_worker.pending_tr_fan_values = plc_values

        # 화면은 즉시 완료 메시지를 띄우고 닫힙니다. (절대 멈추지 않음)
        QMessageBox.information(self, "적용 중", "PLC에 온도 설정값 저장을 지시했습니다.\n(잠시 후 통신 일꾼이 안전하게 씌워 넣습니다.)")
        self.accept()