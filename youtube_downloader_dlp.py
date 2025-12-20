from yt_dlp import YoutubeDL
from pytubefix import Search, YouTube
import validators
async def get_Youtube_Info(url:str)->tuple|None:
    query = Search(url)
    if not validators.url(url):
        text = query.results[0]
        url = text.watch_url    
        title = text.title
        print(url,title)
        return (title,url)
    yt = YouTube(url)
    try:
        return (str(yt.title),str(url))
    except:
        return (None,None)
    
async def get_Audio_Source(url:str)->str:
    ydl_opts =  {
        "format": "bestaudio/best",
        "noplaylist" : True,
    }
    with YoutubeDL(ydl_opts) as ydl:
        info = ydl.extract_info(url, download=False)
        return str(info['url'])
    return None