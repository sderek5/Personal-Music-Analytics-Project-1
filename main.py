import os
import pandas as pd
from spotipy import Spotify
from spotipy.oauth2 import SpotifyOAuth


os.environ['SPOTIPY_CLIENT_ID'] = '18b00fe3ef5e436bb0570c04b7dcb2d8'
os.environ['SPOTIPY_CLIENT_SECRET'] = '05734e0c68c247939099fb7b1f410124'
os.environ['SPOTIPY_REDIRECT_URI'] = 'http://127.0.0.1:8888/callback'



scope = 'user-top-read'
sp = Spotify(auth_manager=SpotifyOAuth(scope=scope, redirect_uri='http://127.0.0.1:8888/callback'))

top_tracks = sp.current_user_top_tracks(limit=10)['items']
for t in top_tracks:
    print(t['name'], "by", t['artists'][0]['name'])