#!/usr/bin/env python3
"""
抖音自拍vlog · 生活记录 热门视频爬虫
=====================================

功能：
  1. 爬取抖音搜索页面的视频数据（标题、作者、点赞、评论、链接等）
  2. 爬取指定话题/标签下的热门视频
  3. 将爬取结果导入工作台的 data/crawled_videos.json
  4. 支持命令行参数配置

使用方式：
  # 基础搜索
  python3 crawler.py --keyword "自拍vlog 生活记录" --count 20

  # 按话题爬取
  python3 crawler.py --topic "生活记录" --count 20

  # 查看帮助
  python3 crawler.py --help

⚠️ 注意：
  - 抖音有反爬机制，需要提供有效的Cookie
  - 建议间隔请求，避免频繁触发反爬
  - 仅供学习研究使用，请遵守平台协议
"""

import argparse
import json
import os
import random
import re
import sys
import time
from pathlib import Path
from urllib.parse import quote

try:
    import requests
except ImportError:
    os.system(f"{sys.executable} -m pip install requests -q")
    import requests

# ====== 配置 ======
SCRIPT_DIR = Path(__file__).parent.parent
DATA_DIR = SCRIPT_DIR / "data"
DATA_DIR.mkdir(exist_ok=True)

OUTPUT_FILE = DATA_DIR / "crawled_videos.json"

# 默认请求头（需要用户更新Cookie）
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Referer": "https://www.douyin.com/",
    "Accept": "application/json, text/plain, */*",
    "Accept-Language": "zh-CN,zh;q=0.9",
    "Cookie": "",  # ← 在这里粘贴你的抖音Cookie
}

# 备用方案：通过移动端页面爬取
MOBILE_HEADERS = {
    "User-Agent": "Mozilla/5.0 (iPhone; CPU iPhone OS 16_0 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/16.0 Mobile/15E148 Safari/604.1",
}


