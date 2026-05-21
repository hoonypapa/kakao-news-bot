import datetime
import html
import json
import os
import re
import time

import feedparser
import requests

KAKAO_TOKEN_URL = "https://kauth.kakao.com/oauth/token"
KAKAO_MEMO_URL = "https://kapi.kakao.com/v2/api/talk/memo/default/send"

# 주제별로 각각 한 통씩 카카오톡 메시지를 보냅니다.
# header: 메시지 제목, feeds: RSS 주소(여러 개 가능), button_url: 하단 버튼 링크
# (링크가 모바일에서 열리려면 해당 도메인이 카카오 콘솔 '웹 도메인'에 등록돼 있어야 함)
TOPICS = [
    {
        "header": "🤖 오늘의 AI 뉴스",
        "feeds": [
            "https://www.aitimes.com/rss/allArticle.xml",  # AI타임스
            "https://www.aitimes.kr/rss/allArticle.xml",   # 인공지능신문
        ],
        "button_url": "https://www.aitimes.com",
    },
    {
        "header": "💰 오늘의 경제 뉴스",
        "feeds": [
            "https://www.yna.co.kr/rss/economy.xml",  # 연합뉴스 경제
        ],
        "button_url": "https://www.yna.co.kr/economy/all",
    },
]

# 리스트 항목에 썸네일이 없을 때 사용할 기본 이미지. 본인 이미지 주소로 바꿔도 됩니다.
DEFAULT_IMAGE_URL = "https://dummyimage.com/400x200/2b6cb0/ffffff.png&text=NEWS"


def get_access_token(rest_api_key, refresh_token, client_secret=None):
    data = {
        "grant_type": "refresh_token",
        "client_id": rest_api_key,
        "refresh_token": refresh_token,
    }
    if client_secret:
        data["client_secret"] = client_secret
    resp = requests.post(KAKAO_TOKEN_URL, data=data, timeout=10)
    resp.raise_for_status()
    data = resp.json()
    # refresh_token은 만료가 1개월 미만으로 남으면 새로 발급됩니다.
    # 그 경우 아래 값을 GitHub Secret(KAKAO_REFRESH_TOKEN)에 갱신해주세요.
    if "refresh_token" in data:
        print("[알림] 새 refresh_token 발급됨 -> GitHub Secret을 갱신하세요:")
        print(data["refresh_token"])
    return data["access_token"]


def clean(text, limit):
    text = re.sub(r"<[^>]+>", "", text or "")
    text = html.unescape(text).strip()
    text = re.sub(r"\s+", " ", text)
    if len(text) > limit:
        text = text[: limit - 1] + "…"
    return text


def extract_image(entry, fallback):
    # RSS 항목에서 썸네일을 최대한 찾아보고, 없으면 기본 이미지 사용
    media = getattr(entry, "media_thumbnail", None) or getattr(entry, "media_content", None)
    if media and isinstance(media, list) and media and media[0].get("url"):
        return media[0]["url"]
    for link in getattr(entry, "links", []) or []:
        if link.get("rel") == "enclosure" and str(link.get("type", "")).startswith("image"):
            return link.get("href")
    return fallback


def fetch_news(feeds, per_feed, fallback_image):
    items = []
    seen = set()
    for url in feeds:
        parsed = feedparser.parse(url)
        for entry in parsed.entries[:per_feed]:
            link = getattr(entry, "link", "")
            if not link or link in seen:
                continue
            seen.add(link)
            items.append(
                {
                    "title": clean(getattr(entry, "title", ""), 60),
                    "summary": clean(getattr(entry, "summary", ""), 80),
                    "link": link,
                    "image": extract_image(entry, fallback_image),
                }
            )
    return items


def send_list(access_token, items, header_title, button_url):
    today = datetime.datetime.now().strftime("%m/%d")
    contents = [
        {
            "title": it["title"],
            "description": it["summary"],
            "image_url": it["image"],
            "image_width": 400,
            "image_height": 200,
            "link": {"web_url": it["link"], "mobile_web_url": it["link"]},
        }
        for it in items
    ]
    template = {
        "object_type": "list",
        "header_title": f"{header_title} ({today})",
        "header_link": {
            "web_url": items[0]["link"],
            "mobile_web_url": items[0]["link"],
        },
        "contents": contents,
        "buttons": [
            {
                "title": "전체 뉴스 보기",
                "link": {
                    "web_url": button_url,
                    "mobile_web_url": button_url,
                },
            }
        ],
    }
    resp = requests.post(
        KAKAO_MEMO_URL,
        headers={"Authorization": f"Bearer {access_token}"},
        data={"template_object": json.dumps(template, ensure_ascii=False)},
        timeout=10,
    )
    if resp.status_code != 200:
        print("[오류] 카카오 응답:", resp.status_code, resp.text)
    resp.raise_for_status()
    return resp.json()


def main():
    rest_api_key = os.environ["KAKAO_REST_API_KEY"]
    refresh_token = os.environ["KAKAO_REFRESH_TOKEN"]
    client_secret = os.environ.get("KAKAO_CLIENT_SECRET")
    per_feed = int(os.environ.get("PER_FEED") or "5")
    list_max = int(os.environ.get("LIST_MAX") or "5")
    fallback_image = os.environ.get("DEFAULT_IMAGE_URL") or DEFAULT_IMAGE_URL

    token = get_access_token(rest_api_key, refresh_token, client_secret)
    for topic in TOPICS:
        items = fetch_news(topic["feeds"], per_feed, fallback_image)[:list_max]
        if not items:
            print(f"[{topic['header']}] 가져온 뉴스가 없습니다.")
            continue
        send_list(token, items, topic["header"], topic["button_url"])
        print(f"[{topic['header']}] 전송 완료: {len(items)}건")
        for it in items:
            print("  -", it["title"])
        time.sleep(0.5)


if __name__ == "__main__":
    main()
