# Lab Booking - 实验室预约登记系统

轻量级实验室/教室在线预约系统，提供问卷式 Web 界面、Agent（LLM）API 接入、Docker 一键部署。

## 功能特性

- **📋 问卷式预约** — 单页表单，支持多时段批量预约，自定义字段和输入校验
- **🛡️ 冲突检测** — 自动检测时间段重叠，防止重复预约
- **📅 隐私排班查询** — 按日期或上/下午查看教室占用情况，不暴露预约人信息
- **🔧 管理后台** — 教室增删改、专业预设、表单字段配置、自定义字段、批次审批
- **🎨 界面自定义** — 副标题文案/字号/颜色、时段备注、成功页警示语均可配置
- **💾 多存储后端** — SQLite / MySQL / PostgreSQL / JSON 文件，通过环境变量切换
- **📥 数据备份** — 一键导出/导入 JSON 格式的预约记录
- **⚙️ 后台任务** — 排课导入异步执行，支持进度查看和批量写入
- **🤖 Agent API** — 为 LLM Agent 设计的查询接口，支持精确可用性检查和口语化时段解析
- **🐳 Docker 部署** — Dockerfile + docker-compose，开箱即用

## 技术栈

| 层 | 技术 |
|---|---|
| 后端 | Python 3.11+ / FastAPI / SQLAlchemy |
| 前端 | 纯 HTML/CSS/JS（零构建，零依赖） |
| 数据库 | SQLite / MySQL / PostgreSQL |
| 存储抽象 | SQLAlchemy ORM + JSON 文件双后端 |

## 快速开始

### Docker 部署

```bash
git clone https://github.com/YuKi-skadi/Lab-booking.git
cd Lab-booking
# 复制 .env.example 为 .env，并至少设置高强度的 ADMIN_PASSWORD
docker compose up -d --build
```

如果使用已导出的镜像 tar，在 NAS 上先加载镜像，再将本项目的 `docker-compose.yml` 和私有 `.env` 放到同一目录：

```bash
docker load -i lab-booking-private-20260901.tar
docker compose up -d
```

Compose 会优先使用已加载的 `lab-booking:latest` 镜像；只有执行 `docker compose up --build` 时才会重新构建。

默认 Docker 配置是一个应用容器开放两个角色端口，预约端为 `8000`，管理端为 `8001`。管理端默认只绑定在部署主机本机的 `127.0.0.1:8001`：

```text
预约端：      http://服务器地址:8000
管理端：      http://127.0.0.1:8001/admin
```

如果 Docker 部署在 NAS 上，并且希望从同一局域网的电脑访问管理端，可在 NAS 项目的 `.env` 中设置：

```env
ADMIN_BIND_IP=0.0.0.0
ADMIN_PORT=8001
```

此时管理端地址为 `http://NAS_IP:8001/admin`。这只代表 NAS 在网卡上监听 8001，不代表它自动变成公网服务；仍必须在 NAS 防火墙中将 8001 限制为局域网网段，并确保路由器没有转发 8001、FRP 没有映射 8001、Nginx 也只反代 8000。预约端才通过 FRP/Nginx 对外提供服务。

容器内部会分别监听 8000 和 8001：8000 只创建预约角色应用，8001 只创建管理角色应用。两个入口共用项目目录下的 `data` SQLite 数据目录；这不是两套数据。直接挂载到 NAS 目录也便于备份和迁移。

SQLite 备份建议由 AstrBot 或 NAS 定时任务调用管理端的 JSON 数据导出接口，导出的预约数据应保存到数据卷之外的 NAS 备份目录或另一块磁盘。它不会直接复制正在写入的数据库文件；后续可再增加 SQLite 原始文件的一致性备份。

如果需要从另一台电脑管理服务器，先建立 SSH 隧道，再访问本机地址：

```bash
ssh -L 8001:127.0.0.1:8001 用户名@服务器地址
```

这套 Docker 配置中，公网容器只提供预约相关接口；管理员页面、管理员 API 和 API 文档不会在公网容器中开放。

