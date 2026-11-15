import os
import aiohttp
import gspread
import asyncio
from config import SPREADSHEET_ID

def _get_spreadsheet():
    gc = gspread.service_account(filename="credentials.json")
    return gc.open_by_key(SPREADSHEET_ID)

async def upload_photo_to_telegraph(file_bytes: bytes) -> str:
    """Загружает фото на ImgBB и возвращает прямую ссылку."""
    imgbb_key = os.environ.get("IMGBB_KEY")
    if not imgbb_key:
        raise ValueError("Ключ IMGBB_KEY не найден в переменных окружения!")
        
    url = f"https://api.imgbb.com/1/upload?key={imgbb_key}"
    data = aiohttp.FormData()
    data.add_field('image', file_bytes, filename='photo.jpg', content_type='image/jpeg')
    
    async with aiohttp.ClientSession() as session:
        async with session.post(url, data=data) as response:
            result = await response.json()
            if result.get("success"):
                return result["data"]["url"]
            raise ValueError(f"Ошибка ImgBB: {result.get('error', {}).get('message', 'Сбой загрузки')}")

# --- РАБОТА С ТУРАМИ ---

def _append_tour_sync(row: list):
    sh = _get_spreadsheet()
    worksheet = sh.worksheet("Tours")
    
    # Забираем все значения из первого столбца (Название)
    col_a = worksheet.col_values(1)
    
    target_row = None
    # Ищем первую пустую ячейку начиная со 2-й строки (1-я — шапка)
    for idx in range(2, len(col_a) + 1):
        if not str(col_a[idx - 1]).strip():
            target_row = idx
            break
            
    # Если пустых строк в середине нет, пишем в конец таблицы
    if target_row is None:
        target_row = len(col_a) + 1
        
    # Вписываем данные тура строго в найденную свободную строку (диапазон A:G)
    worksheet.update(range_name=f"A{target_row}:G{target_row}", values=[row])

async def append_tour_to_sheet(row: list):
    await asyncio.to_thread(_append_tour_sync, row)

def _get_tours_sync(only_for_site: bool = False):
    sh = _get_spreadsheet()
    worksheet = sh.worksheet("Tours")
    records = worksheet.get_all_records()
    
    result = []
    # Индекс строки в таблице начинается с 2 (1-я строка — шапка)
    for idx, r in enumerate(records, start=2):
        # Пропускаем пустые строки, если они образовались после ручной очистки
        if not str(r.get("Название", "")).strip():
            continue
            
        dest = str(r.get("Место публикации", "")).strip()
        if only_for_site and dest not in ["both", "site"]:
            continue
        r["row_index"] = idx  # Запоминаем номер строки для редактирования/удаления
        result.append(r)
    return result

async def get_tours(only_for_site: bool = False):
    return await asyncio.to_thread(_get_tours_sync, only_for_site)

def _delete_tour_sync(row_index: int):
    sh = _get_spreadsheet()
    worksheet = sh.worksheet("Tours")
    worksheet.delete_rows(row_index)

async def delete_tour_from_sheet(row_index: int):
    await asyncio.to_thread(_delete_tour_sync, row_index)

def _update_tour_field_sync(row_index: int, col_index: int, new_value: str):
    sh = _get_spreadsheet()
    worksheet = sh.worksheet("Tours")
    worksheet.update_cell(row_index, col_index, new_value)

async def update_tour_field(row_index: int, col_index: int, new_value: str):
    await asyncio.to_thread(_update_tour_field_sync, row_index, col_index, new_value)

# --- РАБОТА С НАСТРОЙКАМИ САЙТА ---

def _get_settings_sync():
    sh = _get_spreadsheet()
    worksheet = sh.worksheet("Settings")
    records = worksheet.get_all_records()
    return {str(r.get("Параметр")).strip(): str(r.get("Значение")).strip() for r in records if r.get("Параметр")}

async def get_site_settings():
    return await asyncio.to_thread(_get_settings_sync)
