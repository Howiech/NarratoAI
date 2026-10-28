import unittest
import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch

from webui.components import audio_settings

from webui.components.audio_settings import (
    _normalize_source_pills_value,
    get_tts_engine_options,
)


def zh_tr(key):
    return {
        "Select from Resource Directory": "从资源目录选择",
        "Upload Reference Audio": "上传参考音频",
        "Upload Background Music": "上传背景音乐",
    }.get(key, key)


class AudioSettingsSourcePillsTests(unittest.TestCase):
    def test_tts_engine_options_include_indextts_15_macos_as_local_engine(self):
        options = get_tts_engine_options(lambda key: {
            "Local Deployment": "本地部署",
            "Cloud Service": "云服务",
        }.get(key, key))

        self.assertEqual(
            "IndexTTS-1.5-macOS [本地部署]",
            options["indextts_macos"],
        )

    def test_tts_engine_options_include_elevenlabs_as_cloud_service(self):
        options = get_tts_engine_options(lambda key: {
            "Local Deployment": "本地部署",
            "Cloud Service": "云服务",
            "ElevenLabs TTS": "ElevenLabs 多語系配音 (台灣/中英)",
        }.get(key, key))

        self.assertEqual(
            "ElevenLabs 多語系配音 (台灣/中英) [云服务]",
            options["elevenlabs"],
        )

    def test_normalize_source_pills_value_keeps_canonical_value(self):
        options = {
            "resource": "Select from Resource Directory",
            "upload": "Upload Reference Audio",
        }

        self.assertEqual("upload", _normalize_source_pills_value("upload", options, "resource", zh_tr))

    def test_normalize_source_pills_value_migrates_current_translated_label(self):
        options = {
            "resource": "Select from Resource Directory",
            "upload": "Upload Reference Audio",
        }

        self.assertEqual("resource", _normalize_source_pills_value("从资源目录选择", options, "upload", zh_tr))

    def test_normalize_source_pills_value_migrates_untranslated_label_key(self):
        options = {
            "resource": "Select from Resource Directory",
            "upload": "Upload Background Music",
        }

        self.assertEqual("upload", _normalize_source_pills_value("Upload Background Music", options, "resource", zh_tr))

    def test_normalize_source_pills_value_falls_back_to_default(self):
        options = {
            "resource": "Select from Resource Directory",
            "upload": "Upload Reference Audio",
        }

        self.assertEqual("resource", _normalize_source_pills_value("invalid", options, "resource", zh_tr))


class ElevenLabsPreviewTests(unittest.TestCase):
    def test_preview_replays_without_regenerating_and_hides_stale_audio(self):
        cfg = {"api_key": "test", "model_id": "eleven_v4", "emotion": "happy",
               "voice_id": "custom_voice", "speed": 1.0}
        ui = MagicMock()
        ui.session_state = {}
        ui.text_area.return_value = "測試試聽"
        ui.button.return_value = True
        generated_files = []

        def synthesize(**kwargs):
            generated_files.append(Path(kwargs["voice_file"]))
            generated_files[-1].write_bytes(b"sample mp3")
            return object()

        with tempfile.TemporaryDirectory() as folder, patch.object(
            audio_settings, "st", ui
        ), patch.object(audio_settings.config, "elevenlabs", cfg), patch.object(
            audio_settings.utils, "storage_dir", return_value=folder
        ), patch.object(audio_settings.voice, "elevenlabs_tts", side_effect=synthesize) as tts:
            audio_settings.render_voice_preview_new(lambda k: k, "elevenlabs")
            self.assertEqual(tts.call_args.kwargs["voice_name"], "custom_voice")
            self.assertEqual(tts.call_args.kwargs["text"], "測試試聽")
            ui.audio.assert_called_once_with(b"sample mp3", format="audio/mp3")
            self.assertFalse(generated_files[0].exists())

            ui.button.return_value = False
            ui.audio.reset_mock()
            audio_settings.render_elevenlabs_preview(lambda k: k)
            self.assertEqual(tts.call_count, 1)
            ui.audio.assert_called_once()

            cfg["emotion"] = "sad"
            ui.audio.reset_mock()
            audio_settings.render_elevenlabs_preview(lambda k: k)
            ui.audio.assert_not_called()

    def test_preview_rejects_empty_text_and_missing_key(self):
        for text, cfg in (("  ", {"api_key": "test"}), ("test", {})):
            with self.subTest(text=text):
                ui = MagicMock()
                ui.session_state = {}
                ui.text_area.return_value = text
                ui.button.return_value = True
                with patch.object(audio_settings, "st", ui), patch.object(
                    audio_settings.config, "elevenlabs", cfg
                ), patch.dict("os.environ", {"ELEVENLABS_API_KEY": ""}), patch.object(
                    audio_settings.voice, "elevenlabs_tts"
                ) as tts:
                    audio_settings.render_elevenlabs_preview(lambda k: k)
                tts.assert_not_called()
                ui.warning.assert_called_once()

    def test_failed_preview_cleans_up_partial_audio(self):
        ui = MagicMock()
        ui.session_state = {}
        ui.text_area.return_value = "test"
        ui.button.return_value = True

        def fail(**kwargs):
            Path(kwargs["voice_file"]).write_bytes(b"partial")
            raise RuntimeError("generation failed")

        with tempfile.TemporaryDirectory() as folder, patch.object(
            audio_settings, "st", ui
        ), patch.object(audio_settings.config, "elevenlabs", {"api_key": "test"}), patch.object(
            audio_settings.utils, "storage_dir", return_value=folder
        ), patch.object(audio_settings.voice, "elevenlabs_tts", side_effect=fail), patch.object(
            audio_settings.logger, "exception"
        ):
            audio_settings.render_elevenlabs_preview(lambda k: k)
            self.assertEqual(list(Path(folder).iterdir()), [])
        ui.error.assert_called_once()
        ui.audio.assert_not_called()


if __name__ == "__main__":
    unittest.main()
