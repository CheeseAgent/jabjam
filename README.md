# JabJam 🥊🎵

**用自己的歌练节奏拳击。** JabJam 面向在家运动、想自己选歌的玩家。目标是在 Android 手机上跟着节奏轨道和教练挥拳，电视可镜像显示。当前可运行的是 **Linux 桌面原型**：导入本地歌曲，生成可重玩的拳击谱面，用键盘或屏幕按钮练习。音乐分析、播放和记录都在本机完成。

## 现在能玩什么

安装 **Godot 4.6.3 Standard**，在包含 `project.godot` 的目录执行：

```sh
godot --path .
```

- **先试一首**。按 Space 开始 36 秒演示曲。音符到线时，F / J 对应左 / 右直拳，D / K 对应左 / 右勾拳。Esc 暂停或继续，R 重开。结束后按 Space 或拳法键盖章。
- **换自己的歌**。在 **CHOOSE / IMPORT SONG → IMPORT SONG…** 选择 MP3、WAV 或 Ogg Vorbis（8 秒至 10 分钟，最大 64 MiB）。可以选 Easy / Normal，或手动修正 BPM。相同音源和设置复用谱面。[导歌指南](docs/music-import.md)
- **成绩范围**。当前的 3D 教练是几何占位角色，输入均为模拟拳法，练习记录保存在本机。真实挥拳识别、Joy-Con、Android 安装包和运动打卡仍待开发验证。[游戏设计愿景](docs/game-design-vision.md)

## Linux 小服务器怎么用

有桌面、OpenGL 3.3 和音频输出的 Linux 电脑可以用上面的命令试玩。只有 SSH 的服务器可以做导入、规则和启动检查。项目没有 HTTP 服务或浏览器客户端，运行游戏也无需部署后端。

在 Linux x86_64 安装上述 Godot 版本后，如果只剩约 300 MB 内存，用轻量模式执行规则、导歌、场景和启动检查：

```sh
sh scripts/verify.sh --runtime-only
```

完整检查还会启动 Godot 编辑器做资源导入，需要更多内存。仓库提供 amd64 镜像的构建配置，适合在其他机器构建后传到小服务器。256 MiB 限额的 Docker 命令和实测数据见[开发指南](docs/development.md#小服务器运行预算)。

## 接下来要验证什么

优先验证运动控制器能否可靠区分左右手和拳法，以及音乐、动作与反馈能否对齐。首选研究初代 Joy-Con，也保留低成本 DIY 传感器方向。正式运动成绩需要可信动作输入。项目希望开放代码与素材贡献，许可证和投稿规则仍待确定。[引擎选型记录](docs/decisions/0001-game-engine-godot.md)
