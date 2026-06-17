# Lab Booking - 实验室预约登记系统

一个轻量级的实验室/教室在线预约系统，提供问卷式 Web 界面、Agent（LLM）API 接入、Docker 一键部署。

## 功能特性

- **📋 问卷式预约** — 单页表单填写姓名、学号、专业、指导教师、教室、日期、时间段，支持多时段批量预约
- **🛡️ 冲突检测** — 自动检测时间段重叠，防止重复预约
- **📅 公开排班查询** — 按日期查看各教室占用情况（不暴露预约人信息，保护隐私）
- **🔧 管理后台** — 教室增删改、专业预设、表单字段必填/选填配置、时段备注、副标题样式自定义
- **💾 多存储后端** — SQLite（默认）/ MySQL / PostgreSQL / JSON 文件，通过环境变量切换
- **📥 数据备份** — 一键导出/导入 JSON 格式的预约记录
- **🤖 Agent API** — 专为 LLM Agent 设计的查询接口，支持精确可用性检查
- **🐳 Docker 部署** — 提供 Dockerfile 和 docker-compose，开箱即用

## 技术栈

| 层 | 技术 |
|---|---|
| 后端 | Python 3.11+ / FastAPI / SQLAlchemy |
| 前端 | 纯 HTML/CSS/JS（零构建，零依赖） |
| 数据库 | SQLite / MySQL / PostgreSQL |
| 存储抽象 | SQLAlchemy ORM + JSON 文件双后端 |

## 快速开始

### Docker（推荐）

```bash
git clone https://github.com/YuKi-skadi/Lab-booking.git
cd lab-booking

# 使用 SQLite（最简单）
docker compose up -d

# 或使用 PostgreSQL
docker compose -f docker-compose.postgres.yml up -d
```

访问 `http://localhost:8000` 进入预约界面，`http://localhost:8000/admin` 进入管理后台。

### 本地开发

```bash
# Python 3.11+
pip install -r backend/requirements.txt
cp .env.example .env     # 按需修改配置
python run.py
```

## 配置

通过环境变量或 `.env` 文件配置：

| 变量 | 默认值 | 说明 |
|---|---|---|
| `STORAGE_BACKEND` | `sqlite` | 存储后端：`sqlite`、`mysql`、`postgres`、`json` |
| `ADMIN_PASSWORD` | `admin123` | 管理后台密码（首次登录后建议在后台修改） |
| `PORT` | `8000` | 服务端口 |
| `CLASSROOMS` | 见默认值 | 可用教室列表（逗号分隔，首次启动后可在后台管理） |
| `TIME_SLOTS` | 见默认值 | 可预约时间段（逗号分隔） |
| `JSON_DATA_DIR` | `./data` | JSON 文件存储目录 |

### 数据库配置

**SQLite**（默认）：
```env
STORAGE_BACKEND=sqlite
```
无需额外配置。

**MySQL**：
```env
STORAGE_BACKEND=mysql
MYSQL_HOST=localhost
MYSQL_PORT=3306
MYSQL_USER=lab
MYSQL_PASSWORD=your_password
MYSQL_DATABASE=lab_booking
```

**PostgreSQL**：
```env
STORAGE_BACKEND=postgres
POSTGRES_HOST=localhost
POSTGRES_PORT=5432
POSTGRES_USER=lab
POSTGRES_PASSWORD=your_password
POSTGRES_DATABASE=lab_booking
```

**JSON 文件**（用于测试/临时数据）：
```env
STORAGE_BACKEND=json
JSON_DATA_DIR=./data
```
每次写入自动在 `data/backups/` 下创建备份。

## API 参考

### 学生端

| 方法 | 路径 | 说明 |
|---|---|---|
| `POST` | `/api/bookings` | 提交单个预约 |
| `POST` | `/api/bookings/batch` | 批量提交预约（多时段） |
| `GET` | `/api/bookings?student_id=` | 按学号查询预约 |
| `GET` | `/api/bookings/{id}/cancel?student_id=` | 取消预约 |
| `GET` | `/api/availability?classroom=&date=` | 查某教室某天时段可用性 |
| `GET` | `/api/schedule?date=&start_time=&end_time=` | 查某天全教室排班（隐私保护） |
| `GET` | `/api/admin/public/form-config` | 获取表单配置（教室列表、专业、时段等） |

### 管理端

| 方法 | 路径 | 说明 |
|---|---|---|
| `GET` | `/api/bookings/all?password=` | 获取全部预约 |
| `PUT` | `/api/bookings/{id}?password=` | 审核通过/拒绝 |
| `DELETE` | `/api/bookings/{id}?password=` | 删除预约 |
| `GET/POST/PUT/DELETE` | `/api/admin/classrooms?password=` | 教室管理 |
| `GET/POST/DELETE` | `/api/admin/majors?password=` | 专业预设管理 |
| `GET/PUT` | `/api/admin/form-fields/{key}?password=` | 表单字段必填/选填配置 |
| `GET/PUT` | `/api/admin/settings?password=` | 系统设置（密码、提示消息、副标题、时段备注） |
| `GET` | `/api/admin/db/backup?password=` | 导出数据备份 (JSON) |
| `POST` | `/api/admin/db/import?password=` | 导入数据备份 |
| `GET` | `/api/admin/db/config?password=` | 查看数据库配置 |

### Agent 端

| 方法 | 路径 | 说明 |
|---|---|---|
| `GET` | `/api/agent/query?date=` | 某日全教室概况（含 Markdown 摘要） |
| `GET` | `/api/agent/check?classroom=&date=&start_time=` | 精确可用性检查 |
| `GET` | `/api/agent/rooms` | 教室和时间段列表 |

## Agent（LLM）集成

项目提供 AstrBot 插件，位于 `lab-booking-astrbot-plugin/` 目录。

插件提供 5 个 LLM Tool：
- `query_lab_schedule` — 查某天教室占用（支持上午/下午过滤）
- `check_lab_availability` — 精确查某教室某时段可用性（支持"第四节课"等口语化表达）
- `query_my_bookings` — 按学号查个人预约
- `add_lab_booking` — 代学生提交预约
- `list_lab_classrooms` — 列出教室和时段

支持通过 `_conf.yaml` 配置别名映射，适配各种口语化叫法。

## 项目结构

```
lab-booking/
├── backend/
│   ├── app/
│   │   ├── main.py              # FastAPI 入口
│   │   ├── config.py            # 配置管理
│   │   ├── models.py            # SQLAlchemy 模型
│   │   ├── schemas.py           # Pydantic 校验
│   │   ├── database.py          # 数据库连接
│   │   ├── storage.py           # 存储抽象（SQL + JSON）
│   │   ├── settings_manager.py  # 系统设置管理
│   │   └── routers/
│   │       ├── bookings.py      # 预约 CRUD API
│   │       ├── agent.py         # Agent 专用 API
│   │       └── settings_router.py  # 管理设置 API
│   ├── static/
│   │   ├── index.html           # 学生预约界面
│   │   └── admin.html           # 管理后台
│   ├── requirements.txt
│   └── Dockerfile
├── docker-compose.yml
├── docker-compose.postgres.yml
├── .env.example
├── .gitignore
└── run.py                       # 本地启动入口
```

## License

MIT
