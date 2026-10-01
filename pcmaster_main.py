# main.py
import sys
import threading
import time
from PyQt5.QtWidgets import QApplication, QSplashScreen, QDesktopWidget
from PyQt5.QtCore import Qt, QCoreApplication, QThread, pyqtSignal
from PyQt5.QtGui import QCursor, QFont
from PyQt5.QtWidgets import QApplication, QSplashScreen, QDesktopWidget, QMessageBox
from PyQt5.QtCore import Qt, QCoreApplication, QThread, pyqtSignal, QSharedMemory

from PyQt5.QtWidgets import QMessageBox
from PyQt5.QtCore import QSharedMemory

from ui_ventilation import VentilationSettingsDialog
from tr_controller import TRFanSettingsDialog

# 최상위 관리 모듈 로드 (윈도우 로드는 지연 가능하도록 아래에서 하거나 그대로 둠)
import db_manager
import pcmaster_worker

def center_window(widget):
    """위젯을 화면 중앙으로 이동시키는 함수"""
    qr = widget.frameGeometry()
    cp = QDesktopWidget().availableGeometry().center()
    qr.moveCenter(cp)
    widget.move(qr.topLeft())

# 초기화를 담당할 백그라운드 스레드
class InitWorker(QThread):
    progress_signal = pyqtSignal(str)
    finished_signal = pyqtSignal()

    def run(self):
        # 1단계: DB 초기화 (가장 오래 걸리는 작업)
        self.progress_signal.emit("⚡ 데이터베이스 연결 및 구성 중...")
        db_manager.init_db()
        time.sleep(0.3) 
        
        # 2단계: PLC 통신 스레드 기동
        self.progress_signal.emit("🔌 PLC 통신 엔진 시작 중...")
        t = threading.Thread(target=pcmaster_worker.serial_receive_thread, daemon=True)
        t.start()
        time.sleep(0.3)
        
        # 3단계: 준비 완료 신호
        self.progress_signal.emit("🖥️ 시스템 화면 생성 중...")
        self.finished_signal.emit()


if __name__ == "__main__":
    app = QApplication(sys.argv)

    # ⭐ [신규] 프로그램 중복 실행 방지
    shared_memory = QSharedMemory("LS_PLC_SCADA_Shared_Memory")
    if not shared_memory.create(1):
        msg = QMessageBox()
        msg.setIcon(QMessageBox.Warning)
        msg.setWindowTitle("실행 경고")
        msg.setText("이미 프로그램이 실행중에 있습니다. 필요시 실행되고 있는 프로그램을 중지하고 다시 실행하여 주시기 바랍니다.")
        msg.exec_()
        sys.exit(0)
    
    # 1. Splash Screen 즉시 생성 및 표시 (메인 스레드 가볍게 유지)
    splash = QSplashScreen()
    splash.setFixedSize(600, 400)
    splash.setStyleSheet("""
        QSplashScreen {
            background-color: #2c3e50;
            color: white;
            border: 3px solid #34495e;
            border-radius: 15px;
        }
    """)
    
    font = QFont("Malgun Gothic", 18, QFont.Bold)
    splash.setFont(font)
    center_window(splash)
    splash.show()
    splash.raise_()
    
    app.setOverrideCursor(QCursor(Qt.WaitCursor))
    splash.showMessage("\n\n\n\n🚀 시스템 엔진 기동 준비 중...", 
                       Qt.AlignCenter | Qt.AlignVCenter, Qt.white)
    
    # Splash 화면을 OS가 즉시 그리도록 강제 이벤트를 처리
    # 이 시점에는 무거운 객체가 전혀 없으므로 Splash가 0.1초 만에 팍 뜹니다.
    for _ in range(5):
        QCoreApplication.processEvents()
    
    # 2. 백그라운드 스레드 생성 및 시작
    worker = InitWorker()
    
    # 진행 메시지 반영
    worker.progress_signal.connect(
        lambda msg: splash.showMessage(f"\n\n\n\n{msg}", Qt.AlignCenter | Qt.AlignVCenter, Qt.white)
    )
    
    # 전역 참조용 메인 윈도우 변수 선언 (가비지 컬렉션 방지)
    win = None
    
    # ⭐ [핵심 개선] DB 초기화 등이 '완전히 끝난 후' 메인 윈도우를 비로서 임포트하고 생성합니다.
    def on_init_finished():
        global win
        
        # 메인 윈도우 모듈을 이 시점에 로드하여 초기 기동 속도를 극대화
        from ui_main_window import SCADAWindow 
        
        # DB 작업이 끝난 평온한 상태에서 메인 창 생성
        win = SCADAWindow()
        center_window(win)
        
        # 🌟 [신규 추가] 프로그램 구동 시 설정창들을 백그라운드에서 생성하여 초기값을 워커로 자동 전달
        win.vent_dialog = VentilationSettingsDialog(win)
        win.tr_dialog = TRFanSettingsDialog(win)

        # =================================================================
        # ⭐ [누락된 부분 추가] pcmaster_worker의 시그널을 화면의 상태 변경 함수와 연결합니다!
        import pcmaster_worker
        pcmaster_worker.comm_signal.status_changed.connect(win.update_rs485_status)
        pcmaster_worker.comm_signal.plc_data_update.connect(win.hmi_dashboard.update_plc_data)
        # =================================================================
        
        # 최상단 고정으로 메인 화면 표시
        win.setWindowFlags(win.windowFlags() | Qt.WindowStaysOnTopHint)
        win.show()
        
        # 고정 해제 및 포커스 집중
        win.setWindowFlags(win.windowFlags() & ~Qt.WindowStaysOnTopHint) 
        win.show()
        win.raise_()
        win.activateWindow()
        
        # 로딩 창 깔끔하게 종료
        splash.finish(win)
        app.restoreOverrideCursor()

    worker.finished_signal.connect(on_init_finished)
    
    # 3. 백그라운드 초기화 작업 시작
    worker.start()

    def cleanup_before_exit():
        # print("프로그램 종료 중... 통신 스레드를 안전하게 중지합니다.")
        import pcmaster_worker
        import time
        
        # 워커 파일의 무한 루프 플래그를 False로 변경
        pcmaster_worker.is_running = False 
        
        # 스레드가 루프를 빠져나오고 포트를 닫을(close) 시간을 잠시 벌어줌
        time.sleep(0.5) 
        
    # 사용자가 창을 닫아 앱이 종료되기 직전에 cleanup_before_exit 함수 자동 실행
    app.aboutToQuit.connect(cleanup_before_exit)
    
    sys.exit(app.exec_())