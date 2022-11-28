import asyncio
import os
import time
from functools import partial
from itertools import chain
from urllib import request

import ffmpeg
import httpx
from jsonpath import jsonpath
from loguru import logger
import streamlink


async def run(data):
    tasks = []
    for info in data:
        tasks.append(asyncio.create_task(LiveRecoder(info).run(), name=f"{info['platform']}_{info['name']}"))
        await asyncio.sleep(1)
    await asyncio.wait(tasks)


async def start_record(platform, url, title):
    # 文件名处理
    start_time = time.localtime()
    datetime = time.strftime('%Y.%m.%d', start_time)
    for i in '"*:<>?/\|':
        title = title.replace(i, ' ')
    filename = f'[{datetime}][{platform}]{title}.mp4'
    if not os.path.exists('output'):
        os.mkdir('output')
    if os.path.exists(filename) or os.path.exists(f'output/{filename}'):
        filename = filename.replace(datetime, time.strftime('%Y.%m.%d_%H%M%S', start_time))

    logger.info(f'开始录制\n{filename}')
    task = asyncio.current_task()
    recording.append(task.get_name())
    logger.info(f'正在录制\n{recording}')

    stream_task = asyncio.create_task(asyncio.to_thread(stream_writer, url, filename))
    await asyncio.wait({stream_task})
    if os.path.exists(filename):
        ffmpeg_task = asyncio.create_task(asyncio.to_thread(ffmpeg_encode, filename))
        await asyncio.wait({ffmpeg_task})
        if os.path.exists(f'output/{filename}'):
            os.remove(filename)

    logger.info(f'停止录制\n{filename}')
    recording.remove(task.get_name())


def stream_writer(url, filename):
    # proxies_args = ''
    # if proxies:
    #     proxies_args = f'--http-proxy "{proxies}"'
    # cmd = f'streamlink "{url}" best --retry-open 3 --retry-streams 5 --retry-max 10 {proxies_args}' \
    #       f' -O | ffmpeg -re -i pipe:0 -v error -c copy -map_metadata -1 -movflags faststart "{filename}"'
    # process = await asyncio.create_subprocess_shell(cmd)
    # await process.wait()

    session = streamlink.Streamlink()
    if proxies:
        session.set_option('http-proxy', proxies)
    stream = session.streams(url).get('best')
    if stream:
        logger.info(f'\n{filename}\n{stream.url}')
        stream = stream.open()
        with open(filename, 'ab') as output:
            stream_iterator = chain([stream.read(8192)], iter(partial(stream.read, 8192), b''))
            try:
                for chunk in stream_iterator:
                    if chunk:
                        output.write(chunk)
                    else:
                        break
            except OSError as error:
                logger.exception(f'\n{filename}\n{error}')
            finally:
                stream.close()
    else:
        logger.error(f'无直播源\n{filename}')
        stream.close()


def ffmpeg_encode(filename):
    # process = (
    #     ffmpeg
    #     .input('pipe:', readrate=1)
    #     .output(filename, v='warning', f='mp4', c='copy', map_metadata='-1', movflags='faststart')
    #     .run_async(pipe_stdin=True)
    # )
    # while True:
    #     in_bytes = stream.read(size=-1)
    #     if not in_bytes:
    #         break
    #     process.stdin.write(in_bytes)
    # stream.close()
    # process.terminate()
    # shutil.move(filename, 'output/')

    ffmpeg.input(filename).output(f'output/{filename}', f='mp4', c='copy', map_metadata='-1', movflags='faststart').run()


