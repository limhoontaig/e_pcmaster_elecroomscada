# src/ui/fan_graphic.py

from PyQt5.QtWidgets import QWidget, QSizePolicy
from PyQt5.QtCore import Qt, QTimer
from PyQt5.QtGui import QPainter, QColor, QPen, QBrush

class FanGraphicWidget(QWidget):
    def __init__(self, parent=None, fan_type="TR"):
        super().__init__(parent)
        self.setMinimumSize(120, 110)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding) 
        self.is_running = False
        self.angle = 0
        self.fan_type = fan_type
        
        self.timer = QTimer(self)
        self.timer.timeout.connect(self.update_animation)

    def set_fan_state(self, state):
        self.is_running = state
        if self.is_running:
            self.timer.start(150)
        else:
            self.timer.stop()
        self.update()

    def update_animation(self):
        self.angle = (self.angle + 20) % 360
        self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        w, h = self.width(), self.height()

        if self.fan_type == "TR":
            painter.setBrush(QBrush(QColor("#444444"))); painter.setPen(Qt.NoPen)
            painter.drawRect(10, 40, w - 20, 10); painter.drawRect(10, h - 20, w - 20, 10)
            coil_w = (w - 40) / 3; coil_h = h - 70
            painter.setBrush(QBrush(QColor("#900000"))); painter.setPen(QPen(QColor("#111111"), 2))
            gap = 5; start_x = 10 + gap
            for i in range(3):
                painter.drawRoundedRect(int(start_x + (coil_w + gap)*i), 50, int(coil_w), int(coil_h), 4, 4)
            fan_cy = 20
        else:
            painter.setBrush(QBrush(QColor("#7f8c8d"))); painter.setPen(QPen(QColor("#2c3e50"), 3))
            painter.drawEllipse(int(w/2 - 45), int(h/2 - 45), 90, 90)
            fan_cy = h / 2

        fan_cx = w / 2
        fan_radius = 16 if self.fan_type == "TR" else 40
        
        if self.fan_type == "TR":
            painter.setBrush(QBrush(QColor("#111111"))); painter.setPen(QPen(QColor("#7f8c8d"), 2))
            painter.drawEllipse(int(fan_cx - fan_radius), int(fan_cy - fan_radius), fan_radius*2, fan_radius*2)
        
        painter.translate(fan_cx, fan_cy)
        painter.rotate(self.angle) 
        
        painter.setBrush(QBrush(QColor("#3498db" if self.is_running else "#555555"))) 
        painter.setPen(Qt.NoPen)
        for _ in range(4): 
            painter.drawPie(int(-fan_radius*0.8), int(-fan_radius*0.8), int(fan_radius*1.6), int(fan_radius*1.6), 0 * 16, 40 * 16)
            painter.rotate(90)
        painter.resetTransform()