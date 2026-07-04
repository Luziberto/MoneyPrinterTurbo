import os
import os
import sys
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

import requests

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from app.config import config
from app.models.schema import CollectorJobResult, CollectorSelectedClip, VideoAspect, VideoConcatMode
from app.services import material


class TestMaterialTlsVerification(unittest.TestCase):
    def setUp(self):
        self.original_app_config = dict(config.app)
        self.original_proxy_config = dict(config.proxy)

    def tearDown(self):
        config.app.clear()
        config.app.update(self.original_app_config)
        config.proxy.clear()
        config.proxy.update(self.original_proxy_config)

    def test_search_pexels_uses_tls_verification_by_default(self):
        """
        默认路径必须开启 TLS 校验，避免素材 API key 和返回的素材 URL
        在公共网络或不可信代理环境中被中间人攻击截获或篡改。
        """
        config.app["pexels_api_keys"] = ["pexels-key"]
        config.app.pop("tls_verify", None)
        config.proxy.clear()

        fake_response = SimpleNamespace(
            json=lambda: {
                "videos": [
                    {
                        "duration": 8,
                        "video_files": [
                            {
                                "width": 1080,
                                "height": 1920,
                                "link": "https://example.com/video.mp4",
                            }
                        ],
                    }
                ]
            }
        )

        with patch("app.services.material.requests.get", return_value=fake_response) as get:
            results = material.search_videos_pexels("cat", minimum_duration=1)

        self.assertEqual(len(results), 1)
        self.assertTrue(get.call_args.kwargs["verify"])

    def test_search_pixabay_allows_explicit_tls_disable_for_proxy(self):
        """
        少数企业代理会使用自签证书。该场景必须显式配置关闭 TLS 校验，
        不能再由代码硬编码默认关闭。
        """
        config.app["pixabay_api_keys"] = ["pixabay-key"]
        config.app["tls_verify"] = False
        config.proxy.clear()

        fake_response = SimpleNamespace(
            json=lambda: {
                "hits": [
                    {
                        "duration": 8,
                        "videos": {
                            "large": {
                                "width": 1920,
                                "url": "https://example.com/video.mp4",
                            }
                        },
                    }
                ]
            }
        )

        with patch("app.services.material.requests.get", return_value=fake_response) as get:
            results = material.search_videos_pixabay("cat", minimum_duration=1)

        self.assertEqual(len(results), 1)
        self.assertFalse(get.call_args.kwargs["verify"])

    def test_save_video_uses_tls_verification_by_default(self):
        config.app.pop("tls_verify", None)
        config.proxy.clear()

        fake_response = SimpleNamespace(content=b"fake-video")

        class FakeVideoFileClip:
            duration = 1
            fps = 24

            def __init__(self, path):
                self.path = path

            def close(self):
                return None

        with tempfile.TemporaryDirectory() as temp_dir:
            with patch(
                "app.services.material.requests.get", return_value=fake_response
            ) as get, patch("app.services.material.VideoFileClip", FakeVideoFileClip):
                video_path = material.save_video(
                    "https://example.com/video.mp4?token=abc", save_dir=temp_dir
                )

            self.assertTrue(os.path.exists(video_path))
            self.assertTrue(get.call_args.kwargs["verify"])

    def test_download_videos_accepts_plain_string_concat_mode(self):
        """
        download_videos 可能被服务层或测试直接传入字符串模式，而不是
        VideoConcatMode 枚举。这里用空搜索词避免真实网络请求，只验证
        字符串 "random" 不会再因为访问 `.value` 抛 AttributeError。
        """
        result = material.download_videos(
            task_id="string-concat-mode",
            search_terms=[],
            video_concat_mode="random",
        )

        self.assertEqual(result, [])

    def test_download_videos_can_round_robin_terms_in_script_order(self):
        """
        开启按文案顺序匹配素材后，不能让第一个关键词的多个候选先把
        音频时长填满。这里模拟两个关键词各有多个候选，验证下载顺序是
        term1-第1个、term2-第1个、term1-第2个，贴近脚本叙事顺序。
        """
        search_results = {
            "opening city": [
                material.MaterialInfo(provider="pexels", url="https://v.example/a1.mp4", duration=3),
                material.MaterialInfo(provider="pexels", url="https://v.example/a2.mp4", duration=3),
            ],
            "middle office": [
                material.MaterialInfo(provider="pexels", url="https://v.example/b1.mp4", duration=3),
                material.MaterialInfo(provider="pexels", url="https://v.example/b2.mp4", duration=3),
            ],
        }
        downloaded_urls = []

        def fake_search(search_term, minimum_duration, video_aspect):
            return search_results[search_term]

        def fake_save_video(video_url, save_dir=""):
            downloaded_urls.append(video_url)
            return f"/tmp/{video_url.rsplit('/', 1)[-1]}"

        with (
            patch.dict(config.app, {"material_directory": ""}),
            patch.object(material, "search_videos_pexels", side_effect=fake_search),
            patch.object(material, "save_video", side_effect=fake_save_video),
        ):
            result = material.download_videos(
                task_id="ordered-materials",
                search_terms=["opening city", "middle office"],
                source="pexels",
                audio_duration=7,
                max_clip_duration=3,
                match_script_order=True,
            )

        self.assertEqual(
            downloaded_urls,
            [
                "https://v.example/a1.mp4",
                "https://v.example/b1.mp4",
                "https://v.example/a2.mp4",
            ],
        )
        self.assertEqual(result, ["/tmp/a1.mp4", "/tmp/b1.mp4", "/tmp/a2.mp4"])


