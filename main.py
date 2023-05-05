import asyncio
import hashlib
import json
import os
import re
import time
import urllib
from http.cookies import SimpleCookie
from subprocess import Popen
from typing import Dict, Tuple, Union
from urllib import request
from urllib.parse import urlparse

import ffmpeg
import httpx
from httpx_socks import AsyncProxyTransport
from jsonpath_ng.ext import parse
from loguru import logger
import streamlink
from streamlink.stream import StreamIO, HTTPStream
from streamlink_cli.main import open_stream
from streamlink_cli.output import FileOutput
from streamlink_cli.streamrunner import StreamRunner

recording: Dict[str, Tuple[StreamIO, FileOutput, Popen]] = {}


class LiveRecoder:
    def __init__(self, config: dict, user: dict):
        self.proxy = config.get('proxy')
        self.format = config.get('format')

        self.id = user['id']
        platform = user['platform']
        name = user.get('name', self.id)
        self.flag = f'[{platform}][{name}]'

        self.interval = user.get('interval', 10)
        self.headers = user.get('headers', {'User-Agent': 'Chrome'})
        self.cookies = self.get_cookies(user.get('cookies', ''))

        self.client = self.get_client()

    async def start(self):
        logger.info(f'{self.flag}正在检测直播状态')
        while True:
            try:
                await self.run()
            except ConnectionError as error:
                logger.error(error)
                await self.client.aclose()
                self.client = self.get_client()
            except Exception as error:
                logger.exception(f'{self.flag}直播检测未知错误\n{repr(error)}')
            await asyncio.sleep(self.interval)

    async def run(self):
        pass

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
        kwargs = {
            'http2': True,
            'timeout': self.interval,
            'limits': httpx.Limits(max_keepalive_connections=100, keepalive_expiry=self.interval * 2),
            'headers': self.headers,
            'cookies': self.cookies
        }
        if self.proxy:
            if 'socks' in self.proxy:
                kwargs['transport'] = AsyncProxyTransport.from_url(self.proxy)
            else:
                kwargs['proxies'] = self.proxy
        else:
            self.proxy = request.getproxies().get('http')
        return httpx.AsyncClient(**kwargs)

    @staticmethod
    def get_cookies(cookies_str: str):
        if cookies_str:
            cookies = SimpleCookie()
            cookies.load(cookies_str)
            return {k: v.value for k, v in cookies.items()}
        else:
            return {}

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
        if self.format:
            format = self.format
        filename = f'[{live_time}]{self.flag}{title}.{format}'
        return filename

    def get_streamlink(self, plugin_option: dict = None):
        session = streamlink.Streamlink()
        # 添加streamlink的http相关选项
        for arg in ('proxy', 'headers', 'cookies'):
            if attr := getattr(self, arg):
                session.set_option(f'http-{arg}', attr)
        if plugin_option:
            session.set_plugin_option(**plugin_option)
        return session

    async def run_record(self, stream: Union[StreamIO, HTTPStream], title, format):
        # 获取输出文件名
        filename = self.get_filename(title, format)
        if stream:
            logger.info(f'{self.flag}开始录制：{filename}')
            # 新建output目录
            os.makedirs('output', exist_ok=True)
            # 创建ffmpeg管道
            pipe = self.create_pipe(filename)
            # 调用streamlink录制直播
            await asyncio.to_thread(self.stream_writer, stream, filename, pipe)  # 创建线程防止异步阻塞
            pipe.terminate()
            recording.pop(filename, None)
            logger.info(f'{self.flag}停止录制：{filename}')
        else:
            logger.error(f'{self.flag}无可用直播源：{filename}')

    def create_pipe(self, filename):
        logger.info(f'{self.flag}创建ffmpeg管道：{filename}')
        pipe: Popen = (
            ffmpeg
            .input('pipe:')
            .output(
                f'output/{filename}',
                codec='copy',
                map_metadata=-1,
            )
            .global_args('-hide_banner')
            .run_async(pipe_stdin=True)
        )
        return pipe

    def stream_writer(self, stream, filename, pipe: Popen):
        logger.info(f'{self.flag}获取到直播流链接：{filename}\n{stream.url}')
        output = FileOutput(fd=pipe.stdin)
        try:
            stream_fd, prebuffer = open_stream(stream)
            output.open()
            recording[filename] = (stream_fd, output, pipe)
            logger.info(f'{self.flag}正在录制：{filename}')
            StreamRunner(stream_fd, output).run(prebuffer)
        except BrokenPipeError as error:
            logger.error(f'{self.flag}管道损坏错误：{filename}\n{error}')
        except OSError as error:
            logger.error(f'{self.flag}文件写入错误：{filename}\n{error}')
        except Exception as error:
            logger.exception(f'{self.flag}直播录制未知错误\n{error}')
        finally:
            output.close()


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
                await self.run_record(stream, title, 'flv')


class Douyu(LiveRecoder):
    async def run(self):
        url = f'https://www.douyu.com/{self.id}'
        if url not in recording:
            params = {
                'aid': 'wp',
                'client_sys': 'wp',
                'time': int(time.time()),
            }
            params['auth'] = hashlib.md5(
                f'room/{self.id}?{urllib.parse.urlencode(params)}zNzMV1y4EMxOHS6I5WKm'.encode()
            ).hexdigest()
            response = (await self.request(
                method='GET',
                url=f'http://www.douyutv.com/api/v1/room/{self.id}',
                params=params
            )).json()
            if response['data']['show_status'] == '1':
                title = response['data']['room_name']
                rtmp_id = response['data']['rtmp_live'].split('.')[0]
                url = f'http://hw-tct.douyucdn.cn/live/{rtmp_id}_4000.flv'
                stream = HTTPStream(self.get_streamlink(), url)  # HTTPStream[flv]
                await self.run_record(stream, title, 'flv')


class Youtube(LiveRecoder):
    async def run(self):
        response = (await self.request(
            method='POST',
            url=f'https://www.youtube.com/youtubei/v1/browse',
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
                        asyncio.create_task(self.run_record(stream, title, 'ts'), name=url)


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
                await self.run_record(stream, title, 'ts')


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
                stream = self.get_streamlink().streams(url).get('best')  # Stream[mov,mp4,m4a,3gp,3g2,mj2]
                await self.run_record(stream, title, 'mp4')


async def run():
    with open('config.json', 'r', encoding='utf-8') as f:
        config = json.load(f)
    tasks = []
    for item in config['user']:
        platform_class = globals()[item['platform']]
        coro = platform_class(config, item).start()
        tasks.append(asyncio.create_task(coro))
    try:
        await asyncio.wait(tasks)
    except asyncio.CancelledError:
        logger.warning('用户中断录制，正在关闭直播流')
        for stream_fd, output, pipe in recording.copy().values():
            stream_fd.close()
            output.close()
            pipe.terminate()


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
