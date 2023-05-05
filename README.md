<div align="center">

<img src="https://ae01.alicdn.com/kf/Hd20566dcf9e04a8baf615d58a1c97da76.png" width="150" height="150">

# LiveRecoder

![License](https://img.shields.io/badge/License-MIT-green)
![Python](https://img.shields.io/badge/Python-3.8+-blue)
[![QQ群](https://img.shields.io/badge/QQ群-花寄云璃社-yellow)](https://jq.qq.com/?_wv=1027&k=71rz8gZy)

[![鹿乃资源站](https://img.shields.io/badge/鹿乃资源站-brown)](https://kanosuki.com)
[![鹿乃信息站](https://img.shields.io/badge/鹿乃信息站-brown)](https://kano.fan)


</div>

## 简介

一款直播录制脚本，基于强大的[Streamlink](https://streamlink.github.io)
实现多平台直播源录制，通过挖掘直播平台官方API以轮询方式实现直播开播检测，致力于用最少的代码实现最多的功能

## 已支持平台

- [x] 哔哩哔哩
- [x] 斗鱼
- [x] YouTube
- [x] Twitch
- [x] TwitCasting
- [ ] 更多平台欢迎PR

## 使用

### 安装FFmpeg

[FFmpeg官方下载页面](https://ffmpeg.org/download.html)

根据你的运行平台安装对应版本，并添加环境变量确保全局调用

### 下载

当前支持Windows, Mac和Linux，请前往Release下载对应平台的可执行程序

[Release下载页面](https://github.com/auqhjjqdo/LiveRecorder/releases)

下载解压后修改配置，直接运行二进制文件即可

Mac和Linux arm64版本未实际测试，如果打包出错欢迎提issue

### 源码运行

在不支持的平台运行时可使用源码运行，安装好Python后在命令行输入以下命令即可

```shell
# 下载源码（没有git可以直接从release下载Source code）
git clone https://github.com/auqhjjqdo/LiveRecorder.git
cd LiveRecorder
# 安装依赖
python3 -m pip install -r requirements.txt
# 源码运行
python3 -m main.py
```

## 配置

配置文件存储于`config.json`，该文件位于可执行程序相同目录

文件内容要求严格按照json语法，请前往[在线json格式化网站](https://www.bejson.com/)校验后再修改

### 代理配置

`proxy`的值为代理地址，支持http和socks代理，格式为`protocol://[user:password@]ip:port`

例如`http://127.0.0.1:7890`、`socks5://admin:passwd@127.0.0.1:1080`

留空时默认自动检测系统代理

更多格式参照[streamlink代理文档](https://streamlink.github.io/cli/proxy.html)

### 直播录制配置

按照示例修改`user`列表，注意逗号、引号和缩进

| 字段       | 含义          | 可填内容                                                                                        | 是否必填 | 备注                          |
|----------|-------------|---------------------------------------------------------------------------------------------|------|-----------------------------|
| platform | 直播平台        | `Bilibili`<br/>`Douyu`<br/>`Youtube`<br/>`Twitch`<br/>`Twitcasting`                         | 必填   | 必须为首字母大写                    |
| id       | 对应平台的直播用户id | 哔哩哔哩、斗鱼为直播间房间号<br/>youtube为频道id<br/>twitch为登录名<br/>twitcasting为用户名                          | 必填   | 参考config文件示例格式<br/>直播网址即可找到 |
| name     | 自定义主播名      | 任意字符                                                                                        | 非必填  | 用于录制文件区分<br/>未填写时默认使用id     |
| interval | 检测间隔        | 任意整数或小数                                                                                     | 非必填  | 默认检测间隔为10秒                  |
| format   | 输出格式        | 例如`ts`、`flv`、`mp4`、`mkv`等<br/>详见[FFmpeg官方文档](https://ffmpeg.org/ffmpeg-formats.html#Muxers) | 非必填  | 默认使用直播平台的直播流输出格式            |
| headers  | HTTP 标头     | 参考[官方文档](https://developer.mozilla.org/zh-CN/docs/Web/HTTP/Headers)                         | 非必填  | 可用于部分需请求头验证的网站              |
| cookies  | HTTP Cookie | `key=value`<br/>多个cookie使用`;`分隔                                                             | 非必填  | 可用于录制需登录观看的直播               |

### 注意事项

#### Bilibili的房间号

部分主播的B站房间号在使用网页打开时地址栏默认显示的是短号，并不是真实的房间号，如需获取真实房间号可以打开

`https://api.live.bilibili.com/xlive/web-room/v2/index/getRoomPlayInfo?room_id=短号`

返回的数据中`room_id`后的数字即真实房间号

#### YouTube的频道ID

YouTube的频道ID一般是由`UC`开头的一段字符，由于YouTube可以自定义标识名，打开YouTube频道时网址会优先显示标识名而非频道ID

获取YouTube的频道ID可以在打开频道主页后，按F12打开开发者工具，在控制台输入`ytInitialData.metadata.channelMetadataRenderer.externalId`
，返回的字符即YouTube的频道ID

#### TwitCasting的检测间隔

由于直播检测请求使用了HTTP Keep-Alive长连接防止频繁建立TCP通道导致性能下降，但TwitCasting的服务器要求10秒内无请求则关闭连接，所以配置文件在添加TwitCasting的直播时尽量加入`interval`字段并将检测间隔设为小于10秒，以免频繁出现请求协议错误

## 输出文件

默认将直播录制文件输出到运行目录的`output`文件夹

输出文件默认直接使用ffmpeg封装为[配置文件自定义的输出格式](#输出格式配置)
，音视频编码为直播平台直播流默认（一般视频编码为`H.264`，音频编码为`AAC`），录制清晰度为最高画质

输出文件名命名格式为`[年.月.日 时.分.秒][平台][主播名]直播标题.格式`，日期时区为系统默认时区