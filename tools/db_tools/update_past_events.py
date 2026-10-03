# update_past_events.py

import db_manager

def update_past_logs():
    conn = db_manager.get_db_raw_connection()
    c = conn.cursor()
    
    try:
        # 1. 상태(STATUS) 및 운전(OPERATION) 로그 일괄 업데이트
        c.execute("""
            UPDATE alarm_event_logs 
            SET action_taken = '조치사항 없음' 
            WHERE event_type IN ('STATUS', 'OPERATION') 
              AND (action_taken IS NULL OR action_taken = '미조치' OR action_taken = '')
        """)
        print(f"✅ 상태/운전 이벤트 총 {c.rowcount}건 -> '조치사항 없음'으로 수정 완료.")

        # 2. 이미 종료(복구)된 알람(ALARM) 로그 일괄 업데이트
        c.execute("""
            UPDATE alarm_event_logs 
            SET action_taken = '자동 조치 완료(현장 리셋)' 
            WHERE event_type = 'ALARM' 
              AND cleared_at IS NOT NULL 
              AND (action_taken IS NULL OR action_taken = '미조치' OR action_taken = '')
        """)
        print(f"✅ 이미 해제된 알람 총 {c.rowcount}건 -> '자동 조치 완료(현장 리셋)'으로 수정 완료.")

        conn.commit()
        print("🎉 과거 이벤트 DB 정리가 완벽하게 끝났습니다!")
        
    except Exception as e:
        conn.rollback()
        print(f"❌ 작업 중 오류 발생 (롤백됨): {e}")
    finally:
        c.close()
        conn.close()

if __name__ == "__main__":
    update_past_logs()