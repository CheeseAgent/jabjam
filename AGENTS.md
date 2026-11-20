# 接手 JabJam

主分支 `main` 包含本地音乐跟练视频生成器、课程样例和早期 Godot 交互原型。生成视频的入口是仓库根目录下的 `video/export.py`。

导出从 [export.py](video/export.py) 开始。`config` 读课程，`prepare` 取得音乐和成片动作，两种输出共用这一步。`write_course` 把动作写回 JSON，`export` 交给 `Arena.frame` 逐帧绘制，再用 FFmpeg 编码。

## 先跑一份课程

在仓库根目录运行以下命令。只需要 Python 3.9+ 和仓库内的示例文件。

```sh
python3 video/export.py courses/eight-moves.json --check
```

成功时会显示手排动作数（这个示例有 8 个）。改课程时，编辑 JSON 里的 `actions`、`course` 或 `picture` 后重跑即可。想从自己喜欢的歌曲起步，可先生成一份带时间戳的可编辑谱面，见 [README 的改谱示例](README.md#从自动谱开始改)。

## 按任务找入口

| 我想改 | 从这里看 | 怎么验 |
| --- | --- | --- |
| 歌曲、动作顺序、轨道颜色 | [八动作课程](courses/eight-moves.json)，[课程字段](docs/video-export.md) | 对改过的 JSON 运行 `--check`。 |
| 增减课程字段，改默认值或报错 | [course.py](video/course.py) 的 `config` | `python3 tests/test_video_pacing.py` 同时覆盖配置、间隔和命令行。 |
| 调整恢复间隔、自动谱中的侧步 | [choreography.py](video/choreography.py) 的 `required_gap`、`arrange` | 跑上面的规则测试，再用 `--write-course` 查看实际动作和时间。 |
| 增加教练组合 | [choreography.py](video/choreography.py) 的 `PADWORK_COMBOS`，每项给出 ID、显示名和出拳顺序 | 跑规则测试。用默认课程写出手排谱，查看 `combo_name` 和 `combo_step`。 |
| 改动作名称、箭头、脚印或场景 | [动作表](video/movements.py)、[图形](video/cue_art.py)、[画面](video/arena.py) | 导出下方八动作短片，抽帧看左右方向和落点。加 `--scene classic` 可对照经典背景。 |
| 调整拍点分析或交互原型 | [chart_generator.gd](scripts/chart_generator.gd)、[原型开发指南](docs/development.md) | `sh scripts/verify.sh` |

画面验收使用现成的 24 秒课程，需要 Pillow、Noto CJK 字体与 FFmpeg（含 ffprobe）。

```sh
python3 video/export.py courses/eight-moves.json build/eight-moves.mp4
python3 tests/check_eight_moves.py build/eight-moves.mp4
```

课程 JSON 的动作 ID 和以原曲起点计算的秒数也是导出接口。调整动作显示名时改 `label`，让已有课程仍可用同一 ID 打开。自动编排、内置曲的生成还会用到 Godot 4.6.3。

## 全身小奶茶教练（可选渲染层）

独立的绝对时间姿势逻辑在 `video/coach_timeline.py`；绘画后端在 `video/coach_avatar.py`。
课程 `picture.coach.enabled=true` 才开启，未配置的旧课程保持原状。
从 `courses/coach-demo.json`、`docs/coach-avatar.md` 和 `assets/coaches/README.md` 接手。
骨骼与动作数据在 `assets/coaches/milktea/rig/`，Godot 用 `scenes/coach_demo.tscn` 播放相同课程。运行 `python3 tests/test_coach_avatar.py` 和 `python3 tests/test_cutout_rig.py` 后生成八动作样片，用 `python3 tests/check_coach_sample.py build/coach-demo.mp4` 核对解码画面。
