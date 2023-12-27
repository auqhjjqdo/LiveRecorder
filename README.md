<img src="https://socialify.git.ci/auqhjjqdo/LiveRecorder/image?font=Inter&forks=1&issues=1&language=1&name=1&owner=1&pattern=Circuit%20Board&pulls=1&stargazers=1&theme=Auto" alt="LiveRecorder"/>

## 简介

一款无人值守直播录制脚本，基于强大的[Streamlink](https://streamlink.github.io)
实现多平台直播源录制，通过挖掘直播平台官方API以轮询方式实现直播开播检测，致力于用最少的代码实现最多的功能

## 已支持平台

- [x] 哔哩哔哩
- [x] 斗鱼
- [x] 虎牙
- [x] 抖音
- [x] YouTube
- [x] Twitch
- [x] NicoNico
- [x] TwitCasting
- [x] Afreeca
- [x] Pandalive
- [x] Bigolive
- [x] Pixiv Sketch
- [ ] 更多平台欢迎PR

## 已知bug

- YouTube在录制单个频道多开直播间时会出现频繁中断，暂时无法修复
- 斗鱼直播因使用js引擎可能出现偶发的解析错误，会自动重试录制

## 使用

### 安装FFmpeg

[FFmpeg官方下载页面](https://ffmpeg.org/download.html)

根据你的运行平台安装对应版本，并添加环境变量确保全局调用

### 下载

当前支持Windows, Mac和Linux平台（amd64架构），请前往Release下载对应平台的可执行程序

[Release下载页面](https://github.com/auqhjjqdo/LiveRecorder/releases)

下载解压后修改配置，直接运行二进制文件即可

### 源码运行

在不支持的平台运行时可使用源码运行，安装好Python后在命令行输入以下命令即可

```shell
# 下载源码（没有git可以直接从release下载Source code）
git clone https://github.com/auqhjjqdo/LiveRecorder.git
cd LiveRecorder
# 安装依赖
python3 -m pip install .
# 源码运行
python3 live_recorder.py
```

## 配置

配置文件存储于`config.json`，该文件位于可执行程序相同目录

修改示例配置文件`config.sample.json`后务必重命名为`config.json`

文件内容要求严格按照json语法，请前往[在线json格式化网站](https://www.bejson.com/)校验后再修改

### 代理配置

`proxy`的值为代理地址，支持http和socks代理，格式为`protocol://[user:password@]ip:port`

例如`http://127.0.0.1:7890`、`socks5://admin:passwd@127.0.0.1:1080`

建议优先使用http代理，目前socks5代理存在一定兼容性问题

无需代理时去除引号填写`null`或删除该字段即可

### 输出目录配置

`output`字段为录制文件输出后保存的目录路径，非必填字段（请勿填写空字符串），默认输出到运行目录的`output`文件夹

路径分隔符请使用`/`，防止出现转义导致的不兼容问题

支持相对路径和绝对路径，例如`output/video`、`/tmp/output`、`D:/output`

### 直播录制配置

按照示例修改`user`列表，注意逗号、引号和缩进

| 字段       | 含义          | 可填内容                                                                                        | 是否必填 | 备注                             |
|----------|-------------|---------------------------------------------------------------------------------------------|------|--------------------------------|
| platform | 直播平台        | 直播平台的英文名或拼音                                                                                 | 必填   | 必须为首字母大写                       |
| id       | 直播用户id      | 直播平台的房间号或用户名                                                                                | 必填   | 参考config文件示例格式<br/>一般在直播网址即可找到 |
| name     | 自定义主播名      | 任意字符                                                                                        | 非必填  | 用于录制文件区分<br/>未填写时默认使用id        |
| interval | 检测间隔        | 任意整数或小数                                                                                     | 非必填  | 默认检测间隔为10秒                     |
| format   | 输出格式        | 例如`ts`、`flv`、`mp4`、`mkv`等<br/>详见[FFmpeg官方文档](https://ffmpeg.org/ffmpeg-formats.html#Muxers) | 非必填  | 默认使用直播平台的直播流输出格式               |
| output   | 输出目录        | 与[输出目录配置](#输出目录配置)相同                                                                        | 非必填  | 优先级高于[输出目录配置](#输出目录配置)         |
| proxy    | 代理          | 与[代理配置](#代理配置)相同                                                                            | 非必填  | 优先级高于[代理配置](#代理配置)             |
| headers  | HTTP 标头     | 参考[官方文档](https://developer.mozilla.org/zh-CN/docs/Web/HTTP/Headers)                         | 非必填  | 可用于部分需请求头验证的网站                 |
| cookies  | HTTP Cookie | `key=value`<br/>多个cookie使用`;`分隔                                                             | 非必填  | 可用于录制需登录观看的直播                  |

### 注意事项

#### 哔哩哔哩的房间号

部分主播的B站房间号在使用网页打开时地址栏默认显示的是短号，并不是真实的房间号，如需获取真实房间号可以打开

`https://api.live.bilibili.com/xlive/web-room/v2/index/getRoomPlayInfo?room_id=短号`

返回的数据中`room_id`后的数字即真实房间号

#### 哔哩哔哩的清晰度

由于哔哩哔哩的限制，未登录用户无法观看较高画质的直播，因此需要在配置文件中添加`cookies`字段（仅需`SESSDATA`）以获取原画清晰度的直播流

#### 斗鱼的房间号

斗鱼直播同哔哩哔哩在部分直播间的房间号显示的是短号，获取真实房间号可打开F12开发者工具，在控制台输入`room_id`，返回的数字即真实房间号

#### YouTube的频道ID

YouTube的频道ID一般是由`UC`开头的一段字符，由于YouTube可以自定义标识名，打开YouTube频道时网址会优先显示标识名而非频道ID

获取YouTube的频道ID可以在打开频道主页后，按F12打开开发者工具，在控制台输入`ytInitialData.metadata.channelMetadataRenderer.externalId`
，返回的字符即YouTube的频道ID

#### NicoNico的用户ID和频道ID

NicoNico的直播分为用户直播和频道直播，其ID分别以`co`和`ch`开头再加上一段数字，但NicoNico的直播间一般是以`lv`开头的视频ID，获取用户ID或频道ID可在F12开发者工具的控制台输入`NicoGoogleTagManagerDataLayer[0].content`，在返回的数据中`community_id`或`channel_id`的值即对应的用户ID或频道ID

其中部分频道在使用频道ID时无法获取到最新直播，此问题暂时无解，请使用`lv`视频ID代替

#### TwitCasting的检测间隔

由于直播检测请求使用了HTTP
Keep-Alive长连接防止频繁建立TCP通道导致性能下降，但TwitCasting的服务器要求10秒内无请求则关闭连接，所以配置文件在添加TwitCasting的直播时尽量加入`interval`
字段并将检测间隔设为小于10秒，以免频繁出现请求协议错误

## 输出文件

输出文件会在录制结束后使用ffmpeg封装为配置文件自定义的输出格式，音视频编码为直播平台直播流默认（一般视频编码为`H.264`
，音频编码为`AAC`），录制清晰度为最高画质，封装结束后自动删除原始录制文件，输出格式为空或未填写时不进行封装

输出文件名命名格式为`[年.月.日 时.分.秒][平台][主播名]直播标题.格式`，日期时区为系统默认时区
