# clean_test_data.py
import pymysql
from datetime import datetime

# 🌟 db_manager에서 DB 연결 함수, 데이터 라벨, 일계(최고/최저) 함수를 그대로 임포트합니다.
from db_manager import get_db_raw_connection, calculate_daily_extremes, DATA_LABELS

def clean_and_recalculate():
    # 1. DB 연결 (db_manager 활용)
    conn = get_db_raw_connection()
    cursor = conn.cursor()

    try:
        # 🌟 수정된 부분: 어제/오늘 대신 특정 날짜로 직접 지정
        target_date1 = '2026-09-29'
        target_date2 = '2026-09-30'

        # 삭제 조건 지정
        target_condition = """
            (log_date = %s OR log_date = %s)
            AND (
                `KEP_P_kWh` <= 44000000.0  -- 👈 비정상적으로 낮은 값 삭제
                OR `KEP_P_kWh` > 44700000.0 -- 👈 비정상적으로 높은 값 삭제
                OR `실내온도` = 0 
            )
        """

        # 2. 비정상 데이터가 포함된 날짜(date)와 시간(hour) 추출
        find_sql = f"SELECT DISTINCT log_date, HOUR(log_time) FROM raw_data WHERE {target_condition}"
        # 🌟 지정한 변수로 쿼리 실행
        cursor.execute(find_sql, (target_date1, target_date2))
        affected_periods = cursor.fetchall()

        if not affected_periods:
            print("✨ 삭제할 비정상 데이터가 없습니다.")
            return

        # 고유한 날짜만 따로 추출 (daily_extremes 재산출용)
        affected_dates = set(row[0] for row in affected_periods)

        # 3. 비정상 데이터 삭제 (raw_data)
        print(f"🗑️ 비정상 데이터 삭제 진행 (영향받는 시간대: {len(affected_periods)}개)")
        delete_sql = f"DELETE FROM raw_data WHERE {target_condition}"
        # 🌟 지정한 변수로 쿼리 실행
        cursor.execute(delete_sql, (target_date1, target_date2))
        print(f"✅ 비정상 데이터 총 {cursor.rowcount}건 삭제 완료.")

        # 4. 시간대별 평균(hourly_avg) 재산출 및 덮어쓰기
        print("📊 시간대별 평균 데이터(hourly_avg) 재산출 중...")
        avg_select = ", ".join([f'AVG(`{name}`)' for name in DATA_LABELS])
        col_names = ", ".join([f'`{name}`' for name in DATA_LABELS])
        placeholders = ", ".join(["%s"] * len(DATA_LABELS))

        for t_date, t_hour in affected_periods:
            time_pattern = f"{t_hour:02d}:%"
            query = f"SELECT {avg_select} FROM raw_data WHERE log_date = %s AND log_time LIKE %s"
            cursor.execute(query, (t_date, time_pattern))
            result = cursor.fetchone()
            
            if result and result[0] is not None:
                # db_manager의 calculate_hourly_avg 로직과 동일하게 스케일링
                rounded_result = [round(float(val), 1) if val is not None else 0.0 for val in result]
                insert_query = f"REPLACE INTO hourly_avg (log_date, log_time, {col_names}) VALUES (%s, %s, {placeholders})"
                
                # 정확한 정각 시간(예: 14:00:00)으로 hourly_avg 갱신
                cursor.execute(insert_query, [t_date, f"{t_hour:02d}:00:00"] + rounded_result)
        
        conn.commit()

        # 5. 일일 최고/최저(daily_extremes) 재산출
        print("📈 일일 최고/최저 데이터(daily_extremes) 재산출 중...")
        for t_date in affected_dates:
            # 🌟 db_manager에 이미 만들어두신 함수를 호출하기만 하면 완벽하게 MAX/MIN 테이블이 덮어씌워집니다.
            calculate_daily_extremes(t_date)
            
        print("🎉 모든 시운전 가비지 데이터 정리 및 통계 갱신이 완료되었습니다!")

    except Exception as e:
        conn.rollback()
        print(f"❌ 작업 중 오류 발생 (데이터가 롤백되었습니다): {e}")
    finally:
        cursor.close()
        conn.close()

if __name__ == "__main__":
    # 🌟 안내 메시지도 명확하게 수정
    confirm = input("⚠️ 9월 29일과 9월 30일에 생성된 시운전 오류 데이터를 삭제하시겠습니까? (y/n): ")
    if confirm.lower() == 'y':
        clean_and_recalculate()
    else:
        print("작업이 취소되었습니다.")