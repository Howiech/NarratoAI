import glob
import os
import re
import shutil
from typing import Any, Callable, Dict, List, Optional, Tuple
from uuid import uuid4
try:
    from loguru import logger
except ImportError:
    import logging
    logger = logging.getLogger("youtube_service")

from app.config import config
from app.utils import utils

try:
    import yt_dlp
except ImportError:
    yt_dlp = None


class YoutubeService:
    """基于 yt-dlp 的线上影音与字幕下载服务"""

    def __init__(self):
        self.supported_formats = ["mp4", "mkv", "webm", "flv", "avi"]

    @staticmethod
    def is_available() -> bool:
        """检查 yt-dlp 是否已安装"""
        return yt_dlp is not None

    @staticmethod
    def get_proxy() -> Optional[str]:
        """获取系统配置的代理地址（若启用）"""
        try:
            if config.proxy.get("enabled"):
                proxy_url = config.proxy.get("http") or config.proxy.get("https")
                if proxy_url and str(proxy_url).strip():
                    return str(proxy_url).strip()
        except Exception as e:
            logger.warning(f"读取代理配置失败: {e}")
        return None

    def _get_format_selector(self, resolution: str) -> str:
        """根据目标画质返回最优 yt-dlp format 选择器"""
        res = str(resolution or "").strip().lower()
        if not res or res in ("best", "auto", "original", "最高画质", "最高畫質"):
            return "bestvideo[ext=mp4]+bestaudio[ext=m4a]/bestvideo+bestaudio/best"

        digits = re.findall(r"\d+", res)
        if digits:
            height = digits[0]
            return (
                f"bestvideo[height<={height}][ext=mp4]+bestaudio[ext=m4a]/"
                f"bestvideo[height<={height}]+bestaudio/"
                f"best[height<={height}]/best"
            )
        return "bestvideo[ext=mp4]+bestaudio[ext=m4a]/bestvideo+bestaudio/best"

    def _find_best_subtitle(
        self,
        output_dir: str,
        video_stem: str,
        prefer_langs: Optional[List[str]] = None,
    ) -> Optional[str]:
        """在输出目录中寻找匹配的最佳字幕文件 (.srt)"""
        if prefer_langs is None:
            prefer_langs = [
                "zh-TW",
                "zh-Hant",
                "zh-HK",
                "zh-CN",
                "zh-Hans",
                "zh",
                "en",
            ]

        # 查找所有匹配前缀的 .srt 文件
        pattern = os.path.join(output_dir, f"{video_stem}*.srt")
        matched_srts = glob.glob(pattern)
        if not matched_srts:
            return None

        # 依优先语言顺序匹配
        for lang in prefer_langs:
            lang_lower = lang.lower()
            for srt in matched_srts:
                filename_lower = os.path.basename(srt).lower()
                if f".{lang_lower}." in filename_lower or filename_lower.endswith(f".{lang_lower}.srt"):
                    return srt

        # 若无完全匹配语言，返回首个匹配的 srt
        return matched_srts[0]

    def download(
        self,
        url: str,
        resolution: str = "best",
        download_subtitles: bool = True,
        output_format: str = "mp4",
        rename: Optional[str] = None,
        progress_hook: Optional[Callable[[Dict[str, Any]], None]] = None,
        subtitle_langs: Optional[List[str]] = None,
    ) -> Dict[str, Any]:
        """
        下载视频并同步获取字幕

        Args:
            url: 视频网页地址 (YouTube, Bilibili, TikTok 等)
            resolution: 分辨率 ('best', '1080p', '720p', '480p')
            download_subtitles: 是否同时下载字幕并转为 SRT
            output_format: 输出视频格式（默认 mp4）
            rename: 可选自定义文件名（不含扩展名）
            progress_hook: 进度回调用函数
            subtitle_langs: 优先下载的字幕语言列表

        Returns:
            Dict: {
                "task_id": str,
                "video_path": str,
                "subtitle_path": Optional[str],
                "filename": str,
                "title": str,
                "duration": int | float,
                "status": "success",
            }
        """
        if not self.is_available():
            raise RuntimeError("yt-dlp 尚未安装，请在环境中运行 `pip install yt-dlp`")

        url = str(url or "").strip()
        if not url:
            raise ValueError("视频下载 URL 不能为空")

        task_id = str(uuid4())
        output_dir = utils.video_dir()
        os.makedirs(output_dir, exist_ok=True)
        subtitle_dir = utils.subtitle_dir()
        os.makedirs(subtitle_dir, exist_ok=True)

        proxy = self.get_proxy()
        format_selector = self._get_format_selector(resolution)

        # 构造输出模板
        if rename and str(rename).strip():
            safe_name = re.sub(r'[\\/*?:"<>|]', "", str(rename).strip())
            outtmpl = os.path.join(output_dir, f"{safe_name}.%(ext)s")
            expected_stem = safe_name
        else:
            outtmpl = os.path.join(output_dir, "%(title).80B-%(id)s.%(ext)s")
            expected_stem = None

        ydl_opts: Dict[str, Any] = {
            "format": format_selector,
            "outtmpl": outtmpl,
            "merge_output_format": output_format.lower(),
            "windowsfilenames": True,
            "restrictfilenames": False,
            "quiet": True,
            "no_warnings": True,
            "postprocessors": [
                {
                    "key": "FFmpegVideoConvertor",
                    "preferedformat": output_format.lower(),
                }
            ],
        }

        if proxy:
            ydl_opts["proxy"] = proxy
            logger.info(f"yt-dlp 使用代理: {proxy}")

        if progress_hook:
            ydl_opts["progress_hooks"] = [progress_hook]

        # 字幕下载配置
        if download_subtitles:
            if subtitle_langs is None:
                subtitle_langs = [
                    "zh-TW",
                    "zh-Hant",
                    "zh-HK",
                    "zh-CN",
                    "zh-Hans",
                    "zh",
                    "en",
                ]
            ydl_opts.update(
                {
                    "writesubtitles": True,
                    "writeautomaticsub": True,
                    "subtitleslangs": subtitle_langs,
                    "subtitlesformat": "srt",
                }
            )
            ydl_opts["postprocessors"].append(
                {
                    "key": "FFmpegSubtitlesConvertor",
                    "format": "srt",
                }
            )

        logger.info(f"开始使用 yt-dlp 下载视频: {url}, 目标分辨率: {resolution}")
        try:
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(url, download=True)
                if not info:
                    raise RuntimeError("无法提取视频信息，请检查网址是否正确或可公开访问")

                # 如果是播放列表，取第一个
                if "entries" in info:
                    entries = list(info.get("entries") or [])
                    if not entries:
                        raise RuntimeError("播放列表为空")
                    info = entries[0]

                video_title = info.get("title", task_id)
                video_duration = info.get("duration", 0)

                # 寻找下载后的视频真实文件路径
                video_path = None
                # 方法 1: 通过 prepare_filename 获取
                try:
                    prepared = ydl.prepare_filename(info)
                    base, _ = os.path.splitext(prepared)
                    candidate = f"{base}.{output_format.lower()}"
                    if os.path.exists(candidate):
                        video_path = candidate
                    elif os.path.exists(prepared):
                        video_path = prepared
                except Exception:
                    pass

                # 方法 2: 若未找到，在 output_dir 中查找最新文件
                if not video_path or not os.path.exists(video_path):
                    video_id = info.get("id", "")
                    candidates = glob.glob(os.path.join(output_dir, f"*{video_id}*.{output_format.lower()}"))
                    if candidates:
                        video_path = max(candidates, key=os.path.getmtime)

                if not video_path or not os.path.exists(video_path):
                    raise FileNotFoundError("视频下载已完成，但无法定位生成的视频文件")

                video_filename = os.path.basename(video_path)
                video_stem, _ = os.path.splitext(video_filename)

                # 查找字幕文件
                final_subtitle_path = None
                if download_subtitles:
                    found_srt = self._find_best_subtitle(output_dir, video_stem, subtitle_langs)
                    if found_srt and os.path.exists(found_srt):
                        # 同时复制一份到 subtitle_dir
                        dest_srt = os.path.join(subtitle_dir, os.path.basename(found_srt))
                        if found_srt != dest_srt:
                            try:
                                shutil.copy2(found_srt, dest_srt)
                                final_subtitle_path = dest_srt
                            except Exception as copy_err:
                                logger.warning(f"复制字幕到 srt 目录失败: {copy_err}")
                                final_subtitle_path = found_srt
                        else:
                            final_subtitle_path = found_srt
                        logger.info(f"成功获取字幕: {final_subtitle_path}")
                    else:
                        logger.info("未检索到可用字幕文件")

                logger.info(f"视频下载成功: {video_path}")
                return {
                    "task_id": task_id,
                    "video_path": video_path,
                    "subtitle_path": final_subtitle_path,
                    "filename": video_filename,
                    "title": video_title,
                    "duration": video_duration,
                    "status": "success",
                }

        except Exception as e:
            logger.exception(f"yt-dlp 下载视频失败: {str(e)}")
            raise

    def download_video(
        self,
        url: str,
        resolution: str = "best",
        output_format: str = "mp4",
        rename: Optional[str] = None,
    ) -> Tuple[str, str, str]:
        """向下兼容旧版接口，返回 (task_id, output_path, filename)"""
        result = self.download(
            url=url,
            resolution=resolution,
            download_subtitles=True,
            output_format=output_format,
            rename=rename,
        )
        return result["task_id"], result["video_path"], result["filename"]
