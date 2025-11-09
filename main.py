import os
import requests
import spotipy
from spotipy.oauth2 import SpotifyOAuth
import pandas as pd
import time
from sklearn.preprocessing import MultiLabelBinarizer
from collections import Counter

# ---------------- Spotify Auth ----------------
def init_spotify():
    os.environ['SPOTIPY_CLIENT_ID'] = '18b00fe3ef5e436bb0570c04b7dcb2d8'
    os.environ['SPOTIPY_CLIENT_SECRET'] = '05734e0c68c247939099fb7b1f410124'
    os.environ['SPOTIPY_REDIRECT_URI'] = 'http://127.0.0.1:8888/callback'
    return spotipy.Spotify(auth_manager=SpotifyOAuth(
        scope="playlist-read-private",
        redirect_uri=os.environ['SPOTIPY_REDIRECT_URI']
    ))

# ---------------- Fetch Playlist Tracks ----------------
def fetch_playlist_tracks(sp, playlist_id):
    results = sp.playlist_items(playlist_id, limit=100)
    tracks = [
        {
            "spotify_id": item['track']['id'],
            "name": item['track']['name'],
            "artists": [artist['name'] for artist in item['track']['artists']],
            "artist_ids": [artist['id'] for artist in item['track']['artists']]
        }
        for item in results['items'] if item['track'] is not None
    ]
    print(f"Found {len(tracks)} tracks in the playlist.")
    return tracks

# ---------------- Build Global Genre List ----------------
def collect_global_genres(sp, tracks):
    artist_cache = {}
    all_genres_list = []

    for track in tracks:
        for artist_id in track['artist_ids']:
            if artist_id in artist_cache:
                genres = artist_cache[artist_id]
            else:
                try:
                    artist_info = sp.artist(artist_id)
                    genres = artist_info.get('genres', []) if artist_info else []
                    artist_cache[artist_id] = genres
                except Exception as e:
                    print(f"Warning: Could not fetch genres for artist {artist_id}: {e}")
                    genres = []
            all_genres_list.extend(genres)

    # Count frequency and keep top 150
    genre_counts = Counter(all_genres_list)
    top_genres = [genre for genre, _ in genre_counts.most_common(150)]
    print(f"Top {len(top_genres)} genres collected dynamically from playlist.")
    return top_genres, artist_cache

# ---------------- Fetch Track Data ----------------
def fetch_track_data(sp, tracks, artist_cache):
    all_data = []
    headers = {"Accept": "application/json"}

    for idx, track in enumerate(tracks, 1):
        spotify_id = track['spotify_id']
        track_name = track['name']
        artist_names = track['artists']
        artist_ids = track['artist_ids']

        try:
            # --- ReccoBeats lookup ---
            multi_track_url = f"https://api.reccobeats.com/v1/track?ids={spotify_id}"
            response = requests.get(multi_track_url, headers=headers)
            if response.status_code != 200:
                print(f"[{idx}] Failed ReccoBeats lookup for '{track_name}': {response.status_code}")
                continue

            data = response.json()
            if "content" not in data or not data["content"]:
                print(f"[{idx}] No ReccoBeats entry for '{track_name}'")
                continue

            recco_uuid = data["content"][0]["id"]

            # --- Get audio features ---
            features_url = f"https://api.reccobeats.com/v1/track/{recco_uuid}/audio-features"
            features_response = requests.get(features_url, headers=headers)
            if features_response.status_code != 200:
                print(f"[{idx}] Failed to fetch audio features for '{track_name}': {features_response.status_code}")
                continue

            features_data = features_response.json()

            # --- Spotify metadata ---
            spotify_metadata = sp.track(spotify_id)

            # --- Artist genres ---
            all_genres = set()
            for artist_id in artist_ids:
                all_genres.update(artist_cache.get(artist_id, []))

            # --- Combine data ---
            combined = {
                "track_name": track_name,
                "artist_names": ", ".join(artist_names),
                "spotify_id": spotify_id,
                "recco_uuid": recco_uuid,
                "duration_ms": spotify_metadata.get("duration_ms"),
                "popularity": spotify_metadata.get("popularity"),
                "album_name": spotify_metadata['album']['name'],
                "release_date": spotify_metadata['album']['release_date'],
                "genres": list(all_genres),
                "acousticness": features_data.get("acousticness"),
                "danceability": features_data.get("danceability"),
                "energy": features_data.get("energy"),
                "instrumentalness": features_data.get("instrumentalness"),
                "key": features_data.get("key"),
                "liveness": features_data.get("liveness"),
                "loudness": features_data.get("loudness"),
                "mode": features_data.get("mode"),
                "speechiness": features_data.get("speechiness"),
                "tempo": features_data.get("tempo"),
                "valence": features_data.get("valence"),
                "spotify_href": spotify_metadata.get("external_urls", {}).get("spotify"),
                "album_href": spotify_metadata['album']['external_urls']['spotify']
            }

            all_data.append(combined)
            print(f"[{idx}] ✅ '{track_name}' fetched successfully ({len(all_genres)} genres).")
            time.sleep(0.2)

        except Exception as e:
            print(f"[{idx}] ❌ Error processing '{track_name}': {e}")

    return all_data

# ---------------- One-Hot Encode and Save ----------------
def encode_and_save(df, top_genres, filename="playlist_audio_features_with_expanded_genres.csv"):
    # Ensure genre column is list
    df['genres'] = df['genres'].apply(lambda x: x if isinstance(x, list) else [])
    mlb = MultiLabelBinarizer(classes=top_genres)
    genre_encoded = mlb.fit_transform(df['genres'])
    genre_df = pd.DataFrame(genre_encoded, columns=mlb.classes_)
    df = pd.concat([df.drop(columns=["genres"]), genre_df], axis=1)
    df.to_csv(filename, index=False)
    print(f"✅ All data saved to '{filename}'")
    return df

# ---------------- Main Execution ----------------
if __name__ == "__main__":
    sp = init_spotify()
    playlist_id = "5SxG5yIfVryB1UClEPNc7n"
    tracks = fetch_playlist_tracks(sp, playlist_id)
    top_genres, artist_cache = collect_global_genres(sp, tracks)
    all_data = fetch_track_data(sp, tracks, artist_cache)
    df = pd.DataFrame(all_data)
    df = encode_and_save(df, top_genres)