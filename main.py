import asyncio
import json
import os
import time
from functools import partial
from http.cookies import SimpleCookie
from itertools import chain
from urllib import request

import ffmpeg
import httpx
from httpx_socks import AsyncProxyTransport
from jsonpath import jsonpath
from loguru import logger
import streamlink

recording = []


class LiveRecoder:
    def __init__(self, config: dict, user: dict):
        self.interval = config['interval']
        self.proxy = config.get('proxy')

        self.platform = user['platform']
        self.id = user['id']
        self.name = user.get('name', user['id'])
        self.headers = user.get('headers', {'User-Agent': 'Android'})
        self.cookies = self.get_cookies(user.get('cookies', ''))

        self.client = self.get_client()
        self.url = ''
        self.title = ''
        self.live_time = ''
        self.filename = ''

    async def run(self):
        logger.info(f'[{self.platform}][{self.name}]正在检测直播状态')
        while True:
            try:
                await getattr(self, self.platform)()
            except httpx.RequestError as error:
                logger.error(f'[{self.platform}][{self.name}]{repr(error)}')
            except Exception as error:
                logger.exception(f'[{self.platform}][{self.name}]{repr(error)}')
            await asyncio.sleep(self.interval)

    def get_client(self):
        kwargs = {
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

    def get_filename(self):
        self.live_time = time.strftime('%Y.%m.%d %H.%M.%S')
        # 文件名去除特殊字符
        for i in '"*:<>?/\|':
            self.title = self.title.replace(i, ' ')
        self.filename = f'[{self.live_time}][{self.platform}][{self.name}]{self.title}'

    async def start_record(self):
        # 获取输出文件名
        self.get_filename()
        logger.info(f'开始录制\n{self.filename}')

        # 添加到录制列表
        task = asyncio.current_task()
        recording.append(task.get_name())
        recording_list = '\n'.join(recording)
        logger.info(f'录制列表\n{recording_list}')

        # 新建output目录
        if not os.path.exists('output'):
            os.mkdir('output')

        # 调用streamlink录制直播
        await asyncio.to_thread(self.stream_writer)  # 创建线程防止异步阻塞

        # ffmpeg转码
        await asyncio.to_thread(self.ffmpeg_encode)

        logger.info(f'停止录制\n{self.filename}')
        recording.remove(task.get_name())

    def stream_writer(self):
        try:
            session = streamlink.Streamlink(
                options={
                    'http-proxy': self.proxy,
                    'http-headers': self.headers,
                    'http-cookies': self.cookies
                }
            )
            stream = session.streams(self.url).get('best')
            # stream为可用直播源的字典对象，可能为空
            if stream:
                logger.info(f'获取到直播流链接\n{self.filename}\n{stream.url}')
                stream = stream.open()
                with open(f'output/{self.filename}.ts', 'ab') as output:
                    stream_iterator = chain([stream.read(8192)], iter(partial(stream.read, 8192), b''))
                    try:
                        for chunk in stream_iterator:
                            if chunk:
                                output.write(chunk)
                            else:
                                break
                    except OSError as error:
                        logger.exception(f'文件写入错误\n{self.filename}\n{error}')
                    finally:
                        stream.close()
            else:
                logger.error(f'无可用直播源\n{self.filename}')
        except streamlink.StreamlinkError as error:
            logger.exception(f'streamlink错误\n{self.filename}\n{error}')

    def ffmpeg_encode(self):
        temp_file = f'output/{self.filename}.ts'
        if os.path.exists(temp_file):
            stdout, stderr = (ffmpeg.input(temp_file).output(
                f'output/{self.filename}.mp4',
                f='mp4',
                c='copy',
                map_metadata='-1',
                movflags='faststart'
            ).run())
            if stdout:
                logger.info(stdout)
                # 删除转码前的原始文件
                os.remove(temp_file)
            if stderr:
                logger.exception(f'ffmpeg转码错误\n{self.filename}\n{stderr}')


class Bilibili(LiveRecoder):
    async def bilibili(self):
        response = (await self.client.get(
            url='https://api.live.bilibili.com/room/v1/Room/get_info',
            params={'room_id': self.id}
        )).json()
        self.url = f'https://live.bilibili.com/{self.id}'
        if response['data']['live_status'] == 1 and self.url not in recording:
            self.title = response['data']['title']
            asyncio.create_task(
                self.start_record(),
                name=self.url
            )


class Youtube(LiveRecoder):
    async def youtube(self):
        response = (await self.client.get(
            url=f'https://m.youtube.com/channel/{self.id}/streams',
            headers={
                'accept-language': 'zh-CN',
                'x-youtube-client-name': '2',
                'x-youtube-client-version': '2.20220101.00.00',
                'x-youtube-time-zone': 'Asia/Shanghai',
            },
            params={'pbj': 1}
        )).json()
        living_list = jsonpath(
            response,
            "$.response.contents..[?(@.thumbnailOverlays.0.thumbnailOverlayTimeStatusRenderer.style=='LIVE')]"
        )
        if living_list:
            for item in living_list:
                self.url = f"https://www.youtube.com/watch?v={item['videoId']}"
                self.title = item['headline']['runs'][0]['text']
                if self.url not in recording:
                    asyncio.create_task(self.start_record(), name=self.url)


class Twitch(LiveRecoder):
    async def twitch(self):
        response = (await self.client.post(
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
        self.url = f'https://www.twitch.tv/{self.id}'
        if response[0]['data']['user']['stream'] and self.url not in recording:
            self.title = response[0]['data']['user']['lastBroadcast']['title']
            asyncio.create_task(self.start_record(), name=self.url)


class Twitcasting(LiveRecoder):
    async def twitcasting(self):
        self.client.headers['Origin'] = 'https://twitcasting.tv/'
        self.url = f'https://twitcasting.tv/{self.id}'
        response = (await self.client.get(
            url=f'https://frontendapi.twitcasting.tv/users/{self.id}/latest-movie'
        )).json()
        if response['movie']['is_on_live'] and self.url not in recording:
            movie_id = response['movie']['id']
            response = (await self.client.post(
                url='https://twitcasting.tv/happytoken.php',
                data={'movie_id': movie_id}
            )).json()
            token = response['token']
            response = (await self.client.get(
                url=f'https://frontendapi.twitcasting.tv/movies/{movie_id}/status/viewer',
                params={'token': token}
            )).json()
            self.title = response['movie']['title']
            asyncio.create_task(self.start_record(), name=self.url)


async def run():
    with open('config.json', 'r', encoding='utf-8') as f:
        config = json.load(f)
    tasks = []
    for item in config['user']:
        class_name = item['platform'].capitalize()
        task = asyncio.create_task(
            coro=globals()[class_name](config, item).run(),
            name=f"{item['platform']}_{item['name']}"
        )
        tasks.append(task)
        await asyncio.sleep(1)
    await asyncio.wait(tasks)


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
