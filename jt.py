import psutil
import pyshark
import binascii
from threading import Event
import time
import json
import subprocess
from time import sleep

# 雷电模拟器adb配置
ADB_PATH = r"E:\leidian\LDPlayer9\adb.exe"  # 修改为你的adb路径
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

def adb_click(x, y, delay=0.3):
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
    
    if action_name == "速训练":
        adb_click(*BUTTONS['训练'])
        adb_click(*BUTTONS['速'])
        adb_click(*BUTTONS['速'])

    elif action_name == "耐训练":
        adb_click(*BUTTONS['训练'])
        adb_click(*BUTTONS['耐'])
        adb_click(*BUTTONS['耐'])

    elif action_name == "力训练":
        adb_click(*BUTTONS['训练'])
        adb_click(*BUTTONS['力'])
        adb_click(*BUTTONS['力'])

    elif action_name == "根训练":
        adb_click(*BUTTONS['训练'])
        adb_click(*BUTTONS['根'])
        adb_click(*BUTTONS['根'])

    elif action_name == "智训练":
        adb_click(*BUTTONS['训练'])
        adb_click(*BUTTONS['智'])
        adb_click(*BUTTONS['智'])

    elif action_name == "SS训练":
        adb_click(*BUTTONS['训练'])
        adb_click(*BUTTONS['SS'])
        adb_click(*BUTTONS['SS'])

    elif action_name == "休息":
        adb_click(*BUTTONS['休息'])
        
    elif action_name == "友人出行":
        adb_click(*BUTTONS['出行'])
        adb_click(*BUTTONS['友人'])
        
    elif action_name == "单独出行":
        adb_click(*BUTTONS['出行'])
        adb_click(*BUTTONS['担当'])
        
    elif action_name == "比赛":
        adb_click(*BUTTONS['比赛'])

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
    
    # 找到最高分选项
    best_action = max(scores, key=scores.get)
    print(f"当前回合建议: {best_action} (分数: {scores[best_action]})")
    return best_action

# 配置参数
TARGET_EXE = r"E:\凯旋门黑板\UmaAi神经网络版（Nvidia显卡专属）.exe"
FIXED_DST_PORT = 4693
HEARTBEAT_MAX_LEN = 60

# 全局变量
target_ports = set()

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
        data = bytes.fromhex(raw_data.replace(':', ''))
        if len(data) < 8:
            return None
            
        mask_key = data[4:8]
        masked_payload = data[8:]
        return bytes([b ^ mask_key[i % 4] for i, b in enumerate(masked_payload)]).decode('utf-8', 'ignore')
    except Exception as e:
        print(f"解密失败: {str(e)}")
        return None

def packet_handler(pkt):
    """优化后的包处理函数"""
    try:
        # 提前过滤无效包
        if 'TCP' not in pkt or not pkt.tcp.payload:
            return

        src_port = int(pkt.tcp.srcport)
        dst_port = int(pkt.tcp.dstport)

        # 快速过滤条件
        if dst_port != FIXED_DST_PORT or src_port not in target_ports:
            return

        payload = pkt.tcp.payload
        payload_len = len(payload)//2

        if payload_len < HEARTBEAT_MAX_LEN:
            return

        # 立即处理解密
        if result := websocket_decrypt(payload):
            print(f"解密结果:\n{'-'*30}\n{result}\n{'-'*30}")
            
            # 解析JSON数据
            if "PrintUmaAiResult" in result:
                data = json.loads(result)
                Parameters = data["Parameters"]
                
                # 提取有效参数（过滤掉前缀）
                params = [float(p) if not p.startswith('-') and p.replace('.', '', 1).isdigit() else 0.0 for p in Parameters[0].split()]

                if len(params) >= 14:
                    best_action = parse_umaai_data(params)
                    perform_action(best_action)

    except Exception as e:
        print(f"包处理异常: {str(e)}")

def start_capture():
    """优化后的抓包函数"""
    print("启动高速流量监控...")
    display_filter = f'tcp.dstport == {FIXED_DST_PORT} && tcp.srcport in {{{",".join(map(str, target_ports))}}}'
    
    capture = pyshark.LiveCapture(
        interface=r'\Device\NPF_Loopback',
        display_filter=display_filter,
        include_raw=True,
        use_json=True,
        only_summaries=False,
        output_file=None,  # 禁用文件输出提升性能
        use_ek=False,      # 禁用实验功能
        debug=False
    )

    # 设置实时嗅探
    capture.set_debug()
    for pkt in capture.sniff_continuously(packet_count=0):
        packet_handler(pkt)

if __name__ == '__main__':
    # 初始化目标端口
    get_target_ports_once()
    
    # 启动抓包
    while True:
        try:
            start_capture()
        except Exception as e:
            print(f"捕获异常: {str(e)}，3秒后重试...")
            time.sleep(3)
