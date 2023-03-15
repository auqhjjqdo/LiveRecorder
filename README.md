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

一款直播录制脚本，基于强大的Streamlink实现多平台直播源录制，通过挖掘直播平台官方API以轮询方式实现直播开播检测，致力于用最少的代码实现最多的功能

## 已支持平台

- [x] Bilibili
- [x] YouTube
- [x] Twitch
- [x] Twitcasting
- [ ] 更多平台欢迎PR

（需streamlink支持，详见[streamlink插件文档](https://streamlink.github.io/plugins.html)）

## 使用

### 安装FFmpeg

[FFmpeg官方下载页面](https://ffmpeg.org/download.html)

根据你的运行平台安装对应版本，并添加环境变量确保全局调用

### 下载

当前支持Windows, Mac和Linux，请前往Release下载对应平台的可执行程序

[Release下载页面](https://github.com/auqhjjqdo/LiveRecorder/releases)

其他平台请自行构建

## 配置

配置文件存储于`config.json`，该文件位于可执行程序相同目录

文件内容要求严格按照json语法，请前往[在线json格式化网站](https://www.bejson.com/)校验后再修改

### 检测间隔

`interval`的值为检测直播是否开播的轮询时间间隔，单位为秒

不能添加引号，必须为整型或浮点型数字

### 代理配置

`proxy`的值为代理地址，支持http和socks代理，格式为`protocol://[user:password@]ip:port`

例如`http://127.0.0.1:7890`、`socks5://admin:passwd@127.0.0.1:1080`

留空时默认自动检测系统代理

更多格式参照[streamlink代理文档](https://streamlink.github.io/cli/proxy.html)

### 直播录制配置

按照示例修改`user`列表，注意逗号、引号和缩进

| 字段       | 含义          | 可填内容                                                                | 是否必填 | 备注                          |
|----------|-------------|---------------------------------------------------------------------|------|-----------------------------|
| platform | 直播平台        | `bilibili`<br/>`youtube`<br/>`twitch`<br/>`twitcasting`             | 必填   | 必须为小写                       |
| id       | 对应平台的直播用户id | bilibili为直播间房间号<br/>youtube为频道id<br/>twitch为登录名<br/>twitcasting为用户名 | 必填   | 参考config文件示例格式<br/>直播网址即可找到 |
| name     | 自定义主播名      | 任意字符                                                                | 非必填  | 用于录制文件区分<br/>未填写时默认使用id     |
| headers  | HTTP 标头     | 参考[官方文档](https://developer.mozilla.org/zh-CN/docs/Web/HTTP/Headers) | 非必填  | 可用于部分需请求头验证的网站              |
| cookies  | HTTP Cookie | `key=value`<br/>多个cookie使用`;`分隔                                     | 非必填  | 可用于录制需登录观看的直播               |

### 注意事项

#### Bilibili的房间号

部分主播的B站房间号在使用网页打开时地址栏默认显示的是短号，并不是真实的房间号，如需获取真实房间号可以打开

`https://api.live.bilibili.com/xlive/web-room/v2/index/getRoomPlayInfo?room_id=短号`

返回的数据中`room_id`后的数字即真实房间号

#### YouTube的频道ID

YouTube的频道ID一般是由`UC`开头的一段字符，由于YouTube可以自定义标识名，打开YouTube频道时网址会优先显示标识名而非频道ID

获取YouTube的频道ID可以在打开频道主页后，按F12打开开发者工具，在控制台输入`ytInitialData.metadata.channelMetadataRenderer.externalId`
，返回的字符即YouTube的频道ID

## 输出

默认将直播录制输出到`output`文件夹

录制的临时文件为`.ts`流式传输文件格式，可用播放器打开查看，直播录制结束后会自动使用ffmpeg转换为`.mp4`格式，同时删除`.ts`
文件，格式转换失败保存`.ts`文件以供备份

文件名命名格式为`[年.月.日 时.分.秒][平台][主播名]直播标题.mp4`，日期时区为系统默认时区