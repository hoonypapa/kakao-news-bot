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

# 원하는 RSS 주소로 바꾸거나, GitHub의 FEEDS 변수로 덮어쓸 수 있습니다.
# (쉼표로 여러 개 지정 가능)
DEFAULT_FEEDS = [
    "https://news.google.com/rss?hl=ko&gl=KR&ceid=KR:ko",  # 구글 뉴스 한국 주요뉴스
]

# 리스트 항목에 썸네일이 없을 때 사용할 기본 이미지. 본인 이미지 주소로 바꿔도 됩니다.
DEFAULT_IMAGE_URL = "https://dummyimage.com/400x200/2b6cb0/ffffff.png&text=NEWS"


def get_access_token(rest_api_key, refresh_token):
    resp = requests.post(
        KAKAO_TOKEN_URL,
        data={
            "grant_type": "refresh_token",
            "client_id": rest_api_key,
            "refresh_token": refresh_token,
        },
        timeout=10,
    )
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


def send_list(access_token, items):
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
        "header_title": f"📰 오늘의 주요 뉴스 ({today})",
        "header_link": {
            "web_url": items[0]["link"],
            "mobile_web_url": items[0]["link"],
        },
        "contents": contents,
        "buttons": [
            {
                "title": "전체 뉴스 보기",
                "link": {
                    "web_url": "https://news.google.com/?hl=ko&gl=KR&ceid=KR:ko",
                    "mobile_web_url": "https://news.google.com/?hl=ko&gl=KR&ceid=KR:ko",
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
    feeds_env = os.environ.get("FEEDS", "").strip()
    feeds = (
        [u.strip() for u in feeds_env.split(",") if u.strip()]
        if feeds_env
        else DEFAULT_FEEDS
    )
    per_feed = int(os.environ.get("PER_FEED", "5"))
    list_max = int(os.environ.get("LIST_MAX", "5"))
    fallback_image = os.environ.get("DEFAULT_IMAGE_URL", DEFAULT_IMAGE_URL)

    token = get_access_token(rest_api_key, refresh_token)
    items = fetch_news(feeds, per_feed, fallback_image)
    if not items:
        print("가져온 뉴스가 없습니다. RSS 주소를 확인하세요.")
        return

    items = items[:list_max]  # 리스트 항목 수 제한 (카카오 상한 대응)
    send_list(token, items)
    print(f"전송 완료: {len(items)}건")
    for it in items:
        print(" -", it["title"])


if __name__ == "__main__":
    main()
