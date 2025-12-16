from pytubefix import YouTube

def downloadYt(url:str)->tuple:
    try:
        yt = YouTube(url)
        ys = yt.streams.get_audio_only()
        return(yt.title,ys.download('audio_files'))
        
    except:
        print('Not valid url!')
        return None

def getYtTitle(url:str) ->str:
    try:
        return YouTube(url).title
    except:
        return None
