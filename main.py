import asyncio
import json
import os
import re
import time
import urllib
import uuid
from http.cookies import SimpleCookie
from pathlib import Path
from typing import Dict, Tuple, Union
from urllib.parse import parse_qs

import ffmpeg
import httpx
import jsengine
import streamlink
from jsonpath_ng.ext import parse
from loguru import logger
from streamlink.stream import StreamIO, HTTPStream
from streamlink_cli.main import open_stream
from streamlink_cli.output import FileOutput
from streamlink_cli.streamrunner import StreamRunner
from tenacity import retry, stop_after_attempt

recording: Dict[str, Tuple[StreamIO, FileOutput]] = {}


class LiveRecoder:
    def __init__(self, config: dict, user: dict):
        self.id = user['id']
        platform = user['platform']
        name = user.get('name', self.id)
        self.flag = f'[{platform}][{name}]'

        self.interval = user.get('interval', 10)
        self.headers = user.get('headers', {'User-Agent': 'Chrome'})
        self.cookies = user.get('cookies')
        self.format = user.get('format')
        self.proxy = user.get('proxy', config.get('proxy'))
        self.output = user.get('output', config.get('output', 'output'))

        self.get_cookies()
        self.client = self.get_client()

    async def start(self):
        logger.info(f'{self.flag}正在检测直播状态')
        while True:
            try:
                await self.run()
                await asyncio.sleep(self.interval)
            except ConnectionError as error:
                if '直播检测请求协议错误' not in str(error):
                    logger.error(error)
                await self.client.aclose()
                self.client = self.get_client()
            except Exception as error:
                logger.exception(f'{self.flag}直播检测未知错误\n{repr(error)}')

    async def run(self):
        pass

    @retry(reraise=True, stop=stop_after_attempt(5))
    async def request(self, method, url, **kwargs):
        try:
            response = await self.client.request(method, url, **kwargs)
            response.raise_for_status()
            return response
        except httpx.ProtocolError as error:
            raise ConnectionError(f'{self.flag}直播检测请求协议错误\n{error}')
        except httpx.HTTPStatusError as error:
            raise ConnectionError(f'{self.flag}直播检测请求状态码错误\n{error}\n{response.text}')
        except httpx.HTTPError as error:
            raise ConnectionError(f'{self.flag}直播检测请求错误\n{repr(error)}')

    def get_client(self):
        return httpx.AsyncClient(
            http2=True,
            timeout=self.interval,
            proxies=self.proxy,
            limits=httpx.Limits(max_keepalive_connections=100, keepalive_expiry=self.interval * 2),
            headers=self.headers,
            cookies=self.cookies
        )

    def get_cookies(self):
        if self.cookies:
            cookies = SimpleCookie()
            cookies.load(self.cookies)
            self.cookies = {k: v.value for k, v in cookies.items()}

    def get_filename(self, title, format):
        live_time = time.strftime('%Y.%m.%d %H.%M.%S')
        # 文件名特殊字符转换为全角字符
        char_dict = {
            '"': '＂',
            '*': '＊',
            ':': '：',
            '<': '＜',
            '>': '＞',
            '?': '？',
            '/': '／',
            '\\': '＼',
            '|': '｜',
        }
        for half, full in char_dict.items():
            title = title.replace(half, full)
        filename = f'[{live_time}]{self.flag}{title}.{format}'
        return filename

    def get_streamlink(self, plugin_option: dict = None):
        session = streamlink.Streamlink(options={
            'stream-timeout': 180,
            'stream-segment-attempts': 20,
            'hls-playlist-reload-attempts': 20
        })
        # 添加streamlink的http相关选项
        for arg in ('proxy', 'headers', 'cookies'):
            if attr := getattr(self, arg):
                # 代理为socks5时，streamlink的代理参数需要改为socks5h，防止部分直播源获取失败
                if 'socks' in attr:
                    attr = attr.replace('://', 'h://')
                session.set_option(f'http-{arg}', attr)
        if plugin_option:
            session.set_option(**plugin_option)
        return session

    def run_record(self, stream: Union[StreamIO, HTTPStream], url, title, format):
        # 获取输出文件名
        filename = self.get_filename(title, format)
        if stream:
            logger.info(f'{self.flag}开始录制：{filename}')
            # 调用streamlink录制直播
            result = self.stream_writer(stream, url, filename)
            # 录制成功、format配置存在且不等于直播平台默认格式时运行ffmpeg封装
            if result and self.format and self.format != format:
                self.run_ffmpeg(filename, format)
            recording.pop(url, None)
            logger.info(f'{self.flag}停止录制：{filename}')
        else:
            logger.error(f'{self.flag}无可用直播源：{filename}')

    def stream_writer(self, stream, url, filename):
        logger.info(f'{self.flag}获取到直播流链接：{filename}\n{stream.url}')
        output = FileOutput(Path(f'{self.output}/{filename}'))
        try:
            stream_fd, prebuffer = open_stream(stream)
            output.open()
            recording[url] = (stream_fd, output)
            logger.info(f'{self.flag}正在录制：{filename}')
            StreamRunner(stream_fd, output, show_progress=True).run(prebuffer)
            return True
        except OSError as error:
            if 'timeout' in str(error):
                logger.warning(f'{self.flag}直播录制超时，主播可能已下播：{filename}\n{error}')
            else:
                logger.error(f'{self.flag}OS错误：{filename}\n{error}')
        except streamlink.StreamError as error:
            logger.warning(f'{self.flag}直播流错误，请检查主播是否正常开播：{filename}\n{error}')
        except streamlink.StreamlinkError as error:
            logger.exception(f'{self.flag}streamlink错误：{filename}\n{error}')
        except Exception as error:
            logger.exception(f'{self.flag}直播录制未知错误：{filename}\n{error}')
        finally:
            output.close()

    def run_ffmpeg(self, filename, format):
        logger.info(f'{self.flag}开始ffmpeg封装：{filename}')
        new_filename = filename.replace(f'.{format}', f'.{self.format}')
        ffmpeg.input(f'{self.output}/{filename}').output(
            f'{self.output}/{new_filename}',
            codec='copy',
            map_metadata='-1',
            movflags='faststart'
        ).global_args('-hide_banner').run()
        os.remove(f'{self.output}/{filename}')


