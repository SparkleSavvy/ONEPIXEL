import requests
import json
from pathlib import Path
from tqdm import tqdm
from concurrent.futures import ThreadPoolExecutor, as_completed

def load_config(config_path="config.json"):
    with open(config_path, "r", encoding="utf-8") as f:
        return json.load(f)

def get_releases(owner, repo, token=None):
    url = f"https://api.github.com/repos/{owner}/{repo}/releases"
    headers = {"Accept": "application/vnd.github.v3+json"}
    if token:
        headers["Authorization"] = f"token {token}"
    response = requests.get(url, headers=headers)
    response.raise_for_status()
    return response.json()

def filter_mrpack_assets(release):
    return [asset for asset in release.get("assets", []) if asset["name"].endswith(".mrpack")]

def choose_version_and_download(releases, download_dir):
    print("\nДоступные версии:")
    available = [(i, r) for i, r in enumerate(releases) if filter_mrpack_assets(r)]
    for i, release in available:
        tag = release.get("tag_name", "unknown")
        print(f"{i + 1}. {tag}")
    print(f"{len(available) + 1}. Скачать все версии")

    try:
        choice = int(input("\nВыберите действие: ")) - 1
    except ValueError:
        print("Неверный ввод.")
        return

    if choice == len(available):  # Скачать всё
        download_all_versions(releases, download_dir)
    elif 0 <= choice < len(available):
        _, release = available[choice]
        assets = filter_mrpack_assets(release)
        if not assets:
            print("Нет .mrpack файлов в этой версии.")
            return
        if len(assets) == 1:
            asset = assets[0]
        else:
            for idx, asset in enumerate(assets):
                print(f"{idx + 1}. {asset['name']}")
            try:
                idx = int(input("Выберите файл: ")) - 1
                asset = assets[idx]
            except (ValueError, IndexError):
                print("Неверный выбор файла.")
                return
        download_file(asset, download_dir)
    else:
        print("Неверный номер.")

def download_file(asset, download_dir):
    download_path = Path(download_dir)
    download_path.mkdir(exist_ok=True)
    file_url = asset["browser_download_url"]
    filename = asset["name"]
    filepath = download_path / filename

    response = requests.get(file_url, stream=True)
    response.raise_for_status()
    total_size = int(response.headers.get('content-length', 0))

    with open(filepath, 'wb') as f:
        with tqdm(total=total_size, unit='B', unit_scale=True, desc=filename) as pbar:
            for chunk in response.iter_content(chunk_size=8192):
                if chunk:
                    f.write(chunk)
                    pbar.update(len(chunk))

def download_single_asset(args):
    asset, download_dir = args
    download_file(asset, download_dir)

def download_all_versions(releases, download_dir):
    all_assets = []
    for release in releases:
        assets = filter_mrpack_assets(release)
        for asset in assets:
            all_assets.append((release.get("tag_name", "unknown"), asset))

    if not all_assets:
        print("Нет .mrpack файлов для скачивания.")
        return

    print(f"\nНайдено {len(all_assets)} файлов. Начинаю скачивание...")

    # Подготовим аргументы для мультипотока
    tasks = [(asset, download_dir) for _, asset in all_assets]

    # Скачиваем в несколько потоков
    with ThreadPoolExecutor(max_workers=4) as executor:
        futures = [executor.submit(download_single_asset, task) for task in tasks]
        for future in as_completed(futures):
            try:
                future.result()  # Проверяем, не произошло ли исключение
            except Exception as e:
                print(f"Ошибка при скачивании: {e}")

    print("\nВсе файлы скачаны.")

def main():
    config = load_config()
    owner = config["repo_owner"]
    repo = config["repo_name"]
    token = config.get("github_token")
    download_dir = config["download_dir"]

    releases = get_releases(owner, repo, token)

    while True:
        choose_version_and_download(releases, download_dir)
        again = input("\nПродолжить? (y/n): ").lower()
        if again != 'y':
            print("Выход.")
            break

if __name__ == "__main__":
    main()