class TestCoverrProvider(unittest.TestCase):
    """
    Coverr 视频素材源(spec: 2026-06-09-coverr-video-provider-design.md)。
    全部用 unittest.mock 替换 requests，确保 CI 不依赖真实网络和真实 API key。
    """

    def setUp(self):
        self.original_app_config = dict(config.app)
        self.original_proxy_config = dict(config.proxy)

    def tearDown(self):
        config.app.clear()
        config.app.update(self.original_app_config)
        config.proxy.clear()
        config.proxy.update(self.original_proxy_config)

    # ---------------- Tests for search_videos_coverr ----------------

    def test_search_coverr_uses_mp4_download_url(self):
        """
        search_videos_coverr 应把每个 hit 转成 MaterialInfo，并把 urls.mp4_download
        直接作为 MaterialInfo.url。
        按 Coverr 官方文档 (api.coverr.co/docs/videos/#download-a-video),
        GET mp4_download 本身就被 Coverr 计入下载统计,无需额外 PATCH ping。
        同时验证 Authorization header 使用 Bearer scheme。
        """
        config.app["coverr_api_keys"] = ["coverr-key"]
        config.app.pop("tls_verify", None)
        config.proxy.clear()

        fake_response = SimpleNamespace(
            json=lambda: {
                "page": 0,
                "pages": 50,
                "page_size": 20,
                "total": 1,
                "hits": [
                    {
                        "id": "S1YbPl1NfI",
                        "duration": 11.625,
                        "aspect_ratio": "16:9",
                        "urls": {
                            "mp4": "https://storage.coverr.co/videos/abc?token=xyz",
                            "mp4_preview": "https://storage.coverr.co/videos/abc/preview?token=xyz",
                            "mp4_download": "https://storage.coverr.co/videos/abc/download?token=xyz",
                        },
                    }
                ],
            }
        )

        with patch(
            "app.services.material.requests.get", return_value=fake_response
        ) as get:
            results = material.search_videos_coverr("nature", minimum_duration=5)

        self.assertEqual(len(results), 1)
        item = results[0]
        self.assertEqual(item.provider, "coverr")
        self.assertEqual(item.duration, 11)
        # url 字段就是 mp4_download URL,不再做 coverr://id|url 编码
        self.assertEqual(
            item.url, "https://storage.coverr.co/videos/abc/download?token=xyz"
        )
        # Bearer auth + TLS verify on by default
        self.assertEqual(
            get.call_args.kwargs["headers"]["Authorization"], "Bearer coverr-key"
        )
        self.assertTrue(get.call_args.kwargs["verify"])

    def test_search_coverr_uses_tls_verification_by_default(self):
        """与 pexels/pixabay 一致:未显式配置时 TLS 校验默认开启。"""
        config.app["coverr_api_keys"] = ["coverr-key"]
        config.app.pop("tls_verify", None)
        config.proxy.clear()

        fake_response = SimpleNamespace(json=lambda: {"hits": []})

        with patch(
            "app.services.material.requests.get", return_value=fake_response
        ) as get:
            material.search_videos_coverr("nature", minimum_duration=1)

        self.assertTrue(get.call_args.kwargs["verify"])

    def test_search_coverr_allows_explicit_tls_disable_for_proxy(self):
        """企业自签证书代理场景必须能显式关闭 TLS 校验。"""
        config.app["coverr_api_keys"] = ["coverr-key"]
        config.app["tls_verify"] = False
        config.proxy.clear()

        fake_response = SimpleNamespace(json=lambda: {"hits": []})

        with patch(
            "app.services.material.requests.get", return_value=fake_response
        ) as get:
            material.search_videos_coverr("nature", minimum_duration=1)

        self.assertFalse(get.call_args.kwargs["verify"])

    def test_search_coverr_filters_by_min_duration_and_accepts_string(self):
        """
        Coverr duration 字段在不同响应里可能是 number 或 string,
        两种格式都要接受;低于 minimum_duration 的应被过滤。
        """
        config.app["coverr_api_keys"] = ["coverr-key"]
        config.app.pop("tls_verify", None)
        config.proxy.clear()

        fake_response = SimpleNamespace(
            json=lambda: {
                "hits": [
                    {
                        "id": "shortvid",
                        "duration": 3,  # below minimum
                        "urls": {"mp4_download": "https://example.com/a.mp4"},
                    },
                    {
                        "id": "stringdur",
                        "duration": "10.500000",  # string accepted
                        "urls": {"mp4_download": "https://example.com/b.mp4"},
                    },
                ]
            }
        )

        with patch(
            "app.services.material.requests.get", return_value=fake_response
        ):
            results = material.search_videos_coverr("x", minimum_duration=5)

        self.assertEqual(len(results), 1)
        self.assertEqual(results[0].duration, 10)
        self.assertEqual(results[0].url, "https://example.com/b.mp4")

    def test_search_coverr_skips_invalid_items(self):
        """缺 id 或缺 urls.mp4_download 的条目应被跳过,不应抛异常。"""
        config.app["coverr_api_keys"] = ["coverr-key"]
        config.app.pop("tls_verify", None)
        config.proxy.clear()

        fake_response = SimpleNamespace(
            json=lambda: {
                "hits": [
                    {  # missing urls.mp4_download
                        "id": "no-download",
                        "duration": 10,
                        "urls": {"mp4_preview": "https://example.com/preview.mp4"},
                    },
                    {  # missing id
                        "duration": 10,
                        "urls": {"mp4_download": "https://example.com/x.mp4"},
                    },
                    {  # valid baseline
                        "id": "good",
                        "duration": 10,
                        "urls": {"mp4_download": "https://example.com/good.mp4"},
                    },
                ]
            }
        )

        with patch(
            "app.services.material.requests.get", return_value=fake_response
        ):
            results = material.search_videos_coverr("x", minimum_duration=1)

        self.assertEqual(len(results), 1)
        self.assertEqual(results[0].url, "https://example.com/good.mp4")

    def test_search_coverr_returns_empty_on_failure(self):
        """
        响应结构异常 / 网络异常时,函数必须返回 [] 而不是抛异常,
        与 pexels/pixabay 行为保持一致。
        """
        config.app["coverr_api_keys"] = ["coverr-key"]
        config.app.pop("tls_verify", None)
        config.proxy.clear()

        # Subtest A: malformed response (no "hits" key)
        with self.subTest("malformed response"):
            fake_response = SimpleNamespace(
                json=lambda: {"error": "rate limited"}
            )
            with patch(
                "app.services.material.requests.get", return_value=fake_response
            ):
                results = material.search_videos_coverr("x", minimum_duration=1)
            self.assertEqual(results, [])

        # Subtest B: network exception bubbles up from requests.get
        with self.subTest("network exception"):
            with patch(
                "app.services.material.requests.get",
                side_effect=requests.ConnectionError("boom"),
            ):
                results = material.search_videos_coverr("x", minimum_duration=1)
            self.assertEqual(results, [])

    # ---------------- Tests for download_videos coverr branch ----------------

    def test_download_videos_passes_mp4_download_url_to_save_video(self):
        """
        在 source="coverr" 时:
          1. dispatch 到 search_videos_coverr
          2. coverr item 走通用下载路径:save_video 收到的就是 mp4_download URL
             (不再有 coverr://id|url 编码,也不再调用 PATCH ping)
          3. 返回保存路径
        """
        config.app["coverr_api_keys"] = ["coverr-key"]
        config.app.pop("tls_verify", None)
        config.app.pop("material_directory", None)
        config.proxy.clear()

        fake_item = material.MaterialInfo()
        fake_item.provider = "coverr"
        fake_item.url = "https://storage.coverr.co/videos/abc/download?token=xyz"
        fake_item.duration = 10

        with patch(
            "app.services.material.search_videos_coverr",
            return_value=[fake_item],
        ) as search, patch(
            "app.services.material.save_video",
            return_value="/tmp/coverr-saved.mp4",
        ) as save:
            result = material.download_videos(
                task_id="t-coverr",
                search_terms=["nature"],
                source="coverr",
                audio_duration=5,
                max_clip_duration=5,
            )

        # 1. dispatch
        self.assertEqual(search.call_count, 1)

        # 2. save_video 收到的就是 mp4_download URL,原样传入
        save_url = save.call_args.kwargs.get("video_url") or save.call_args.args[0]
        self.assertEqual(
            save_url, "https://storage.coverr.co/videos/abc/download?token=xyz"
        )

        # 3. 返回值正确
        self.assertEqual(result, ["/tmp/coverr-saved.mp4"])