class Bilibili(LiveRecoder):
    async def run(self):
        url = f'https://live.bilibili.com/{self.id}'
        if url not in recording:
            response = (await self.request(
                method='GET',
                url='https://api.live.bilibili.com/room/v1/Room/get_info',
                params={'room_id': self.id}
            )).json()
            if response['data']['live_status'] == 1:
                title = response['data']['title']
                stream = self.get_streamlink().streams(url).get('best')  # HTTPStream[flv]
                await asyncio.to_thread(self.run_record, stream, url, title, 'flv')


class Douyu(LiveRecoder):
    async def run(self):
        url = f'https://www.douyu.com/{self.id}'
        if url not in recording:
            response = (await self.request(
                method='GET',
                url=f'https://open.douyucdn.cn/api/RoomApi/room/{self.id}',
            )).json()
            if response['data']['room_status'] == '1':
                title = response['data']['room_name']
                stream = HTTPStream(
                    self.get_streamlink(),
                    await self.get_live()
                )  # HTTPStream[flv]
                await asyncio.to_thread(self.run_record, stream, url, title, 'flv')

    async def get_js(self):
        response = (await self.request(
            method='POST',
            url=f'https://www.douyu.com/swf_api/homeH5Enc?rids={self.id}'
        )).json()
        js_enc = response['data'][f'room{self.id}']
        crypto_js = (await self.request(
            method='GET',
            url='https://cdn.staticfile.org/crypto-js/4.1.1/crypto-js.min.js'
        )).text
        return jsengine.JSEngine(js_enc + crypto_js)

    async def get_live(self):
        did = uuid.uuid4().hex
        tt = str(int(time.time()))
        params = {
            'cdn': 'tct-h5',
            'did': did,
            'tt': tt,
            'rate': 0
        }
        js = await self.get_js()
        query = js.call('ub98484234', self.id, did, tt)
        params.update({k: v[0] for k, v in parse_qs(query).items()})
        response = (await self.request(
            method='POST',
            url=f'https://www.douyu.com/lapi/live/getH5Play/{self.id}',
            params=params
        )).json()
        return f"{response['data']['rtmp_url']}/{response['data']['rtmp_live']}"


class Huya(LiveRecoder):
    async def run(self):
        url = f'https://www.huya.com/{self.id}'
        if url not in recording:
            response = (await self.request(
                method='GET',
                url=url
            )).text
            if '"isOn":true' in response:
                title = re.search('"introduction":"(.*?)"', response).group(1)
                stream = self.get_streamlink().streams(url).get('best')  # HTTPStream[flv]
                await asyncio.to_thread(self.run_record, stream, url, title, 'flv')


class Douyin(LiveRecoder):
    async def run(self):
        url = f'https://live.douyin.com/{self.id}'
        if url not in recording:
            response = (await self.request(
                method='GET',
                url=url,
                cookies={'__ac_nonce': uuid.uuid4().hex[:21]}
            )).text
            result = re.search('<script id="RENDER_DATA".*?>(.*?)</script>', response).group(1)
            data = json.loads(urllib.parse.unquote(result))
            initial_state = data['app']['initialState']
            if stream := initial_state['streamStore']['streamData']['H264_streamData']['stream']:
                title = initial_state['roomStore']['roomInfo']['room']['title']
                stream = HTTPStream(
                    self.get_streamlink(),
                    stream['origin']['main']['flv']
                )  # HTTPStream[flv]
                await asyncio.to_thread(self.run_record, stream, url, title, 'flv')


