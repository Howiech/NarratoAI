import os
import sys
import unittest
from unittest.mock import MagicMock, patch

# Provide lightweight mock for third-party dependencies if not installed
for mod in [
    "loguru", "toml", "tomli", "requests", "pysrt", "streamlit", "urllib3",
    "moviepy", "moviepy.video", "moviepy.video.io", "moviepy.video.io.VideoFileClip",
    "moviepy.editor", "edge_tts", "openai", "google", "dashscope", "tqdm", "tenacity",
    "pydantic", "pydantic.v1"
]:
    if mod not in sys.modules:
        try:
            __import__(mod)
        except ImportError:
            sys.modules[mod] = MagicMock()

from app.services.youtube_service import YoutubeService


class TestYoutubeService(unittest.TestCase):
    def setUp(self):
        self.service = YoutubeService()

    def test_format_selector_best(self):
        selector = self.service._get_format_selector("best")
        self.assertIn("bestvideo", selector)
        self.assertIn("bestaudio", selector)

    def test_format_selector_resolution(self):
        selector_1080 = self.service._get_format_selector("1080p")
        self.assertIn("height<=1080", selector_1080)

        selector_720 = self.service._get_format_selector("720p")
        self.assertIn("height<=720", selector_720)

    def test_get_proxy(self):
        with patch("app.services.youtube_service.config.proxy", {"enabled": True, "http": "http://127.0.0.1:7890"}):
            proxy = self.service.get_proxy()
            self.assertEqual(proxy, "http://127.0.0.1:7890")

        with patch("app.services.youtube_service.config.proxy", {"enabled": False, "http": "http://127.0.0.1:7890"}):
            proxy = self.service.get_proxy()
            self.assertIsNone(proxy)

    def test_find_best_subtitle_priority(self):
        with patch("glob.glob") as mock_glob:
            mock_glob.return_value = [
                "/tmp/video.en.srt",
                "/tmp/video.zh-CN.srt",
                "/tmp/video.zh-TW.srt",
            ]
            best = self.service._find_best_subtitle("/tmp", "video")
            self.assertEqual(best, "/tmp/video.zh-TW.srt")

    def test_find_best_subtitle_fallback(self):
        with patch("glob.glob") as mock_glob:
            mock_glob.return_value = ["/tmp/video.en.srt"]
            best = self.service._find_best_subtitle("/tmp", "video")
            self.assertEqual(best, "/tmp/video.en.srt")

        with patch("glob.glob") as mock_glob:
            mock_glob.return_value = []
            best = self.service._find_best_subtitle("/tmp", "video")
            self.assertIsNone(best)

    def test_empty_url_validation(self):
        with patch.object(self.service, "is_available", return_value=True):
            with self.assertRaises(ValueError):
                self.service.download(url="")

    @patch("app.services.youtube_service.yt_dlp")
    @patch("app.utils.utils.video_dir", return_value="/tmp/test_videos")
    @patch("app.utils.utils.subtitle_dir", return_value="/tmp/test_srts")
    def test_download_mocked(self, mock_sub_dir, mock_vid_dir, mock_ytdlp):
        mock_instance = MagicMock()
        mock_ytdlp.YoutubeDL.return_value.__enter__.return_value = mock_instance

        mock_instance.extract_info.return_value = {
            "id": "abc12345",
            "title": "Test Video Title",
            "duration": 120,
        }
        mock_instance.prepare_filename.return_value = "/tmp/test_videos/Test Video Title-abc12345.mp4"

        with patch("os.path.exists", return_value=True), \
             patch("glob.glob", return_value=["/tmp/test_videos/Test Video Title-abc12345.zh-TW.srt"]), \
             patch("shutil.copy2") as mock_copy:

            result = self.service.download(
                url="https://www.youtube.com/watch?v=abc12345",
                resolution="1080p",
                download_subtitles=True,
            )

            self.assertEqual(result["status"], "success")
            self.assertEqual(result["title"], "Test Video Title")
            self.assertEqual(result["video_path"], "/tmp/test_videos/Test Video Title-abc12345.mp4")
            self.assertIsNotNone(result["subtitle_path"])


if __name__ == "__main__":
    unittest.main()