class TestStockVideoAggregator(unittest.TestCase):
    def setUp(self):
        self.original_app_config = dict(config.app)
        self.original_proxy_config = dict(config.proxy)

    def tearDown(self):
        config.app.clear()
        config.app.update(self.original_app_config)
        config.proxy.clear()
        config.proxy.update(self.original_proxy_config)

    def _make_item(self, provider: str, url: str, duration: int = 10) -> material.MaterialInfo:
        item = material.MaterialInfo()
        item.provider = provider
        item.url = url
        item.duration = duration
        return item

    def test_search_stock_videos_merges_and_dedupes(self):
        config.app["pexels_api_keys"] = ["pexels-key"]
        config.app["pixabay_api_keys"] = ["pixabay-key"]
        config.app["coverr_api_keys"] = ["coverr-key"]

        pexels_items = [
            self._make_item("pexels", "https://example.com/a.mp4?token=1"),
            self._make_item("pexels", "https://example.com/b.mp4"),
        ]
        pixabay_items = [
            self._make_item("pixabay", "https://example.com/a.mp4?token=2"),
            self._make_item("pixabay", "https://example.com/c.mp4"),
        ]
        coverr_items = [
            self._make_item("coverr", "https://example.com/d.mp4?dl=1"),
        ]

        with patch(
            "app.services.material.search_videos_pexels", return_value=pexels_items
        ), patch(
            "app.services.material.search_videos_pixabay", return_value=pixabay_items
        ), patch(
            "app.services.material.search_videos_coverr", return_value=coverr_items
        ):
            results = material.search_stock_videos("japan", minimum_duration=5)

        urls = [item.url for item in results]
        self.assertEqual(len(results), 4)
        self.assertIn("https://example.com/a.mp4?token=1", urls)
        self.assertIn("https://example.com/b.mp4", urls)
        self.assertIn("https://example.com/c.mp4", urls)
        self.assertIn("https://example.com/d.mp4?dl=1", urls)
        providers = {item.provider for item in results}
        self.assertEqual(providers, {"pexels", "pixabay", "coverr"})

    def test_search_stock_videos_skips_missing_api_key(self):
        config.app["pexels_api_keys"] = []
        config.app["pixabay_api_keys"] = ["pixabay-key"]
        config.app["coverr_api_keys"] = ["coverr-key"]

        pixabay_items = [self._make_item("pixabay", "https://example.com/p.mp4")]
        coverr_items = [self._make_item("coverr", "https://example.com/c.mp4")]

        with patch(
            "app.services.material.search_videos_pexels",
        ) as search_pexels, patch(
            "app.services.material.search_videos_pixabay", return_value=pixabay_items
        ), patch(
            "app.services.material.search_videos_coverr", return_value=coverr_items
        ):
            results = material.search_stock_videos("japan", minimum_duration=5)

        search_pexels.assert_not_called()
        self.assertEqual(len(results), 2)
        self.assertEqual({item.provider for item in results}, {"pixabay", "coverr"})

    def test_search_stock_videos_continues_on_provider_error(self):
        config.app["pexels_api_keys"] = ["pexels-key"]
        config.app["pixabay_api_keys"] = ["pixabay-key"]
        config.app["coverr_api_keys"] = ["coverr-key"]

        pixabay_items = [self._make_item("pixabay", "https://example.com/p.mp4")]
        coverr_items = [self._make_item("coverr", "https://example.com/c.mp4")]

        with patch(
            "app.services.material.search_videos_pexels",
            side_effect=RuntimeError("pexels down"),
        ), patch(
            "app.services.material.search_videos_pixabay", return_value=pixabay_items
        ), patch(
            "app.services.material.search_videos_coverr", return_value=coverr_items
        ):
            results = material.search_stock_videos("japan", minimum_duration=5)

        self.assertEqual(len(results), 2)
        self.assertEqual({item.provider for item in results}, {"pixabay", "coverr"})

    def test_download_videos_dispatches_stock_source(self):
        config.app["pexels_api_keys"] = ["pexels-key"]
        config.app["pixabay_api_keys"] = ["pixabay-key"]
        config.app["coverr_api_keys"] = ["coverr-key"]
        config.app.pop("material_directory", None)

        fake_item = self._make_item("pexels", "https://example.com/stock.mp4")

        with patch(
            "app.services.material.search_stock_videos",
            return_value=[fake_item],
        ) as search_stock, patch(
            "app.services.material.save_video",
            return_value="/tmp/stock-saved.mp4",
        ):
            result = material.download_videos(
                task_id="t-stock",
                search_terms=["japan"],
                source="stock",
                audio_duration=5,
                max_clip_duration=5,
            )

        self.assertEqual(search_stock.call_count, 1)
        self.assertEqual(result, ["/tmp/stock-saved.mp4"])