class Youtube(LiveRecoder):
    async def run(self):
        response = (await self.request(
            method='POST',
            url='https://www.youtube.com/youtubei/v1/browse',
            params={
                'key': 'AIzaSyAO_FJ2SlqU8Q4STEHLGCilw_Y9_11qcW8',
                'prettyPrint': False
            },
            json={
                'context': {
                    'client': {
                        'hl': 'zh-CN',
                        'clientName': 'WEB',
                        'clientVersion': '2.20230101.00.00',
                        'timeZone': 'Asia/Shanghai'
                    }
                },
                'browseId': self.id,
                'params': 'EghmZWF0dXJlZPIGBAoCMgA%3D'
            }
        )).json()
        jsonpath = parse('$..channelFeaturedContentRenderer').find(response)
        for match in jsonpath:
            for item in match.value['items']:
                video = item['videoRenderer']
                if '"style": "LIVE"' in json.dumps(video):
                    url = f"https://www.youtube.com/watch?v={video['videoId']}"
                    title = video['title']['runs'][0]['text']
                    if url not in recording:
                        stream = self.get_streamlink().streams(url).get('best')  # HLSStream[mpegts]
                        # FIXME:多开直播间中断
                        asyncio.create_task(asyncio.to_thread(self.run_record, stream, url, title, 'ts'))


class Twitch(LiveRecoder):
    async def run(self):
        url = f'https://www.twitch.tv/{self.id}'
        if url not in recording:
            response = (await self.request(
                method='POST',
                url='https://gql.twitch.tv/gql',
                headers={'Client-Id': 'kimne78kx3ncx6brgo4mv6wki5h1ko'},
                json=[{
                    'operationName': 'StreamMetadata',
                    'variables': {'channelLogin': self.id},
                    'extensions': {
                        'persistedQuery': {
                            'version': 1,
                            'sha256Hash': 'a647c2a13599e5991e175155f798ca7f1ecddde73f7f341f39009c14dbf59962'
                        }
                    }
                }]
            )).json()
            if response[0]['data']['user']['stream']:
                title = response[0]['data']['user']['lastBroadcast']['title']
                stream = self.get_streamlink(plugin_option={
                    'plugin': 'twitch',
                    'key': 'disable-ads',
                    'value': True,
                }).streams(url).get('best')  # HLSStream[mpegts]
                await asyncio.to_thread(self.run_record, stream, url, title, 'ts')


class Twitcasting(LiveRecoder):
    async def run(self):
        url = f'https://twitcasting.tv/{self.id}'
        if url not in recording:
            response = (await self.request(
                method='GET',
                url='https://twitcasting.tv/streamserver.php',
                params={
                    'target': self.id,
                    'mode': 'client'
                }
            )).json()
            if response['movie']['live']:
                response = (await self.request(
                    method='GET',
                    url=url
                )).text
                title = re.search('<meta name="twitter:title" content="(.*?)">', response).group(1)
                stream = self.get_streamlink().streams(url).get('best')  # Stream[mp4]
                await asyncio.to_thread(self.run_record, stream, url, title, 'mp4')


class Afreeca(LiveRecoder):
    async def run(self):
        url = f'https://play.afreecatv.com/{self.id}'
        if url not in recording:
            response = (await self.request(
                method='POST',
                url='https://live.afreecatv.com/afreeca/player_live_api.php',
                data={'bid': self.id}
            )).json()
            if response['CHANNEL']['RESULT'] != 0:
                title = response['CHANNEL']['TITLE']
                stream = self.get_streamlink().streams(url).get('best')  # HLSStream[mpegts]
                await asyncio.to_thread(self.run_record, stream, url, title, 'ts')


async def run():
    with open('config.json', 'r', encoding='utf-8') as f:
        config = json.load(f)
    try:
        tasks = []
        for item in config['user']:
            platform_class = globals()[item['platform']]
            coro = platform_class(config, item).start()
            tasks.append(asyncio.create_task(coro))
        await asyncio.wait(tasks)
    except (asyncio.CancelledError, KeyboardInterrupt, SystemExit):
        logger.warning('用户中断录制，正在关闭直播流')
        for stream_fd, output in recording.copy().values():
            stream_fd.close()
            output.close()


if __name__ == '__main__':
    logger.add(
        sink='logs/log_{time:YYYY-MM-DD}.log',
        rotation='00:00',
        retention='3 days',
        level='INFO',
        encoding='utf-8',
        format='[{time:YYYY-MM-DD HH:mm:ss}][{level}][{name}][{function}:{line}]{message}'
    )
    asyncio.run(run())
