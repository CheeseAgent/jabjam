# JabJam · 音乐拳击跟练视频生成器

选一首歌，生成一段可以在普通播放器打开的 MP4。跟练时面向屏幕，看方块沿左右轨道飞近，在它抵达击打线的音乐拍点空击。视频会在该拍点播放碎裂效果。左轨青色对应左手，右轨橙色对应右手；直箭头提示直拳，左摆拳箭头朝右、右摆拳朝左，J 形箭头提示上勾拳。地面出现带脚印的箭头时，跟着方向侧步。

## 在 GitHub Actions 生成视频

1. 打开 **Actions → Render follow-along MP4**。工作流进入默认分支后，可用 **Run workflow** 选择分支并填入课程 JSON 路径、画面上要显示的歌名、难度和最短拳间隔。歌名留空时自动读取歌曲标题。开发中的合并请求也会自动运行示例课程。
2. 默认课程 `courses/neon-round.json` 使用项目合成的 37 秒音乐，由现有 Godot 节拍分析与动作编排生成谱面。要精确指定每一拳的时间，参考 [八动作课程](courses/eight-moves.json)。
3. 运行完成后，在该次 Actions 的 **Artifacts** 下载保留 **1 天** 的 `jabjam-follow-along-…`。解压后播放 `jabjam.mp4`。包内还有四拳和八动作验收短片、成片对照图及资源报告。

构建依赖、排谱、渲染、编码和测试都可以在 GitHub 托管的 Linux runner 上完成。构建完成后，导出作业关闭容器网络。播放只需要成片，阿里云服务器无需参与。

## 导出入口

在装有 Godot 4.6.3 Standard、Python 3、Pillow、Noto CJK 字体、FFmpeg 和 ffprobe 的 Linux 环境中执行：

```sh
python3 video/export.py courses/neon-round.json build/neon-round.mp4 \
  --song-title "JabJam Demo Loop" --difficulty easy --min-gap 1.4
```

输出为横屏 H.264 / AAC MP4。音乐在本地分析；拳法、侧步、方块接近速度、配色、分辨率与帧率都由课程控制。课程字段、时间轴和测试口径见[视频导出指南](docs/video-export.md)。

## 早期交互原型

Godot 互动工程仍可以独立运行。导出器直接复用它的导歌及编排实现，成片播放与动作计分彼此独立。[原型运行指南](docs/development.md) · [游戏设计历史](docs/game-design-vision.md) · [引擎选型记录](docs/decisions/0001-game-engine-godot.md)
