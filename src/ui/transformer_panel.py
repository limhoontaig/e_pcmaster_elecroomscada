# src/ui/transformer_panel.py
from PyQt5.QtWidgets import (QVBoxLayout, QHBoxLayout, QGridLayout, 
                             QLabel, QGroupBox, QPushButton, QFrame, QSizePolicy)
from PyQt5.QtCore import Qt

from src.ui.fan_graphic import FanGraphicWidget

class TransformerPanel(QFrame):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.parent_dashboard = parent
        self.setStyleSheet("QFrame { background-color: #111111; border: 1px solid #333; }")
        self.init_ui()

    def init_ui(self):
        layout = QVBoxLayout(self)
        
        lbl_title = QLabel("<h3 style='color:#3498db; margin:0;'>⚡ 변압기(TR) 현황 및 휀 제어</h3>")
        lbl_title.setAlignment(Qt.AlignCenter)
        lbl_title.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Maximum)
        if hasattr(self.parent_dashboard, "open_tr_settings_dialog"):
            lbl_title.mouseDoubleClickEvent = self.parent_dashboard.open_tr_settings_dialog
        layout.addWidget(lbl_title)

        tr_layout = QHBoxLayout()
        self.parent_dashboard.tr1_graphic, self.parent_dashboard.lbl_tr1_status = self.create_tr_panel("TR-1", tr_layout)
        self.parent_dashboard.tr2_graphic, self.parent_dashboard.lbl_tr2_status = self.create_tr_panel("TR-2", tr_layout)
        self.parent_dashboard.tr3_graphic, self.parent_dashboard.lbl_tr3_status = self.create_tr_panel("TR-3", tr_layout)
        layout.addLayout(tr_layout, 1) 

        ctrl_lbl = QLabel("<b>[제어 스위치]</b>")
        ctrl_lbl.setFixedHeight(40)
        ctrl_lbl.setAlignment(Qt.AlignCenter)
        layout.addWidget(ctrl_lbl, 0)

        ctrl_layout = QGridLayout()
        ctrl_layout.setSpacing(8)
        ctrl_layout.setColumnStretch(0, 1)
        ctrl_layout.setColumnStretch(1, 1)
        ctrl_layout.setColumnStretch(2, 1)
        
        self.parent_dashboard.btn_master = QPushButton("전체 냉각설비 가동중")
        self.parent_dashboard.btn_master.setCheckable(True)
        self.parent_dashboard.btn_master.setChecked(True)
        self.parent_dashboard.btn_master.setStyleSheet(self.parent_dashboard.get_master_style(True))
        self.parent_dashboard.btn_master.setFixedHeight(40)
        self.parent_dashboard.btn_master.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        self.parent_dashboard.btn_master.clicked.connect(self.parent_dashboard.on_master_toggled)

        self.parent_dashboard.btn_auto = QPushButton("자동 운전")
        self.parent_dashboard.btn_auto.setCheckable(True)
        self.parent_dashboard.btn_auto.setChecked(True)
        self.parent_dashboard.btn_auto.setStyleSheet(self.parent_dashboard.get_auto_manual_style(True))
        self.parent_dashboard.btn_auto.setFixedHeight(40)
        self.parent_dashboard.btn_auto.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        self.parent_dashboard.btn_auto.clicked.connect(self.parent_dashboard.on_auto_manual_toggled)

        self.parent_dashboard.btn_tr1 = self.parent_dashboard.create_toggle_button("TR-1 수동 OFF")
        self.parent_dashboard.btn_tr2 = self.parent_dashboard.create_toggle_button("TR-2 수동 OFF")
        self.parent_dashboard.btn_tr3 = self.parent_dashboard.create_toggle_button("TR-3 수동 OFF")
        self.parent_dashboard.btn_tr1.setFixedHeight(40)
        self.parent_dashboard.btn_tr2.setFixedHeight(40)
        self.parent_dashboard.btn_tr3.setFixedHeight(40)

        ctrl_layout.addWidget(self.parent_dashboard.btn_master, 0, 0, 1, 2)
        ctrl_layout.addWidget(self.parent_dashboard.btn_auto, 0, 2, 1, 1)
        
        ctrl_layout.addWidget(self.parent_dashboard.btn_tr1, 1, 0)
        ctrl_layout.addWidget(self.parent_dashboard.btn_tr2, 1, 1)
        ctrl_layout.addWidget(self.parent_dashboard.btn_tr3, 1, 2)

        layout.addLayout(ctrl_layout, 0)

        self.parent_dashboard.btn_tr1.toggled.connect(lambda checked: self.parent_dashboard.update_tr_fan_status(1, checked))
        self.parent_dashboard.btn_tr2.toggled.connect(lambda checked: self.parent_dashboard.update_tr_fan_status(2, checked))
        self.parent_dashboard.btn_tr3.toggled.connect(lambda checked: self.parent_dashboard.update_tr_fan_status(3, checked))

        for btn in [self.parent_dashboard.btn_auto, self.parent_dashboard.btn_tr1, self.parent_dashboard.btn_tr2, self.parent_dashboard.btn_tr3]:
            sp = btn.sizePolicy()
            sp.setRetainSizeWhenHidden(True)
            btn.setSizePolicy(sp)

        self.parent_dashboard.set_individual_buttons_enabled(False) 

    def create_tr_panel(self, title, parent_layout):
        group = QGroupBox(title)
        group.setStyleSheet("QGroupBox { border: 1px solid #555; margin-top: 10px; font-weight: bold; } QGroupBox::title { subcontrol-origin: margin; left: 10px; }")
        
        layout = QVBoxLayout(group)
        layout.setSpacing(12) 
        
        graphic_widget = FanGraphicWidget(fan_type="TR")
        layout.addWidget(graphic_widget, 1)

        status_lbl = QLabel("정지중")
        status_lbl.setAlignment(Qt.AlignCenter)
        status_lbl.setFixedHeight(40) 
        status_lbl.setStyleSheet("background-color: #555; color: white; padding: 5px; font-weight: bold;")
        layout.addWidget(status_lbl, 0)
        
        parent_layout.addWidget(group)
        return graphic_widget, status_lbl