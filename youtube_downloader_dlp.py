import re
import requests
import os
import base64
from dotenv import load_dotenv
from yt_dlp import YoutubeDL
from yt_dlp.utils import DownloadError
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
YOUTUBE = 'youtu'
SOUNDCLOUD = 'soundcloud'
SPOTIFY = 'spotify'
def get_token()->None|str:
    auth_string = CLIENT_ID + ":" + CLIENT_SECRET
    auth_bytes = auth_string.encode("utf-8")
    auth_base64 = str(base64.b64encode(auth_bytes), "utf-8")
    token_res = requests.post("https://accounts.spotify.com/api/token",headers={
            "Authorization": f"Basic {auth_base64}",
            "Content-Type": "application/x-www-form-urlencoded",
        },
        data={"grant_type": "client_credentials"},)
    if token_res.status_code == 200:
        token = token_res.json()['access_token']
        return token
    print(f'Token collection returned: {token_res.reason}:{token_res.status_code}')
    return None
def get_Youtube_Info(url:str)->tuple[str:str]|tuple[None:None]:
    try:
        with YoutubeDL(YDL_OPTS) as ydl:
            result = ydl.extract_info(url)
            return (result['title'],url)
    except DownloadError:
        return (None,None)
    
def get_Spotify_Info(track_id:str)->tuple[str:str]|tuple[None:None]:
    if track_id is None:
        return (None,None)
    api_link = 'https://api.spotify.com/v1/tracks/'+track_id
    token = get_token()
    info = requests.get(api_link,headers={"Authorization": f"Bearer {token}"}) 
    if info.status_code == 200:
        song_json = info.json()
        song_info = song_json['artists'][0]['name'] + ' - ' + song_json['name'] 
        with YoutubeDL(YDL_OPTS) as ydl:
            result = ydl.extract_info(song_info)
            song_name = result['title']
            song_url = result['entries'][0]['original_url']
            return (song_name,song_url)
    print(f'Spotify returned error: {info.reason}:{info.status_code}')
    return (None,None)

def get_Soundcloud_Info(url:str)->tuple[str:str]|tuple[None:None]:
    if re.match(r'(.*sets+.*)(?:\?)',url):
        print('Soundcloud playlists are not accepted')
        return(None,None)
    with YoutubeDL(YDL_OPTS) as ydl:
        pattern = re.compile(r'(.*)(?:\?)') #formats soundclound links to just be domain/artist/track_name
        formatted_url = pattern.match(url).group(1)
        result = ydl.extract_info(formatted_url)
        restricted = True
        for key in result['formats']:
            if 'http_mp3' in key['format_id']:
                restricted = False
        if restricted:
            print('Unable to retrieve soundcloud http_mp3')
            return (None,None)
        return (result['title'],formatted_url)   
    
def search_Query(query:str)->tuple[str:str]:
    with YoutubeDL(YDL_OPTS) as ydl:    
        result = ydl.extract_info(query)
        if 'channel' in (result['entries'][0]['original_url']):
            return (result['title'],result['entries'][0]['entries'][0]['entries'][0]['original_url']) #<-- TODO Terrible code fix later
        song_url = result['entries'][0]['original_url']
        song_title = result['title']
        return (song_title,song_url)
    
async def get_Song_Info(url:str)->tuple[str:str]|tuple[None:None]:
    pattern = re.compile(r'(?:https://)([a-z.]+)(?:/\w+/?)(\w+)') #filters link into two groups domain and track id for spotify links
    grouped_url = pattern.match(url)
    if grouped_url is None:
        return search_Query(url)
    url_domain = grouped_url.group(1)
    print(f'Domain: {url_domain}')
    if SPOTIFY in url_domain:
        track_id = grouped_url.group(2)
        return get_Spotify_Info(track_id)
    if YOUTUBE in url_domain:
        return get_Youtube_Info(url)
    if SOUNDCLOUD in url_domain:
        return get_Soundcloud_Info(url)
    return (None,None)
async def get_Audio_Source(url:str)->str:
    try:
        with YoutubeDL(YDL_OPTS) as ydl:
            result = ydl.extract_info(url)
            return result['url']
    except DownloadError as e:
        print(e)