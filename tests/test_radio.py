import subprocess
import unittest
from mock import patch
from radio import Recommend, Dialogue

import json
import os
import shutil

from feedparser.util import FeedParserDict
from billboard import ChartEntry
from requests.models import Response
from itunespy.track import Track
from pydub.generators import WhiteNoise


class Test_Recommend(unittest.TestCase):
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

    def test_playlist_by_genre(self):
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

    @patch("radio.ytmdl.main.main")
    def test_music(self, mock_main):
        # Generate an mp3 file and fill it with white noise
        audio_file = WhiteNoise().to_audio_segment(duration=1000)
        audio_file.export(f"{self.test_path}/new.mp3", format="mp3")

        dialogue = Dialogue(self.test_path)
        dialogue.music("Song 1", artist="Artist 1")
        self.assertEqual(mock_main.call_count, 1)
        self.assertTrue(not os.path.exists(f"{self.test_path}/new.mp3"))
        self.assertTrue(os.path.exists(f"{self.test_path}/a0.wav"))

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
    @patch("radio.ytmdl.metadata.get_from_itunes")
    def test_music_meta_start(self, mock_get_from_itunes, mock_music_intro_outro):
        mock_get_from_itunes.return_value = [
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
        speech = dialogue.music_meta("Song 1", artist=None, start=True)
        self.assertEqual(mock_get_from_itunes.call_count, 1)
        self.assertEqual(mock_music_intro_outro.call_count, 1)
        self.assertEqual(isinstance(speech, str), True)

    @patch("radio.Recommend.music_intro_outro")
    @patch("radio.ytmdl.metadata.get_from_itunes")
    def test_music_meta_no_start(self, mock_get_from_itunes, mock_music_intro_outro):
        mock_get_from_itunes.return_value = [
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
        speech = dialogue.music_meta("Song 1", artist=None, start=False)
        self.assertEqual(mock_get_from_itunes.call_count, 1)
        self.assertEqual(mock_music_intro_outro.call_count, 1)
        self.assertEqual(isinstance(speech, str), True)

    @patch("radio.ytmdl.metadata.get_from_itunes")
    def test_music_meta_none(self, mock_get_from_itunes):
        mock_get_from_itunes.return_value = TypeError
        dialogue = Dialogue(self.test_path)
        speech = dialogue.music_meta("Song 1", artist=None, start=False)
        self.assertEqual(mock_get_from_itunes.call_count, 1)
        self.assertEqual(speech, None)

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

    def test_curate_discography_default(self):
        dialogue = Dialogue(self.test_path)
        meta = ["Song 1", "Song 2"]
        songs = dialogue.curate_discography(action="music", meta=meta)
        self.assertEqual(len(songs), 2)

    @patch("radio.Dialogue.wakeup")
    @patch("radio.Dialogue.speak")
    @patch("radio.Dialogue.sprinkle_gpt")
    @patch("radio.Dialogue.curate_discography")
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
        mock_curate_discography,
        mock_sprinkle_gpt,
        mock_speak,
        mock_wakeup,
    ):
        mock_music_meta.side_effect = ["Speech", "Speech", None]
        mock_curate_discography.return_value = [
            ["Artist 1", "Song 1"],
            ["Artist 2", "Song 2"],
        ]
        dialogue = Dialogue(self.test_path)
        dialogue.schema = [
            ["no-ads", None],
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
        self.assertEqual(mock_music.call_count, 1)
        self.assertEqual(mock_music_meta.call_count, 3)
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
        self.assertTrue(not os.path.exists(f"./radio.wav"))
        dialogue.radio()
        self.assertTrue(os.path.exists(f"{self.test_path}/a0.wav"))
        self.assertTrue(os.path.exists(f"{self.test_path}/a1.wav"))
        self.assertTrue(os.path.exists(f"./radio.wav"))

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
        os.mkdir(f"./test_audio_cleanup/")

        # Generate two mp3 files and fill it with white noise
        audio_file = WhiteNoise().to_audio_segment(duration=1000)
        audio_file.export(f"./test_audio_cleanup/a0.wav", format="wav")
        audio_file.export(f"./test_audio_cleanup/a1.wav", format="wav")

        # Generate a radio.wav file, which will be deleted
        audio_file.export(f"./radio.wav", format="wav")

        # Important, otherwise it will delete your radio.mp3 file
        mock_is_file.return_value = False

        dialogue = Dialogue("./test_audio_cleanup/")
        dialogue.index = 2
        dialogue.cleanup()
        self.assertEqual(mock_run.call_count, 1)
        self.assertEqual(mock_is_file.call_count, 1)
        self.assertEqual(mock_metadata.call_count, 1)
        self.assertTrue(not os.path.exists(f"./test_audio_cleanup/"))
        self.assertTrue(not os.path.exists(f"./radio.wav"))

    def test_metadata(self):
        metadata_path = f"{self.test_path}/radio.mp3"
        # Generate an mp3 file and fill it with white noise
        audio_file = WhiteNoise().to_audio_segment(duration=1000)
        audio_file.export(metadata_path, format="mp3")

        dialogue = Dialogue(self.test_path)
        dialogue.metadata(metadata_path)

    @patch("radio.english_cleaners")
    def test_cleaner(self, mock_english_cleaners):
        def side_effect(arg):
            return arg

        mock_english_cleaners.side_effect = side_effect
        dialogue = Dialogue(self.test_path)
        cleaned = dialogue.cleaner("ABC")
        self.assertEqual(mock_english_cleaners.call_count, 1)
        self.assertEqual(cleaned, "ae bee sieh ")

    def test_save_speech(self):
        dialogue = Dialogue(self.test_path)
        dialogue.index = 10
        dialogue.save_speech("Speech")
        self.assertTrue(os.path.exists(f"{self.test_path}/a10.wav"))
