import glob
import unittest
from unittest.mock import MagicMock
from mock import patch
from radio import Recommend, Dialogue

import json
import os
import shutil
from pathlib import Path

import pandas as pd
from feedparser.util import FeedParserDict
from billboard import ChartEntry
from requests.models import Response
from itunespy.track import Track
from pydub.generators import WhiteNoise
from PIL import Image


class Test_Recommend(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.local_song_path = "./test_songs/"
        if not os.path.exists(cls.local_song_path):
            os.makedirs(cls.local_song_path)

    @classmethod
    def tearDownClass(cls):
        if os.path.exists(cls.local_song_path):
            shutil.rmtree(cls.local_song_path)

    @patch("random.random")
    def test_title_day(self, mock_random):
        mock_random.return_value = 0.01
        rec = Recommend()
        title = rec.title()
        self.assertEqual(mock_random.call_count, 1)
        self.assertEqual(isinstance(title, str), True)

    @patch("random.random")
    def test_title_timeofday(self, mock_random):
        mock_random.return_value = 0.99
        rec = Recommend()
        title = rec.title()
        self.assertEqual(mock_random.call_count, 1)
        self.assertEqual(isinstance(title, str), True)

    @patch("radio.parse")
    def test_news(self, mock_parse):
        mock_parse.return_value = FeedParserDict(
            {
                "entries": [
                    {
                        "title": "Title 1",
                        "summary": "Summary 1",
                    },
                    {
                        "title": "Title 2",
                        "summary": "Summary 2",
                    },
                ]
            }
        )
        rec = Recommend()
        news = rec.news("world", 2)
        self.assertEqual(mock_parse.call_count, 1)
        mock_parse.assert_called_once()
        self.assertNotEqual(news, None)
        self.assertEqual(len(news), 2)

    @patch("pandas.read_csv")
    def test_playlist_by_genre(self, mock_read_csv):
        data = {
            "tags": [["rock", "soft rock"], ["rock", "britpop"]],
            "artist_name": ["Adele", "Oasis"],
            "title": ["Hello", "Wonderwall"],
        }
        df = pd.DataFrame(data)
        mock_read_csv.return_value = df

        rec = Recommend()
        songs = rec.playlist_by_genre("rock", 2)
        self.assertNotEqual(songs, None)
        self.assertEqual(len(songs), 2)

    @patch("radio.musicbrainzngs.search_recordings")
    def test_artist_discography(self, mock_search_recordings):
        mock_search_recordings.return_value = {
            "recording-list": [
                {"title": "Song 1"},
                {"title": "Song 2"},
                {"title": "Song 3"},
            ]
        }
        rec = Recommend()
        songs = rec.artist_discography("Artist 1", 2)
        self.assertEqual(mock_search_recordings.call_count, 8)
        self.assertNotEqual(songs, None)
        self.assertEqual(len(songs), 2)

    @patch("radio.billboard.ChartData")
    def test_billboard(self, mock_ChartData):
        mock_ChartData.return_value = {
            ChartEntry("Artist 1", "Song 1", None, None, None, None, None, None),
            ChartEntry("Artist 2", "Song 2", None, None, None, None, None, None),
        }
        rec = Recommend()
        songs = rec.billboard("Chart 1", 2)
        self.assertEqual(mock_ChartData.call_count, 1)
        self.assertNotEqual(songs, None)
        self.assertEqual(len(songs), 2)

    def test_local_music(self):
        rec = Recommend()
        # Create test songs
        song_names = ["song1.mp3", "song2.mp3", "song3.mp3"]
        for song_name in song_names:
            Path(f"./{self.local_song_path}/{song_name}").touch()

        songs = rec.local_music(self.local_song_path, 2)
        self.assertNotEqual(songs, [])
        self.assertEqual(len(songs), 2)
        self.assertEqual(
            set(song_names).issuperset(set(song.split("/")[-1] for song in songs)), True
        )

        # Delete test songs
        for song_name in song_names:
            os.remove(f"./{self.local_song_path}/{song_name}")

    def test_local_music_one_song(self):
        rec = Recommend()
        # Create test songs
        song_path = f"./{self.local_song_path}/song.mp3"
        Path(song_path).touch()

        songs = rec.local_music(song_path, 1)
        self.assertNotEqual(songs, [])
        self.assertEqual(songs, [song_path])

        # Delete test songs
        os.remove(song_path)

    def test_local_music_one_song_not_exist(self):
        rec = Recommend()
        # Create test songs
        song_path = f"./{self.local_song_path}/no_such_song.mp3"
        songs = rec.local_music(song_path, 1)
        self.assertEqual(songs, [])

    def test_local_music_empty_dir(self):
        rec = Recommend()
        songs = rec.local_music("./test_songs_does_not_exist/", 2)
        self.assertEqual(songs, [])

    def test_music_intro_outro(self):
        rec = Recommend()
        intro, outro = rec.music_intro_outro()
        self.assertNotEqual(intro, None)
        self.assertNotEqual(outro, None)

    def test_person(self):
        rec = Recommend()
        first, last, loc = rec.person()
        self.assertNotEqual(first, None)
        self.assertNotEqual(last, None)
        self.assertNotEqual(loc, None)

    def test_daily_question(self):
        rec = Recommend()
        question = rec.daily_question(question=True)
        resp = rec.daily_question(question=False)
        self.assertNotEqual(question, None)
        self.assertNotEqual(resp, None)

    def test_advertisement(self):
        rec = Recommend()
        company, advertisement = rec.advertisement()
        self.assertNotEqual(company, None)
        self.assertNotEqual(advertisement, None)

    def test_no_advertisement(self):
        rec = Recommend()
        rec.ad_prob = 0
        company, advertisement = rec.advertisement()
        self.assertEqual(company, None)
        self.assertEqual(advertisement, None)

    @patch("radio.requests.get")
    def test_weather(self, mock_get):
        resp = Response()
        resp_content = {
            "current_condition": [
                {
                    "cloudcover": "100",
                    "temp_C": "5",
                    "temp_F": "41",
                    "weatherDesc": [{"value": "Overcast"}],
                    "windspeedKmph": "6",
                }
            ],
            "weather": [
                {
                    "hourly": [
                        {
                            "weatherDesc": [{"value": "Partly cloudy"}],
                        },
                    ]
                }
            ],
        }
        resp._content = json.dumps(resp_content, indent=2).encode("utf-8")
        mock_get.return_value.status_code = 201
        mock_get.return_value = resp
        rec = Recommend()
        forecast = rec.weather("City 1")
        self.assertEqual(mock_get.call_count, 1)
        self.assertNotEqual(forecast, None)
        self.assertEqual(len(forecast), 6)

    @patch("radio.requests.get")
    def test_weather_no_location(self, mock_get):
        resp = Response()
        resp_content = {
            "current_condition": [
                {
                    "cloudcover": "100",
                    "temp_C": "5",
                    "temp_F": "41",
                    "weatherDesc": [{"value": "Overcast"}],
                    "windspeedKmph": "6",
                }
            ],
            "weather": [
                {
                    "hourly": [
                        {
                            "weatherDesc": [{"value": "Partly cloudy"}],
                        },
                    ]
                }
            ],
        }
        resp._content = json.dumps(resp_content, indent=2).encode("utf-8")
        mock_get.return_value.status_code = 201
        mock_get.return_value = resp
        rec = Recommend()
        forecast = rec.weather(None)
        self.assertEqual(mock_get.call_count, 1)
        self.assertNotEqual(forecast, None)
        self.assertEqual(len(forecast), 6)

    @patch("radio.requests.get")
    def test_on_this_day(self, mock_get):
        resp = Response()
        resp_content = {
            "events": [
                {"text": "event 1"},
                {"text": "event 2"},
                {"text": "event 3"},
            ]
        }
        resp._content = json.dumps(resp_content, indent=2).encode("utf-8")
        mock_get.return_value.status_code = 201
        mock_get.return_value = resp
        rec = Recommend()
        facts = rec.on_this_day(k=2)
        self.assertEqual(mock_get.call_count, 1)
        self.assertNotEqual(facts, None)
        self.assertEqual(len(facts), 2)


class Test_Dialogue(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.test_path = "./test_audio/"

    @classmethod
    def tearDownClass(cls):
        # If radio.wav exists, delete it
        os.remove("./radio.wav")

        if os.path.exists(cls.test_path):
            shutil.rmtree(cls.test_path)

    def test_wakeup(self):
        dialogue = Dialogue(self.test_path)
        speech = dialogue.wakeup()
        self.assertEqual(isinstance(speech, str), True)

    @patch("radio.Recommend.advertisement")
    def test_sprinkle_gpt_speech(self, mock_advertisement):
        mock_advertisement.return_value = ("Company Name", "Speech 1")
        dialogue = Dialogue(self.test_path)
        speech = dialogue.sprinkle_gpt()
        self.assertEqual(mock_advertisement.call_count, 1)
        self.assertEqual(isinstance(speech, str), True)

    @patch("radio.Recommend.advertisement")
    @patch("radio.Recommend.daily_question")
    def test_sprinkle_gpt_question(self, mock_daily_question, mock_advertisement):
        mock_advertisement.return_value = ("Company Name", None)
        mock_daily_question.return_value = "Question 1"
        dialogue = Dialogue(self.test_path)
        speech = dialogue.sprinkle_gpt()
        self.assertEqual(mock_advertisement.call_count, 1)
        self.assertEqual(mock_daily_question.call_count, 1)
        self.assertEqual(isinstance(speech, str), True)

    @patch("radio.Recommend.advertisement")
    @patch("radio.Recommend.daily_question")
    @patch("radio.Recommend.person")
    def test_sprinkle_gpt_answer(
        self, mock_person, mock_daily_question, mock_advertisement
    ):
        mock_advertisement.return_value = ("Company Name", None)
        mock_daily_question.return_value = "Question 1"
        mock_person.return_value = ("Fname", "Lname", "Location")
        dialogue = Dialogue(self.test_path)
        dialogue.rec.question = True
        speech = dialogue.sprinkle_gpt()
        self.assertEqual(mock_advertisement.call_count, 1)
        self.assertEqual(mock_daily_question.call_count, 1)
        self.assertEqual(isinstance(speech, str), True)

    def test_over(self):
        dialogue = Dialogue(self.test_path)
        speech = dialogue.over()
        self.assertEqual(isinstance(speech, str), True)

    @patch("radio.Recommend.news")
    def test_news(self, mock_news):
        mock_news.return_value = ["News 1", "News 2"]
        dialogue = Dialogue(self.test_path)
        speech = dialogue.news("Category 1", 2)
        self.assertEqual(mock_news.call_count, 1)
        self.assertEqual(isinstance(speech, str), True)

    @patch("radio.Recommend.weather")
    def test_weather(self, mock_weather):
        mock_weather.return_value = {
            "weather": "Sunny",
            "c": "20",
            "f": "68",
            "next_hour": "19",
            "cloudcover": "80",
            "windspeedKmph": "5",
        }
        dialogue = Dialogue(self.test_path)
        speech = dialogue.weather("Location 1")
        self.assertEqual(mock_weather.call_count, 1)
        self.assertEqual(isinstance(speech, str), True)

    @patch("radio.Recommend.on_this_day")
    def test_on_this_day(self, mock_on_this_day):
        mock_on_this_day.return_value = ["Fact 1", "Fact 2", "Fact 3"]
        dialogue = Dialogue(self.test_path)
        speech = dialogue.on_this_day()
        self.assertEqual(mock_on_this_day.call_count, 1)
        self.assertEqual(isinstance(speech, str), True)

    @patch("radio.ytmdl.core.search")
    @patch("yt_dlp.YoutubeDL.download")
    def test_music(self, mock_download, mock_search):
        # Generate an mp3 file and fill it with white noise
        audio_file = WhiteNoise().to_audio_segment(duration=1000)
        audio_file.export(f"{self.test_path}/new.mp3", format="mp3")
        mock_search.return_value = "YOUTUBE_URL", "Song Title"
        mock_download.return_value = 0

        dialogue = Dialogue(self.test_path)
        dialogue.music("Song 1", artist="Artist 1")
        self.assertEqual(mock_search.call_count, 1)
        self.assertEqual(mock_download.call_count, 1)
        self.assertTrue(not os.path.exists(f"{self.test_path}/new.mp3"))
        self.assertTrue(os.path.exists(f"{self.test_path}/song.mp3"))

    def test_postprocess_music(self):
        # Generate an mp3 file and fill it with white noise
        audio_file = WhiteNoise().to_audio_segment(duration=1000)
        audio_file.export(f"{self.test_path}/song.mp3", format="mp3")
        audio_file.export(f"{self.test_path}/a0.wav", format="wav")

        dialogue = Dialogue(self.test_path)
        dialogue.index += 2
        dialogue.postprocess_music("Song 1", is_local=False)
        self.assertTrue(os.path.exists(f"{self.test_path}/a2.wav"))
        self.assertTrue(not os.path.exists(f"{self.test_path}/song.mp3"))

        # Delete test songs
        os.remove(f"{self.test_path}/a0.wav")
        os.remove(f"{self.test_path}/a2.wav")

    def test_postprocess_music_local(self):
        # Generate an mp3 file and fill it with white noise
        audio_file = WhiteNoise().to_audio_segment(duration=1000)
        song_path = f"{self.test_path}/song.mp3"
        audio_file.export(song_path, format="mp3")
        audio_file.export(f"{self.test_path}/a0.wav", format="wav")

        dialogue = Dialogue(self.test_path)
        dialogue.index += 2
        dialogue.postprocess_music(song_path, is_local=True)
        self.assertTrue(os.path.exists(f"{self.test_path}/a2.wav"))
        self.assertTrue(os.path.exists(f"{self.test_path}/song.mp3"))

        # Delete test songs
        os.remove(f"{self.test_path}/a0.wav")
        os.remove(f"{self.test_path}/a2.wav")
        os.remove(song_path)

    @patch("podcastparser.parse")
    @patch("urllib.request.urlopen")
    def test_podcast_dialogue_start(self, mock_urlopen, mock_parse):
        mock_parse.return_value = {"title": "Title", "itunes_author": "Author"}
        mock_urlopen.return_value = "URL"
        dialogue = Dialogue(self.test_path)
        speech = dialogue.podcast_dialogue("RSS feed", start=True)
        self.assertEqual(mock_parse.call_count, 1)
        self.assertEqual(isinstance(speech, str), True)

    @patch("podcastparser.parse")
    @patch("urllib.request.urlopen")
    def test_podcast_dialogue_end(self, mock_urlopen, mock_parse):
        mock_parse.return_value = {"title": "Title", "itunes_author": "Author"}
        mock_urlopen.return_value = "URL"
        dialogue = Dialogue(self.test_path)
        speech = dialogue.podcast_dialogue("RSS feed", start=False)
        self.assertEqual(mock_parse.call_count, 1)
        self.assertEqual(isinstance(speech, str), True)

    @patch("os.remove")
    @patch("pydub.AudioSegment.export")
    @patch("pydub.AudioSegment.from_mp3")
    @patch("subprocess.run")
    @patch("podcastparser.parse")
    @patch("urllib.request.urlopen")
    def test_podcast_clip(
        self,
        mock_urlopen,
        mock_parse,
        mock_run,
        mock_from_mp3,
        mock_export,
        mock_remove,
    ):
        dialogue = Dialogue(self.test_path)

        mock_parse.return_value = {
            "title": "Title",
            "itunes_author": "Author",
            "episodes": [{"enclosures": [{"url": "URL"}]}],
        }
        mock_urlopen.return_value = "URL"

        # Generate an mp3 file and fill it with white noise
        audio_file = WhiteNoise().to_audio_segment(duration=1000)
        mock_from_mp3.return_value = audio_file

        dialogue.podcast_clip("RSS feed", duration=100)
        self.assertEqual(mock_parse.call_count, 1)
        self.assertEqual(mock_run.call_count, 1)
        self.assertEqual(mock_from_mp3.call_count, 1)
        self.assertEqual(mock_export.call_count, 2)
        self.assertEqual(mock_remove.call_count, 1)

    @patch("radio.Recommend.music_intro_outro")
    @patch("itunespy.search_track")
    def test_music_meta_start(self, mock_search_track, mock_music_intro_outro):
        # Generate an mp3 file, fill it with white noise and add metadata
        audio_file = WhiteNoise().to_audio_segment(duration=1000)
        audio_file.export(
            f"{self.test_path}/song.mp3",
            format="mp3",
            tags={"artist": "Artist 1", "title": "Song 1"},
        )

        mock_search_track.return_value = [
            Track(
                json={
                    "artistName": "Artist 1",
                    "trackName": "Track 1",
                    "primaryGenreName": "Genre 1",
                }
            )
        ]
        mock_music_intro_outro.return_value = ("Intro speech", "Outro speech")
        dialogue = Dialogue(self.test_path)
        speech = dialogue.music_meta("Song 1", artist=None, is_local=False, start=True)
        self.assertEqual(mock_search_track.call_count, 1)
        self.assertEqual(mock_music_intro_outro.call_count, 1)
        self.assertEqual(isinstance(speech, str), True)
        self.assertIn("Artist 1", speech)

        # Delete test song
        os.remove(f"{self.test_path}/song.mp3")

    @patch("radio.Recommend.music_intro_outro")
    @patch("itunespy.search_track")
    def test_music_meta_no_start(self, mock_search_track, mock_music_intro_outro):
        # Generate an mp3 file, fill it with white noise and add metadata
        audio_file = WhiteNoise().to_audio_segment(duration=1000)
        audio_file.export(
            f"{self.test_path}/song.mp3",
            format="mp3",
            tags={"artist": "Artist 1", "title": "Song 1"},
        )

        mock_search_track.return_value = [
            Track(
                json={
                    "artistName": "Artist 1",
                    "trackName": "Track 1",
                    "primaryGenreName": "Genre 1",
                }
            )
        ]
        mock_music_intro_outro.return_value = ("Intro speech", "Outro speech")
        dialogue = Dialogue(self.test_path)
        speech = dialogue.music_meta("Song 1", artist=None, is_local=False, start=False)
        self.assertEqual(mock_search_track.call_count, 1)
        self.assertEqual(mock_music_intro_outro.call_count, 1)
        self.assertEqual(isinstance(speech, str), True)
        self.assertIn("Artist 1", speech)

        # Delete test song
        os.remove(f"{self.test_path}/song.mp3")

    @patch("itunespy.search_track")
    @patch("time.sleep")
    def test_music_meta_exception(self, mock_sleep, mock_search_track):
        # Generate an mp3 file, fill it with white noise and add metadata
        audio_file = WhiteNoise().to_audio_segment(duration=1000)
        audio_file.export(
            f"{self.test_path}/song.mp3",
            format="mp3",
            tags={"artist": "Artist 1", "title": "Song 1"},
        )

        mock_search_track.side_effect = [
            Exception("No results found"),
            [
                Track(
                    json={
                        "artistName": "Artist 1",
                        "trackName": "Track 1",
                        "primaryGenreName": "Genre 1",
                    }
                )
            ],
        ]
        mock_sleep.return_value = None

        dialogue = Dialogue(self.test_path)
        speech = dialogue.music_meta("Song 1", artist=None, is_local=False, start=False)
        self.assertEqual(mock_search_track.call_count, 2)
        self.assertEqual(mock_sleep.call_count, 1)
        self.assertEqual(isinstance(speech, str), True)
        self.assertIn("Artist 1", speech)

        # Delete test song
        os.remove(f"{self.test_path}/song.mp3")

    @patch("radio.Recommend.music_intro_outro")
    @patch("eyed3.load")
    def test_music_meta_local_start(self, mock_load, mock_music_intro_outro):
        metadata_mock = MagicMock()
        metadata_mock.tag.title = "Example Song"
        metadata_mock.tag.artist = "Example Artist"
        mock_load.return_value = metadata_mock
        mock_music_intro_outro.return_value = ("Intro speech", "Outro speech")

        dialogue = Dialogue(self.test_path)
        speech = dialogue.music_meta("Song 1", artist=None, is_local=True, start=True)
        self.assertEqual(mock_music_intro_outro.call_count, 1)
        self.assertEqual(mock_load.call_count, 1)
        self.assertEqual(isinstance(speech, str), True)
        self.assertIn("Example Song", speech)
        self.assertIn("Example Artist", speech)

    @patch("radio.Recommend.music_intro_outro")
    @patch("eyed3.load")
    def test_music_meta_local_no_start(self, mock_load, mock_music_intro_outro):
        metadata_mock = MagicMock()
        metadata_mock.tag.title = "Example Song"
        metadata_mock.tag.artist = "Example Artist"
        mock_load.return_value = metadata_mock
        mock_music_intro_outro.return_value = ("Intro speech", "Outro speech")

        dialogue = Dialogue(self.test_path)
        speech = dialogue.music_meta("Song 1", artist=None, is_local=True, start=False)
        self.assertEqual(mock_music_intro_outro.call_count, 1)
        self.assertEqual(mock_load.call_count, 1)
        self.assertEqual(isinstance(speech, str), True)
        self.assertIn("Example Song", speech)
        self.assertIn("Example Artist", speech)

    @patch("radio.Recommend.music_intro_outro")
    @patch("eyed3.load")
    def test_music_meta_local_no_metadata(self, mock_load, mock_music_intro_outro):
        metadata_mock = MagicMock()
        metadata_mock.tag.title = "Example Song"
        metadata_mock.tag.artist = None
        mock_load.return_value = metadata_mock
        mock_music_intro_outro.return_value = ("Intro speech", "Outro speech")

        dialogue = Dialogue(self.test_path)
        speech = dialogue.music_meta("Song 1", artist=None, is_local=True, start=True)
        self.assertEqual(mock_music_intro_outro.call_count, 1)
        self.assertEqual(mock_load.call_count, 1)
        self.assertEqual(isinstance(speech, str), True)
        self.assertNotIn("Example Song", speech)

    @patch("radio.Recommend.artist_discography")
    def test_curate_discography_artist(self, mock_artist_discography):
        mock_artist_discography.return_value = [
            "Song",
        ]
        dialogue = Dialogue(self.test_path)
        meta = [("Artist 1", 1), ("Artist 2", 1)]
        songs = dialogue.curate_discography(action="music-artist", meta=meta)
        self.assertEqual(mock_artist_discography.call_count, 2)
        self.assertEqual(len(songs), 2)

    @patch("radio.Recommend.playlist_by_genre")
    def test_curate_discography_genre(self, mock_playlist_by_genre):
        mock_playlist_by_genre.return_value = [
            ("Artist", "Song"),
        ]
        dialogue = Dialogue(self.test_path)
        meta = [("Genre 1", 1), ("Genre 2", 1)]
        songs = dialogue.curate_discography(action="music-genre", meta=meta)
        self.assertEqual(mock_playlist_by_genre.call_count, 2)
        self.assertEqual(len(songs), 2)

    @patch("radio.Recommend.billboard")
    def test_curate_discography_billboard(self, mock_billboard):
        mock_billboard.return_value = [
            ("Artist", "Song"),
        ]
        dialogue = Dialogue(self.test_path)
        meta = [("Chart 1", 1), ("Chart 2", 1)]
        songs = dialogue.curate_discography(action="music-billboard", meta=meta)
        self.assertEqual(mock_billboard.call_count, 2)
        self.assertEqual(len(songs), 2)

    @patch("radio.Recommend.local_music")
    def test_curate_discography_local_album(self, mock_local_music):
        mock_local_music.return_value = ["SONG_PATH_1", "SONG_PATH_2"]
        dialogue = Dialogue(self.test_path)
        meta = [["ALBUM_PATH_1", 2], ["ALBUM_PATH_2", 2]]
        songs = dialogue.curate_discography(action="local-music", meta=meta)
        self.assertEqual(mock_local_music.call_count, 2)
        self.assertEqual([name for _, name in songs], mock_local_music.return_value * 2)
        self.assertEqual(len(songs), 4)

    @patch("radio.Recommend.local_music")
    def test_curate_discography_local_song(self, mock_local_music):
        mock_local_music.return_value = ["SONG_PATH_X_VALIDATED"]
        dialogue = Dialogue(self.test_path)
        meta = ["SONG_PATH_1", "SONG_PATH_2"]
        songs = dialogue.curate_discography(action="local-music", meta=meta)
        self.assertEqual(len(songs), 2)
        self.assertEqual([name for _, name in songs], mock_local_music.return_value * 2)

    def test_curate_discography_default(self):
        dialogue = Dialogue(self.test_path)
        meta = ["Song 1", "Song 2"]
        songs = dialogue.curate_discography(action="music", meta=meta)
        self.assertEqual(len(songs), 2)

    @patch("radio.Dialogue.wakeup")
    @patch("radio.Dialogue.speak")
    @patch("radio.Dialogue.sprinkle_gpt")
    @patch("radio.Dialogue.curate_discography")
    @patch("radio.Dialogue.postprocess_music")
    @patch("radio.Dialogue.music_meta")
    @patch("radio.Dialogue.music")
    @patch("radio.Dialogue.podcast_dialogue")
    @patch("radio.Dialogue.podcast_clip")
    @patch("radio.Dialogue.news")
    @patch("radio.Dialogue.weather")
    @patch("radio.Dialogue.on_this_day")
    @patch("radio.Dialogue.over")
    @patch("radio.Dialogue.radio")
    @patch("radio.Dialogue.cleanup")
    def test_flow(
        self,
        mock_cleanup,
        mock_radio,
        mock_over,
        mock_on_this_day,
        mock_weather,
        mock_news,
        mock_podcast_clip,
        mock_podcast_dialogue,
        mock_music,
        mock_music_meta,
        mock_postprocess_music,
        mock_curate_discography,
        mock_sprinkle_gpt,
        mock_speak,
        mock_wakeup,
    ):
        mock_music.side_effect = [0, 1]
        mock_curate_discography.return_value = [
            ["Artist 1", "Song 1"],
            ["Artist 2", "Song 2"],
        ]
        dialogue = Dialogue(self.test_path)
        dialogue.schema = [
            ["no-ads", None],
            ["no-qna", None],
            ["up", None],
            ["music", [["Song 1", "Artist 1"], ["Song 2", "Artist 2"]]],
            ["podcast", ["PODCAST_RSS_URL", None]],
            ["news", ["Category", 5]],
            ["weather", "City name"],
            ["fun", None],
            ["end", None],
        ]
        dialogue.flow()
        self.assertEqual(mock_cleanup.call_count, 1)
        self.assertEqual(mock_radio.call_count, 1)
        self.assertEqual(mock_over.call_count, 1)
        self.assertEqual(mock_on_this_day.call_count, 1)
        self.assertEqual(mock_weather.call_count, 1)
        self.assertEqual(mock_news.call_count, 1)

        self.assertEqual(mock_podcast_clip.call_count, 1)
        self.assertEqual(mock_podcast_dialogue.call_count, 2)

        self.assertEqual(mock_curate_discography.call_count, 1)
        self.assertEqual(mock_music.call_count, 2)
        self.assertEqual(mock_music_meta.call_count, 2)
        self.assertEqual(mock_postprocess_music.call_count, 1)
        self.assertEqual(mock_speak.call_count, 11)

        self.assertEqual(mock_sprinkle_gpt.call_count, 2)
        self.assertEqual(mock_wakeup.call_count, 1)

    def test_radio(self):
        # Generate two mp3 files and fill it with white noise
        audio_file = WhiteNoise().to_audio_segment(duration=1000)
        audio_file.export(f"{self.test_path}/a0.wav", format="wav")
        audio_file.export(f"{self.test_path}/a1.wav", format="wav")

        dialogue = Dialogue(self.test_path)
        dialogue.index = 2
        self.assertTrue(not os.path.exists("./radio.wav"))
        dialogue.radio()
        self.assertTrue(os.path.exists(f"{self.test_path}/a0.wav"))
        self.assertTrue(os.path.exists(f"{self.test_path}/a1.wav"))
        self.assertTrue(os.path.exists("./radio.wav"))

    @patch("radio.Dialogue.save_speech")
    @patch("radio.Dialogue.cleaner")
    @patch("radio.Dialogue.background_music")
    @patch("radio.Dialogue.silence")
    def test_speak_announce(
        self,
        mock_silence,
        mock_background_music,
        mock_cleaner,
        mock_save_speech,
    ):
        dialogue = Dialogue(self.test_path)
        dialogue.speak("Speech", announce=True)
        self.assertEqual(mock_silence.call_count, 1)
        self.assertEqual(mock_background_music.call_count, 1)
        self.assertEqual(mock_save_speech.call_count, 1)

    @patch("radio.Dialogue.save_speech")
    @patch("radio.Dialogue.cleaner")
    @patch("radio.Dialogue.slow_it_down")
    @patch("radio.Dialogue.silence")
    def test_speak(
        self,
        mock_silence,
        mock_slow_it_down,
        mock_cleaner,
        mock_save_speech,
    ):
        dialogue = Dialogue(self.test_path)
        dialogue.speak("Speech", announce=False)
        self.assertEqual(mock_silence.call_count, 1)
        self.assertEqual(mock_slow_it_down.call_count, 1)
        self.assertEqual(mock_save_speech.call_count, 1)

    @patch("radio.Dialogue.save_speech")
    @patch("radio.Dialogue.cleaner")
    @patch("radio.Dialogue.slow_it_down")
    @patch("radio.Dialogue.silence")
    def test_speak_long(
        self,
        mock_silence,
        mock_slow_it_down,
        mock_cleaner,
        mock_save_speech,
    ):
        speech = (
            "The birch canoe slid on the smooth planks, "
            "Glue the sheet to the dark blue background, "
            "It's easy to tell the depth of a well, "
            "These days a chicken leg is a rare dish, "
            "Rice is often served in round bowls. "
        )
        dialogue = Dialogue(self.test_path)
        dialogue.speak(speech, announce=False)
        self.assertEqual(mock_silence.call_count, 1)
        self.assertEqual(mock_cleaner.call_count, 1)
        self.assertEqual(mock_slow_it_down.call_count, 1)
        # The first time, as length is greater than 300, it will
        # try and output what's before, which is nothing, and then
        # output this long sentence
        self.assertEqual(mock_save_speech.call_count, 2)

    def test_speak_no_speech(self):
        dialogue = Dialogue(self.test_path)
        speech = dialogue.speak(None, announce=False)
        self.assertEqual(speech, None)

    def test_slow_it_down(self):
        # Generate an mp3 file and fill it with white noise
        audio_file = WhiteNoise().to_audio_segment(duration=1000)
        audio_file.export(f"{self.test_path}/a0.wav", format="wav")

        dialogue = Dialogue(self.test_path)
        dialogue.index = 1
        dialogue.slow_it_down(start_index=0)
        self.assertTrue(os.path.exists(f"{self.test_path}/a0.wav"))
        self.assertTrue(not os.path.exists(f"{self.test_path}/out.wav"))

    @patch("pydub.AudioSegment.from_wav")
    def test_background_music(self, mock_from_wav):
        # Generate an mp3 file and fill it with white noise
        audio_file = WhiteNoise().to_audio_segment(duration=1000)
        mock_from_wav.return_value = audio_file
        dialogue = Dialogue(self.test_path)
        dialogue.background_music()

    @patch("pathlib.Path.is_file")
    @patch("ffmpy.FFmpeg.run")
    @patch("radio.Dialogue.metadata")
    def test_cleanup(self, mock_metadata, mock_run, mock_is_file):
        # NOTE: Using a different path specifically for this test
        os.mkdir("./test_audio_cleanup/")

        # Generate two mp3 files and fill it with white noise
        audio_file = WhiteNoise().to_audio_segment(duration=1000)
        audio_file.export("./test_audio_cleanup/a0.wav", format="wav")
        audio_file.export("./test_audio_cleanup/a1.wav", format="wav")

        # Generate a radio.wav file, which will be deleted
        audio_file.export("./radio.wav", format="wav")

        # Important, otherwise it will delete your radio.mp3 file
        mock_is_file.return_value = False

        dialogue = Dialogue("./test_audio_cleanup/")
        dialogue.index = 2
        dialogue.cleanup()
        self.assertEqual(mock_run.call_count, 1)
        self.assertEqual(mock_is_file.call_count, 1)
        self.assertEqual(mock_metadata.call_count, 1)
        self.assertTrue(not os.path.exists("./test_audio_cleanup/"))
        self.assertTrue(not os.path.exists("./radio.wav"))

    @patch("randimage.utils.get_random_image")
    @patch("matplotlib.image.imsave")
    def test_metadata(self, mock_imsave, mock_get_random_image):
        mock_get_random_image.return_value = MagicMock()
        mock_imsave.return_value = MagicMock()

        metadata_path = f"{self.test_path}/radio.mp3"
        # Generate an mp3 file and fill it with white noise
        audio_file = WhiteNoise().to_audio_segment(duration=1000)
        audio_file.export(metadata_path, format="mp3")

        # Create a simple poster image in jpeg format
        # https://stackoverflow.com/a/70261284/7543474
        # License: CC BY-SA 4.0
        image = Image.new("RGB", (1, 1), color="red")
        pixels = image.load()
        pixels[0, 0] = (255, 255, 255)
        image.save(f"{self.test_path}/poster.jpeg", format="jpeg")

        dialogue = Dialogue(self.test_path)
        dialogue.metadata(metadata_path)

        # Restore the original function after the test
        mock_get_random_image.assert_called_once()
        mock_imsave.assert_called_once()

    @patch("radio.english_cleaners")
    def test_cleaner(self, mock_english_cleaners):
        def side_effect(arg):
            return arg

        mock_english_cleaners.side_effect = side_effect
        dialogue = Dialogue(self.test_path)
        cleaned = dialogue.cleaner("ABC")
        self.assertEqual(mock_english_cleaners.call_count, 1)
        self.assertEqual(cleaned, "ae bee sieh ")

    @patch("TTS.utils.synthesizer.Synthesizer.tts")
    @patch("TTS.utils.synthesizer.Synthesizer.save_wav")
    def test_save_speech(self, mock_save_wav, mock_tts):
        dialogue = Dialogue(self.test_path)
        dialogue.index = 10
        dialogue.save_speech("Speech")
        self.assertEqual(mock_tts.call_count, 1)
        self.assertEqual(mock_save_wav.call_count, 1)