### 本地开发

```bash
pip install -r backend/requirements.txt
cp .env.example .env
python run.py
```

## 配置

| 变量 | 默认值 | 说明 |
|---|---|---|
| `STORAGE_BACKEND` | `sqlite` | 存储后端：`sqlite`、`mysql`、`postgres`、`json` |
| `APP_ROLE` | `all` | 运行角色：`all`（本地开发）、`public`（公网预约端）、`admin`（管理端） |
| `ADMIN_PASSWORD` | 无 | 管理后台密码；公网 Docker 部署必须通过 `.env` 设置 |
| `CORS_ORIGINS` | 空 | 只有跨域调用时才填写允许的来源，多个来源用逗号分隔 |
| `PORT` | `8000` | 服务端口 |

### 公网部署安全说明

- 如果管理端只在 NAS 本机使用，保持 `ADMIN_BIND_IP=127.0.0.1`；如果需要局域网使用，才改为 `0.0.0.0`，并配合 NAS 防火墙限制来源。公网只映射预约端口 8000。
- 建议在前面使用 Caddy、Nginx 或 Traefik 配置 HTTPS；不要直接用 HTTP 传输学生信息。
- 管理员 API 优先使用 `X-Admin-Password` 请求头，旧版 `?password=` 查询参数仍保留兼容，但不建议继续使用。
- 公网角色已关闭 `/admin`、管理员 API、管理员文档以及包含个人预约详情的 Agent 查询接口。
- 公网预约接口不再允许省略学号查询全部预约，公开可用性接口也不会返回姓名、学号等预约人信息。
- 生产环境不要使用示例密码、数据库默认密码或把 `.env`、`data/` 提交到 Git；定期备份并限制数据卷权限。
- 当前默认 Docker 方案使用单容器 SQLite，适合预约量和并发量较小的个人/小型实验室项目。建议保留多份定期备份，并至少有一份备份不放在同一个 Docker 数据卷中。

首次启动且 `data/settings.json` 尚不存在时，还可以通过以下环境变量设置本地部署的初始数据：

| 变量 | 格式 | 说明 |
|---|---|---|
| `LAB_BOOKING_DEFAULT_CLASSROOMS` | 逗号分隔 | 初始教室列表 |
| `LAB_BOOKING_DEFAULT_MAJORS` | 逗号分隔 | 初始专业列表 |
| `LAB_BOOKING_DEFAULT_TIME_SLOTS_JSON` | JSON 数组 | 初始时段及备注 |

这些变量只用于初始化，不会覆盖已经存在的 `data/settings.json`。`.env.example` 和 `docker-compose.yml` 中保留的是通用示例值；本地私有值请放在未提交的 `.env` 或本地数据目录中。

### 数据库切换

**SQLite**（默认，无需额外配置）：
```env
STORAGE_BACKEND=sqlite
```

**MySQL**：
```env
STORAGE_BACKEND=mysql
MYSQL_HOST=localhost
MYSQL_PORT=3306
MYSQL_USER=lab
MYSQL_PASSWORD=your_password
MYSQL_DATABASE=lab_booking
```

**PostgreSQL**（也可用 `docker-compose.postgres.yml`）：
```env
STORAGE_BACKEND=postgres
POSTGRES_HOST=localhost
POSTGRES_PORT=5432
POSTGRES_USER=lab
POSTGRES_PASSWORD=your_password
POSTGRES_DATABASE=lab_booking
```

**JSON 文件**（测试/临时使用，每次写入自动备份）：
```env
STORAGE_BACKEND=json
JSON_DATA_DIR=./data
```

## API 参考

### 学生端

| 方法 | 路径 | 说明 |
|---|---|---|
| `POST` | `/api/bookings/batch` | 批量提交预约（支持多时段 + 自定义字段） |
| `GET` | `/api/bookings?student_id=` | 按学号查询个人预约 |
| `POST` | `/api/bookings/{id}/cancel?student_id=` | 取消预约 |
| `GET` | `/api/availability?classroom=&date=` | 查某教室某天时段可用性 |
| `GET` | `/api/schedule?date=&start_time=&end_time=` | 查某天全教室排班（隐私保护，支持上/下午过滤） |
| `GET` | `/api/admin/public/form-config` | 获取表单配置（教室、专业、时段、自定义字段） |