class TestMaterialScoring(unittest.TestCase):
    def _make_item(
        self,
        provider: str = "pexels",
        url: str = "https://example.com/video.mp4",
        duration: int = 10,
        width: int = 0,
        height: int = 0,
        search_term: str = "",
        metadata_text: str = "",
    ) -> material.MaterialInfo:
        item = material.MaterialInfo()
        item.provider = provider
        item.url = url
        item.duration = duration
        item.width = width
        item.height = height
        item.search_term = search_term
        item.metadata_text = metadata_text
        return item

    def test_score_material_portrait_high(self):
        item = self._make_item(
            width=1080,
            height=1920,
            duration=10,
            search_term="japan street",
            metadata_text="japan street market",
        )
        score = material._score_material(
            item, VideoAspect.portrait, target_w=1080, target_h=1920
        )
        self.assertEqual(score, 12)

    def test_score_material_landscape_low_for_portrait(self):
        item = self._make_item(
            width=1920,
            height=1080,
            duration=10,
            search_term="japan street",
            metadata_text="unrelated scenery",
        )
        score = material._score_material(
            item, VideoAspect.portrait, target_w=1080, target_h=1920
        )
        self.assertEqual(score, 2)

    def test_rank_materials_top_n(self):
        high_items = [
            self._make_item(
                url=f"https://example.com/high-{index}.mp4",
                width=1080,
                height=1920,
                duration=10,
                search_term="japan",
                metadata_text="japan street",
            )
            for index in range(35)
        ]
        low_items = [
            self._make_item(
                url=f"https://example.com/low-{index}.mp4",
                width=1920,
                height=1080,
                duration=10,
                search_term="japan",
                metadata_text="unrelated",
            )
            for index in range(5)
        ]

        ranked = material._rank_materials(high_items + low_items, VideoAspect.portrait)

        self.assertEqual(len(ranked), material.MATERIAL_SCORE_TOP_N)
        self.assertTrue(all(item.score == 12 for item in ranked))
        self.assertTrue(
            all("high-" in item.url for item in ranked)
        )

    def test_rank_materials_stable_tie(self):
        first = self._make_item(
            url="https://example.com/first.mp4",
            width=1080,
            height=1920,
            duration=10,
            search_term="tokyo",
            metadata_text="tokyo street",
        )
        second = self._make_item(
            url="https://example.com/second.mp4",
            width=1080,
            height=1920,
            duration=10,
            search_term="tokyo",
            metadata_text="tokyo street",
        )
        ranked = material._rank_materials([first, second], VideoAspect.portrait)

        self.assertEqual(ranked[0].url, "https://example.com/first.mp4")
        self.assertEqual(ranked[1].url, "https://example.com/second.mp4")
        self.assertEqual(ranked[0].score, ranked[1].score)

    def test_download_videos_random_shuffles_only_ranked(self):
        config.app.pop("material_directory", None)

        fake_items = [
            self._make_item(
                url=f"https://example.com/ranked-{index}.mp4",
                width=1080,
                height=1920,
                duration=10,
            )
            for index in range(3)
        ]

        with patch(
            "app.services.material.search_videos_pexels",
            return_value=fake_items,
        ), patch(
            "app.services.material._rank_materials",
            return_value=fake_items,
        ) as rank, patch(
            "app.services.material.random.shuffle",
        ) as shuffle, patch(
            "app.services.material.save_video",
            return_value="/tmp/ranked.mp4",
        ):
            material.download_videos(
                task_id="t-random",
                search_terms=["japan"],
                source="pexels",
                video_contact_mode=VideoConcatMode.random,
                audio_duration=5,
                max_clip_duration=5,
            )

        rank.assert_called_once()
        shuffle.assert_called_once_with(fake_items)

    def test_download_videos_sequential_no_shuffle(self):
        config.app.pop("material_directory", None)

        fake_items = [
            self._make_item(
                url="https://example.com/sequential.mp4",
                width=1080,
                height=1920,
                duration=10,
            )
        ]

        with patch(
            "app.services.material.search_videos_pexels",
            return_value=fake_items,
        ), patch(
            "app.services.material._rank_materials",
            return_value=fake_items,
        ), patch(
            "app.services.material.random.shuffle",
        ) as shuffle, patch(
            "app.services.material.save_video",
            return_value="/tmp/sequential.mp4",
        ):
            material.download_videos(
                task_id="t-sequential",
                search_terms=["japan"],
                source="pexels",
                video_contact_mode=VideoConcatMode.sequential,
                audio_duration=5,
                max_clip_duration=5,
            )

        shuffle.assert_not_called()


