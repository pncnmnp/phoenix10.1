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


class Test_Recommend(unittest.TestCase):
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
        self.assertEqual(isinstance(speech, str), True)

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

    @patch("radio.english_cleaners")
    def test_cleaner(self, mock_english_cleaners):
        def side_effect(arg):
            return arg

        mock_english_cleaners.side_effect = side_effect
        dialogue = Dialogue(self.test_path)
        cleaned = dialogue.cleaner("ABC")
        self.assertEqual(mock_english_cleaners.call_count, 1)
        self.assertEqual(cleaned, "ae bee sieh ")
