import psutil
from scapy.all import *
import binascii
import json
import subprocess
from time import sleep
import asyncio
from concurrent.futures import ThreadPoolExecutor
import threading

# 雷电模拟器adb配置
ADB_PATH = r"E:\leidian\LDPlayer9\adb.exe"
DEVICE_ID = "emulator-5554"

# 按钮坐标配置（720x1280分辨率）
BUTTONS = {
    '训练': (365, 945),
    '速': (60, 1040),
    '耐': (180, 1040),
    '力': (300, 1040),
    '根': (420, 1040),
    '智': (540, 1040),
    'SS': (660, 1040),
    '休息': (125, 945),
    '出行': (280, 1175),
    '比赛': (610, 1175),
    '友人': (350, 395),
    '担当': (350, 645)
}

# 配置参数
TARGET_EXE = r"E:\凯旋门黑板\UmaAi神经网络版（Nvidia显卡专属）.exe"
FIXED_DST_PORT = 4693
HEARTBEAT_MAX_LEN = 60

# 全局变量
target_ports = set()
executor = ThreadPoolExecutor(max_workers=4)
packet_buffer = asyncio.Queue()
processing = True

def adb_click(x, y, delay=0.5):
    cmd = f'"{ADB_PATH}" -s {DEVICE_ID} shell input tap {x} {y}'
    try:
        result = subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=5)
        if result.returncode == 0:
            print(f"点击成功: ({x}, {y})")
        else:
            print(f"点击失败: {result.stderr}")
    except Exception as e:
        print(f"命令执行异常: {str(e)}")
    sleep(delay)

def perform_action(action_name):
    """执行完整的操作流程"""
    print(f"执行操作: {action_name}")
    
    actions = {
        "速训练": lambda: [adb_click(*BUTTONS['训练']), adb_click(*BUTTONS['速']), adb_click(*BUTTONS['速'])],
        "耐训练": lambda: [adb_click(*BUTTONS['训练']), adb_click(*BUTTONS['耐']), adb_click(*BUTTONS['耐'])],
        "力训练": lambda: [adb_click(*BUTTONS['训练']), adb_click(*BUTTONS['力']), adb_click(*BUTTONS['力'])],
        "根训练": lambda: [adb_click(*BUTTONS['训练']), adb_click(*BUTTONS['根']), adb_click(*BUTTONS['根'])],
        "智训练": lambda: [adb_click(*BUTTONS['训练']), adb_click(*BUTTONS['智']), adb_click(*BUTTONS['智'])],
        "SS训练": lambda: [adb_click(*BUTTONS['训练']), adb_click(*BUTTONS['SS']), adb_click(*BUTTONS['SS'])],
        "休息": lambda: [adb_click(*BUTTONS['休息'])],
        "友人出行": lambda: [adb_click(*BUTTONS['出行']), adb_click(*BUTTONS['友人'])],
        "单独出行": lambda: [adb_click(*BUTTONS['出行']), adb_click(*BUTTONS['担当'])],
        "比赛": lambda: [adb_click(*BUTTONS['比赛'])]
    }
    
    if action := actions.get(action_name):
        action()

def parse_umaai_data(parameters):
    """解析umaai数据并返回最佳选项"""
    scores = {
        "速训练": float(parameters[6]),
        "耐训练": float(parameters[7]),
        "力训练": float(parameters[8]),
        "根训练": float(parameters[9]),
        "智训练": float(parameters[10]),
        "SS训练": float(parameters[11]),
        "休息": float(parameters[12]),
        "友人出行": float(parameters[13]),
        "单独出行": float(parameters[14]),
        "比赛": float(parameters[15])
    }
    
    best_action = max(scores, key=scores.get)
    print(f"当前回合建议: {best_action} (分数: {scores[best_action]})")
    return best_action

def get_target_ports_once():
    """启动时一次性获取目标端口"""
    global target_ports
    for conn in psutil.net_connections(kind='tcp'):
        if conn.status == 'ESTABLISHED' and conn.pid:
            try:
                process = psutil.Process(conn.pid)
                if process.exe() == TARGET_EXE:
                    target_ports.add(conn.laddr.port)
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                continue
    print(f"初始目标端口: {target_ports}")

def websocket_decrypt(raw_data):
    """优化后的解密函数"""
    try:
        # 快速检查数据有效性
        if len(raw_data) < 16:  # 至少需要8字节
            return None
            
        # 直接处理二进制数据，跳过hex转换
        mask_key = raw_data[4:8]
        masked_payload = raw_data[8:]
        
        # 使用列表推导式优化解密过程
        decrypted = bytes(b ^ mask_key[i % 4] for i, b in enumerate(masked_payload))
        return decrypted.decode('utf-8', 'ignore')
    except Exception as e:
        return None

async def process_packet_queue():
    """异步处理数据包队列"""
    while processing:
        try:
            packet_data = await packet_buffer.get()
            if "PrintUmaAiResult" in packet_data:
                data = json.loads(packet_data)
                params = data["Parameters"][0].split()
                params = [float(p) if not p.startswith('-') and p.replace('.', '', 1).isdigit() else 0.0 
                         for p in params]
                
                if len(params) >= 14:
                    best_action = parse_umaai_data(params)
                    sleep(2.5)
                    executor.submit(perform_action, best_action)
            
            packet_buffer.task_done()
        except Exception as e:
            print(f"处理包异常: {str(e)}")

def packet_callback(packet):
    """数据包回调函数"""
    try:
        if not packet.haslayer(TCP):
            return
            
        # 快速过滤
        if packet[TCP].dport != FIXED_DST_PORT or packet[TCP].sport not in target_ports:
            return
            
        # 检查是否有负载
        if not packet.haslayer(Raw):
            return
            
        payload = bytes(packet[Raw])
        if len(payload) < HEARTBEAT_MAX_LEN:
            return
            
        if result := websocket_decrypt(payload):
            asyncio.run_coroutine_threadsafe(packet_buffer.put(result), loop)
            
    except Exception as e:
        print(f"回调异常: {str(e)}")

def start_capture():
    """优化后的抓包函数"""
    print("启动高速流量监控...")
    
    # 设置BPF过滤器，在抓包层面就过滤
    filter_str = f"tcp and dst port {FIXED_DST_PORT} and ("
    filter_str += " or ".join(f"src port {port}" for port in target_ports)
    filter_str += ")"
    
    # 使用AsyncSniffer进行异步抓包
    sniffer = AsyncSniffer(
        iface=r'\Device\NPF_Loopback',
        filter=filter_str,
        prn=packet_callback,
        store=0  # 不保存包，减少内存使用
    )
    
    return sniffer

if __name__ == '__main__':
    # 初始化目标端口
    get_target_ports_once()
    
    # 创建事件循环
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    
    # 启动异步处理队列
    loop.create_task(process_packet_queue())
    
    # 启动事件循环
    threading.Thread(target=loop.run_forever, daemon=True).start()
    
    while True:
        try:
            # 启动抓包
            sniffer = start_capture()
            sniffer.start()
            sniffer.join()
        except Exception as e:
            print(f"捕获异常: {str(e)}，3秒后重试...")
            sleep(3)