class DouyinCrawler:
    """抖音视频爬虫"""

    def __init__(self, cookie=""):
        self.session = requests.Session()
        self.session.headers.update(HEADERS)
        if cookie:
            self.session.headers["Cookie"] = cookie
        self.videos = []

    def search_videos(self, keyword, count=20, sort_type=0):
        """
        搜索视频
        :param keyword: 搜索关键词
        :param count: 获取数量
        :param sort_type: 0=综合排序, 1=最新发布, 2=最多点赞
        """
        print(f"🔍 搜索关键词: {keyword}")
        print(f"📊 目标数量: {count}")
        
        # 抖音搜索API（web端）
        api_url = "https://www.douyin.com/aweme/v1/web/general/search/single/"
        
        params = {
            "keyword": keyword,
            "search_source": "normal_search",
            "query_correct_type": "1",
            "is_filter_search": "0",
            "from_group_id": "",
            "offset": "0",
            "count": str(min(count, 20)),
            "search_id": "",
            "sort_type": str(sort_type),
            "publish_time": "0",
            "filter_selected_type": "0",
        }

        try:
            # 尝试通过搜索页获取
            print("📡 正在请求抖音搜索...")
            resp = self.session.get(
                "https://www.douyin.com/search/" + quote(keyword),
                timeout=15,
                allow_redirects=True,
            )
            
            # 提取SSR数据
            ssr_data = self._extract_ssr_data(resp.text)
            if ssr_data:
                videos = self._parse_ssr_videos(ssr_data, keyword)
                if videos:
                    self.videos.extend(videos)
                    print(f"✅ 从SSR数据获取到 {len(videos)} 个视频")

            # 尝试API接口
            if len(self.videos) < count:
                api_videos = self._try_api_search(params, keyword)
                self.videos.extend(api_videos)

            # 补充通过移动端页面
            if len(self.videos) < count:
                print("📱 尝试移动端页面...")
                mobile_videos = self._crawl_mobile_search(keyword, count - len(self.videos))
                self.videos.extend(mobile_videos)

        except Exception as e:
            print(f"❌ 搜索失败: {e}")
            print("💡 提示: 可能需要更新Cookie或使用代理")

        # 截取所需数量
        self.videos = self.videos[:count]
        
        # 去重
        seen = set()
        unique = []
        for v in self.videos:
            key = v.get("title", "") + v.get("author", "")
            if key not in seen:
                seen.add(key)
                unique.append(v)
        self.videos = unique

        print(f"📦 最终获取 {len(self.videos)} 个视频")
        return self.videos

    def _extract_ssr_data(self, html):
        """从页面HTML中提取SSR渲染数据"""
        try:
            # 抖音SSR数据通常在 RENDER_DATA 或 __INITIAL_STATE__ 中
            patterns = [
                r'<script id="RENDER_DATA"[^>]*>(.*?)</script>',
                r'window\._SSR_DATA\s*=\s*({.*?});',
                r'window\.__INITIAL_STATE__\s*=\s*({.*?});',
            ]
            for pattern in patterns:
                match = re.search(pattern, html, re.DOTALL)
                if match:
                    raw = match.group(1)
                    # URL解码
                    from urllib.parse import unquote
                    raw = unquote(raw)
                    return json.loads(raw)
        except Exception as e:
            pass
        return None

    def _parse_ssr_videos(self, ssr_data, keyword):
        """解析SSR数据中的视频列表"""
        videos = []
        try:
            # 尝试多种数据路径
            search_data = (
                ssr_data.get("aweme", {}).get("search", {})
                or ssr_data.get("search", {})
                or ssr_data.get("data", {})
            )
            
            items = (
                search_data.get("data", [])
                or search_data.get("aweme_list", [])
                or search_data.get("list", [])
            )

            for item in items:
                aweme = item.get("aweme_info") or item
                video = self._parse_aweme(aweme)
                if video:
                    videos.append(video)
        except Exception as e:
            print(f"  SSR解析异常: {e}")
        
        return videos

    def _parse_aweme(self, aweme):
        """解析单个视频数据"""
        try:
            statistics = aweme.get("statistics", {})
            author = aweme.get("author", {})
            video = aweme.get("video", {})
            
            return {
                "title": aweme.get("desc", "无标题"),
                "author": author.get("nickname", "未知"),
                "authorId": author.get("unique_id") or author.get("short_id", ""),
                "url": f"https://www.douyin.com/video/{aweme.get('aweme_id', '')}",
                "cover": video.get("cover", {}).get("url_list", [""])[0] if video.get("cover") else "",
                "duration": self._format_duration(video.get("duration", 0)),
                "likes": statistics.get("digg_count", 0),
                "comments": statistics.get("comment_count", 0),
                "shares": statistics.get("share_count", 0),
                "views": statistics.get("play_count", 0),
                "favorites": statistics.get("collect_count", 0),
                "publishedAt": self._format_timestamp(aweme.get("create_time", 0)),
                "tags": [t.get("hashtag_name", "") for t in aweme.get("text_extra", []) if t.get("hashtag_name")],
            }
        except Exception:
            return None

    def _try_api_search(self, params, keyword):
        """尝试通过API接口搜索"""
        videos = []
        try:
            # 需要a_bogus参数，这里做简化尝试
            api_url = "https://www.douyin.com/aweme/v1/web/general/search/single/"
            resp = self.session.get(api_url, params=params, timeout=15)
            
            if resp.status_code == 200:
                data = resp.json()
                items = data.get("data", [])
                for item in items:
                    aweme = item.get("aweme_info")
                    if aweme:
                        v = self._parse_aweme(aweme)
                        if v:
                            videos.append(v)
        except Exception as e:
            print(f"  API搜索异常: {e}")
        
        return videos

    def _crawl_mobile_search(self, keyword, count):
        """通过移动端页面爬取"""
        videos = []
        try:
            url = f"https://www.douyin.com/search/{quote(keyword)}?type=video"
            headers = MOBILE_HEADERS.copy()
            if self.session.headers.get("Cookie"):
                headers["Cookie"] = self.session.headers["Cookie"]
            
            resp = requests.get(url, headers=headers, timeout=15)
            ssr_data = self._extract_ssr_data(resp.text)
            if ssr_data:
                videos = self._parse_ssr_videos(ssr_data, keyword)[:count]
        except Exception as e:
            print(f"  移动端爬取异常: {e}")
        
        return videos

    def crawl_topic(self, topic, count=20):
        """爬取指定话题下的视频"""
        print(f"🏷️ 爬取话题: #{topic}")
        # 话题页URL
        url = f"https://www.douyin.com/hashtag/{quote(topic)}"
        
        videos = []
        try:
            resp = self.session.get(url, timeout=15)
            ssr_data = self._extract_ssr_data(resp.text)
            if ssr_data:
                # 话题页数据结构不同
                challenge_data = ssr_data.get("challenge", {})
                items = challenge_data.get("aweme_list", [])
                for item in items:
                    v = self._parse_aweme(item)
                    if v:
                        v["tags"] = v.get("tags", []) + [topic]
                        videos.append(v)
        except Exception as e:
            print(f"❌ 话题爬取失败: {e}")
        
        # 如果话题页没数据，退回搜索
        if not videos:
            print("  话题页无数据，使用搜索替代...")
            videos = self.search_videos(topic, count)

        self.videos = videos[:count]
        print(f"📦 获取 {len(self.videos)} 个视频")
        return self.videos

    def _format_duration(self, ms):
        """格式化时长"""
        if not ms:
            return ""
        try:
            ms = int(ms)
            if ms > 100000:  # 可能是秒
                ms = ms
            s = ms // 1000 if ms > 1000 else ms
            m = s // 60
            s = s % 60
            return f"{m:02d}:{s:02d}"
        except:
            return ""

    def _format_timestamp(self, ts):
        """格式化时间戳"""
        if not ts:
            return ""
        try:
            from datetime import datetime
            return datetime.fromtimestamp(int(ts)).isoformat()
        except:
            return ""

    def save_results(self, filepath=None):
        """保存结果到JSON"""
        filepath = filepath or OUTPUT_FILE
        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(self.videos, f, ensure_ascii=False, indent=2)
        print(f"💾 结果已保存到: {filepath}")
        return filepath

    def print_summary(self):
        """打印汇总"""
        if not self.videos:
            print("没有获取到视频")
            return
        
        print("\n" + "=" * 60)
        print(f"📊 爬取结果汇总 ({len(self.videos)} 个视频)")
        print("=" * 60)
        
        # 按点赞排序展示前10
        sorted_videos = sorted(self.videos, key=lambda x: x.get("likes", 0), reverse=True)
        for i, v in enumerate(sorted_videos[:10], 1):
            print(f"\n  #{i} {v['title'][:40]}...")
            print(f"     作者: {v['author']} | 点赞: {v.get('likes', 0):,} | 评论: {v.get('comments', 0):,}")
            print(f"     链接: {v.get('url', '')}")
        
        if len(self.videos) > 10:
            print(f"\n  ... 还有 {len(self.videos) - 10} 个视频")
        
        print("\n" + "=" * 60)

    def export_for_workbench(self):
        """导出为工作台兼容格式"""
        export_data = []
        for v in self.videos:
            export_data.append({
                "title": v.get("title", ""),
                "author": v.get("author", ""),
                "url": v.get("url", ""),
                "cover": v.get("cover", ""),
                "duration": v.get("duration", ""),
                "likes": v.get("likes", 0),
                "comments": v.get("comments", 0),
                "shares": v.get("shares", 0),
                "views": v.get("views", 0),
                "favorites": v.get("favorites", 0),
                "publishedAt": v.get("publishedAt", ""),
                "tags": v.get("tags", []),
            })
        return export_data


