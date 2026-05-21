"""카카오 토큰 최초 발급용 (한 번만 실행).

순서:
1) 아래 URL을 브라우저에 입력해 동의 후, 주소창의 code= 값을 복사
   https://kauth.kakao.com/oauth/authorize?client_id=REST_API_KEY&redirect_uri=REDIRECT_URI&response_type=code&scope=talk_message
2) 이 스크립트를 실행해 REST API 키 / Redirect URI / code 를 입력
3) 출력된 refresh_token 을 GitHub Secret(KAKAO_REFRESH_TOKEN)에 등록
"""

import requests

KAKAO_TOKEN_URL = "https://kauth.kakao.com/oauth/token"


def main():
    rest_api_key = input("REST API 키: ").strip()
    redirect_uri = input("Redirect URI (예: https://localhost:5000): ").strip()
    code = input("인가 코드(code): ").strip()

    resp = requests.post(
        KAKAO_TOKEN_URL,
        data={
            "grant_type": "authorization_code",
            "client_id": rest_api_key,
            "redirect_uri": redirect_uri,
            "code": code,
        },
        timeout=10,
    )
    data = resp.json()
    print("\n--- 응답 ---")
    print(data)
    if "refresh_token" in data:
        print("\n[중요] 아래 refresh_token 을 GitHub Secret 'KAKAO_REFRESH_TOKEN' 에 저장하세요:\n")
        print(data["refresh_token"])


if __name__ == "__main__":
    main()
