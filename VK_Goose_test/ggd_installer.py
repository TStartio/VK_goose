import os
import winreg
import requests
import re
import subprocess
import ctypes
import sys
import tempfile
import traceback
import time


def is_admin():
    try:
        result = ctypes.windll.shell32.IsUserAnAdmin()
        print('Проверка прав администратора: успешно')
        return result
    except Exception as e:
        print('Ошибка проверки прав администратора')
        traceback.print_exc()
        return False


def get_steam_path():
    print('Поиск пути к Steam...')
    try:
        key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, r"Software\Valve\Steam")
        steam_path = winreg.QueryValueEx(key, "SteamPath")[0]
        winreg.CloseKey(key)
        fixed_path = steam_path.replace('/', '\\')
        print(f'Путь к Steam: {fixed_path}')
        return fixed_path
    except Exception as e:
        print('Не удалось найти путь к Steam')
        traceback.print_exc()
        return None


def parse_libraryfolders(steam_path):
    print('Поиск Steam-библиотек...')
    vdf_path = os.path.join(steam_path, 'steamapps', 'libraryfolders.vdf')
    libraries = []

    if not os.path.exists(vdf_path):
        print("[ОШИБКА] Файл libraryfolders.vdf не найден!")
        return libraries

    try:
        with open(vdf_path, 'r', encoding='utf-8') as f:
            content = f.read()
            found = re.findall(r'"path"\s+"(.*?)"', content)
            libraries = [p.replace('\\\\', '\\') for p in found]
            print(f"Найдено Steam-библиотек: {len(libraries)}")
    except Exception as e:
        print(f"Ошибка чтения libraryfolders.vdf: {str(e)}")
        traceback.print_exc()

    return libraries


def find_game_data_path():
    print("\n=== Поиск игры ===")
    steam_path = get_steam_path()
    if not steam_path:
        return None

    default_path = os.path.join(
        steam_path,
        'steamapps',
        'common',
        'Goose Goose Duck',
        'Goose Goose Duck_Data'
    )
    print(f"\nПроверка стандартного пути: {default_path}")
    if os.path.exists(default_path):
        print("Игра найдена в стандартной папке!")
        return default_path

    libraries = parse_libraryfolders(steam_path)
    for i, lib in enumerate(libraries, 1):
        game_path = os.path.join(
            lib,
            'steamapps',
            'common',
            'Goose Goose Duck',
            'Goose Goose Duck_Data'
        )
        print(f"\nПроверка библиотеки {i}/{len(libraries)}: {game_path}")
        if os.path.exists(game_path):
            print("Игра найдена в альтернативной библиотеке!")
            return game_path

    print("\n[ОШИБКА] Игра не найдена в Steam-библиотеках!")
    return None


def download_reg_file(url):
    print("\n=== Загрузка файла реестра ===")
    print(f"Источник: {url}")

    try:
        session = requests.Session()
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
        }

        response = session.get(url, headers=headers, allow_redirects=True)
        response.raise_for_status()

        if "confirm=" in response.url:
            import re
            confirm_token = re.findall(r"confirm=([\w-]+)", response.url)
            if confirm_token:
                new_url = f"{url}&confirm={confirm_token[0]}"
                response = session.get(new_url, headers=headers, allow_redirects=True)
                response.raise_for_status()

        print("Файл реестра загружен успешно")
        return response.content

    except Exception as e:
        print(f"Ошибка загрузки: {str(e)}")
        traceback.print_exc()
        return None


def modify_and_import_reg(data, game_path):
    print("\n=== Обработка реестра ===")
    original_path = r"C:\Games\GameSoft\steamapps\common\Goose Goose Duck\Goose Goose Duck_Data"

    try:
        try:
            content = data.decode('utf-16')
        except UnicodeDecodeError:
            content = data.decode('utf-8')

        pattern = re.escape(original_path.replace('\\', '\\\\'))
        replacement = game_path.replace('\\', '\\\\')
        modified = content.replace(pattern, replacement)

        with tempfile.NamedTemporaryFile(
                mode='w',
                encoding='utf-16',
                suffix='.reg',
                delete=False
        ) as f:
            f.write(modified)
            tmp_path = f.name

        print(f"Импорт файла реестра: {tmp_path}")
        result = subprocess.run(
            f'reg import "{tmp_path}"',
            capture_output=True,
            text=True,
            shell=True
        )

        if result.returncode == 0:
            print("Реестр успешно обновлен!")
        else:
            print(f"Ошибка импорта (код {result.returncode}): {result.stderr}")

        os.remove(tmp_path)
        return result.returncode == 0

    except Exception as e:
        print(f"Критическая ошибка: {str(e)}")
        traceback.print_exc()
        return False


def launch_game():
    print("\n=== Запуск игры ===")
    try:
        os.startfile('steam://rungameid/1568590')
        print("Запуск игры через Steam...")
    except Exception as e:
        print(f"Ошибка запуска: {str(e)}")
        traceback.print_exc()


def main():
    if not is_admin():
        print("\nТребуются права администратора!")
        print("Попытка перезапуска с повышенными привилегиями...")

        script = os.path.abspath(sys.argv[0])
        params = ' '.join([script] + sys.argv[1:])

        result = ctypes.windll.shell32.ShellExecuteW(
            None,
            "runas",
            sys.executable,
            params,
            None,
            1
        )

        if result <= 32:
            errors = {
                2: "Файл не найден",
                3: "Путь не найден",
                5: "Доступ запрещен",
                8: "Недостаточно памяти",
                13: "Ошибка взаимодействия",
                1223: "Отменено пользователем"
            }
            print(f"Ошибка перезапуска: {errors.get(result, 'Код ' + str(result))}")
            time.sleep(5)
        return

    try:
        game_path = find_game_data_path()
        if not game_path:
            print("\nИгра не найдена!")
            input("Нажмите Enter для выхода...")
            return

        REG_URL = 'https://drive.google.com/uc?export=download&id=18Yr6wfSAJZTqhttMFVDNx7pZkez2vJBq'
        reg_data = download_reg_file(REG_URL)
        if not reg_data:
            print("\nНе удалось загрузить файл реестра")
            input("Нажмите Enter для выхода...")
            return

        if not modify_and_import_reg(reg_data, game_path):
            print("\nОшибка изменения реестра")
            input("Нажмите Enter для выхода...")
            return

        launch_game()
        print("\nВыполнение завершено успешно!")

    except Exception as e:
        print(f"\nКритическая ошибка: {str(e)}")
        traceback.print_exc()

    input("\nНажмите Enter для выхода...")


if __name__ == "__main__":
    if '--debug' in sys.argv:
        main()
    else:
        time.sleep(1)
        main()