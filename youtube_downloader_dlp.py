import re
import requests
import os
import base64
from dotenv import load_dotenv
from yt_dlp import YoutubeDL
load_dotenv()
CLIENT_SECRET = os.getenv('CLIENT_SECRET')
CLIENT_ID = os.getenv('CLIENT_ID')
YDL_OPTS = {
        "skip_download": True,
        "format": "bestaudio/best",
        "default_search": "ytsearch1",
        "playlistend": 1,
        "noplaylist": True,
    }
def get_token()->None:
    auth_string = CLIENT_ID + ":" + CLIENT_SECRET
    auth_bytes = auth_string.encode("utf-8")
    auth_base64 = str(base64.b64encode(auth_bytes), "utf-8")
    token_res = requests.post("https://accounts.spotify.com/api/token",headers={
            "Authorization": f"Basic {auth_base64}",
            "Content-Type": "application/x-www-form-urlencoded",
        },
        data={"grant_type": "client_credentials"},)
    token = token_res.json()['access_token']
    return token
async def get_Song_Info(url:str)->tuple:
    pattern = re.compile(r'(?:https://)([a-z.]+)(?:/\w+/?)(\w+)')
    m = pattern.match(url)
    if m is None: #m None means its a search
        with YoutubeDL(YDL_OPTS) as ydl:
            result = ydl.extract_info(url)
            if 'channel' in (result['entries'][0]['original_url']):
                return (result['title'],result['entries'][0]['entries'][0]['entries'][0]['original_url']) #<-- LOL 
            return (result['title'],result['entries'][0]['original_url'])
    if 'spotify' in m.group(1):
        id = m.group(2)
        api_link = 'https://api.spotify.com/v1/tracks/'+id
        token = get_token()
        info = requests.get(api_link,headers={"Authorization": f"Bearer {token}"})
        song_info = info.json()
        song_name = song_info['artists'][0]['name'] +' - '+song_info['name'] 
        with YoutubeDL(YDL_OPTS) as ydl:
            result = ydl.extract_info(song_name)
            return (result['title'],result['entries'][0]['original_url'])
    if 'youtu' in m.group(1):
        with YoutubeDL(YDL_OPTS) as ydl:
            result = ydl.extract_info(url)
            return (result['title'],url)
    
async def get_Audio_Source(url:str)->str:
    with YoutubeDL(YDL_OPTS) as ydl:
        result = ydl.extract_info(url)
        return result['url']