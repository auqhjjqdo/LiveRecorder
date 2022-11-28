<div align="center">

<img src="https://ae01.alicdn.com/kf/Hd20566dcf9e04a8baf615d58a1c97da76.png" width="150" height="150">

# LiveRecoder

![License](https://img.shields.io/badge/License-MIT-green)
![Python](https://img.shields.io/badge/Python-3.8+-blue)
[![QQ群](https://img.shields.io/badge/QQ群-花寄云璃社-brown)](https://jq.qq.com/?_wv=1027&k=71rz8gZy)

</div>

## 简介

又一款直播录制脚本，基于强大的Streamlink实现多平台直播源录制，通过挖掘直播平台官方API以轮询方式实现直播开播检测，致力于用最少的代码实现最多的功能

## 已支持平台

- [x] Bilibili
- [x] YouTube
- [x] Twitch
- [x] Twitcasting

## 安装

### 下载

https://raw.githubusercontent.com/auqhjjqdo/LiveRecorder/main/main.py

### pip安装依赖

```
pip install streamlink ffmpeg-python httpx jsonpath loguru
```

### 安装FFmpeg

[点此打开FFmpeg官方下载页面](https://ffmpeg.org/download.html)

根据你的运行平台安装对应版本，并添加环境变量确保全局调用

## 配置

### 直播录制配置
打开`main.py`，按照示例修改`config`变量，注意逗号和引号

| 字段       | 可填内容                                                                                | 备注               |
|----------|-------------------------------------------------------------------------------------|------------------|
| platform | `bilibili`、`youtube`、`twitch`、`twitcasting`                                         | 必须为小写            |
| id       | 对应平台的录播用户id<br/>bilibili为直播间房间号<br/>youtube为频道id<br/>twitch为登录名<br/>twitcasting为用户名 | 参考示例格式，直播url即可找到 |
| name     | 自定义录播主播名                                                                            | 用于录制文件区分         |

### 代理配置

修改`proxies`变量为代理地址，支持http/socks5，Windows平台可不修改，会自动检测系统代理

## 友链

* [鹿乃资源站](https://kanosuki.com)
* [鹿乃信息站](https://kano.fan)