class TestCollectorProvider(unittest.TestCase):
    def setUp(self):
        self.original_app_config = dict(config.app)
        self.original_proxy_config = dict(config.proxy)

    def tearDown(self):
        config.app.clear()
        config.app.update(self.original_app_config)
        config.proxy.clear()
        config.proxy.update(self.original_proxy_config)

    def test_map_collector_path_different_dirs(self):
        import tempfile

        with tempfile.TemporaryDirectory() as temp_dir:
            local_root = os.path.join(temp_dir, "collector_local")
            os.makedirs(os.path.join(local_root, "clips"), exist_ok=True)
            source_file = os.path.join(local_root, "clips", "taiyaki.mp4")
            with open(source_file, "wb") as handle:
                handle.write(b"fake")

            config.app["collector_remote_dir"] = "/downloads"
            config.app["collector_local_dir"] = local_root

            resolved = material.map_collector_path("/downloads/clips/taiyaki.mp4")
            self.assertEqual(resolved, source_file)

    def test_map_collector_path_rejects_traversal(self):
        config.app["collector_remote_dir"] = "/data/downloads"
        config.app["collector_local_dir"] = "/data/downloads"

        with self.assertRaises(ValueError):
            material.map_collector_path("/data/downloads/../etc/passwd")

    def test_search_collector_maps_api_response(self):
        fake_hits = [
            {
                "clip_id": "abc123",
                "title": "Taiyaki street vendor",
                "local_path": "/data/downloads/taiyaki.mp4",
                "duration": 12.4,
                "width": 1080,
                "height": 1920,
                "source_site": "storyblocks",
            }
        ]

        with patch(
            "app.services.material.collector_client.search_collector_clips",
            return_value=fake_hits,
        ):
            results = material.search_videos_collector("taiyaki", minimum_duration=5)

        self.assertEqual(len(results), 1)
        item = results[0]
        self.assertEqual(item.provider, "collector")
        self.assertEqual(item.url, "/data/downloads/taiyaki.mp4")
        self.assertEqual(item.duration, 12)
        self.assertEqual(item.width, 1080)
        self.assertEqual(item.height, 1920)
        self.assertIn("Taiyaki", item.metadata_text)

    def test_stage_collector_clip_copies_to_cache(self):
        import tempfile

        class FakeVideoFileClip:
            duration = 10
            fps = 24

            def __init__(self, path):
                self.path = path

            def close(self):
                return None

        with tempfile.TemporaryDirectory() as temp_dir:
            remote_root = os.path.join(temp_dir, "remote")
            local_root = os.path.join(temp_dir, "local")
            cache_dir = os.path.join(temp_dir, "cache")
            os.makedirs(remote_root)
            os.makedirs(local_root)
            os.makedirs(cache_dir)

            source_file = os.path.join(local_root, "clip.mp4")
            with open(source_file, "wb") as handle:
                handle.write(b"video-bytes")

            config.app["collector_remote_dir"] = remote_root
            config.app["collector_local_dir"] = local_root

            with patch("app.services.material.VideoFileClip", FakeVideoFileClip):
                staged = material.stage_collector_clip(
                    os.path.join(remote_root, "clip.mp4"),
                    save_dir=cache_dir,
                )

            self.assertTrue(staged.startswith(cache_dir))
            self.assertTrue(os.path.exists(staged))
            with open(staged, "rb") as handle:
                self.assertEqual(handle.read(), b"video-bytes")

    def test_download_videos_dispatches_collector_source(self):
        config.app.pop("material_directory", None)
        selected_clip = CollectorSelectedClip(
            path="/tmp/collector.mp4",
            score=0.8,
            retrieval_score=0.7,
            visual_score=0.9,
            duration=12.0,
            matched_keyword="taiyaki",
            source="magnific",
            width=1080,
            height=1920,
        )

        with patch(
            "app.services.material.download_videos_with_collector_fallback",
            return_value=[selected_clip],
        ) as fallback:
            result = material.download_videos(
                task_id="t-collector",
                search_terms=["taiyaki"],
                source="collector",
                audio_duration=30,
                max_clip_duration=5,
            )

        fallback.assert_called_once()
        self.assertEqual(result, [selected_clip])

    def test_collector_sufficient_skips_stock(self):
        selected_clip = CollectorSelectedClip(
            path="/tmp/c1.mp4",
            score=0.8,
            retrieval_score=0.7,
            visual_score=0.9,
            duration=12.0,
            matched_keyword="taiyaki",
            source="magnific",
            width=1080,
            height=1920,
        )
        with patch(
            "app.services.material.collector_client.check_collector_health",
            return_value=True,
        ), patch(
            "app.services.material.download_videos_from_collector",
            return_value=[selected_clip],
        ), patch(
            "app.services.material._download_videos_from_remote",
        ) as remote:
            result = material.download_videos_with_collector_fallback(
                task_id="t-enough",
                search_terms=["taiyaki"],
                audio_duration=50,
                max_clip_duration=5,
            )

        remote.assert_not_called()
        self.assertEqual(result, [selected_clip])

    def test_collector_error_can_fallback_when_enabled(self):
        config.app["collector_enable_legacy_fallback"] = True
        with patch(
            "app.services.material.collector_client.check_collector_health",
            return_value=True,
        ), patch(
            "app.services.material.download_videos_from_collector",
            side_effect=material.collector_client.CollectorJobFailedError(
                "NO_RESULTS", "Not enough clips found"
            ),
        ), patch(
            "app.services.material._download_videos_from_remote",
            return_value=["/tmp/s1.mp4"],
        ) as remote:
            result = material.download_videos_with_collector_fallback(
                task_id="t-fallback-enabled",
                search_terms=["taiyaki"],
                audio_duration=60,
                max_clip_duration=5,
            )

        remote.assert_called_once()
        self.assertEqual(remote.call_args.kwargs["audio_duration"], 60)
        self.assertEqual(result, ["/tmp/s1.mp4"])

    def test_collector_health_fail_full_stock(self):
        config.app["collector_fallback_source"] = "stock"
        config.app["collector_enable_legacy_fallback"] = True

        with patch(
            "app.services.material.collector_client.check_collector_health",
            return_value=False,
        ), patch(
            "app.services.material.download_videos_from_collector",
        ) as from_collector, patch(
            "app.services.material._download_videos_from_remote",
            return_value=["/tmp/stock.mp4"],
        ) as remote:
            result = material.download_videos_with_collector_fallback(
                task_id="t-fallback",
                search_terms=["taiyaki"],
                audio_duration=60,
                max_clip_duration=5,
            )

        from_collector.assert_not_called()
        remote.assert_called_once()
        self.assertEqual(remote.call_args.kwargs["audio_duration"], 60)
        self.assertEqual(result, ["/tmp/stock.mp4"])

    def test_collector_health_fail_raises_without_legacy_fallback(self):
        config.app["collector_enable_legacy_fallback"] = False

        with patch(
            "app.services.material.collector_client.check_collector_health",
            return_value=False,
        ):
            with self.assertRaises(
                material.collector_client.CollectorJobFailedError
            ) as ctx:
                material.download_videos_with_collector_fallback(
                    task_id="t-no-fallback",
                    search_terms=["taiyaki"],
                    audio_duration=60,
                    max_clip_duration=5,
                )

        self.assertEqual(ctx.exception.code, "COLLECTOR_UNAVAILABLE")

    def test_download_videos_from_collector_creates_job_and_stages_selected_clips(self):
        config.app["collector_target_clips"] = 25
        config.app["collector_min_acceptable_clips"] = 1
        config.app.pop("material_directory", None)
        ready_job = CollectorJobResult(
            job_id="job-123",
            status="ready",
            selected_clips_count=1,
            min_acceptable_clips=1,
            selected_clips=[
                {
                    "path": "/data/downloads/clip.mp4",
                    "score": 0.8,
                    "retrieval_score": 0.7,
                    "visual_score": 0.9,
                    "duration": 12.0,
                    "matched_keyword": "taiyaki",
                    "source": "magnific",
                    "width": 1080,
                    "height": 1920,
                }
            ],
        )

        with patch(
            "app.services.material.collector_client.create_stock_job",
            return_value=CollectorJobResult(job_id="job-123", status="pending"),
        ) as create_job, patch(
            "app.services.material.collector_client.wait_for_stock_job",
            return_value=ready_job,
        ), patch(
            "app.services.material.collector_client.load_selected_clips",
            return_value=ready_job.selected_clips,
        ), patch(
            "app.services.material.stage_collector_clip",
            return_value="/tmp/staged-clip.mp4",
        ):
            result = material.download_videos_from_collector(
                task_id="t-job",
                search_terms=["taiyaki"],
                audio_duration=60,
                max_clip_duration=5,
            )

        self.assertEqual(len(result), 1)
        self.assertEqual(result[0].path, "/tmp/staged-clip.mp4")
        self.assertEqual(create_job.call_args.args[0].client_task_id, "mpt_t-job")


if __name__ == "__main__":
    unittest.main()