def setup_cookie():
    """交互式设置Cookie"""
    print("\n" + "=" * 60)
    print("🔧 Cookie 设置指南")
    print("=" * 60)
    print("""
  获取Cookie步骤：
  1. 打开浏览器访问 https://www.douyin.com 并登录
  2. 按 F12 打开开发者工具
  3. 切换到 Network (网络) 标签
  4. 刷新页面
  5. 点击任意请求，找到 Request Headers
  6. 复制 Cookie 字段的完整值
  7. 粘贴到下方

  ⚠️ Cookie有时效性，过期后需要重新获取
  ⚠️ Cookie包含敏感信息，请勿泄露给他人
""")
    cookie = input("请粘贴Cookie (直接回车跳过): ").strip()
    if cookie:
        # 保存到配置文件
        config_file = DATA_DIR / "crawler_config.json"
        with open(config_file, "w", encoding="utf-8") as f:
            json.dump({"cookie": cookie}, f)
        print(f"✅ Cookie已保存到 {config_file}")
        return cookie
    return ""


def load_cookie():
    """从配置文件加载Cookie"""
    config_file = DATA_DIR / "crawler_config.json"
    if config_file.exists():
        with open(config_file, "r", encoding="utf-8") as f:
            config = json.load(f)
            return config.get("cookie", "")
    return ""