class LiveRecoder:
    def __init__(self, info):
        self.client = httpx.AsyncClient(
            headers={
                'User-Agent': 'Android'
            },
            proxies=proxies
        )
        self.platform = info['platform']
        self.id = info['id']
        self.name = f"{info['platform']}_{info['name']}"

    async def run(self):
        logger.info(f'[{self.name}]正在检测直播状态')
        while True:
            try:
                # logger.info(recording)
                await getattr(self, self.platform)()
            except (httpx.ConnectTimeout, httpx.ReadTimeout):
                logger.error(f'[{self.name}]连接超时')
            except Exception as error:
                logger.exception(f'[{self.name}]{repr(error)}')
            await asyncio.sleep(10)

    async def bilibili(self):
        response = await self.client.get(
            url='https://api.live.bilibili.com/room/v1/Room/get_info',
            params={'room_id': self.id}
        )
        data = response.json()
        live_url = f'https://live.bilibili.com/{self.id}'
        if data['data']['live_status'] == 1 and live_url not in recording:
            title = data['data']['title']
            asyncio.create_task(start_record(self.platform, live_url, title), name=live_url)

    async def youtube(self):
        response = await self.client.get(
            url=f'https://m.youtube.com/channel/{self.id}/streams',
            headers={
                'accept-language': 'zh-CN',
                'x-youtube-client-name': '2',
                'x-youtube-client-version': '2.20220101.00.00',
                'x-youtube-time-zone': 'Asia/Shanghai',
            },
            params={'pbj': 1}
        )
        living_list = jsonpath(response.json(), "$.response.contents..[?(@.thumbnailOverlays.0.thumbnailOverlayTimeStatusRenderer.style=='LIVE')]")
        if living_list:
            for item in living_list:
                live_url = f"https://www.youtube.com/watch?v={item['videoId']}"
                title = item['headline']['runs'][0]['text']
                if live_url not in recording:
                    asyncio.create_task(start_record(self.platform, live_url, title), name=live_url)

    async def twitch(self):
        response = await self.client.post(
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
        )
        data = response.json()
        live_url = f'https://www.twitch.tv/{self.id}'
        if data[0]['data']['user']['stream'] and live_url not in recording:
            title = data[0]['data']['user']['lastBroadcast']['title']
            asyncio.create_task(start_record(self.platform, live_url, title), name=live_url)

    async def twitcasting(self):
        response = await self.client.get(url=f'https://frontendapi.twitcasting.tv/users/{self.id}/latest-movie')
        data = response.json()
        live_url = f'https://twitcasting.tv/{self.id}'
        if data['movie']['is_on_live'] and live_url not in recording:
            movie_id = data['movie']['id']
            response = await self.client.post(
                url='https://twitcasting.tv/happytoken.php',
                data={'movie_id': movie_id}
            )
            token = response.json()['token']
            response = await self.client.get(
                url=f'https://frontendapi.twitcasting.tv/movies/{movie_id}/status/viewer',
                params={'token': token}
            )
            title = response.json()['movie']['title']
            asyncio.create_task(start_record(self.platform, live_url, title), name=live_url)


if __name__ == '__main__':
    # 脚本依赖：ffmpeg(全局)
    # pip install streamlink ffmpeg-python httpx jsonpath loguru

    logger.add(
        sink='logs/log_{time:YYYY-MM-DD}.log',
        rotation='00:00',
        retention='3 days',
        level='INFO',
        encoding='utf-8',
        format='[{time:YYYY-MM-DD HH:mm:ss}][{level}][{name}][{function}:{line}]{message}'
    )
    recording = []

    # proxies = 'http://127.0.0.1:7890'
    proxies = request.getproxies().get('http')
    config = (
        {'platform': 'bilibili', 'id': '15152878', 'name': '鹿乃'},
        {'platform': 'bilibili', 'id': '25600815', 'name': 'MKLNtic'},
        {'platform': 'youtube', 'id': 'UCShXNLMXCfstmWKH_q86B8w', 'name': '斑比鹿乃'},
        {'platform': 'youtube', 'id': 'UCfuz6xYbYFGsWWBi3SpJI1w', 'name': '桜帆鹿乃'},
        {'platform': 'youtube', 'id': 'UCN3M-Nwa-eaZuMhPb5c3Pww', 'name': 'MKLNtic'},
        {'platform': 'twitch', 'id': 'kanomahoro', 'name': '桜帆鹿乃'},
        {'platform': 'twitcasting', 'id': 'kano_2525', 'name': '鹿乃'}
    )
    asyncio.run(run(config))
