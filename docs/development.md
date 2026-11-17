# JabJam 基础工程

## 当前范围

本次实现是产品愿景的首个开发原型，不是完整 MVP，也不改变愿景中的真实动作计分要求。

- Godot 4.6.3 Standard + GDScript，Compatibility 渲染器，1280×720 横屏逻辑画布，窗口按比例缩放。
- 首页 → 36 秒练习 → 最后一拳盖章 → 结算 → 再来一次。
- 120 BPM 原创合成音频，4 秒准备，32 个固定拳法音符；不包含用户版权音乐。
- D / F / J / K 分别模拟左勾拳 / 左直拳 / 右直拳 / 右勾拳，支持屏幕按钮。
- 音频播放位置作为主时钟；Perfect ±85ms，Good ±180ms；错拳消耗音符并打断连击，漏拳不打断音乐。
- Esc / Space 暂停，R 重开；失去应用焦点自动暂停。暂停期间不计分、不推进谱面。
- 原创几何 3D 占位教练，提前示范下一个动作；尚无正式模型、配音和素材生产流程。
- 本地仅保存最近 100 次模拟练习，无正式 Full Combo、运动打卡、热力图或热量统计。

尚未实现：Joy-Con/IMU、真实运动识别、歌曲导入/自动谱面、Android 打包/设备测试、音频或投屏延迟校准、正式角色、训练计划。首次进入时会在内存中生成约 1.6MB 音频。

## Linux 本地运行

使用 Godot 4.6.3 Standard 的 Linux x86_64 版本；无需 Node、Python、数据库或 .NET。

```sh
godot --version
godot --editor --path .
# 或直接进入游戏
godot --path .
```

正常游玩需要 X11 或 Wayland 桌面、支持 OpenGL 3.3 的图形环境以及可用音频输出。软件渲染可以用作兼容性验证，不能替代目标手机上的性能测试。音频判定尚未做设备校准。

默认练习记录位于 Godot 的 `user://simulation_history.json`。通常为：

```text
~/.local/share/godot/app_userdata/JabJam/simulation_history.json
```

使用 `XDG_DATA_HOME` 时随之改变；保存错误会在结算页显示。记录先写临时文件再重命名，避免正常写入被打断时覆盖已有文件；此实现假定单个游戏实例写入。

## 无界面验证

```sh
sh scripts/verify.sh
```

脚本使用临时 XDG 数据、配置和缓存目录，避免污染练习历史；依次执行编辑器导入、规则/场景测试和主场景启动。导入、资源或脚本错误即使引擎返回 0 也会使验证失败。

仅当沙箱禁止编辑器的本地调试 socket 时，可使用 `ALLOW_EDITOR_SOCKET_ERRORS=1 sh scripts/verify.sh`，放行导入阶段两个已知 socket 错误；其他错误仍然失败。普通本机和 Docker/CI 不应启用此例外。

测试覆盖正确/错误拳法、判定窗口、长帧漏判、暂停、时间不倒退、重开、完整模拟谱面、一次性盖章、持久化与坏文件恢复，以及真实主场景的键盘启动、音频暂停和界面状态切换。无界面模式使用 Dummy 显示和音频驱动，不能证明画面、实际音频延迟或触屏手感。

## Docker

Godot 可作为普通 Linux 程序在容器内运行。仓库默认让 Docker 负责**可重复的无界面验证**；启动游戏画面需要额外连接宿主桌面。

```sh
docker build --platform linux/amd64 -t jabjam-dev .
docker run --rm --network none jabjam-dev
# 等价的 Compose 命令
docker compose run --build --rm check
```

镜像固定 Godot 4.6.3，下载官方 Linux 二进制并校验同一 release 的 SHA-512 清单，使用非 root 用户执行。构建需要 Debian 软件源和 GitHub 网络；测试和游戏运行不需要网络。当前 Dockerfile 仅支持 amd64，不宣称原生 ARM64 支持。

### 容器中显示游戏窗口（Linux X11 可选）

需要宿主有 X11 会话（或 Wayland 的 XWayland）、`xauth` 和 Docker。以下配置使用专用 Xauthority 文件，只把当前显示的 cookie 授予容器，不使用 `xhost +` 或 `--privileged`。

```sh
docker build --platform linux/amd64 -t jabjam-dev .
auth_file=$(mktemp)
xauth nlist "$DISPLAY" | sed -e 's/^..../ffff/' | xauth -f "$auth_file" nmerge -
docker run --rm \
  --user "$(id -u):$(id -g)" \
  -e DISPLAY -e XAUTHORITY=/tmp/jabjam.xauth \
  -e XDG_DATA_HOME=/tmp/jabjam-data \
  -e XDG_CONFIG_HOME=/tmp/jabjam-config \
  -e XDG_CACHE_HOME=/tmp/jabjam-cache \
  -e LIBGL_ALWAYS_SOFTWARE=1 \
  -v /tmp/.X11-unix:/tmp/.X11-unix:ro \
  -v "$auth_file:/tmp/jabjam.xauth:ro" \
  jabjam-dev godot --path /app --display-driver x11 --audio-driver Dummy
rm -f "$auth_file"
```

上例用于画面检查，**没有声音且记录随容器退出丢失**。正式听音试玩建议直接在 Linux 桌面运行 Godot；容器音频需要根据宿主 PulseAudio/PipeWire socket、cookie 与 UID 配置转发。原生 Wayland、GPU 直通、远程桌面、浏览器串流不在此次配置范围内。无显示服务器的 Docker 容器不会自动变成可访问的网页游戏。

## 工程结构

| 文件 | 职责 |
| --- | --- |
| `project.godot` / `scenes/main.tscn` | 引擎配置和入口 |
| `scripts/session.gd` | 纯状态机、固定谱面、判定和模拟结果 |
| `scripts/main.gd` | 音频时钟、流程、UI 与适配器编排 |
| `scripts/simulated_input.gd` | 键盘输入适配，发出语义拳法信号 |
| `scripts/demo_audio.gd` | 无外部依赖的演示音频生成 |
| `scripts/coach.gd` | 可替换的几何 3D 教练 |
| `scripts/practice_store.gd` | 独立模拟记录和原子替换保存 |
| `tests/run_tests.gd` | 规则、保存和主场景集成检查 |
| `Dockerfile` / `compose.yaml` | Linux 容器验证环境 |
| `.github/workflows/verify.yml` | GitHub Actions 构建并验证容器 |

真实硬件将来可提供同样的拳法信号，但仍需定义时间戳、置信度、掉线处理和可信输入认证，不能直接把当前模拟分数当正式成绩。曲谱和音频目前是一对固定演示资源；接入任意歌曲前需要单独实现分析与谱面持久化。

## 本次验证记录（2026-11-17）

- Debian 13 x86_64、Godot 4.6.3：完成无界面导入、27 项规则/场景检查和启动验证，包含音频时间线推进及自动结束。
- 当前沙箱禁止编辑器监听本地调试 socket，本地验证使用上述显式例外；规则/场景测试和启动检查没有放宽错误检查。
- 本机 Docker socket 权限受限；改用 GitHub Actions 执行容器验证。首轮镜像构建及 27 项测试成功，但日志暴露了 `/app` 缓存目录权限问题。已补充目录授权，并把所有引擎错误纳入失败条件；最终容器检查结果以 [PR 检查记录](https://github.com/CheeseAgent/jabjam/pull/7/checks) 为准。
- 当前没有可用桌面控制工具，未完成图形桌面、音频输出、Android 或 X11 转发实测。
