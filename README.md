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
docker compose up -d
```

访问 `http://localhost:8000` 进入预约界面，`http://localhost:8000/admin` 进入管理后台。

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
| `ADMIN_PASSWORD` | `admin123` | 管理后台密码（首次登录后建议在后台修改） |
| `PORT` | `8000` | 服务端口 |

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
| `GET` | `/api/bookings/{id}/cancel?student_id=` | 取消预约 |
| `GET` | `/api/availability?classroom=&date=` | 查某教室某天时段可用性 |
| `GET` | `/api/schedule?date=&start_time=&end_time=` | 查某天全教室排班（隐私保护，支持上/下午过滤） |
| `GET` | `/api/admin/public/form-config` | 获取表单配置（教室、专业、时段、自定义字段） |

### 管理端

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
