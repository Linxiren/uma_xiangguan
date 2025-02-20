from InquirerPy import inquirer
import subprocess

def run_adb_and_jt():
    subprocess.run(['python', 'adb_control.py'])
    subprocess.run(['python', 'jt.py'])

def run_gui():
    subprocess.run(['python', 'gui.py'])

def main():
    menu_choice = inquirer.select(
        message="菜单(用↑和↓切换选项，回车确认):",
        choices=["启动", "设置"],
    ).execute()

    if menu_choice == "启动":
        run_adb_and_jt()
    elif menu_choice == "设置":
        run_gui()

if __name__ == '__main__':
    main()