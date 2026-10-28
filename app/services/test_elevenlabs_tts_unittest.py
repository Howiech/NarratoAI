import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from app.services import voice


class FakeElevenLabsAudioResponse:
    status_code = 200
    text = "OK"
    content = b"ID3-fake-mp3-audio-bytes"


class FakeElevenLabsNotFoundResponse:
    status_code = 404
    text = '{"detail":{"status":"voice_not_found","message":"Voice not found"}}'
    content = b""


class FakeElevenLabsSharedSearchResponse:
    status_code = 200
    text = "OK"

    def json(self):
        return {
            "voices": [
                {
                    "voice_id": "9lHjugDhwqoxA5MhX0az",
                    "public_owner_id": "owner_tw_123",
                    "name": "Anna Su",
                }
            ]
        }


class FakeElevenLabsAddVoiceResponse:
    status_code = 200
    text = "OK"

    def json(self):
        return {"voice_id": "9lHjugDhwqoxA5MhX0az"}


class ElevenLabsTtsTests(unittest.TestCase):
    def setUp(self):
        self.original_elevenlabs = dict(getattr(voice.config, "elevenlabs", {}) or {})
        self.original_ui = dict(getattr(voice.config, "ui", {}) or {})
        self.original_proxy = dict(getattr(voice.config, "proxy", {}) or {})

    def tearDown(self):
        voice.config.elevenlabs.clear()
        voice.config.elevenlabs.update(self.original_elevenlabs)
        voice.config.ui.clear()
        voice.config.ui.update(self.original_ui)
        voice.config.proxy.clear()
        voice.config.proxy.update(self.original_proxy)

    def test_default_voice_is_taiwanese_anna_su(self):
        voice.config.elevenlabs.clear()
        voice.config.ui.clear()
        resolved = voice.parse_elevenlabs_voice("")
        self.assertEqual(resolved, "9lHjugDhwqoxA5MhX0az")

        preset_map = voice.get_elevenlabs_preset_voice_map("zh")
        self.assertIn("9lHjugDhwqoxA5MhX0az", preset_map)
        self.assertIn("Anna Su", preset_map["9lHjugDhwqoxA5MhX0az"])
        self.assertIn("r6qgCCGI7RWKXCagm158", preset_map)
        self.assertIn("21m00Tcm4TlvDq8ikWAM", preset_map)

    def test_elevenlabs_tts_sends_xi_api_key_and_saves_audio(self):
        voice.config.elevenlabs.clear()
        voice.config.elevenlabs.update(
            {
                "api_key": "sk_test_elevenlabs_key",
                "api_url": "https://api.elevenlabs.io",
                "model_id": "eleven_multilingual_v2",
                "voice_id": "9lHjugDhwqoxA5MhX0az",
                "stability": 0.45,
                "similarity_boost": 0.8,
                "style": 0.15,
                "use_speaker_boost": True,
                "speed": 1.0,
            }
        )
        voice.config.proxy.clear()
        voice.config.proxy.update({"http": "", "https": "", "enabled": False})

        with tempfile.TemporaryDirectory() as temp_dir:
            output_file = Path(temp_dir) / "elevenlabs.mp3"
            with patch(
                "requests.post", return_value=FakeElevenLabsAudioResponse()
            ) as mock_post, patch(
                "app.services.voice.get_audio_duration_from_file", return_value=2.5
            ):
                sub_maker = voice.tts(
                    text=" 大家好，我是來自台灣的 Anna Su。 ",
                    voice_name="9lHjugDhwqoxA5MhX0az",
                    voice_rate=1.05,
                    voice_pitch=1.0,
                    voice_file=str(output_file),
                    tts_engine="elevenlabs",
                )
            saved_bytes = output_file.read_bytes()

        self.assertIsNotNone(sub_maker)
        self.assertEqual(saved_bytes, b"ID3-fake-mp3-audio-bytes")

        args, kwargs = mock_post.call_args
        self.assertEqual(
            args[0],
            "https://api.elevenlabs.io/v1/text-to-speech/9lHjugDhwqoxA5MhX0az?output_format=mp3_44100_128",
        )
        self.assertEqual(kwargs["headers"]["xi-api-key"], "sk_test_elevenlabs_key")
        self.assertEqual(kwargs["json"]["text"], "大家好，我是來自台灣的 Anna Su。")
        self.assertEqual(kwargs["json"]["model_id"], "eleven_multilingual_v2")
        self.assertEqual(kwargs["json"]["voice_settings"]["stability"], 0.45)
        self.assertEqual(kwargs["json"]["voice_settings"]["similarity_boost"], 0.8)
        self.assertEqual(kwargs["json"]["voice_settings"]["style"], 0.15)
        self.assertEqual(kwargs["json"]["voice_settings"]["speed"], 1.05)

    def test_emotion_payloads_and_subtitles_across_models(self):
        for model, emotion, expected_text in (
            ("eleven_v4", "happy", "[happy] 測試配音"),
            ("eleven_v4", "whispering", "[whispers] 測試配音"),
            ("eleven_v4", "neutral", "測試配音"),
            ("eleven_v4", "invalid", "測試配音"),
            ("eleven_v3", "sad", "[sad] 測試配音"),
            ("eleven_multilingual_v2", "happy", "測試配音"),
            ("eleven_flash_v2_5", "angry", "測試配音"),
        ):
            with self.subTest(model=model, emotion=emotion):
                voice.config.elevenlabs.clear()
                voice.config.elevenlabs.update({
                    "api_key": "test_key", "model_id": model,
                    "emotion": emotion, "stability": 0.45, "speed": 1.1,
                })
                with tempfile.TemporaryDirectory() as folder, patch(
                    "requests.post", return_value=FakeElevenLabsAudioResponse()
                ) as post, patch(
                    "app.services.voice.get_audio_duration_from_file", return_value=2
                ), patch("app.services.voice.add_subtitle_event") as subtitle:
                    result = voice.elevenlabs_tts(
                        "測試配音", "test_voice", str(Path(folder) / "sample.mp3")
                    )
                self.assertIsNotNone(result)
                payload = post.call_args.kwargs["json"]
                self.assertEqual(payload["model_id"], model)
                self.assertEqual(payload["text"], expected_text)
                self.assertEqual(subtitle.call_args.args[-1], "測試配音")
                settings = payload["voice_settings"]
                if model == "eleven_v4":
                    self.assertEqual(settings, {"stability": 0.45, "similarity_boost": 0.75})
                elif model == "eleven_v3":
                    self.assertEqual(settings["stability"], 0.5)
                    self.assertNotIn("use_speaker_boost", settings)
                else:
                    self.assertEqual(settings["speed"], 1.1)
                    self.assertIn("style", settings)

    def test_auto_adds_shared_voice_from_library_when_not_yet_in_account(self):
        voice.config.elevenlabs.clear()
        voice.config.elevenlabs.update({"api_key": "sk_test_key"})

        with tempfile.TemporaryDirectory() as temp_dir:
            output_file = Path(temp_dir) / "anna_su.mp3"
            with patch(
                "requests.post",
                side_effect=[
                    FakeElevenLabsNotFoundResponse(),
                    FakeElevenLabsAddVoiceResponse(),
                    FakeElevenLabsAudioResponse(),
                ],
            ) as mock_post, patch(
                "requests.get",
                return_value=FakeElevenLabsSharedSearchResponse(),
            ) as mock_get, patch(
                "app.services.voice.get_audio_duration_from_file", return_value=1.8
            ):
                result = voice.elevenlabs_tts(
                    text="測試自動加入共享台灣口音音色",
                    voice_name="9lHjugDhwqoxA5MhX0az",
                    voice_file=str(output_file),
                    speed=1.0,
                )

        self.assertIsNotNone(result)
        self.assertEqual(mock_get.call_count, 1)
        self.assertEqual(mock_post.call_count, 3)


if __name__ == "__main__":
    unittest.main()

