import asyncio
from pymodbus.server import StartAsyncSerialServer
from pymodbus.datastore import ModbusSparseDataBlock, ModbusServerContext

# PyModbus 버전에 맞춰 바뀐 이름을 자동으로 감지
try:
    from pymodbus.datastore import ModbusSlaveContext as DataContext
except ImportError:
    from pymodbus.datastore import ModbusDeviceContext as DataContext

async def run_simulator():
    print("🟢 가상 PLC 시뮬레이터 기동 완료!")
    print("🔌 대기 중인 포트: /tmp/vcom2 (19200 bps)")
    print("SCADA 프로그램을 실행하면 통신이 시작됩니다. (종료: Control + C)")
    
    # 0~1500번지까지 0으로 채워진 딕셔너리를 직접 생성
    memory_map = {i: 0 for i in range(1500)}
    block = ModbusSparseDataBlock(memory_map)
    store = DataContext(di=block, co=block, hr=block, ir=block)
    
    # ⭐ [핵심 수정] 버전별 단어 변경(slaves -> devices) 완벽 호환 처리
    try:
        # 최신 버전 (devices 사용)
        context = ModbusServerContext(devices=store, single=True)
    except TypeError:
        # 구버전 (slaves 사용)
        context = ModbusServerContext(slaves=store, single=True)
    
    await StartAsyncSerialServer(context=context, port='/tmp/vcom2', baudrate=19200)

if __name__ == "__main__":
    try:
        asyncio.run(run_simulator())
    except KeyboardInterrupt:
        print("\n🔴 시뮬레이터가 종료되었습니다.")