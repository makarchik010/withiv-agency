import aiohttp
import gspread
import asyncio
from config import SPREADSHEET_ID

async def upload_photo_to_telegraph(file_bytes: bytes) -> str:
    url = 'https://telegra.ph/upload'
    data = aiohttp.FormData()
    data.add_field('file', file_bytes, filename='photo.jpg', content_type='image/jpeg')
    async with aiohttp.ClientSession() as session:
        async with session.post(url, data=data) as response:
            result = await response.json()
            if isinstance(result, list) and 'src' in result[0]:
                return f"https://telegra.ph{result[0]['src']}"
            raise ValueError("Ошибка при загрузке фото на Telegraph")

def _append_to_google_sheet_sync(row: list):
    gc = gspread.service_account(filename="credentials.json")
    sh = gc.open_by_key(SPREADSHEET_ID)
    worksheet = sh.sheet1
    worksheet.append_row(row)

async def append_tour_to_sheet(row: list):
    await asyncio.to_thread(_append_to_google_sheet_sync, row)