def generate_demo_data():
    """生成演示数据（当爬虫无法工作时使用）"""
    demo_videos = [
        {
            "title": "一个人的独居日记｜第30天 做了顿大餐犒劳自己",
            "author": "小林的日常",
            "url": "https://www.douyin.com/video/demo1",
            "cover": "",
            "duration": "02:35",
            "likes": 156000,
            "comments": 3200,
            "shares": 8900,
            "views": 1200000,
            "favorites": 45000,
            "publishedAt": "2026-07-28T18:00:00",
            "tags": ["vlog日常", "独居生活", "一人食"],
        },
        {
            "title": "早起vlog｜5点起床的一天，把时间还给自己",
            "author": "早起的小兔子",
            "url": "https://www.douyin.com/video/demo2",
            "cover": "",
            "duration": "03:12",
            "likes": 234000,
            "comments": 5600,
            "shares": 12000,
            "views": 2100000,
            "favorites": 78000,
            "publishedAt": "2026-07-27T06:00:00",
            "tags": ["早起vlog", "自律", "生活记录"],
        },
        {
            "title": "下班后的两小时｜打工人的自我疗愈时刻",
            "author": "治愈系生活家",
            "url": "https://www.douyin.com/video/demo3",
            "cover": "",
            "duration": "01:58",
            "likes": 89000,
            "comments": 2100,
            "shares": 5600,
            "views": 680000,
            "favorites": 32000,
            "publishedAt": "2026-07-26T20:30:00",
            "tags": ["下班日常", "独居vlog", "治愈"],
        },
        {
            "title": "花100块过一周挑战 day1｜穷开心才是真开心",
            "author": "省钱小能手",
            "url": "https://www.douyin.com/video/demo4",
            "cover": "",
            "duration": "04:20",
            "likes": 432000,
            "comments": 12000,
            "shares": 28000,
            "views": 3500000,
            "favorites": 156000,
            "publishedAt": "2026-07-25T12:00:00",
            "tags": ["挑战", "省钱", "vlog日常", "生活记录"],
        },
        {
            "title": "周末独处日记｜一个人逛超市的快乐你不懂",
            "author": "独处美学",
            "url": "https://www.douyin.com/video/demo5",
            "cover": "",
            "duration": "02:45",
            "likes": 178000,
            "comments": 4300,
            "shares": 9200,
            "views": 1500000,
            "favorites": 67000,
            "publishedAt": "2026-07-24T15:30:00",
            "tags": ["周末日常", "独处", "vlog"],
        },
        {
            "title": "我的一天｜从晨跑开始的能量满格vlog",
            "author": "元气满满日记",
            "url": "https://www.douyin.com/video/demo6",
            "cover": "",
            "duration": "03:30",
            "likes": 267000,
            "comments": 6700,
            "shares": 15000,
            "views": 2400000,
            "favorites": 89000,
            "publishedAt": "2026-07-23T07:00:00",
            "tags": ["晨跑", "自律vlog", "生活记录", "正能量"],
        },
        {
            "title": "搬家后第一天｜把出租屋变成家的过程太治愈了",
            "author": "改造日记",
            "url": "https://www.douyin.com/video/demo7",
            "cover": "",
            "duration": "05:15",
            "likes": 345000,
            "comments": 9800,
            "shares": 22000,
            "views": 2800000,
            "favorites": 134000,
            "publishedAt": "2026-07-22T19:00:00",
            "tags": ["出租屋改造", "搬家vlog", "独居生活"],
        },
        {
            "title": "一个人的旅行vlog｜说走就走的周末出逃",
            "author": "独自远行",
            "url": "https://www.douyin.com/video/demo8",
            "cover": "",
            "duration": "06:42",
            "likes": 512000,
            "comments": 15000,
            "shares": 35000,
            "views": 4200000,
            "favorites": 201000,
            "publishedAt": "2026-07-21T10:00:00",
            "tags": ["独自旅行", "周末出行", "vlog", "生活记录"],
        },
        {
            "title": "深夜厨房｜下班后给自己做一碗热汤面",
            "author": "深夜食堂日记",
            "url": "https://www.douyin.com/video/demo9",
            "cover": "",
            "duration": "02:10",
            "likes": 134000,
            "comments": 3400,
            "shares": 7800,
            "views": 980000,
            "favorites": 43000,
            "publishedAt": "2026-07-20T22:00:00",
            "tags": ["深夜食堂", "一人食", "治愈vlog"],
        },
        {
            "title": "断舍离vlog｜清理房间也清理了心情",
            "author": "极简生活家",
            "url": "https://www.douyin.com/video/demo10",
            "cover": "",
            "duration": "03:55",
            "likes": 198000,
            "comments": 5200,
            "shares": 11000,
            "views": 1700000,
            "favorites": 72000,
            "publishedAt": "2026-07-19T14:00:00",
            "tags": ["断舍离", "极简生活", "vlog日常"],
        },
    ]
    
    print("📋 生成演示数据（模拟抖音热门vlog视频）...")
    return demo_videos