### 管理端

管理 API 推荐通过请求头 `X-Admin-Password` 传递密码；下面表格中的 `?password=` 仅为旧客户端兼容保留。

| 方法 | 路径 | 说明 |
|---|---|---|
| `GET` | `/api/bookings/all?password=` | 获取全部预约 |
| `PUT` | `/api/bookings/{id}?password=` | 审核通过/拒绝 |
| `PUT` | `/api/bookings/batch-status?password=` | 批量审批（通过/拒绝） |
| `DELETE` | `/api/bookings/{id}?password=` | 删除预约 |
| `GET/POST/PUT/DELETE` | `/api/admin/classrooms?password=` | 教室管理 |
| `GET/POST/DELETE` | `/api/admin/majors?password=` | 专业预设管理 |
| `GET/PUT` | `/api/admin/form-fields/{key}?password=` | 字段标签/必填/校验规则配置 |
| `POST/DELETE` | `/api/admin/form-fields/custom?password=` | 自定义字段增删 |
| `GET/PUT` | `/api/admin/settings?password=` | 系统设置（密码、提示消息、副标题、时段备注、警示语） |
| `GET` | `/api/admin/db/backup?password=` | 导出数据库备份 (JSON) |
| `POST` | `/api/admin/db/import?password=` | 导入数据库备份 |
| `GET` | `/api/admin/db/config?password=` | 查看数据库配置 |
| `POST` | `/api/admin/courses?password=` | 建立后台排课导入任务（立即返回任务编号） |
| `GET` | `/api/admin/courses/batches?password=` | 查看课程批次（支持学期筛选） |
| `GET` | `/api/admin/courses/batches/{batch_id}?password=` | 查看批次内的全部课程 |
| `PUT` | `/api/admin/courses/{booking_id}?password=` | 调整单条课程的日期、教室或时段 |
| `GET` | `/api/admin/tasks?password=` | 查看后台任务列表及进度 |
| `GET` | `/api/admin/tasks/{task_id}?password=` | 查看单个后台任务 |
| `POST` | `/api/admin/tasks/{task_id}/cancel?password=` | 取消尚未开始的后台任务 |
| `GET/POST/DELETE` | `/api/admin/semesters?password=` | 设置、查看和删除学期信息 |

### Agent 端

| 方法 | 路径 | 说明 |
|---|---|---|
| `GET` | `/api/agent/query?date=` | 某日全教室概况 |
| `GET` | `/api/agent/check?classroom=&date=&start_time=` | 精确可用性检查 |

## 项目结构

```
lab-booking/
├── backend/
│   ├── app/
│   │   ├── main.py              # FastAPI 入口
│   │   ├── config.py            # 环境变量配置
│   │   ├── models.py            # SQLAlchemy 模型
│   │   ├── schemas.py           # Pydantic 校验
│   │   ├── database.py          # 数据库连接 + SQLite 自动迁移
│   │   ├── storage.py           # 存储抽象（SQL + JSON 双后端）
│   │   ├── task_manager.py      # 管理后台任务队列
│   │   ├── settings_manager.py  # 系统设置管理（JSON 持久化）
│   │   └── routers/
│   │       ├── bookings.py      # 预约 CRUD + 批量审批 + 排班查询
│   │       ├── agent.py         # Agent 专用 API
│   │       └── settings_router.py  # 教室/专业/字段/设置管理 + 数据备份导入
│   ├── static/
│   │   ├── index.html           # 学生预约界面
│   │   └── admin.html           # 管理后台
│   ├── requirements.txt
│   └── Dockerfile
├── docker-compose.yml           # SQLite 默认部署
├── docker-compose.postgres.yml  # PostgreSQL 示例
├── .env.example
├── .gitignore
├── run.py
└── README.md
```

## License

MIT
