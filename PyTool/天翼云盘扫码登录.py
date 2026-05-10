#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
天翼云盘扫码登录工具

扫码登录流程:
  Step 1: 获取登录页面参数 (unifyLoginForPC)
  Step 2: 获取二维码UUID
  Step 3: 生成二维码
  Step 4: 轮询扫码状态
  Step 5: 用redirectUrl交换Session
  Step 6: 获取Open API AccessToken
"""

import requests
import re
import json
import time
import uuid
import os
import random
from urllib.parse import quote, urlparse, urlencode, unquote

APP_BASE_URL = "https://api.cloud.189.cn"
WEB_BASE_URL = "https://cloud.189.cn/api"
AUTH_BASE_URL = "https://open.e.189.cn"

APP_CLIENT_TYPE = "TELEPC"
APP_VERSION = "6.2"
APP_CHANNEL_ID = "web_cloud.189.cn"
APP_USER_AGENT = "desktop"
APP_ID = "8025431004"
APP_CLIENT_TYPE_NUM = "10020"
APP_RETURN_URL = "https://m.cloud.189.cn/zhuanti/2020/loginErrorPc/index.html"

BROWSER_UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/147.0.0.0 Safari/537.36 Edg/147.0.0.0"

CONFIG_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "cloud189_session.json")


def save_session(session_data):
    try:
        with open(CONFIG_FILE, 'w', encoding='utf-8') as f:
            json.dump(session_data, f, ensure_ascii=False, indent=2)
        return True
    except Exception:
        return False


def client_suffix():
    return {
        'clientType': APP_CLIENT_TYPE,
        'version': APP_VERSION,
        'channelId': APP_CHANNEL_ID,
        'rand': f"{random.randint(1, 99999)}_{random.randint(1, 9999999999)}",
    }


def qr_login():
    """
    返回: dict with sessionKey, sessionSecret, accessToken, cookieLoginUser, sson
    """
    print("\n" + "=" * 60)
    print("       天翼云盘扫码登录")
    print("=" * 60)

    s = requests.Session()
    s.headers.update({
        'User-Agent': BROWSER_UA,
        'Accept': '*/*',
        'Accept-Language': 'zh-CN,zh;q=0.9,en;q=0.8',
    })

    # Step 1: 访问unifyLoginForPC获取登录页面参数
    print("\n[Step 1] 获取登录页面参数 (unifyLoginForPC)...")
    lt = ""
    req_id = ""
    param_id = ""
    captcha_token = ""
    login_page_url = ""

    try:
        login_entry_url = f"{WEB_BASE_URL}/portal/unifyLoginForPC.action"
        params = {
            'appId': APP_ID,
            'clientType': APP_CLIENT_TYPE_NUM,
            'returnURL': APP_RETURN_URL,
            'timeStamp': str(int(time.time() * 1000)),
        }
        print(f"    访问: {login_entry_url}")
        resp = s.get(login_entry_url, params=params, timeout=30)
        html = resp.text

        lt_matches = re.findall(r'lt\s*=\s*"([A-F0-9]{16,})"', html)
        if lt_matches:
            lt = lt_matches[0]
        param_id_matches = re.findall(r'paramId\s*=\s*"([^"]+)"', html)
        if param_id_matches:
            param_id = param_id_matches[0]
        req_id_matches = re.findall(r'reqId\s*=\s*"([^"]+)"', html)
        if req_id_matches:
            req_id = req_id_matches[0]
        captcha_matches = re.findall(r"'captchaToken'\s+value='([^']+)'", html)
        if captcha_matches:
            captcha_token = captcha_matches[0]

        login_page_url = resp.url
    except Exception as e:
        print(f"[-] 访问unifyLoginForPC失败: {e}")

    if not lt:
        print("[*] 方式1未获取到lt，尝试方式2...")
        try:
            login_page_url = f"{AUTH_BASE_URL}/api/logbox/separate/web/index.html?appId={APP_ID}"
            resp = s.get(login_page_url, timeout=30)
            current_url = resp.url
            parsed = urlparse(current_url)
            qs_params = dict([p.split('=', 1) for p in parsed.query.split('&') if '=' in p])
            lt = qs_params.get('lt', '')
            req_id = qs_params.get('reqId', '')
            login_page_url = current_url
        except Exception as e:
            print(f"[-] 方式2也失败: {e}")

    if not req_id:
        req_id = uuid.uuid4().hex[:32]

    if not login_page_url:
        login_page_url = f"{AUTH_BASE_URL}/api/logbox/separate/web/index.html?appId={APP_ID}"

    user_finger = str(random.randint(1000000000, 9999999999))

    print(f"    lt: {lt[:40]}..." if len(lt) > 40 else f"    lt: {lt}")
    print(f"    reqId: {req_id}")
    print(f"    paramId: {param_id[:40]}..." if len(param_id) > 40 else f"    paramId: {param_id}")

    # Step 2: 获取二维码UUID
    print("\n[Step 2] 获取二维码UUID...")
    uuid_url = f"{AUTH_BASE_URL}/api/logbox/oauth2/getUUID.do"

    uuid_headers = {
        'Content-Type': 'application/x-www-form-urlencoded',
        'Origin': AUTH_BASE_URL,
        'Referer': login_page_url,
        'user-finger': user_finger,
    }
    if lt:
        uuid_headers['lt'] = lt
    if req_id:
        uuid_headers['reqid'] = req_id

    try:
        resp = s.post(uuid_url, data={'appId': APP_ID}, headers=uuid_headers, timeout=30)
        uuid_data = resp.json()
        print(f"    UUID响应: {json.dumps(uuid_data, ensure_ascii=False)[:300]}")
    except Exception as e:
        print(f"[-] 获取UUID失败: {e}")
        return None

    qr_url = uuid_data.get('uuid', '')
    encryuuid = uuid_data.get('encryuuid', '')
    encodeuuid = uuid_data.get('encodeuuid', '')

    if not qr_url:
        print("[-] UUID为空")
        return None

    print(f"    二维码URL: {qr_url}")
    print(f"    encryuuid: {encryuuid[:40]}..." if len(encryuuid) > 40 else f"    encryuuid: {encryuuid}")

    # Step 3: 生成二维码
    print("\n[Step 3] 生成二维码...")

    print(f"\n    请使用天翼云盘APP扫描以下二维码:")
    print()

    try:
        import qrcode
        qr = qrcode.QRCode(
            box_size=1,
            border=1,
        )
        qr.add_data(qr_url)
        qr.make(fit=True)
        qr.print_ascii(invert=True)
    except ImportError:
        print("    [提示] 安装 qrcode 库可在终端显示二维码: pip install qrcode")

    print()
    print(f"    如果二维码无法扫描，请在浏览器打开:")
    print(f"    {qr_url}")
    print()

    # Step 4: 轮询扫码状态
    print("[Step 4] 等待扫码...")

    poll_headers = {
        'Content-Type': 'application/x-www-form-urlencoded',
        'Origin': AUTH_BASE_URL,
        'Referer': login_page_url,
        'user-finger': user_finger,
    }
    if lt:
        poll_headers['lt'] = lt
    if req_id:
        poll_headers['reqid'] = req_id

    redirect_url = ""
    max_poll = 60
    for i in range(max_poll):
        now = time.time()

        poll_data = {
            'appId': APP_ID,
            'clientType': APP_CLIENT_TYPE_NUM,
            'returnUrl': APP_RETURN_URL,
            'paramId': param_id,
            'uuid': qr_url,
            'encryuuid': encryuuid,
            'date': time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(now)),
            'timeStamp': str(int(now * 1000)),
        }

        try:
            resp = s.post(
                f"{AUTH_BASE_URL}/api/logbox/oauth2/qrcodeLoginState.do",
                data=poll_data,
                headers=poll_headers,
                timeout=30
            )
            result_text = resp.text.strip()

            if not result_text:
                print(f"\r    等待扫码... ({i+1}/{max_poll})", end='', flush=True)
                time.sleep(3)
                continue

            print(f"\r    [调试] 响应({len(result_text)}字节): {result_text[:150]}...        ", end='', flush=True)

            try:
                result_json = json.loads(result_text)
            except (json.JSONDecodeError, ValueError):
                if result_text == '0':
                    print(f"\n[✓] 二维码已扫描，请在手机上确认登录!")
                elif result_text == '1':
                    print(f"\n[✓] 登录已确认!")
                    break
                else:
                    print(f"\r    等待扫码... ({i+1}/{max_poll})", end='', flush=True)
                time.sleep(3)
                continue

            if not isinstance(result_json, dict):
                time.sleep(3)
                continue

            status = result_json.get('status', None)
            msg = result_json.get('msg', '')

            redirect_url = result_json.get('redirectUrl', '') or result_json.get('toUrl', '')

            if status == 0 and redirect_url:
                print(f"\n[✓] 扫码登录成功!")
                break
            elif status == -106 or status == -1:
                print(f"\r    等待扫码... ({i+1}/{max_poll})", end='', flush=True)
            elif status == -11002:
                print(f"\r    已扫码，等待确认... ({i+1}/{max_poll})   ", end='', flush=True)
            elif status == -11001:
                print(f"\n[-] 二维码已过期，请重新运行程序")
                return None
            elif status == 0:
                print(f"\n[✓] 登录已确认!")
                break
            elif redirect_url:
                print(f"\n[✓] 扫码登录成功! (检测到redirectUrl)")
                break
            else:
                print(f"\r    等待扫码... ({i+1}/{max_poll}) status={status}", end='', flush=True)

        except Exception as e:
            print(f"\n[!] 轮询异常: {e}")

        time.sleep(3)

    if i >= max_poll - 1:
        print("\n[-] 扫码超时")
        return None

    # Step 5: exchangeSession - 用redirectUrl换取SessionKey/Secret
    session_key = ""
    session_secret = ""
    access_token = ""
    refresh_token = ""

    if redirect_url:
        print(f"\n[Step 5] 用redirectUrl交换Session (exchangeSession)...")
        print(f"    redirectUrl: {redirect_url[:120]}...")

        try:
            q_params = client_suffix()
            q_params['redirectURL'] = redirect_url

            resp = requests.post(
                f"{APP_BASE_URL}/getSessionForPC.action",
                params=q_params,
                headers={
                    'Accept': 'application/json;charset=UTF-8',
                    'User-Agent': APP_USER_AGENT,
                    'X-Request-ID': str(uuid.uuid4()),
                },
                timeout=30
            )

            print(f"    状态码: {resp.status_code}")
            print(f"    响应体: {resp.text[:500]}")

            if resp.status_code == 200:
                try:
                    data = resp.json()
                    session_key = data.get('sessionKey', '')
                    session_secret = data.get('sessionSecret', '')
                    access_token = data.get('accessToken', '')
                    refresh_token = data.get('refreshToken', '')

                    if session_key and session_secret:
                        print(f"[✓] exchangeSession成功! (query参数方式)")
                        print(f"    SessionKey: {session_key}")
                        print(f"    SessionSecret: {session_secret[:30]}...")
                except Exception as e:
                    print(f"    JSON解析失败: {e}")
        except Exception as e:
            print(f"[-] 方式1异常: {e}")

        if not session_key or not session_secret:
            try:
                body_params = {
                    'redirectURL': redirect_url,
                    'clientType': APP_CLIENT_TYPE,
                    'version': APP_VERSION,
                    'channelId': APP_CHANNEL_ID,
                    'rand': str(int(time.time() * 1000)),
                }

                resp = requests.post(
                    f"{APP_BASE_URL}/getSessionForPC.action",
                    data=urlencode(body_params),
                    headers={
                        'Accept': 'application/json;charset=UTF-8',
                        'Content-Type': 'application/x-www-form-urlencoded',
                        'User-Agent': APP_USER_AGENT,
                        'X-Request-ID': str(uuid.uuid4()),
                    },
                    timeout=30
                )

                print(f"    状态码: {resp.status_code}")
                print(f"    响应体: {resp.text[:500]}")

                if resp.status_code == 200:
                    try:
                        data = resp.json()
                        sk = data.get('sessionKey', '')
                        ss = data.get('sessionSecret', '')

                        if sk and ss:
                            session_key = sk
                            session_secret = ss
                            if not access_token:
                                access_token = data.get('accessToken', '')
                            if not refresh_token:
                                refresh_token = data.get('refreshToken', '')
                            print(f"[✓] exchangeSession成功! (POST body方式)")
                            print(f"    SessionKey: {session_key}")
                            print(f"    SessionSecret: {session_secret[:30]}...")
                    except Exception as e:
                        print(f"    JSON解析失败: {e}")
            except Exception as e:
                print(f"[-] 方式2异常: {e}")

    # Step 6: 通过sessionKey获取Open API AccessToken
    open_access_token = ""

    if session_key:
        print(f"\n[Step 6] 获取Open API AccessToken (getAccessTokenBySsKey)...")
        try:
            token_url = f"{WEB_BASE_URL}/open/oauth2/getAccessTokenBySsKey.action"
            resp = s.get(token_url, params={
                'noCache': str(random.random()),
                'sessionKey': session_key,
            }, headers={
                'appkey': '600100422',
                'Accept': 'application/json;charset=UTF-8',
                'Referer': 'https://cloud.189.cn/web/main/file/folder/-11',
            }, timeout=30)

            token_data = resp.json()
            open_access_token = token_data.get('accessToken', '')

            if open_access_token:
                print(f"[✓] Open API AccessToken: {open_access_token[:30]}...")
            else:
                res_msg = token_data.get('res_message', '') or json.dumps(token_data, ensure_ascii=False)
                print(f"[-] 获取Open API AccessToken失败: {res_msg}")
        except Exception as e:
            print(f"[-] getAccessTokenBySsKey异常: {e}")

    if not open_access_token and access_token:
        open_access_token = access_token
        print(f"[*] 使用App AccessToken作为备用 (可能不支持Open API)")

    cookie_login_user = ""
    sson = ""

    # Step 7: 如果exchangeSession失败，尝试其他方式获取Session
    web_session_key = ""

    if not session_key or not session_secret:
        print(f"\n[Step 7] exchangeSession未成功，尝试其他方式...")

        # 获取用户信息中的sessionKey
        try:
            user_info_url = f"{WEB_BASE_URL}/portal/v2/getUserBriefInfo.action"
            resp = s.get(user_info_url, params={
                'noCache': str(random.random()),
            }, headers={
                'Accept': 'application/json;charset=UTF-8',
                'Referer': 'https://cloud.189.cn/web/main/file/folder/-11',
            }, timeout=30)

            user_data = resp.json()
            web_session_key = user_data.get('sessionKey', '')

            if web_session_key:
                print(f"[✓] webSessionKey: {web_session_key}")
        except Exception as e:
            print(f"[-] 获取用户信息失败: {e}")

        # 用webSessionKey获取AccessToken
        import hashlib
        if web_session_key and not access_token:
            try:
                token_url = f"{WEB_BASE_URL}/open/oauth2/getAccessTokenBySsKey.action"
                timestamp = str(int(time.time() * 1000))
                sign_data = f"600100422{timestamp}1"
                signature = hashlib.md5(sign_data.encode()).hexdigest()

                resp = s.get(token_url, params={
                    'noCache': str(random.random()),
                    'sessionKey': web_session_key,
                }, headers={
                    'Accept': 'application/json;charset=UTF-8',
                    'appkey': '600100422',
                    'sign-type': '1',
                    'signature': signature,
                    'timestamp': timestamp,
                    'Referer': 'https://cloud.189.cn/web/main/file/folder/-11',
                }, timeout=30)

                token_data = resp.json()
                access_token = token_data.get('accessToken', '')

                if access_token:
                    print(f"[✓] AccessToken: {access_token}")
            except Exception as e:
                print(f"[-] 获取AccessToken失败: {e}")

        # 尝试用AccessToken获取Session
        if access_token:
            try:
                print(f"    尝试RefreshSession (GET + query参数)...")
                q_params = client_suffix()
                q_params['appId'] = APP_ID
                q_params['accessToken'] = access_token

                resp = requests.get(
                    f"{APP_BASE_URL}/getSessionForPC.action",
                    params=q_params,
                    headers={
                        'Accept': 'application/json;charset=UTF-8',
                        'User-Agent': APP_USER_AGENT,
                        'X-Request-ID': str(uuid.uuid4()),
                    },
                    timeout=30
                )

                print(f"    响应: {resp.text[:300]}")

                data = resp.json()
                sk = data.get('sessionKey', '')
                ss = data.get('sessionSecret', '')

                if sk and ss:
                    session_key = sk
                    session_secret = ss
                    print(f"[✓] SessionKey: {session_key}")
                    print(f"[✓] SessionSecret: {session_secret[:30]}...")
            except Exception as e:
                print(f"    RefreshSession异常: {e}")

    session_data = {
        'sessionKey': session_key,
        'sessionSecret': session_secret,
        'accessToken': open_access_token or access_token,
        'appAccessToken': access_token,
        'openAccessToken': open_access_token,
        'refreshToken': refresh_token,
        'cookieLoginUser': cookie_login_user,
        'sson': sson,
        'webSessionKey': web_session_key,
        'savedAt': time.time(),
    }

    if session_key and session_secret:
        session_data['authMode'] = 'app'
        print(f"\n[✓] 登录成功! (App签名模式)")
    else:
        session_data['authMode'] = 'web'
        print(f"\n[✓] 登录成功! (Web Cookie模式 - 大文件可能不支持)")

    save_session(session_data)
    print(f"    Session已保存到 {CONFIG_FILE}")

    return session_data


if __name__ == "__main__":
    session_data = qr_login()
    
    if session_data:
        print("\n" + "=" * 60)
        print("登录信息摘要:")
        print("=" * 60)
        print(f"  SessionKey: {session_data.get('sessionKey', '')}")
        print(f"  SessionSecret: {session_data.get('sessionSecret', '')[:30]}..." if session_data.get('sessionSecret') else "  SessionSecret: (空)")
        print(f"  AccessToken: {session_data.get('accessToken', '')[:30]}..." if session_data.get('accessToken') else "  AccessToken: (空)")
        print(f"  AuthMode: {session_data.get('authMode', '')}")
        print(f"  保存文件: {CONFIG_FILE}")
        print("=" * 60)
    else:
        print("\n[-] 登录失败")