def main():
    parser = argparse.ArgumentParser(
        description="抖音自拍vlog · 生活记录 热门视频爬虫",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
使用示例:
  # 搜索爬取
  python3 crawler.py --keyword "自拍vlog 生活记录" --count 20

  # 话题爬取
  python3 crawler.py --topic "生活记录" --count 15

  # 设置Cookie
  python3 crawler.py --setup-cookie

  # 生成演示数据（无需爬取）
  python3 crawler.py --demo

  # 查看结果
  python3 crawler.py --show
        """,
    )
    
    parser.add_argument("--keyword", "-k", type=str, default="自拍vlog 生活记录 日常", help="搜索关键词")
    parser.add_argument("--topic", "-t", type=str, help="话题/标签名称")
    parser.add_argument("--count", "-n", type=int, default=20, help="爬取数量 (默认20)")
    parser.add_argument("--sort", "-s", type=str, default="likes", choices=["likes", "newest", "comments"], help="排序方式")
    parser.add_argument("--cookie", "-c", type=str, help="直接提供Cookie")
    parser.add_argument("--setup-cookie", action="store_true", help="交互式设置Cookie")
    parser.add_argument("--demo", action="store_true", help="生成演示数据")
    parser.add_argument("--show", action="store_true", help="显示已爬取的结果")
    parser.add_argument("--output", "-o", type=str, help="输出文件路径")

    args = parser.parse_args()

    # 设置Cookie
    if args.setup_cookie:
        setup_cookie()
        return

    # 显示已有结果
    if args.show:
        if OUTPUT_FILE.exists():
            with open(OUTPUT_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
            print(f"📊 已保存 {len(data)} 个视频:")
            for i, v in enumerate(data[:20], 1):
                print(f"  {i}. {v.get('title', '')[:50]} | ❤️ {v.get('likes', 0):,} | 👤 {v.get('author', '')}")
        else:
            print("❌ 还没有爬取结果")
        return

    # 生成演示数据
    if args.demo:
        print("🎲 生成演示数据模式")
        demo = generate_demo_data()
        output_file = Path(args.output) if args.output else OUTPUT_FILE
        with open(output_file, "w", encoding="utf-8") as f:
            json.dump(demo, f, ensure_ascii=False, indent=2)
        print(f"💾 演示数据已保存到: {output_file}")
        print(f"📦 共 {len(demo)} 个视频")
        print(f"\n💡 接下来:")
        print(f"  1. 在工作台 trending.html 页面点击「爬取视频」")
        print(f"  2. 点击「导入已爬取数据」")
        print(f"  3. 复制 {output_file} 的内容粘贴进去")
        return

    # 正式爬取
    print("\n" + "=" * 60)
    print("🕷️ 抖音vlog热门视频爬虫")
    print("=" * 60)

    # 获取Cookie
    cookie = args.cookie or load_cookie()
    if not cookie:
        print("\n⚠️  未检测到Cookie！")
        print("   抖音需要Cookie才能正常爬取。")
        print("   运行 `python3 crawler.py --setup-cookie` 设置Cookie")
        print("   或者运行 `python3 crawler.py --demo` 使用演示数据\n")
        
        # 询问是否使用演示数据
        choice = input("是否生成演示数据？(y/n): ").strip().lower()
        if choice == 'y':
            demo = generate_demo_data()
            output_file = Path(args.output) if args.output else OUTPUT_FILE
            with open(output_file, "w", encoding="utf-8") as f:
                json.dump(demo, f, ensure_ascii=False, indent=2)
            print(f"💾 演示数据已保存到: {output_file}")
        return

    # 创建爬虫
    crawler = DouyinCrawler(cookie=cookie)

    # 排序映射
    sort_map = {"likes": 2, "newest": 1, "comments": 0}
    sort_type = sort_map.get(args.sort, 0)

    # 执行爬取
    if args.topic:
        crawler.crawl_topic(args.topic, args.count)
    else:
        crawler.search_videos(args.keyword, args.count, sort_type)

    # 保存结果
    output_file = Path(args.output) if args.output else OUTPUT_FILE
    crawler.save_results(output_file)

    # 打印汇总
    crawler.print_summary()

    # 提示下一步
    print("\n💡 接下来:")
    print(f"  1. 打开 trending.html 页面")
    print(f"  2. 点击「爬取视频」→「导入已爬取数据」")
    print(f"  3. 复制 {output_file} 的内容粘贴进去")


if __name__ == "__main__":
    main()
