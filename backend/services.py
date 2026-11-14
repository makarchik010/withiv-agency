import os
import aiohttp
import gspread
import asyncio
from config import SPREADSHEET_ID

# Оставляем старое название функции, чтобы не ломать код в других файлах
async def upload_photo_to_telegraph(file_bytes: bytes) -> str:
    """Загружает фото на ImgBB и возвращает прямую ссылку для сайта."""
    imgbb_key = os.environ.get("IMGBB_KEY")
    if not imgbb_key:
        raise ValueError("Ключ IMGBB_KEY не найден в настройках!")
        
    url = f"https://api.imgbb.com/1/upload?key={imgbb_key}"
    data = aiohttp.FormData()
    data.add_field('image', file_bytes, filename='photo.jpg', content_type='image/jpeg')
    
    async with aiohttp.ClientSession() as session:
        async with session.post(url, data=data) as response:
            result = await response.json()
            if result.get("success"):
                return result["data"]["url"]
            raise ValueError(f"Ошибка ImgBB: {result.get('error', {}).get('message', 'Неизвестная ошибка')}")

def _append_to_google_sheet_sync(row: list):
    gc = gspread.service_account(filename="credentials.json")
    sh = gc.open_by_key(SPREADSHEET_ID)
    worksheet = sh.sheet1
    worksheet.append_row(row)

async def append_tour_to_sheet(row: list):
    await asyncio.to_thread(_append_to_google_sheet_sync, row)