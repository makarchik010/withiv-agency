import os
import re
import time
import json
import base64
import asyncio
import aiohttp
import gspread
from google.oauth2.service_account import Credentials
from config import SPREADSHEET_ID

_cached_spreadsheet = None
_cache_time = 0


def _get_spreadsheet():
    global _cached_spreadsheet, _cache_time
    # Держим подключение в памяти 45 минут (токен Google живет 60 минут)
    if _cached_spreadsheet is not None and (time.time() - _cache_time) < 2700:
        return _cached_spreadsheet

    b64_creds = os.getenv("GOOGLE_B64_CREDS", "")
    if b64_creds:
        clean_b64 = re.sub(r'[^A-Za-z0-9+/=]', '', b64_creds)
        creds_dict = json.loads(base64.b64decode(clean_b64).decode("utf-8"))
        credentials = Credentials.from_service_account_info(
            creds_dict,
            scopes=[
                "https://www.googleapis.com/auth/spreadsheets",
                "https://www.googleapis.com/auth/drive"
            ]
        )
        gc = gspread.authorize(credentials)
    else:
        # Фолбэк для локального запуска, если переменной нет
        gc = gspread.service_account(filename="credentials.json")

    _cached_spreadsheet = gc.open_by_key(SPREADSHEET_ID.strip())
    _cache_time = time.time()
    return _cached_spreadsheet


async def upload_photo_to_telegraph(file_bytes: bytes) -> str:
    """Загружает фото на Telegraph (Telegram) и возвращает прямую ссылку. Хранится вечно."""
    url = "https://telegra.ph/upload"
    data = aiohttp.FormData()
    data.add_field('file', file_bytes, filename='photo.jpg', content_type='image/jpeg')

    async with aiohttp.ClientSession() as session:
        async with session.post(url, data=data) as response:
            result = await response.json()
            if isinstance(result, list) and "src" in result[0]:
                return f"https://telegra.ph{result[0]['src']}"
            raise ValueError(f"Ошибка загрузки на Telegraph: {result}")


# --- РАБОТА С ТУРАМИ ---

def _append_tour_sync(row: list):
    sh = _get_spreadsheet()
    worksheet = sh.worksheet("Tours")
    clean_row = [str(item) if item is not None else "" for item in row]
    worksheet.append_row(clean_row, value_input_option='USER_ENTERED')


async def append_tour_to_sheet(row: list):
    await asyncio.to_thread(_append_tour_sync, row)


def _get_tours_sync(only_for_site: bool = False):
    sh = _get_spreadsheet()
    worksheet = sh.worksheet("Tours")
    records = worksheet.get_all_records()

    result = []
    for idx, r in enumerate(records, start=2):
        if not str(r.get("Название", "")).strip():
            continue
        dest = str(r.get("Место публикации", "")).strip()
        if only_for_site and dest not in ["both", "site"]:
            continue
        r["row_index"] = idx
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
    worksheet.update_cell(row_index, col_index, str(new_value))


async def update_tour_field(row_index: int, col_index: int, new_value: str):
    await asyncio.to_thread(_update_tour_field_sync, row_index, col_index, new_value)


# --- РАБОТА С ОТЗЫВАМИ ---

def _append_review_sync(row: list):
    sh = _get_spreadsheet()
    worksheet = sh.worksheet("Reviews")
    clean_row = [str(item) if item is not None else "" for item in row]
    worksheet.append_row(clean_row, value_input_option='USER_ENTERED')


async def append_review(row: list):
    await asyncio.to_thread(_append_review_sync, row)


def _get_reviews_sync():
    sh = _get_spreadsheet()
    worksheet = sh.worksheet("Reviews")
    records = worksheet.get_all_records()

    result = []
    for idx, r in enumerate(records, start=2):
        if not str(r.get("Имя", "")).strip():
            continue
        r["row_index"] = idx
        result.append(r)
    return result


async def get_reviews():
    return await asyncio.to_thread(_get_reviews_sync)


def _delete_review_sync(row_index: int):
    sh = _get_spreadsheet()
    worksheet = sh.worksheet("Reviews")
    worksheet.delete_rows(row_index)


async def delete_review(row_index: int):
    await asyncio.to_thread(_delete_review_sync, row_index)


# --- РАБОТА С НАСТРОЙКАМИ САЙТА ---

def _get_settings_sync():
    sh = _get_spreadsheet()
    worksheet = sh.worksheet("Settings")
    records = worksheet.get_all_records()
    return {str(r.get("Параметр")).strip(): str(r.get("Значение")).strip() for r in records if r.get("Параметр")}


async def get_site_settings():
    return await asyncio.to_thread(_get_settings_sync)
